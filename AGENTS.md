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
