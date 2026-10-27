# Ryan_DAM 二期技术架构详细设计（V2）

- **版本**：v0.2 / 技术设计建议（2026-10-27）
- **需求事实基线**：[V2 Spec](./Ryan_DAM_Product_Spec_v2.md)
- **既有架构**：[V1 技术架构](./TECHNICAL_ARCHITECTURE_V1.md)
- **适用分支**：feat/phase2-ai-workbench
- **状态**：设计稿，不代表开发已完成；下文具体表、接口、并发、文件目录和重试规则为**推荐实现方案**，不是新追加的用户决定。

## 0. 收口结论与实施边界

### 已确认需求（不可擅改）
- Windows 本地个人使用；V1 资产库不重做；独立 AI 工作台 + 现有画廊/预览快捷动作。
- 自定义第三方 OpenAI Compatible 是 Provider 添加时的优先入口；支持多连接、多模型、多能力；默认图片生成使用经用户配置的 GPT 图像模型，场景级覆盖；官方接入保留。
- 模型能力分别包含文本 LLM 优化、视觉理解/反推、图片生成、图片编辑；本期执行器只覆盖正式纳入的模型服务，不接 ComfyUI。
- 图片生成/编辑统一工作台但明确模式；参考图来自资产、历史、本地、拖放、剪贴板；不强制临时图入库。
- 任务后台受控并发；所有生成结果永久保留在生成历史，**绝不自动转正式资产**；用户选择后入库；生成历史不随入库消失。
- 每张正式资产最多一份 Prompt；保留 prompt_text；要区分物理存储 source_type、资产创作来源、Prompt 来源；已有 Prompt 替换必须确认。
- 单图/批量反推；反推结果审核与选择保存；反推可选后续 LLM 优化；提示词优化可跳过。
- 再生成/变体/继续编辑产生新任务；通过任务关联追溯来源，不创建跨项目通用资产使用图谱。
- AI 自动打标签明确暂缓；**ComfyUI 依据产品决策㉒移出整个二期交付**，二期完成后再评估是否接入。

### 范围工作假设（**尚待产品最终确认，不写回“已确认决策”**）
- 首批仅实现**图片**的生成、编辑、反推；V1 视频提示词仍可手动保存。视频生成/视频反推仅预留执行器任务类型，不安排本批开发。
- 软件维持单机本地模式，不引入服务器端账号体系、Redis、Celery、云端 DAM。
- 二期开发与验收不需要 ComfyUI 实例、API Workflow 适配器或 ComfyUI 专项 PoC；不以“预留扩展”为由提前实现相关功能。
- “永久生成历史”指应用**不自动按时间删除本地结果**；用户明确手动删除或磁盘/文件丢失是单独异常。

## 1. V1 代码依据与可复用组件

| 层 | 现状（仓库中已存在） | 二期策略 |
|---|---|---|
| Electron | apps/desktop/main.cjs、preload.cjs，受限 IPC 与本机 FastAPI 子进程 | 保留系统文件选择与受限 IPC；必要时加粘贴/文件拖放的安全桥接 |
| Vue | apps/web/src/App.vue、AssetCard/AssetPreview/BatchActionBar/TargetFolderDialog、Pinia library store | 增加独立 AI 视图和 stores，不继续膨胀 App.vue；复用目录选择与确认弹窗 |
| API | backend/app/api/v1/assets.py 支持 get/put 单 prompt_text | 扩展来源元数据与安全覆盖机制，不建立多 Prompt 表 |
| DB | assets.source_type managed/external；prompt_text；SQLite/Alembic 0001–0009 | 只增迁移，不修改 V1 字段既有语义 |
| 文件 | managed_root/objects/<asset-id>、.staging；导入 Worker 单线程 | AI 独立调度器与独立历史对象区，复用安全落盘、缩略图服务 |
| 安全 | loopback 127.0.0.1 + 启动令牌 + Host/Origin 校验 | 新 AI API 使用相同认证与路径白名单；Provider Key 仅后端保管 |

V1 的 ImportWorker 仅服务导入；AI 任务不可直接复用此队列造成导入和生成互相阻塞。

## 2. 逻辑总体架构

~~~mermaid
flowchart TB
  U[用户] --> UI[Vue 资产库 + AI 创作工作台]
  UI -->|本地受保护 REST| API[FastAPI /api/v1]
  UI --> IPC[Electron 受限 IPC：文件选择与拖入]
  API --> A[已有资产/目录/提示词服务]
  API --> P[AI Provider / Model / Capability 服务]
  API --> T[反推模板 + 创作预设 + Prompt Service]
  API --> J[持久化 AI Task Scheduler]
  J --> V[视觉分析 / LLM 优化适配器]
  J --> G[图像生成/编辑适配器]
  V --> EXT[远程/本地 AI 服务]
  G --> EXT
  J --> H[历史结果物理存储]
  A --> DB[(SQLite)]
  P --> DB
  T --> DB
  J --> DB
  H -->|用户选择正式入库| A
  A --> FILE[托管资产文件]
~~~

**核心边界**：仅服务端调用第三方 API、保存密钥及读写磁盘；Renderer 使用 asset_id、result_id、受控 upload_token，不传任意本机路径给业务 API。AI 模块与资产模块通过明确的“入库服务”连接。

## 3. 模块目录建议（不要求一次全部生成）

~~~
backend/app/api/v1/ai/
  providers.py models.py capabilities.py
  presets.py templates.py prompt.py
  jobs.py results.py reverse.py uploads.py
backend/app/models/ai/
  provider.py model.py template.py preset.py
  task.py task_item.py result.py reference.py
backend/app/services/ai/
  credentials.py provider_registry.py capability_service.py
  adapter_base.py adapters/{openai_compatible.py,openai_native.py,gemini_native.py}
  prompt_optimizer.py reverse_service.py
  task_scheduler.py task_executor.py task_recovery.py
  reference_service.py history_store.py result_import_service.py
apps/web/src/features/ai/
  components/ stores/ composables/ views/ api/
~~~

遵守仓库 AGENTS.md 的 SRP 与单文件 800 行控制线；真实实施以垂直切片拆文件。

## 4. AI Provider、模型能力与路由

### 4.1 领域对象
- **ProviderInstance**：用户命名的单个连接配置，family={openai_compatible, openai_native, gemini_native}；包含 base_url、启用状态、credential_ref、超时等非秘密设置。同类 Provider 可多实例。
- **ModelProfile**：归属一个 ProviderInstance，具有 model_id、显示名、adapter_kind、能力集合与 capability_schema；由用户手动添加为主，第三方 model list 可选，不依赖自动发现。
- **Capability**：text_optimize / image_understand / image_generate / image_edit；可为模型/能力分别配置支持情况、格式、最大参考数量与可用参数。能力表是**运行契约**，不是只读展示标签。
- **DefaultBinding**：全局生成 GPT 模型、视觉反推模型、Prompt 优化 LLM、场景预设覆盖模型；选择顺序：本次手动 > 场景默认 > 全局该能力默认。无可用模型必须明确要求用户配置，不能悄悄切换供应商。

### 4.2 Adapter 协议（建议）

- describe_capabilities(profile) -> CapabilitySchema
- validate(config, inputs) -> ValidationResult
- run_vision(image_inputs, template, params) -> TextResult
- optimize_prompt(user_text, system_rules, optional_images) -> TextResult
- generate_images(prompt, references, params) -> ImageResultCollection
- submit/poll/cancel(resumable_handle) -> JobState (仅支持的异步 Provider 实现)
- normalize_error(provider_error) -> {code, message, retryable, provider_request_id}

采用**按动作适配**：OpenAI Compatible 的聊天兼容不推出它的生图兼容；对 /images/generations、/images/edits、Responses 类交互、非标准代理响应分别按实际合同处理。Gemini Native 独立实现。任何所谓“万能 OpenAI 兼容模式”只能是明确声明了协议的适配器，失败时清楚告知不支持。

### 4.3 动态参数描述

CapabilitySchema 推荐字段：
- 支持的 mode、accepts_references、min/max_reference_count、accepted_mime_types、max_file_bytes；
- param_specs = [{name, type, required, default, enum/range, depends_on, visible_when, adapter_key}]；
- output_media_types、max_outputs、supports_seed、supports_cancel、supports_status_poll、supports_remote_resume；
- ui_hints（折叠分组、文案）仅作展示，不当作服务器校验替代。

**UI 和后端双重校验**：模型切换时重新校验之前参数；不兼容值显示待处理提示而非静默保留并提交。模型版本更新可能使旧能力配置失效，触发重新测试。

### 4.4 配置安全

- Windows 优先使用系统用户作用域安全存储（如 Windows Credential Manager/DPAPI）的封装；SQLite 保存 key 引用与非秘密配置，不明文保存 API Key。
- 服务端只对用户登记的连接目标发外部请求；验证 scheme/目标域名/端口，安全处理重定向、代理、TLS，默认不把本地 asset 内容或 Key 发到未知 host；不额外开放本期未使用的 ComfyUI 服务入口。
- Provider API 响应、日志、失败信息脱敏；敏感请求体、参考图片和 Prompt 不写原始 debug 日志；连接测试按能力单独报告。
- UI 不支持未经额外安全审核任意 URL 直接载入远程文件/重定向访问内网地址。

## 5. 数据模型与迁移建议

**不在 SQLite 存图片大文件。** 使用 Alembic 0010+ 向前迁移，字段命名仅为方案草案。

| 建议表/变更 | 核心字段（示例） | 说明 |
|---|---|---|
| assets 增量 | asset_origin, prompt_origin, generation_task_id(nullable), generation_result_id(nullable), prompt_revision | 保留 prompt_text/source_type；在 V1 文本已有时默认 prompt_origin=manual；未知历史资产来源标成 legacy/imported 并在迁移说明体现，不伪造创作信息 |
| ai_provider_instances | id, family, name, base_url, credential_ref, enabled, settings_json | 多连接实例；API Key 不入普通 TEXT |
| ai_model_profiles | id, provider_id, model_id, adapter_kind, capability_json, enabled | 模型能力与参数定义 |
| ai_templates | id, kind(reverse/create), name, system_rules, variable_schema_json, builtin, updated_at | 内置/用户自定义分类，不混淆反推与创作 |
| ai_presets | id, name, mode, model_profile_id, template_id, settings_json, ref_slots_json | 图片创作场景预设；可选覆盖 |
| ai_tasks | id, task_type, provider_id, model_id/workflow_id, status, retry_of, idempotency_key, input_snapshot_json, external_handle, error_code, created/updated/finished_at | 持久任务与执行配置快照 |
| ai_task_items | id, task_id, asset_id(nullable), status, draft_prompt_text, prompt_revision_at_start, error | 单/批量反推逐项结果及审核状态 |
| ai_task_references | id, task_id, seq, role, source_kind, source_id, snapshot_path, hash | 永久的输入图快照，保序；角色用途只是语义 |
| ai_results | id, task_id, idx, history_file_path, mime_type, sha256, width, height, imported_asset_id(nullable), created_at | 生成结果；独立于正式资产生命周期 |
| ai_storage_settings | root/path, last_import_target, other policies（或 app_settings 键空间） | 历史存储位置的具体产品暴露方式待 UX 定稿 |

必要索引：task(status,provider_id,created_at)、result(task_id,idx)、result(imported_asset_id)、task_item(task_id,status,asset_id)、asset(generation_task_id)、model(provider_id,enabled)。批量反推写入要为每个 asset 逐项事务提交，避免单个失败回滚全部。

### 数据迁移与历史 Prompt 安全

1. 运行迁移前应提供数据库备份与失败回滚指引；对重要字段只**追加**列，不拆掉 V1 prompt_text。
2. V1 prompt_text 非空 → prompt_origin=manual（因为 V1 只支持手工填写），空则 null；V1 来源若无法精确区分导入/关联，存 legacy/unknown 比虚构更准确。
3. 保存/覆盖 Prompt 时以 **expected_prompt_revision**（或等价版本校验）做并发控制；用户看见原文 → 预览新内容 → 确认替换；版本冲突 409 则刷新提示再处理。
4. 入库成功后再回写 ai_results.imported_asset_id；如文件成功/数据库提交失败，执行补偿并标记待修复。
5. prompt_revision 是防误覆盖所需的技术并发控制，不代表增加“多提示词版本历史”。

## 6. 文件布局与永久历史

建议把 AI 永久数据默认放在**用户托管素材所在卷**下独立命名空间（例如 managed_root/ai-history），而不是默认占满系统 C 盘。历史文件路径逐记录持久化，用户修改新存储位置后，旧历史仍在原位可用，不静默迁移。

~~~
<managed_root>/
  objects/<asset-id>/<filename>       # V1 正式资产
  ai-history/
    inputs/<task-id>/<seq>.<ext>       # 本次参考图不可变快照
    results/<task-id>/<result-id>.<ext>
    staging/<task-id>/                 # 未完成下载/产物组装
  cache/thumbnails/...                # 可重建缓存（位置依现有配置）
~~~

**不变量**：
- 云端 API 返回的临时图片 URL 或第三方短期可用下载地址都不能成为“永久历史的唯一文件地址”；在任务成功时校验文件格式、大小、hash，再**拷贝到 Ryan_DAM 控制的历史区**、原子提交。
- 生成历史 → 正式资产入库，推荐**复制 + 校验 + 原子改名**到 assets/objects 对应位置，以保证两个独立生命周期；同源文件再入库须避免未经确认重复创建，禁止复用原结果文件作为可删共享对象。
- 临时本地参考图不强制成为正式 asset，但参与执行前复制不可变快照；按任务保留。用户移动原文件不影响已完成任务复现。
- 托管根/历史盘满、移除或断联要明确报错，不能默默切到 C 盘；落盘前空间预检及崩溃补偿。
- 删除生成历史时与“删除正式资产”区分：已入库资产副本不被删除；历史记录/快照的删除要有危险确认与物理文件安全检查。**没有自动 TTL 清理**。

## 7. AI Task Scheduler 与持久化状态

### 7.1 单机执行策略

- 新增独立 task scheduler，进程内有界执行器，SQLite 负责持久任务和去重；不复用 V1 ImportWorker 的单线程队列。
- 每 Provider/连接实例限流、全局小并发，默认值由技术 PoC 决定并暴露后续可调的设置（**非用户已确认固定值**）。
- DB 事务只负责领取任务、更新状态、提交结果；第三方 HTTP 等待、图像下载、外部异步任务长时间轮询必须放在事务外。SQLite WAL 下短事务写入，避免对资产浏览造成写锁阻塞。
- 任务优先保持输入快照完整、执行可追溯；API 开始执行前检查 Provider、模型、输入图存在、磁盘空间、格式及参考数限制。

### 7.2 状态机

~~~mermaid
stateDiagram-v2
  [*] --> queued
  queued --> running: 获得执行配额
  queued --> canceled: 取消排队
  running --> succeeded: 结果全部校验并落盘
  running --> partial_failed: 多项任务部分成功
  running --> failed: 明确失败
  running --> cancel_requested: 用户请求取消
  cancel_requested --> canceled: 上游确认终止
  cancel_requested --> succeeded: 上游实际已完成
  running --> recovery_needed: 进程意外退出 / 状态未知
  recovery_needed --> running: 可通过外部句柄重新查询
  recovery_needed --> failed: 可确认已失败
  failed --> queued: 创建新的 retry_of 任务
~~~

- Retry 的默认含义是**新建带 retry_of 的任务**，不会覆盖原失败记录。
- 任务提交外部成功但本地响应丢失时，标记 recovery_needed；使用 request_id/external_handle 查询可恢复状态，不能自动盲重试造成多次计费。
- 只有 Provider 确认支持远程取消时才承诺取消已运行任务；否则“停止本地等待”与“上游停止计费”分别提示。
- 模型不报告准确百分比时 UI 展示“执行中 + 已经过时间”，不伪造进度数字。
- 批量反推每个 item 有独立成功、失败、待审核及保存状态，整体任务可 partial_failed。

## 8. 主要 API 草案（均为**建议路由**）

| 路由 | 方法 | 用途 |
|---|---|---|
| /api/v1/ai/providers | GET/POST/PATCH/DELETE | 连接实例管理，响应严格不含密钥 |
| /api/v1/ai/providers/{id}/test | POST | 测试连接或具体能力 |
| /api/v1/ai/models | GET/POST/PATCH/DELETE | ModelProfile 和 CapabilitySchema |
| /api/v1/ai/templates | GET/POST/PATCH/DELETE | 视觉反推与创作 Prompt 规则 |
| /api/v1/ai/presets | GET/POST/PATCH/DELETE | 创作场景预设 |
| /api/v1/ai/prompts/optimize | POST | 简单描述 → LLM 生成可审阅最终 Prompt（后端可落任务记录） |
| /api/v1/ai/reverse | POST | 单图/批量视觉反推任务 |
| /api/v1/ai/reverse/{task_id}/commit | POST | 逐项审核保存，expected_prompt_revision CAS |
| /api/v1/ai/references/import | POST | 受控导入临时图，返回上传引用令牌 |
| /api/v1/ai/tasks | GET/POST | 列表或提交图片生成/编辑任务 |
| /api/v1/ai/tasks/{id} | GET | 状态/过程/结果与错误 |
| /api/v1/ai/tasks/{id}/cancel | POST | 排队取消或请求中止 |
| /api/v1/ai/tasks/{id}/retry | POST | 创建关联重试任务 |
| /api/v1/ai/results | GET | 永久生成历史搜索/筛选/分页 |
| /api/v1/ai/results/{id}/content | GET | 经认证的历史文件流/Range |
| /api/v1/ai/results/import-to-library | POST | 单项/多项正式入库、目标 folder_id |
| /api/v1/ai/results/{id} | DELETE | 用户明确删除历史项 |
| /api/v1/assets/{id} | GET | V1 资产详情增加来源和生成任务关联 |
| /api/v1/assets/{id}/prompt | PUT | 扩展 expected_prompt_revision 与 prompt_origin（兼容旧客户端） |

**安全审查**：所有文件访问经服务端 ID 绑定记录路径与状态；不接受 Renderer 任意绝对路径；图像 multipart 上传需要大小、类型、像素预算、总任务输入数量等限制。前端请求沿用 X-Ryan-DAM-Token 和 loopback guard。

### 8.1 示例业务接口字段（概念示例）

- SubmitImageJob: mode(generate/edit), model_profile_id, prompt_final, raw_user_request?, preset_id?, references:[{source_kind,source_id/upload_token,seq,role}], params, client_request_id。
- ResultToLibrary: result_ids[], target_folder_id, confirmed_by_user, duplication_policy（具体去重约束待定）。
- ReverseBatch: asset_ids[], template_id, model_profile_id, optional_overrides；返回 task_id。
- ReverseCommit: items:[{asset_id, draft_text, expected_prompt_revision, confirm_overwrite}]；逐项报告冲突，不静默重试覆盖。

## 9. Prompt 及模板安全

- **视觉反推模板**：系统提示词要求只描述画面可观察事实，不声称提取真正原始 Prompt；反推不应虚构镜头/设备信息为确定事实。
- **创作预设模板**：System Rules + 可选用户自定义变量 + 用户自然语言，LLM 优化得到可编辑最终 Prompt。
- “默认 AI 优化”表示工作台重点引导优化流程，**不会在用户没确认最终 Prompt 时自动提交生图**；用户有“直接生成”跳过选择。
- 参考图作为不可信内容，只能作为视觉输入，不执行从图里文字识别到的“系统指令”；外部模型结果也不能覆盖本地安全规则。
- 任务记录保存实际发送给模型的 final prompt；正式资产只保存一份实际 Prompt。不建立版本集合。
- Prompt 保存不能破坏换行/特殊字符；此前用户手工输入内容遇覆盖须确认。

## 10. 二期执行器边界与后续扩展（决策㉒）

**本期没有 ComfyUI 实现工作量**：不创建 ComfyUI 连接表单、API Workflow 导入/映射、ComfyUI Adapter、ComfyUI 任务状态适配器或专项测试；不做相关技术 PoC。

架构层面的图像执行器通过 Provider/Model/Capability Adapter 协议隔离即可，不必提前实现未用到的 Workflow 领域对象。**二期全部完成后**如果用户决定接入 ComfyUI，再基于⑪的历史方案单独出 Spec/技术设计：API Workflow JSON → 输入输出映射 → 预设 → 队列任务 → 结果回收。是否真正接入届时重新评估，**不视作承诺开发**。

## 11. 设计验证与测试矩阵

| 编号 | 重点验收 |
|---|---|
| ARCH-01 | 两个第三方兼容实例独立保存，连接、模型能力、全局 GPT 默认与场景覆盖正确路由 |
| ARCH-02 | API Key 不出现在 Vue 持久化状态、SQLite 明文、任务历史、失败日志及网络可见 JSON |
| ARCH-03 | 多参考图次序/用途稳定保留；某张临时源文件删除后历史输入快照仍可读 |
| ARCH-04 | 模型切换时未支持参数被拒绝且 UI 给出明确处理 |
| ARCH-05 | LLM 优化与直接生成均提交正确 final prompt；提示词不被系统暗改 |
| ARCH-06 | 并发两类 Provider，导入/预览不卡顿；模拟取消/超时/中断不造成重复任务误提交 |
| ARCH-07 | 生成 4 张，仅 2 张入库；4 张历史和 Prompt/来源/任务关联均保留 |
| ARCH-08 | 覆盖已有 Prompt 时 CAS 检查冲突，旧值未经确认不变 |
| ARCH-09 | V1 DB 升级保留 prompt_text、source_type、file_path；V1 回收站/外部引用行为不变 |
| ARCH-10 | 第三方图片 API 返回临时链接或 base64 图像；均正确保存为本地永久历史副本，断网后仍可预览 |
| ARCH-11 | 历史删除不会误删已入库资产；磁盘空间不足/崩溃 staging 清理可恢复 |
| ARCH-12 | 未经本地 token 和允许 Origin 的 AI API 被拒绝；任意路径访问被拒绝 |

## 12. 官方协议参考与风险说明

- OpenAI 图片 API 生成/编辑： https://developers.openai.com/api/docs/guides/image-generation
- OpenAI 图片编辑参考： https://developers.openai.com/api/reference/resources/images/methods/edit
- Gemini 图片接口： https://ai.google.dev/gemini-api/docs/image-generation

**协议随供应商与模型版本变化**：本设计不写死“GPT Image 永远只有某个 Model ID”、固定参考图数、固定尺寸枚举或 Gemini 统一返回结构；均通过能力声明/Adapter/集成测试保证。

## 13. 对 V2 Spec 尚未决事项的处理建议

| 未决事项 | 当前设计建议 | 是否阻塞设计 |
|---|---|---|
| 优化 LLM 默认型号 | 由用户选择其已配置模型；未配置时明确引导 | 否 |
| 图片接口协议差异 | Adapter + capability contracts + PoC | 否 |
| 反推模板最终措辞 | 单独模板验收样例和用户可编辑 | 否 |
| 模型参数与场景默认冲突 | 明确优先级和兼容性检查 | 否 |
| 并发/费用/重试具体阈值 | 小并发、可配置、危险失败不自动重提 | 否 |
| 永久历史文件方案 | App 独立历史副本、用户可手动删除 | 否 |
| 同一结果重复入库 | UI 阻止默认重复，明确复制选项另评估 | 否 |
| 视频功能范围 | **暂未确认**，当前仅为图片路径设计 | **不阻塞图片开发，但影响未来批次排期** |

> 本文是可交付给开发者 review 的详细技术方案；正式实施前先开展 **本期 Provider 图片协议**、Windows 凭据存储及磁盘原子化流程的小型 PoC，结果反哺本设计。**ComfyUI 专项 PoC 不属于二期。**
