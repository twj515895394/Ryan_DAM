# Ryan_DAM 开发与设计规范指南（Agent / Developer Guide）

本文档供所有参与本项目的 AI Agent 及开发者阅读，必须严格遵守。

---

## 1. 运行环境与后端约束

- **Python 环境**：必须且仅能使用当前项目的虚拟环境 `.venv/Scripts/python.exe`。严禁调用全局系统 Python。
- **端口约束**：后端 CORS 白名单硬编码只允许 `http://127.0.0.1:5173`。前端开发与测试冒烟必须在 5173 端口运行。
- **本地代码交付**：开发期间在本地 Git 仓库原子化提交，待完整阶段自测、审查全部通过后方可执行推送。

---

## 2. 前端设计与组件规范（Apple HIG & Anti-Slop）

本项目为面向个人创作者的高品质桌面级资产管理器，拒绝简陋廉价感（Anti-Slop），严格遵循 Apple Human Interface Guidelines 桌面风格：

### 2.1 严禁原生浏览器弹窗
- ❌ **绝对禁止**使用 `window.confirm()`、`window.alert()` 或 `window.prompt()`。
- ✅ **统一使用** `apps/web/src/components/ConfirmDialog.vue`。
  - **背景质感**：采用 `backdrop-blur-xl` 高度半透明毛玻璃、`bg-white/95`、`rounded-2xl` 与 `shadow-2xl`。
  - **语义意图（Intent）**：
    - `danger`：危险与破坏性操作（彻底删除、粉碎、清空回收站）。对应红底微光环图标与深红操作按钮。
    - `warning`：警示操作（解除外部目录关联、移除索引）。对应琥珀黄微光环图标。
    - `default`：常规系统操作（转为托管存储）。对应系统强调蓝图标。
  - **键盘流规范**：弹窗弹出后自动聚焦确认按钮，按 <kbd>Enter</kbd> 确认，按 <kbd>Esc</kbd> 取消。

### 2.2 命名与输入对话框
- ✅ **统一使用** `apps/web/src/components/NameDialog.vue`：
  - 用于新建项目/文件夹/标签、重命名、修改托管存储路径等。
  - 自动获得焦点并选中文本，支持 <kbd>Enter</kbd> 提交、<kbd>Esc</kbd> 取消，并具备防重复并发提交锁。

### 2.3 资产多选与交互逻辑
- **命中热区（Hit Target）**：卡片勾选按钮遵循 Apple HIG 规范，外层透明容器尺寸保持在 44×44px（`h-11 w-11`，内嵌 `h-5 w-5`），确保轻松点选，杜绝误触。
- **双模交互区分**：
  - **浏览模式**（无任何资产勾选）：点击卡片任意区域直接打开全屏沉浸预览。
  - **多选模式**（已有勾选项，或按住 `Ctrl` / `Cmd` / `Shift`）：点击卡片任意区域切换勾选，绝不打断弹出预览。
- **快捷键体系**：
  - <kbd>Ctrl+A</kbd> / <kbd>Cmd+A</kbd>：全选当前视图资产。
  - <kbd>Shift + Click</kbd>：区间连选。
  - <kbd>Esc</kbd>：若有预览弹窗则关闭预览；若处于多选则一键取消选择。

### 2.4 内联标签与即时创建（Combobox）
- 标签选择器（单资产预览面板、多选底部批量操作栏）必须支持实时过滤搜索。
- 支持在下拉框内直接输入新标签名，回车即完成「新建并立即打标」，杜绝跳转到标签管理页的繁琐操作。

### 2.5 严禁原生表单控件（No Native OS Form Slop）
- ❌ **绝对禁止**在业务组件中使用原生 `<select>` 标签。原生 OS 下拉菜单视觉粗糙、各操作系统渲染不一致、缺乏搜索且破坏整体毛玻璃设计语言。
- ✅ **统一使用** `apps/web/src/components/AppleSelect.vue`：
  - 具备半透明毛玻璃背景、微羽化阴影、状态徽标（badge/badgeColor）、次级辅助说明（subLabel）、选中间隙 checkmark。
  - 支持多候选项时的实时搜索（searchable）及根据视口空间自动向上/向下翻折弹出。
- ❌ **绝对禁止**暴露浏览器默认的粗灰直角滚动条。所有滚动容器依赖全局注入的高级悬浮微型滚动条（`scrollbar-width: thin`，透明轨道，6px 圆角半透明悬浮滑块），杜绝粗糙边缘割裂质感。

### 2.6 弹窗与浮层容器规范（Modal Layout Architecture & Anti-Overflow & Z-Index）
为防止出现「动态生成长文本撑爆弹窗容器，导致底部操作栏被顶出屏幕或关闭/取消按钮点击无反应」的恶性体验缺陷，所有模态弹窗必须严格执行以下容器规范：
- ❌ **严禁使用未受限的平铺式弹窗容器**（即高度由子节点随意撑大、外层没有最大高度限制与内层滚动机制）。
- ✅ **强制统一采用「三段式固定+滚动」容器架构（Fixed Header / Body / Footer）**：
  - 外层卡片严格限制视口最大高度与弹性列布局：`max-h-[90vh]`（或 `max-h-[85vh]`），配合 `flex flex-col overflow-hidden`。
  - **固定头部（Fixed Header）**：设置 `shrink-0 border-b`，包含标题与显式关闭按钮。关闭按钮必须声明 `type="button"`，内部图标添加 `pointer-events-none`（避免 SVG 拦截点击事件），并绑定 `@click.stop="handleClose"`。
  - **独立滚动体（Scrollable Body）**：设置 `flex-1 overflow-y-auto px-6 py-5`。所有表单项、参数选择器、动态执行结果、多行编辑框（textarea）必须收纳在滚动体内部。内容增多时只在内部平滑滚动，绝不撑大外层视口。
  - **固定底部（Fixed Footer）**：设置 `shrink-0 border-t bg-canvas/40 px-6 py-3.5`。状态提示与操作按钮（取消、保存、执行）固定吸附在底部，确保无论内容多长，操作按钮始终可见、始终可点。
- **全链路键盘流（Keyboard Escape）**：
  - 每个弹窗组件必须挂载全局 <kbd>Esc</kbd> 监听（`e.preventDefault(); e.stopPropagation(); handleClose()`），确保在任何输入与浏览状态下都能通过键盘直接安全退出。
- **严格的分层上下文规范（Z-Index Hierarchy）**：
  - 底层视图层：`z-0` ~ `z-30`
  - 全屏资产预览（`AssetPreview.vue`）：`z-40`
  - 普通主业务弹窗（`AiWorkbenchModal.vue` / `PromptModal.vue` / `SettingsDialog.vue`）：`z-50` ~ `z-[55]`
  - 嵌套子业务弹窗（如预览内唤起的 `AiReverseModal.vue`）：`z-[60]`
  - 全局系统级二次确认框（`ConfirmDialog.vue`）：`z-[70]`（确保其无论在任何业务弹窗上呼出，均处在最顶层并获得第一交互焦点与响应优先级）。

---

## 3. 代码架构与设计模式规范（Clean Architecture & File Size Limit）

- **单一职责原则（Single Responsibility Principle, SRP）**：
  - 每个模块、服务类与组件应只承担单一维度的核心职责。
  - 避免将数据获取、复杂业务处理、视图渲染与弹窗状态混杂在单一巨型文件中。
  - 复杂视图或业务面板应适时提取为独立原子子组件（例如独立的 Dialog、Drawer、Panel、Card 等）。
- **文件代码行数上限约束**：
  - **建议及控制上限**：每个源码文件（包括 Vue 组件 `.vue`、TypeScript 模块 `.ts`、Python 脚本 `.py`）的代码行数**尽量不要超过 800 行**。
  - **超限重构规则**：若某个文件随着业务迭代即将或已经达到 800 行，必须按照功能域拆分子组件、子服务（Service）或抽离 hooks/composables/utils，杜绝千行以上的「上帝组件（God Component）」或「上帝类」。

---

## 4. 测试与验证标准

修改代码后，交付前必须执行以下三项验证：
1. `npm run typecheck`（Vue 3 + TypeScript 类型检查无报错）
2. `npm run build:web`（Vite 生产构建成功）
3. `.venv/Scripts/python.exe -m pytest backend/tests`（后端全部 120+ 单元测试绿灯通过）
