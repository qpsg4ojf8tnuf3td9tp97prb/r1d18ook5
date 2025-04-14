[English](/README.md) | [한국인](/READMEs/README-KR.md) | [日本語](/READMEs/README-JP.md) | [正體中文](/READMEs/README-CHT.md) | [简体中文](/READMEs/README-CHS.md)

# Ridibooks Viewer Injector

This project provides tools to patch and inject custom JavaScript into the Ridibooks Viewer for Windows. It enables access to internal viewer APIs, such as injecting download buttons, via Chrome DevTools remote debugging.

Whether you're trying to extract with something you own, learn how Electron apps work, or explore the capabilities of Chrome DevTools, this project is meant to help you do that—**as long as you're doing it right (see [Leagal Notice](#%EF%B8%8F-legal-notice) AND [`LICENSE`](/LICENSE))**. 


> ⚠️ This repository is **for educational and archival purposes only**.  
> ⚠️ You are solely responsible for any consequences of using this tool.

---

## ⚖️ Legal Notice

**⚠️⚠️⚠️You must read this section before using this project.⚠️⚠️⚠️**

This project is distributed under a unique license (see `LICENSE`) which is only active if you're using it **properly**. The license enforces a strict self-termination clause for misuse.

### ✅ Proper use includes:
- You are using it on things you own or have full, lawful permission to interact with.
- You are not circumventing paywalls, DRM, or accessing/distributing copyrighted materials.
- You are not building services/tools that encourage or depend on violating those boundaries.
- You delete any extracted content you're not supposed to keep.

### ❌ Improper use results in:
- **Immediate and permanent loss** of rights to use this project.
- **Loss of access to all current and future works** by the author—no exceptions, no second chances.
- You're **entirely liable** for any consequences that arise from your misuse.

If you’re unsure whether your use is allowed: **don’t use it.**

You have full freedom only if you are within your legal and ethical bounds.  
If you’re not—this project is not for you. It will not protect you, and neither will I.

---

## 🧩 Features

- Fully rebuildable from source (via Nuitka)
- ...

---

## 🛠️ Instructions

0. **Download and install Ridibooks Viewer** from the official site:  
   https://getapp.ridibooks.com/windows

1. **Download `patch.exe` and `inject.exe`** from:
   [latest release](/../../releases/latest).

2. **Run `patch.exe`**  
   This enables Developer Tools in the Ridibooks application.  
   If you want to revert this, go to the Ridibooks installation folder (`/resources`), delete `app.asar`, and rename `app.asar.bak` back to `app.asar`.

3. **Launch Ridibooks**
   You need to run Ridibooks once first to initialize the registry values.

4. **Run `inject.exe`**  
   This launches Ridibooks with remote debugging enabled and injects JavaScript into the viewer. The injected script adds a download button.

> 💡 If you don't trust the pre-built binaries, you can audit the Python source code under `src/` and run directly from source.

---

## ⚠️ Important Notes

- This project is built using **Nuitka**; build parameters are defined in `build.bat`.
- Some antivirus software may **falsely flag the binary as malicious**. This is a common false positive for PyInstaller/Nuitka-packaged binaries. If needed, whitelist the binary.
- The software is distributed **as-is**, without warranty of any kind.  
- This is **source-available**, but not open source, due to potential legal concerns.  
  See `LICENSE` for usage terms.

---

## 🧾 License

This project is not traditional open source.
The source code is available for personal modification and redistribution **if and only if** your use is lawful and respectful of the boundaries stated above **AND** in  [`LICENSE`](/LICENSE).  
Refer to the [`LICENSE`](/LICENSE) file for full details.  
No warranty is provided. Use at your own risk.


---

## 📦 Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

---

### [0.1.1] - 2025-04-14

#### ✨ Added
- Full rewrite of the process startup flow using `RidiProcess` async context manager for better lifecycle control
- Enhanced logging for subprocess output using async logging tasks (`_log_process_output`)
- Robust WebSocket error handling for `execute_js()` and debugger polling
- Auto-cleanup of all remaining RidiBooks processes on exit via `terminate_process()`
- Console collector now captures warnings separately and allows toggling console passthrough with `__enableConsoleOutput`

#### 🛠️ Changed
- Changed `DebuggerMonitor.polling_interval` from 1.0s to 0.1s for more responsive debugger detection
- Improved `setup_logger()` formatting to a cleaner `[LEVEL] message` style for better readability
- Rewrote `main()` to enforce clean start of RidiBooks and gracefully handle startup errors (e.g. missing EXE, timeout)
- Injected JS now waits for 60 animation frames to ensure viewer iframe is fully loaded before proceeding
- Reorganized `inject_to_viewer()` and related injection flow for better timing and reliability

#### 🧹 Removed
- Deprecated verbose timestamped logging format in favor of concise output
- Removed hardcoded assumption that console output should always print (added toggle support)

---

### [0.1.0] - 2025-03-26

#### ✨ Added
- Logging system with support for log level and optional file output (`--log-level`, `--log-file`)
- Command-line argument parsing for better configurability
- Modular class-based design for debugger monitoring (`DebuggerMonitor`) and process lifecycle management (`RidiProcess`)
- Console output collection from Chrome DevTools via WebSocket
- Error tracking and log forwarding from the injected browser context
- Graceful process management with `terminate_process()` and fallback kill logic
- Richer error handling and structured logging throughout

#### 🛠️ Changed
- Completely rewrote `inject.py` with clear modular structure, better documentation, and typing annotations
- Restructured the project to separate concerns (e.g. monitoring, injection, utilities)
- Replaced ad-hoc logic with encapsulated async classes and helpers
- Improved WebSocket communication robustness using exception handling and `websockets.exceptions`
- Unified `main()` flow for both clean start and restart of RidiBooks process

#### 🧹 Removed
- Old ad-hoc global logic and tightly coupled `monitor_debuggers` + `inject_to_viewer` loop
- Direct process calls without output capture
- Unsafe condition checks and vague error handling

---

### [OLDVERSION] - ?

#### Added
- Initial implementation of `inject.py` for RidiBooks JavaScript injection
- Basic support for runtime evaluation via Chrome DevTools Protocol
- Auto-detection of RidiBooks install path via registry
- Debug port assignment and monitoring loop

---

## 🙏 Acknowledgments

Thanks to everyone who explores, dissects, and reimagines the tools around them—  
not to break rules, but to understand them better.

Special appreciation goes to the developers of  
[Ridibooks Viewer](https://ridibooks.com) for building a platform worth learning from,  
and to the creators of [Nuitka](https://nuitka.net) and [websockets](https://websockets.readthedocs.io/)  
for providing the core tools that made this project possible.

Also, the one that inspired me to perfect this project [a person who wishes to remain anonymous like me].

This project wouldn't exist without curiosity, respect for boundaries,  
and a little bit of “what if...?”