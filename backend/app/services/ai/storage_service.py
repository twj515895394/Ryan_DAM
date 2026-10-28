from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.ai.task import AiResult, AiTask, AiTaskReference
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.services.settings_service import get_managed_root
from backend.app.services.thumbnail_service import enqueue_asset

logger = logging.getLogger(__name__)


def get_ai_history_layout(managed_root: str) -> dict[str, Path]:
    """计算 AI 永久历史存储区目录结构。"""
    root = Path(managed_root) / "ai-history"
    inputs_dir = root / "inputs"
    results_dir = root / "results"
    staging_dir = root / "staging"
    return {
        "root": root,
        "inputs": inputs_dir,
        "results": results_dir,
        "staging": staging_dir,
    }


def check_storage_space(managed_root: str, required_bytes: int = 10 * 1024 * 1024) -> None:
    """校验存储卷剩余磁盘空间，空间不足时阻断操作，绝不静默写入 C 盘。"""
    root = Path(managed_root)
    drive, _ = os.path.splitdrive(str(root))
    probe = drive + os.sep if drive else str(root)
    if not os.path.exists(probe):
        # 驱动器未挂载或不存在
        raise ApiError(
            code="storage_unavailable",
            message=f"托管存储路径不可用（{managed_root}），请检查外置盘是否已连接",
            status_code=507,
        )
    try:
        free_bytes = shutil.disk_usage(probe).free
    except Exception as exc:
        logger.warning(f"无法探测存储盘空间: {exc}")
        return

    if free_bytes < required_bytes:
        raise ApiError(
            code="storage_full",
            message=f"存储盘空间不足（剩余 {free_bytes // (1024 * 1024)}MB，需至少 {required_bytes // (1024 * 1024)}MB）",
            status_code=507,
        )


def _compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_input_snapshot(
    db: Session,
    task_id: str,
    seq: int,
    source_path: Path,
    role: str | None = None,
    source_kind: str = "local_upload",
    source_id: str | None = None,
) -> AiTaskReference:
    """复制并保存输入参考图的不可变快照，保存在 <managed_root>/ai-history/inputs/<task-id>/。"""
    if not source_path.exists() or not source_path.is_file():
        raise ApiError(code="input_file_missing", message=f"参考图源文件不存在: {source_path}", status_code=400)

    file_size = source_path.stat().st_size
    if file_size == 0:
        raise ApiError(code="invalid_input_file", message="参考图文件内容为空（0 字节）", status_code=400)

    managed_root = get_managed_root(db)
    check_storage_space(managed_root, required_bytes=file_size + 1024 * 1024)

    layout = get_ai_history_layout(managed_root)
    task_inputs_dir = layout["inputs"] / task_id
    task_inputs_dir.mkdir(parents=True, exist_ok=True)

    ext = source_path.suffix.lower() or ".png"
    target_path = task_inputs_dir / f"{seq}{ext}"

    # 复制文件
    shutil.copy2(source_path, target_path)
    sha256 = _compute_sha256(target_path)

    ref = AiTaskReference(
        task_id=task_id,
        seq=seq,
        role=role,
        source_kind=source_kind,
        source_id=source_id,
        snapshot_path=str(target_path),
        sha256=sha256,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return ref


def commit_generated_result(
    db: Session,
    task_id: str,
    idx: int,
    staging_file: Path,
    mime_type: str = "image/png",
) -> AiResult:
    """校验 staging 产物完整性，并将其原子转移至 <managed_root>/ai-history/results/<task-id>/。"""
    if not staging_file.exists() or not staging_file.is_file():
        raise ApiError(code="result_missing", message="生成产物暂存文件不存在", status_code=500)

    file_size = staging_file.stat().st_size
    if file_size == 0:
        raise ApiError(code="corrupted_result", message="生成产物校验失败：文件为空（0 字节）", status_code=502)

    # 尝试校验图片分辨率
    width: int | None = None
    height: int | None = None
    try:
        with Image.open(staging_file) as img:
            img.verify()
        with Image.open(staging_file) as img:
            width, height = img.size
    except Exception as exc:
        logger.error(f"生成图片损坏或截断: {exc}")
        raise ApiError(code="corrupted_result", message=f"生成图片损坏或截断无法解析: {exc}", status_code=502)

    managed_root = get_managed_root(db)
    check_storage_space(managed_root, required_bytes=file_size + 1024 * 1024)

    layout = get_ai_history_layout(managed_root)
    task_results_dir = layout["results"] / task_id
    task_results_dir.mkdir(parents=True, exist_ok=True)

    result_id = f"aires_{uuid.uuid4().hex[:16]}"
    ext = staging_file.suffix.lower() or ".png"
    target_path = task_results_dir / f"{result_id}{ext}"

    # 原子重命名/移动
    shutil.move(str(staging_file), str(target_path))
    sha256 = _compute_sha256(target_path)

    result = AiResult(
        id=result_id,
        task_id=task_id,
        idx=idx,
        history_file_path=str(target_path),
        mime_type=mime_type,
        sha256=sha256,
        width=width,
        height=height,
        size_bytes=file_size,
        is_deleted=False,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def delete_history_result(db: Session, result_id: str, delete_physical: bool = False) -> None:
    """删除 AI 生成历史结果。已入库资产不受影响。"""
    result = db.query(AiResult).filter(AiResult.id == result_id).first()
    if not result:
        raise ApiError(code="result_not_found", message=f"生成历史结果 #{result_id} 不存在", status_code=404)

    result.is_deleted = True
    if delete_physical and result.history_file_path:
        file_path = Path(result.history_file_path)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as exc:
                logger.warning(f"删除物理文件失败: {file_path}, err: {exc}")

    db.commit()


def get_result_file_path(db: Session, result_id: str) -> tuple[Path, str]:
    """获取历史结果文件路径及 MIME 类型，供安全文件流使用。"""
    result = db.query(AiResult).filter(AiResult.id == result_id).first()
    if not result or result.is_deleted:
        raise ApiError(code="result_not_found", message=f"生成历史结果 #{result_id} 不存在或已删除", status_code=404)

    path = Path(result.history_file_path)
    if not path.exists():
        raise ApiError(code="file_not_found", message="历史图片实体文件在磁盘上丢失", status_code=404)

    return path, result.mime_type


def stage_upload_file(db: Session, file_content: bytes, filename: str) -> dict[str, Any]:
    """将本地上传的临时参考图存入 <managed_root>/ai-history/staging/，返回校验后的信息。"""
    if not file_content:
        raise ApiError(code="empty_file", message="上传的参考图文件为空", status_code=400)

    managed_root = get_managed_root(db)
    check_storage_space(managed_root, required_bytes=len(file_content) + 1024 * 1024)

    layout = get_ai_history_layout(managed_root)
    staging_dir = layout["staging"]
    staging_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower() or ".png"
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        raise ApiError(code="unsupported_format", message=f"不支持的图片格式: {ext}，仅支持 jpg/png/webp", status_code=400)

    upload_id = f"up_{uuid.uuid4().hex[:16]}"
    target_path = staging_dir / f"{upload_id}{ext}"
    target_path.write_bytes(file_content)

    width, height = 0, 0
    try:
        with Image.open(target_path) as img:
            img.verify()
        with Image.open(target_path) as img:
            width, height = img.size
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise ApiError(code="invalid_image", message=f"上传的文件不是有效图片: {exc}", status_code=400)

    return {
        "upload_id": f"{upload_id}{ext}",
        "filename": filename,
        "size_bytes": len(file_content),
        "width": width,
        "height": height,
        "staging_path": str(target_path),
    }


def get_or_create_default_ai_folder(db: Session) -> Folder:
    """获取或自动创建通用资产库中的顶层默认『AI 生成』目录。"""
    folder = (
        db.query(Folder)
        .filter(
            Folder.scope_type == "general",
            Folder.parent_id.is_(None),
            Folder.name == "AI 生成",
        )
        .first()
    )
    if not folder:
        folder = Folder(
            name="AI 生成",
            scope_type="general",
            project_id=None,
            parent_id=None,
            description="AI 图像生成默认存储目录",
        )
        db.add(folder)
        db.flush()
    return folder


def import_result_to_asset(
    db: Session,
    result_id: str,
    target_folder_id: int | None = None,
    custom_name: str | None = None,
) -> tuple[Asset, bool]:
    """将 AI 生成历史结果手动导入为主库托管资产。

    返回 (Asset, is_newly_imported):
    如果该结果已经入库过且主库资产处于 active 状态，则执行幂等返回 (existing_asset, False)。
    """
    result = db.query(AiResult).filter(AiResult.id == result_id).first()
    if not result or result.is_deleted:
        raise ApiError(code="result_not_found", message=f"生成历史结果 #{result_id} 不存在或已删除", status_code=404)

    # 1. 幂等性检查：若已有绑定的 active asset，直接返回
    if result.imported_asset_id:
        existing = db.get(Asset, result.imported_asset_id)
        if existing and existing.status == "active":
            return existing, False

    source_path = Path(result.history_file_path)
    if not source_path.exists():
        raise ApiError(code="file_not_found", message="历史图片实体文件在磁盘上丢失", status_code=404)

    # 2. 验证目标目录（若未指定则自动定位到默认「AI 生成」目录）
    if target_folder_id is not None:
        folder = db.get(Folder, target_folder_id)
        if not folder:
            raise ApiError(code="folder_not_found", message="目标文件夹不存在", status_code=404)
    else:
        default_folder = get_or_create_default_ai_folder(db)
        target_folder_id = default_folder.id

        # 自愈以往可能存在的 folder_id 为 None 的孤儿 AI 资产
        orphan_ai_assets = (
            db.query(Asset)
            .filter(
                Asset.asset_origin == "ai_generated",
                Asset.folder_id.is_(None),
            )
            .all()
        )
        for orphan in orphan_ai_assets:
            orphan.folder_id = default_folder.id

    # 3. 准备目标路径与资产名称
    managed_root = get_managed_root(db)
    check_storage_space(managed_root, required_bytes=result.size_bytes or 1024 * 1024)
    objects_dir = Path(managed_root) / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)

    task = result.task or db.get(AiTask, result.task_id)
    ext = source_path.suffix.lstrip(".") or "png"
    if custom_name and custom_name.strip():
        base_name = custom_name.strip()
        if not base_name.lower().endswith(f".{ext.lower()}"):
            asset_filename = f"{base_name}.{ext}"
        else:
            asset_filename = base_name
    else:
        task_kind = task.task_type if task else "gen"
        asset_filename = f"AI_{task_kind}_{result.id[-8:]}.{ext}"

    # 4. 创建 Asset 记录
    prompt_text = task.prompt_final if task else None
    asset = Asset(
        folder_id=target_folder_id,
        name=asset_filename,
        extension=ext,
        mime_type=result.mime_type,
        asset_type="image",
        size_bytes=result.size_bytes or source_path.stat().st_size,
        media_width=result.width,
        media_height=result.height,
        file_path="",  # 稍后写入
        source_type="managed",
        sha256=result.sha256,
        asset_origin="ai_generated",
        prompt_origin="generation_prompt" if prompt_text else None,
        prompt_text=prompt_text,
        prompt_revision=1,
        generation_task_id=result.task_id,
        generation_result_id=result.id,
        thumbnail_status="pending",
        status="active",
    )
    db.add(asset)
    db.flush()

    # 5. 复制实体文件到 objects/<asset_id>/<filename>
    final_dir = objects_dir / str(asset.id)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / asset_filename
    shutil.copy2(str(source_path), str(final_path))

    asset.file_path = str(final_path)
    result.imported_asset_id = asset.id

    db.commit()
    db.refresh(asset)

    # 6. 加入缩略图生成队列
    try:
        enqueue_asset(asset.id)
    except Exception as exc:
        logger.warning(f"入库资产 #{asset.id} 缩略图入队失败: {exc}")

    return asset, True


def batch_import_results(
    db: Session,
    result_ids: list[str],
    target_folder_id: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """批量将 AI 生成结果入库。"""
    items: list[dict[str, Any]] = []
    success_count = 0

    for res_id in result_ids:
        try:
            asset, is_new = import_result_to_asset(db, res_id, target_folder_id=target_folder_id)
            items.append({
                "result_id": res_id,
                "asset_id": asset.id,
                "status": "success" if is_new else "already_imported",
                "error_message": None,
            })
            success_count += 1
        except Exception as exc:
            items.append({
                "result_id": res_id,
                "asset_id": None,
                "status": "error",
                "error_message": str(exc),
            })

    return items, success_count
