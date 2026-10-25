"""reclassify code files registered as documents into the "other" category

用户要求代码类文件不再归入「文档」分类：此前一版构建把 CODE_EXTS 并入文档注册，
本迁移把存量 asset_type='document' 且扩展名属于代码/配置/日志的文件改回 'other'。

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels = None
depends_on = None

# 与 import_service.CODE_EXTS 同步的时点快照（2026-10）。数据迁移不依赖应用代码，
# 以免该清单后续变化改变历史迁移的语义。
CODE_EXTS = frozenset({
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
    ".html", ".htm", ".css", ".scss", ".less", ".yml", ".yaml", ".xml",
    ".toml", ".ini", ".cfg", ".conf", ".properties", ".sh", ".bash", ".zsh",
    ".bat", ".cmd", ".ps1", ".sql", ".java", ".c", ".h", ".cpp", ".hpp",
    ".cc", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".lua",
    ".pl", ".r", ".gradle", ".proto", ".graphql", ".log",
})


def _reclassify(conn, from_type: str, to_type: str) -> int:
    rows = conn.execute(
        sa.text("SELECT id, name FROM assets WHERE asset_type = :t"), {"t": from_type}
    ).fetchall()
    moved = 0
    for row in rows:
        if Path(str(row.name)).suffix.lower() in CODE_EXTS:
            conn.execute(
                sa.text("UPDATE assets SET asset_type = :target WHERE id = :i"),
                {"target": to_type, "i": row.id},
            )
            moved += 1
    return moved


def reclassify_code_documents(conn) -> int:
    """document → other：返回改类的资产数。可安全重复执行（幂等）。"""
    return _reclassify(conn, "document", "other")


def upgrade() -> None:
    reclassify_code_documents(op.get_bind())


def downgrade() -> None:
    _reclassify(op.get_bind(), "other", "document")
