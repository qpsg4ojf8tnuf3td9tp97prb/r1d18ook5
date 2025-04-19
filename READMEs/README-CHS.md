[English](/README.md) | [한국인](/READMEs/README-KR.md) | [日本語](/READMEs/README-JP.md) | [正體中文](/READMEs/README-CHT.md) | [简体中文](/READMEs/README-CHS.md)

# Ridibooks 阅读器注入器

本项目提供了一套工具，用于对 Windows 平台上的 Ridibooks 阅读器进行补丁修改和自定义 JavaScript 注入。通过启用 Chrome DevTools 的远程调试功能，你可以访问阅读器的内部 API，比如注入下载按钮等。

无论你是希望提取自己拥有的内容，想了解 Electron 应用的运行机制，还是想探索 Chrome DevTools 的各种可能，这个项目都是为你准备的——**前提是你用对了方式（详见[法律声明](#%EF%B8%8F-法律声明)以及 [`LICENSE`](/LICENSE)）**。

> ⚠️ 本仓库**仅用于学习和归档目的**。  
> ⚠️ 使用本工具所带来的任何后果，均由你本人承担。

---

## ⚖️ 法律声明

**⚠️⚠️⚠️在使用本项目之前，请务必阅读本节内容。⚠️⚠️⚠️**

本项目采用独特的授权协议（详见 `LICENSE`），仅当你**正确使用**时才视为有效。该协议包含针对滥用行为的强制终止条款。

### ✅ 正确使用包括但不限于：
- 你操作的内容是你合法拥有或有明确授权的；
- 你不会绕过付费墙、DRM，或访问/传播受版权保护的内容；
- 你不会开发鼓励或依赖违规行为的服务/工具；
- 你会删除任何不该保留的提取内容。

### ❌ 错误使用将导致：
- **立即且永久失去使用本项目的权利**；
- **永久失去访问作者所有当前和未来作品的权利**——无例外、无二次机会；
- 所有因滥用所造成的后果，**由你自行承担**。

如果你无法确定自己的用途是否合法：**那就别用。**

只要你在法律和道德允许的范围内，你就拥有完全的自由。  
如果不是——这个项目不适合你。它不会保护你，我也不会。

---

## 🧩 功能特性

- 可从源码完整构建（基于 Nuitka）
- ...

---

## 🛠️ 使用说明

0. **从官网下载并安装 Ridibooks 阅读器**:  
   https://getapp.ridibooks.com/windows

1. **下载 `patch.exe` 与 `inject.exe`**：
   [最新版本](/../../releases/latest).

2. **运行 `patch.exe`**  
   此操作将启用 Ridibooks 应用内的开发者工具。  
   若需还原，请进入 Ridibooks 安装目录中的 `/resources`，删除 `app.asar`，并将 `app.asar.bak` 重命名回 `app.asar`。

3. **启动 Ridibooks**  
   你需要先运行一次 Ridibooks，以初始化注册表项。

4. **运行 `inject.exe`**  
   启动带远程调试功能的 Ridibooks，并注入自定义 JavaScript 脚本。注入后的脚本将为阅读器添加下载按钮。

> 💡 如果你不信任已编译好的二进制文件，可以查看 `src/` 目录下的 Python 源码并直接运行。

---

## ⚠️ 注意事项

- 本项目使用 **Nuitka** 构建；构建参数定义在 `build.bat` 中。
- 某些杀毒软件可能会**误报该程序为恶意软件**。这是 PyInstaller/Nuitka 打包程序的常见误报。如有需要请手动将其加入白名单。
- 软件以**“现状”形式发布**，不提供任何形式的担保。
- 本项目为**源代码可用**，但并非开放源代码，主要出于法律风险考量。  
  使用条款详见 `LICENSE` 文件。

---

## 🧾 授权许可

本项目并非传统意义上的开源项目。  
你可以在符合法律并尊重上述规则的前提下，**自行修改与再发布源代码**。  
前提是你必须同时遵守本文件和 [`LICENSE`](/LICENSE) 中所述的所有约束。  
请自行阅读 [`LICENSE`](/LICENSE) 以获取完整细节。  
本项目不提供任何担保，使用风险自负。

---

## 📦 更新日志

本项目的所有重要更新都会记录在本文件中。

版本格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，  
并遵循 [语义化版本控制规范](https://semver.org/lang/zh-CN/)。

---

### [0.1.1] - 2025-04-14

#### ✨ 新增
- 使用 `RidiProcess` 异步上下文管理器完全重写进程启动流程，更好地控制生命周期
- 使用异步任务 (`_log_process_output`) 改善子进程输出的日志记录
- 为 `execute_js()` 和调试器轮询增加稳健的 WebSocket 错误处理
- 在退出时通过 `terminate_process()` 自动清理所有剩余的 Ridibooks 进程
- 控制台收集器独立捕获警告信息，并支持通过 `__enableConsoleOutput` 切换控制台输出

#### 🛠️ 修改
- 将 `DebuggerMonitor.polling_interval` 从 1.0 秒改为 0.1 秒，以加快调试器检测速度
- 改进 `setup_logger()` 日志格式为更易读的 `[LEVEL] 消息` 格式
- 重构 `main()`，确保 Ridibooks 干净启动，并妥善处理启动异常（如 EXE 缺失、超时等）
- 注入的 JS 会等待 60 帧动画，以确保阅读器 iframe 完全加载后再继续执行
- 为更好的时序和可靠性，重新组织了 `inject_to_viewer()` 及相关的注入流程

#### 🧹 移除
- 弃用冗长的带时间戳的日志格式，改为简洁输出
- 移除控制台输出必须始终开启的硬性设置（增加了可切换选项）

---

### [0.1.0] - 2025-03-26

#### ✨ 新增
- 日志系统，支持日志等级和可选文件输出（`--log-level`、`--log-file`）
- 命令行参数解析，增强配置能力
- 使用类模块化设计：调试器监控器（`DebuggerMonitor`）、进程生命周期管理器（`RidiProcess`）
- 通过 WebSocket 从 Chrome DevTools 收集控制台输出
- 捕获注入脚本中的错误并转发日志
- 使用 `terminate_process()` 实现平稳的进程关闭及备用终止逻辑
- 全面改进错误处理与结构化日志输出

#### 🛠️ 修改
- 完全重写 `inject.py`，结构清晰，文档齐全，支持类型注解
- 项目结构重新整理，明确分离监控、注入与工具模块
- 用异步类和辅助模块封装原先的零散逻辑
- WebSocket 通讯增强鲁棒性，添加异常捕获机制（`websockets.exceptions`）
- 统一 `main()` 流程，支持 RidiBooks 的干净启动与重启

#### 🧹 移除
- 原始的全局混乱逻辑及耦合严重的 `monitor_debuggers` + `inject_to_viewer` 循环
- 所有无输出捕获的直接进程调用
- 不安全的条件检查与含糊的错误处理

---

### [OLDVERSION] - ?

#### 新增
- 初始版本的 `inject.py`，实现 Ridibooks 的 JavaScript 注入
- 基于 Chrome DevTools Protocol 的运行时评估功能
- 自动检测 Ridibooks 安装路径（通过注册表）
- 调试端口分配及监听机制

---

## 🙏 鸣谢

感谢所有愿意去探索、解构、再创造工具的人——  
不是为了打破规则，而是为了更好地理解它们。

特别感谢  
[Ridibooks 阅读器](https://ridibooks.com) 的开发者们，提供了值得学习的平台，  
以及 [Nuitka](https://nuitka.net) 和 [websockets](https://websockets.readthedocs.io/)  
这两个强大的工具项目，为本项目提供了坚实基础。

还有那位不愿具名却启发我完善本项目的人。

这个项目的诞生离不开好奇心、对边界的尊重，  
以及一丝“要不我们试试……？”的念头。
