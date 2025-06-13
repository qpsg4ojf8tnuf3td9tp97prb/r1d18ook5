"""
RidiBooks Injector

This script interacts with the RidiBooks electron application to inject custom JavaScript
into the viewer. It uses Chrome DevTools Protocol to connect to the application and execute
JavaScript code through websockets.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request
import platform
import tempfile

import frida
import psutil
import websockets
from websockets.exceptions import WebSocketException


# Constants
match platform.system():
    case "Windows":
        import winreg

        IS_WINDOWS = True
    case "Darwin":
        import plistlib

        IS_WINDOWS = False
    case _:
        raise NotImplementedError("Unsupported platform")
RIDI: str = "Ridibooks.exe" if IS_WINDOWS else "Ridibooks"
TIMEOUT: float = 0.2  # Seconds
MAX_WAIT: int = 1000  # Maximum wait iterations

# Determine application path based on run environment (PyInstaller or direct)
APP_PATH: Path = (
    Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent
)

logger = logging.getLogger("ridi_injector")


def terminate_process(name: str) -> bool:
    """Terminate a running process by name.

    Args:
        name: The name of the process to terminate (e.g., "Ridibooks.exe").

    Returns:
        bool: True if termination was successful, False otherwise.
    """
    terminated = False
    try:
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] != name:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except psutil.TimeoutExpired:
                proc.kill()

            terminated = True
            logger.info("Successfully terminated process %s (PID: %s)", name, proc.pid)

        if not terminated:
            logger.info("No process with name %s was found", name)

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
        logger.error("Failed to terminate process %s: %s", name, e)
    return terminated


def read_file(relative_path: str | Path) -> str | bool:
    """Read a file from the application directory.

    Args:
        relative_path: Relative path to the file from APP_PATH.

    Returns:
        str: Content of the file if successful.
        bool: False if file not found or could not be read.

    Raises:
        No exceptions are raised as they are caught and logged internally.
    """
    logger.debug("[inject] Read file: '%s'", relative_path)
    try:
        with open(
            APP_PATH / relative_path,
            "r",
            encoding="utf-8",
        ) as f:
            return f.read()
    except FileNotFoundError as e:
        logger.error("[inject] Failed to find '%s': %s", relative_path, e)
        return False
    except OSError as e:
        logger.error("[inject] Failed to read '%s': %s", relative_path, e)
        return False


JSZIP_JS = read_file("scripts/jszip.js")
INJECT_JS = read_file("scripts/inject.js")
REMOTE_DEBUGGING_JS = read_file("scripts/remote-debugging.js")


def setup_logger(
    log_level: str = "INFO", log_file: str | None = None
) -> logging.Logger:
    """Set up logger with console and optional file output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional file path to save logs to.

    Returns:
        logging.Logger: Configured logger.
    """

    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set level
    level = getattr(logging, log_level.upper())
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info("Logging to file: %s", log_file)
        except (PermissionError, IOError) as e:
            logger.error("Failed to set up log file: %s", e)

    return logger


def get_free_port() -> int:
    """Find an available port to use for the debug connection.

    Returns:
        int: An available port number.

    Raises:
        socket.error: If socket operations fail.
    """
    try:
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]
    except socket.error as e:
        logger.error("Failed to get free port: %s", e)
        raise


def is_process_running(name: str) -> bool:
    """Check if a process with the given name is running.

    Args:
        name: The name of the process to check (e.g., "Ridibooks.exe").

    Returns:
        bool: True if the process is running, False otherwise.
    """
    try:
        return any(
            proc.info.get("name") == name for proc in psutil.process_iter(["name"])
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
        logger.error("Failed to check if process %s is running: %s", name, e)
        return False


def get_ridi_path() -> str | None:
    """[platform-specific-windows] Get the installation path of RidiBooks from Windows registry.

    Returns:
        str | None: Path to RidiBooks executable or None if not found.
    """
    if not IS_WINDOWS:
        return RIDI
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, "ridi\\shell\\open\\command", 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)

        match = re.match(r'^(?:"([^"]+)"|([^\s"]+))', value.strip())
        return match and (match.group(1) or match.group(2))
    except (OSError, re.error) as e:
        logger.error("Failed to get RidiBooks path from registry: %s", e)
        return None


#
# Platform-specific functions
#


def sudo_run(command: str) -> None:
    """Run a command with sudo privileges.

    Args:
        command: Command to run with sudo.

    Raises:
        CalledProcessError: If the command fails or user cancels the procedure.
    """
    command = command.replace('"', r"\"")
    if IS_WINDOWS:
        logger.error("[macOS setup] This error should not ever happen")
        raise NotImplementedError("Sudo run is not implemented for Windows")

    logger.debug("[macOS setup] Running command with sudo: %s", command)
    result = subprocess.run(
        [
            "osascript",
            "-e",
            f'do shell script "{command}" with administrator privileges',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.returncode, result.stdout.rstrip("\0").strip(), result.stderr.rstrip("\0").strip()


def mac_setup() -> None:
    logger.debug("[macOS setup] Trying to kill Ridibooks process")
    terminate_process(RIDI)
    time.sleep(1)
    logger.debug("[macOS setup] Checking if codesign is needed")
    proc = subprocess.run(
        f"codesign -d --entitlements - /Applications/{RIDI}.app --xml",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    logger.debug("[macOS setup] Codesign entitlements fetched")
    plist = plistlib.loads(proc.stdout.rstrip("\0").strip())
    if plist.get("com.apple.security.get-task-allow") is not True:
        logger.debug("[macOS setup] Important entitlements not found, adding")
        plist["com.apple.security.get-task-allow"] = True
        with tempfile.NamedTemporaryFile() as temp:
            plistlib.dump(plist, temp, fmt=plistlib.FMT_XML)
            temp.flush()
            logger.debug("[macOS setup] Signing with codesign")
            try:
                sudo_run(
                    "codesign --force --deep --options runtime "
                    f'--entitlements "{temp.name}" '
                    "--sign - "
                    f'"/Applications/{RIDI}.app";'
                    f"xattr -rd com.apple.quarantine /Applications/{RIDI}.app"
                )
            except subprocess.CalledProcessError as e:
                logger.debug("[macOS setup] Error message: %s", e.stderr)
                raise
            logger.debug("[macOS setup] Codesign completed")
            logger.debug("[macOS setup] Removing old keychain entry")
            subprocess.run(
                "security delete-generic-password -s com.ridi.books",
                shell=True,
                check=False,
            )
            logger.debug("[macOS setup] Old keychain entry removed")


#
# Debugger communication
#


def get_debuggers(debug_url: str) -> list[dict[str, Any]] | None:
    """Get list of available Chrome DevTools debuggers.

    Args:
        debug_url: URL for Chrome DevTools debugging.

    Returns:
        list[dict[str, Any]] | None: List of debugger information or None if failed.
    """
    try:
        with urllib.request.urlopen(debug_url, timeout=3.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logger.debug("Failed to get debuggers: %s", e)
        return None


async def execute_js(ws_url: str, script: str) -> Any:
    """Execute JavaScript code through WebSocket connection.

    Args:
        ws_url: WebSocket URL for the debugger.
        script: JavaScript code to execute.

    Returns:
        Any: Result of the JavaScript execution or None if failed.
    """
    try:
        async with websockets.connect(ws_url) as ws:
            command = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": script,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            }
            await ws.send(json.dumps(command))
            response = json.loads(await ws.recv())
            return response.get("result", {}).get("result", {}).get("value")
    except (WebSocketException, json.JSONDecodeError, ConnectionError) as e:
        logger.error("Failed to execute JavaScript: %s", e)
        return None


async def wait_for(
    condition_func: Callable[[], bool | Any], max_attempts: int = MAX_WAIT
) -> bool:
    """Wait for a condition to become true.

    Args:
        condition_func: Function that returns a truthy value when condition is met.
        max_attempts: Maximum number of attempts before giving up.

    Returns:
        bool: True if condition was met, False if timed out.
    """
    for _ in range(max_attempts):
        try:
            result = condition_func()
            if result:
                return True
        except Exception as e:
            # This broad exception is intentional as condition_func could fail in many ways
            # and we want to continue trying until max_attempts is reached
            logger.debug("Exception in condition function: %s", e)
        await asyncio.sleep(TIMEOUT)
    logger.warning("Condition not met after %d attempts", max_attempts)
    return False


class DebuggerMonitor:
    """Monitor for Chrome DevTools debugger output."""

    def __init__(self, debug_url: str, polling_interval: float = 0.1):
        """Initialize the debugger monitor.

        Args:
            debug_url: URL for Chrome DevTools debugging.
            polling_interval: How often to poll for debugger output in seconds.
        """
        self.debug_url = debug_url
        self.polling_interval = polling_interval
        self.active_debuggers: dict[str, str] = {}  # id -> websocket_url
        self.monitoring_task = None

    async def start_monitoring(self):
        """Start the monitoring task."""
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("[debugger] Started debugger monitoring")

    async def stop_monitoring(self):
        """Stop the monitoring task."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("[debugger] Stopped debugger monitoring")

    async def _monitor_loop(self):
        """Main monitoring loop that periodically checks debugger output."""
        while is_process_running(RIDI):
            try:
                # Get current debuggers
                debuggers = get_debuggers(self.debug_url)
                if debuggers:
                    # Update active debuggers list
                    current_ids = {d["id"] for d in debuggers}
                    new_debuggers = [
                        d for d in debuggers if d["id"] not in self.active_debuggers
                    ]

                    # Add new debuggers to monitoring
                    for debugger in new_debuggers:
                        debugger_id = debugger["id"]
                        ws_url = debugger["webSocketDebuggerUrl"]
                        self.active_debuggers[debugger_id] = ws_url
                        logger.info(
                            "[debugger-%s] Started monitoring debugger", debugger_id
                        )

                    # Remove debuggers that are no longer active
                    closed_debuggers = [
                        debugger_id
                        for debugger_id in list(self.active_debuggers.keys())
                        if debugger_id not in current_ids
                    ]
                    for debugger_id in closed_debuggers:
                        logger.info("[debugger-%s] Debugger closed", debugger_id)
                        del self.active_debuggers[debugger_id]

                    # Poll each active debugger for output
                    for debugger_id, ws_url in self.active_debuggers.items():
                        await self._poll_debugger_output(debugger_id, ws_url)

            except Exception as e:
                logger.error("[debugger] Error in debugger monitor: %s", e)

            await asyncio.sleep(self.polling_interval)

        logger.info("[debugger] RidiBooks process exited, stopping monitor")

    async def _poll_debugger_output(self, debugger_id: str, ws_url: str):
        """Poll a specific debugger for console output.

        Args:
            debugger_id: ID of the debugger.
            ws_url: WebSocket URL for the debugger.
        """
        try:
            # Get console messages by injecting a collector script
            await self._setup_console_collector(ws_url)

            # Get collected console messages
            console_messages = await execute_js(
                ws_url,
                """
                (function() {
                    const messages = window.__ridiInjector_consoleMessages || [];
                    window.__ridiInjector_consoleMessages = [];
                    return messages;
                })()
                """,
            )

            if (
                console_messages
                and isinstance(console_messages, list)
                and len(console_messages) > 0
            ):
                for msg in console_messages:
                    logger.debug("[debugger-%s] %s", debugger_id, msg)

            # Check for errors
            errors = await execute_js(
                ws_url,
                """
                (function() {
                    const errors = window.__ridiInjector_consoleErrors || [];
                    window.__ridiInjector_consoleErrors = [];
                    return errors;
                })()
                """,
            )

            if errors and isinstance(errors, list) and len(errors) > 0:
                for error in errors:
                    logger.error("[debugger-%s] %s", debugger_id, error)

            # Check for warnings
            warnings = await execute_js(
                ws_url,
                """
                (function() {
                    const warnings = window.__ridiInjector_consoleWarnings || [];
                    window.__ridiInjector_consoleWarnings = [];
                    return warnings;
                })()
                """,
            )

            if warnings and isinstance(warnings, list) and len(warnings) > 0:
                for warning in warnings:
                    logger.warning("[debugger-%s] %s", debugger_id, warning)

        except (WebSocketException, json.JSONDecodeError, ConnectionError) as e:
            logger.error("[debugger-%s] Failed to poll debugger: %s", debugger_id, e)

    async def _setup_console_collector(self, ws_url: str):
        """Set up console output collector in the browser.

        Args:
            ws_url: WebSocket URL for the debugger.
        """
        script = """
        (function() {
            if (window.__ridiInjector_consoleCollectorSetup) return "already-setup";
            
            window.__enableConsoleOutput = false;
            window.__ridiInjector_consoleMessages = [];
            window.__ridiInjector_consoleErrors = [];
            window.__ridiInjector_consoleWarnings = [];
            
            const originalConsoleLog = console.log;
            const originalConsoleError = console.error;
            const originalConsoleWarn = console.warn;
            
            console.log = function() {
                window.__ridiInjector_consoleMessages.push(
                    Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                if (window.__enableConsoleOutput) {
                    return originalConsoleLog.apply(this, arguments);
                }
            };
            
            console.error = function() {
                window.__ridiInjector_consoleErrors.push(
                    Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                if (window.__enableConsoleOutput) {
                    return originalConsoleError.apply(this, arguments);
                }
            };
            
            console.warn = function() {
                window.__ridiInjector_consoleWarnings.push(
                    "WARN: " + Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                if (window.__enableConsoleOutput) {
                    return originalConsoleWarn.apply(this, arguments);
                }
            };
            
            window.addEventListener("error", function(event) {
                window.__ridiInjector_consoleErrors.push(
                    "UNCAUGHT: " + event.message + " at " + event.filename + ":" + event.lineno
                );
            });
            
            window.__ridiInjector_consoleCollectorSetup = true;
            return "setup-complete";
        })();
        """

        result = await execute_js(ws_url, script)
        if result == "setup-complete":
            logger.debug("[debugger] Set up console collector for WebSocket %s", ws_url)


async def inject_to_viewer(ws_url: str) -> Any:
    """Inject JavaScript code into the RidiBooks viewer.

    Args:
        ws_url: WebSocket URL for the debugger.

    Returns:
        Any: Result of the injection or False if failed.
    """
    # Check if we're in the viewer page
    if not await execute_js(ws_url, "location.href.endsWith('Viewer');"):
        return False

    # Wait for iframe to be loaded
    if not await wait_for(
        lambda: execute_js(ws_url, "!!document.querySelector('iframe');")
    ):
        logger.warning("[inject] Timeout waiting for iframe")
        return False

    # Wait for animation frames - this exact timing is important
    await execute_js(
        ws_url,
        "(async()=>{for(let i=0;i<60;i++)await new Promise(requestAnimationFrame);})();",
    )

    # Inject JSZip library
    if not JSZIP_JS:
        return False
    await execute_js(ws_url, JSZIP_JS)

    # Inject main injection script
    if not INJECT_JS:
        return False
    await execute_js(ws_url, INJECT_JS)


async def monitor_debuggers(debug_url: str) -> None:
    """Monitor and inject into new debugger connections.

    Args:
        debug_url: URL for Chrome DevTools debugging.

    This function runs in a loop, checking for new debugger connections
    and injecting JavaScript code when appropriate.
    """
    known_ids = set()

    # Start debugger monitor for console output
    monitor = DebuggerMonitor(debug_url)
    await monitor.start_monitoring()

    try:
        while is_process_running(RIDI):
            debuggers = get_debuggers(debug_url)
            if not debuggers:
                await asyncio.sleep(TIMEOUT)
                continue

            current_ids = {d["id"] for d in debuggers}
            new_debuggers = [d for d in debuggers if d["id"] not in known_ids]

            for debugger in new_debuggers:
                ws_url = debugger["webSocketDebuggerUrl"]
                logger.info("[debugger-%s] New debugger found", debugger["id"])

                # Check if we can connect to the debugger
                if await execute_js(ws_url, "1"):
                    # Wait for a frame to ensure page is ready
                    await execute_js(
                        ws_url,
                        "(async()=>{await new Promise(requestAnimationFrame);})();",
                    )

                    # Try to inject to viewer
                    result = await inject_to_viewer(ws_url)
                    if result:
                        logger.info(
                            "[debugger-%s] Successfully injected", debugger["id"]
                        )
                    else:
                        logger.debug(
                            "[debugger-%s] Not a viewer or injection failed",
                            debugger["id"],
                        )
                else:
                    logger.warning(
                        "[debugger-%s] Could not connect to debugger", debugger["id"]
                    )

            known_ids = current_ids
            await asyncio.sleep(TIMEOUT)

        logger.info("[debugger] RidiBooks process exited, stopping monitor")
    finally:
        await monitor.stop_monitoring()


class RidiProcess:
    """Context manager for handling RidiBooks process lifecycle."""

    def __init__(self, path: str, debug_port: int):
        """Initialize RidiBooks process handler.

        Args:
            path: Path to the RidiBooks executable.
            debug_port: Port to use for Chrome DevTools debugging.
        """
        self.command = (
            f'"{path}"' if IS_WINDOWS else f"open -a {RIDI} --args"
        ) + f" --remote-debugging-port={debug_port}"
        self.process = None

    async def __aenter__(self) -> subprocess.Popen:
        """Start the RidiBooks process.

        Returns:
            subprocess.Popen: The process object.
        """
        logger.info("[RidiBooks] Starting RidiBooks with command: %s", self.command)
        self.process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        await asyncio.sleep(0.5)

        if IS_WINDOWS:
            pid = self.process.pid
        else:
            pids = [
                proc.info["pid"]
                for proc in psutil.process_iter(["pid", "name"])
                if proc.info.get("name") == RIDI
            ]
            if len(pids) != 1:
                logger.error("[RidiBooks] Failed to find Ridibooks process")
                raise RuntimeError("Failed to find Ridibooks process")
            pid = pids[0]

        if not REMOTE_DEBUGGING_JS:
            logger.error("[RidiBooks] Failed to read remote debugging script")
            raise RuntimeError("Failed to read remote debugging script")
        logger.debug("[RidiBooks] Injecting into RidiBooks process pid: %s", pid)
        try:
            frida.attach(pid).create_script(REMOTE_DEBUGGING_JS).load()
        except frida.ProcessNotFoundError as e:
            logger.error("RidiBooks process not found for injection")
            raise RuntimeError("RidiBooks process not found for injection") from e
        logger.debug("[RidiBooks] Injected into RidiBooks process pid: %s", pid)

        # Start tasks to capture process output
        asyncio.create_task(
            self._log_process_output(self.process.stdout, logging.DEBUG)
        )
        asyncio.create_task(
            self._log_process_output(self.process.stderr, logging.ERROR)
        )

        return self.process

    async def _log_process_output(self, pipe, log_level):
        """Log process output.

        Args:
            pipe: Process pipe to read from.
            log_level: Logging level to use.
        """
        while True:
            line = await asyncio.to_thread(pipe.readline)
            if not line:
                break
            logger.log(log_level, "[RidiBooks] %s", line.strip())

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Terminate the RidiBooks process when exiting context.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        if self.process:
            try:
                logger.info("[RidiBooks] Terminating RidiBooks process")
                self.process.terminate()
                self.process.wait(timeout=1)
                logger.info("[RidiBooks] RidiBooks process terminated")
            except subprocess.TimeoutExpired:
                logger.warning(
                    "[RidiBooks] Failed to terminate RidiBooks process, try kill"
                )
                try:
                    self.process.kill()
                    self.process.wait()
                    logger.info("[RidiBooks] RidiBooks process killed")
                except subprocess.SubprocessError as e:
                    logger.error("[RidiBooks] Failed to kill RidiBooks process: %s", e)

        # Ensure all Ridibooks processes are terminated using platform-specific function
        if is_process_running(RIDI):
            logger.info("[RidiBooks] Killing all remaining RidiBooks processes")
            terminate_process(RIDI)


async def main() -> None:
    """Main function - start or connect to RidiBooks and inject custom code."""
    # Initialize debug port and URL
    debug_port = get_free_port()
    logger.info("Debug port: %d", debug_port)
    debug_url = f"http://127.0.0.1:{debug_port}/json"

    try:
        # Always kill any existing RidiBooks process first
        if is_process_running(RIDI):
            logger.info("RidiBooks is already running, terminating it")
            terminate_process(RIDI)
            # Wait for the process to terminate
            if not await wait_for(lambda: not is_process_running(RIDI)):
                raise TimeoutError("Failed to terminate existing RidiBooks.exe")

        # Now start a fresh instance
        ridi_path = get_ridi_path()
        if not ridi_path:
            raise FileNotFoundError(
                "Cannot find RidiBooks.exe, registry value may be broken"
            )

        logger.info("Found RidiBooks at: %s", ridi_path)

        async with RidiProcess(ridi_path, debug_port):
            if not await wait_for(lambda: is_process_running(RIDI)):
                raise TimeoutError("Start RidiBooks.exe timeout")

            logger.info("RidiBooks started successfully")
            await monitor_debuggers(debug_url)

    except FileNotFoundError as e:
        logger.error("File not found: %s", e, exc_info=True)
        sys.exit(1)
    except TimeoutError as e:
        logger.error("Timeout error: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        # Keep a general exception handler here as this is the main function
        # and we want to prevent unhandled exceptions from crashing the program
        logger.error("Error in main function: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="RidiBooks Injector")
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level",
    )
    parser.add_argument(
        "--log-file",
        default="inject.log",
        help="Save logs to file",
    )
    parser.add_argument(
        "--no-log",
        help="Disable logging to file",
    )
    args = parser.parse_args()

    # Configure logger
    setup_logger(args.log_level, None if args.no_log else args.log_file)

    if not IS_WINDOWS:
        try:
            logger.info("[macOS setup] Starting macOS setup")
            mac_setup()
            logger.info("[macOS setup] macOS setup completed successfully")
        except Exception as e:
            logger.critical(
                "[macOS setup] Critical error during macOS setup: %s", e, exc_info=True
            )
            raise

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.critical("Unhandled exception: %s", e, exc_info=True)
        sys.exit(1)
