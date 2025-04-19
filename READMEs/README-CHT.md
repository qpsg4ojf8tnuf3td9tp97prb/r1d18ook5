[English](/README.md) | [한국인](/READMEs/README-KR.md) | [日本語](/READMEs/README-JP.md) | [正體中文](/READMEs/README-CHT.md) | [简体中文](/READMEs/README-CHS.md)

# Ridibooks 閱讀器注入工具

本專案提供一套工具，用來修補並注入自訂 JavaScript 至 Ridibooks Windows 版閱讀器中。  
透過 Chrome DevTools 遠端除錯功能，您可以存取內部的閱讀器 API，例如加入下載按鈕等。

無論您是想備份自己合法擁有的內容、學習 Electron 應用的運作方式，或是探索 Chrome DevTools 的潛能，這個專案都是為此而設計的——**前提是您使用的方式正當（詳見[法律聲明](#%EF%B8%8F-法律聲明)以及 [`LICENSE`](/LICENSE)）**。

> ⚠️ 此專案**僅供學術研究與歷史存檔用途**。  
> ⚠️ 使用本工具所造成的任何後果，請自行負責。

---

## ⚖️ 法律聲明

**⚠️⚠️⚠️在使用本專案前，請務必閱讀本節內容。⚠️⚠️⚠️**

本專案採用一份特殊授權條款（見 `LICENSE`），該授權**僅在您正當使用時生效**。若濫用，授權將自動終止。

### ✅ 合法使用包括：
- 使用於您本人擁有或擁有完整合法授權的內容。
- 不用於繞過付費牆、DRM 或存取／散布受著作權保護的內容。
- 不開發鼓勵或依賴違法行為的服務或工具。
- 若擷取到不應保留的內容，請立即刪除。

### ❌ 不當使用將導致：
- **立即且永久失去使用本專案的權利**。
- **永久失去存取作者所有現有與未來作品的權利**——不設例外、亦無補救機會。
- 使用者需**自行承擔一切後果與法律責任**。

若您不確定自己的使用是否正當：**請不要使用本工具。**

只要您行為合法合情，您就享有完全的自由。  
若您跨越這些界線——這個專案不屬於您。我無法保護您，也不會為您辯護。

---

## 🧩 功能特色

- 可從原始碼完整重建（使用 Nuitka）
- ...

---

## 🛠️ 使用說明

0. **從官方網站下載並安裝 Ridibooks 閱讀器**:  
   https://getapp.ridibooks.com/windows

1. **下載 `patch.exe` 與 `inject.exe`**：
   [最新版本](/../../releases/latest).

2. **執行 `patch.exe`**  
   此操作會啟用 Ridibooks 的開發者工具。  
   若想還原，請前往 Ridibooks 安裝資料夾的 `/resources` 目錄，刪除 `app.asar`，再將 `app.asar.bak` 更名為 `app.asar`。

3. **啟動 Ridibooks**  
   請先執行一次 Ridibooks，以初始化登錄檔設定值。

4. **執行 `inject.exe`**  
   此操作會啟動 Ridibooks，開啟遠端除錯模式，並將 JavaScript 注入至閱讀器中。注入的腳本會加入一個下載按鈕。

> 💡 若您不信任預編譯的執行檔，可檢視 `src/` 目錄下的 Python 原始碼，並直接從原始碼執行。

---

## ⚠️ 注意事項

- 本專案使用 **Nuitka** 編譯，建構參數定義於 `build.bat`。
- 某些防毒軟體可能會**誤判此程式為惡意軟體**。這在 PyInstaller 或 Nuitka 打包的執行檔中是常見的誤報情況。若必要請將其加入白名單。
- 本軟體**不提供任何保證**，依「現狀」提供。  
- 此專案屬於**原始碼開放（source-available）**，並非傳統開源（open source），原因涉及潛在法律風險。  
  詳見 `LICENSE` 中的使用條款。

---

## 🧾 授權條款

本專案**非傳統開源**。  
原始碼僅在您**合法且尊重上述限制條件的情況下**，可供個人修改與再發佈。  
詳見 [`LICENSE`](/LICENSE) 完整授權條款。  
本工具不提供任何形式的保固，使用風險請自負。

---

## 📦 更新紀錄（Changelog）

所有重大變更都會記錄於此檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)  
版本規則採用 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

---

### [0.1.1] - 2025-04-14

#### ✨ 新增
- 以 `RidiProcess` 非同步上下文管理器全面重寫程序啟動流程，實現更好的生命周期控制
- 使用非同步記錄任務 (`_log_process_output`) 強化子程序輸出的日誌記錄
- 加強 `execute_js()` 與除錯輪詢的 WebSocket 錯誤處理機制
- 結束時透過 `terminate_process()` 自動清理所有剩餘的 Ridibooks 程序
- 主控台收集器獨立捕捉警告訊息，並支援透過 `__enableConsoleOutput` 開關主控台輸出

#### 🛠️ 變更
- 為更快速的偵測除錯工具，將 `DebuggerMonitor.polling_interval` 從 1.0 秒調整至 0.1 秒
- 改進 `setup_logger()` 格式，採用更易讀的 `[LEVEL] 訊息` 風格
- 重構 `main()`，確保 Ridibooks 程序能乾淨啟動並妥善處理啟動錯誤（如 EXE 遺失或超時）
- 注入的 JS 現在會等待 60 幀動畫，以確保閱讀器 iframe 完全載入後再繼續執行
- 為更佳的時序和可靠性，重新組織了 `inject_to_viewer()` 與相關的注入流程

#### 🧹 移除
- 廢棄過於冗長的時間戳記錄格式，改用精簡輸出
- 移除主控台輸出必須總是顯示的硬性設定（改為可切換設定）

---

### [0.1.0] - 2025-03-26

#### ✨ 新增
- 日誌系統，支援等級設定與可選的檔案輸出（`--log-level`、`--log-file`）
- 支援命令列參數以提升設定彈性
- 使用模組化類別設計 `DebuggerMonitor`（除錯監控）與 `RidiProcess`（程序管理）
- 經由 WebSocket 從 Chrome DevTools 收集主控台輸出
- 自注入的瀏覽器環境中擷取錯誤訊息並轉發至主控台
- 支援優雅地關閉程序與後備強制結束邏輯
- 更完善的錯誤處理與結構化日誌輸出

#### 🛠️ 變更
- 完全重寫 `inject.py`，模組結構清晰，註解與型別標註完善
- 重構整體專案架構，明確分離監控、注入與工具等邏輯
- 替換臨時邏輯為封裝良好的非同步類別與輔助函式
- 使用例外處理與 `websockets.exceptions` 提升 WebSocket 穩定性
- 統一 `main()` 流程，支援乾淨啟動與重啟 RidiBooks 程序

#### 🧹 移除
- 舊有的全域臨時邏輯與緊耦合的 `monitor_debuggers` + `inject_to_viewer` 迴圈
- 直接執行程序但未擷取輸出的寫法
- 不安全的條件檢查與模糊的錯誤處理邏輯

---

### [OLDVERSION] - ?

#### 新增
- 初版 `inject.py` 實作，用於注入 JavaScript 至 RidiBooks 閱讀器
- 初步支援透過 Chrome DevTools Protocol 執行即時指令
- 自動偵測 RidiBooks 安裝路徑（透過登錄檔）
- 除錯埠分配與監控迴圈

---

## 🙏 特別感謝

感謝所有願意探索、拆解並重新想像身邊工具的人——  
不是為了打破規則，而是為了更深入理解這些規則。

特別感謝  
[Ridibooks 閱讀器](https://ridibooks.com) 的開發團隊，讓我們有值得學習的平台，  
以及 [Nuitka](https://nuitka.net) 與 [websockets](https://websockets.readthedocs.io/) 的作者們，  
提供了構建本專案的核心工具。

還有那位啟發我完善這個專案的人——一位同樣選擇匿名的朋友。

這個專案的誕生，離不開好奇心、界線意識，  
還有那一句：“如果……會怎樣？”
