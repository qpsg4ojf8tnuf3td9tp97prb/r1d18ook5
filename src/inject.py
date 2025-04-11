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
from typing import Any, Callable
import urllib.error
import urllib.request
import winreg
import websockets
from websockets.exceptions import WebSocketException


# Constants
RIDI_EXE: str = "Ridibooks.exe"
TIMEOUT: float = 0.01  # Seconds
MAX_WAIT: int = 200  # Maximum wait iterations

# Determine application path based on run environment (PyInstaller or direct)
APP_PATH: Path = (
    Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent
)

logger = logging.getLogger("ridi_injector")


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
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info("Logging to file: %s", log_file)
        except (PermissionError, IOError) as e:
            logger.error("Failed to set up log file: %s", e)

    return logger


#
# Platform-specific functions
#


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


def get_ridi_path() -> str | None:
    """[platform-specific-windows] Get the installation path of RidiBooks from Windows registry.

    Returns:
        str | None: Path to RidiBooks executable or None if not found.
    """
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


def is_process_running(name: str) -> bool:
    """[platform-specific-windows] Check if a process with the given name is running.

    Args:
        name: The name of the process to check (e.g., "Ridibooks.exe").

    Returns:
        bool: True if the process is running, False otherwise.
    """
    cmd = f'tasklist /NH /FI "IMAGENAME eq {name}"'
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, shell=True, check=False
        ).stdout
        return name in result
    except subprocess.SubprocessError as e:
        logger.error("Failed to check if process %s is running: %s", name, e)
        return False


def terminate_process(name: str) -> bool:
    """[platform-specific-windows] Terminate a running process by name.

    Args:
        name: The name of the process to terminate (e.g., "Ridibooks.exe").

    Returns:
        bool: True if termination was successful, False otherwise.
    """
    cmd = f"taskkill /F /T /IM {name}"
    try:
        subprocess.run(cmd, shell=True, check=True)
        logger.info("Successfully terminated process %s", name)
        return True
    except subprocess.SubprocessError as e:
        logger.error("Failed to terminate process %s: %s", name, e)
        return False


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
        with urllib.request.urlopen(debug_url) as response:
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

    def __init__(self, debug_url: str, polling_interval: float = 1.0):
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
        logger.info("Started debugger monitoring")

    async def stop_monitoring(self):
        """Stop the monitoring task."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped debugger monitoring")

    async def _monitor_loop(self):
        """Main monitoring loop that periodically checks debugger output."""
        while is_process_running(RIDI_EXE):
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
                        logger.info("Started monitoring debugger: %s", debugger_id)

                    # Remove debuggers that are no longer active
                    closed_debuggers = [
                        debugger_id
                        for debugger_id in list(self.active_debuggers.keys())
                        if debugger_id not in current_ids
                    ]
                    for debugger_id in closed_debuggers:
                        logger.info("Debugger closed: %s", debugger_id)
                        del self.active_debuggers[debugger_id]

                    # Poll each active debugger for output
                    for debugger_id, ws_url in self.active_debuggers.items():
                        await self._poll_debugger_output(debugger_id, ws_url)

            except Exception as e:
                logger.error("Error in debugger monitor: %s", e)

            await asyncio.sleep(self.polling_interval)

        logger.info("RidiBooks process exited, stopping monitor")

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
                    logger.debug("Debugger %s console: %s", debugger_id, msg)

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
                    logger.error("Debugger %s error: %s", debugger_id, error)

        except (WebSocketException, json.JSONDecodeError, ConnectionError) as e:
            logger.error("Failed to poll debugger %s: %s", debugger_id, e)

    async def _setup_console_collector(self, ws_url: str):
        """Set up console output collector in the browser.

        Args:
            ws_url: WebSocket URL for the debugger.
        """
        script = """
        (function() {
            if (window.__ridiInjector_consoleCollectorSetup) return "already-setup";
            
            window.__ridiInjector_consoleMessages = [];
            window.__ridiInjector_consoleErrors = [];
            
            const originalConsoleLog = console.log;
            const originalConsoleError = console.error;
            const originalConsoleWarn = console.warn;
            
            console.log = function() {
                window.__ridiInjector_consoleMessages.push(
                    Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                return originalConsoleLog.apply(this, arguments);
            };
            
            console.error = function() {
                window.__ridiInjector_consoleErrors.push(
                    Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                return originalConsoleError.apply(this, arguments);
            };
            
            console.warn = function() {
                window.__ridiInjector_consoleErrors.push(
                    "WARN: " + Array.from(arguments).map(arg => String(arg)).join(" ")
                );
                return originalConsoleWarn.apply(this, arguments);
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
            logger.debug("Set up console collector for WebSocket %s", ws_url)


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
        logger.warning("Timeout waiting for iframe")
        return False

    # Wait for animation frames - this exact timing is important
    await execute_js(
        ws_url,
        "(async()=>{for(let i=0;i<60;i++)await new Promise(requestAnimationFrame);})();",
    )

    # Inject JSZip library
    try:
        with open(
            APP_PATH / "inject" / "jszip.js",
            "r",
            encoding="utf-8",
        ) as f:
            await execute_js(ws_url, f.read())
    except FileNotFoundError as e:
        logger.error("Failed to find jszip.js: %s", e)
        return False
    except (PermissionError, IOError) as e:
        logger.error("Failed to read jszip.js: %s", e)
        return False

    # Inject main injection script
    try:
        with open(
            APP_PATH / "inject" / "inject.js",
            "r",
            encoding="utf-8",
        ) as f:
            return await execute_js(ws_url, f.read())
    except FileNotFoundError as e:
        logger.error("Failed to find inject.js: %s", e)
        return False
    except (PermissionError, IOError) as e:
        logger.error("Failed to read inject.js: %s", e)
        return False


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
        while is_process_running(RIDI_EXE):
            debuggers = get_debuggers(debug_url)
            if not debuggers:
                await asyncio.sleep(TIMEOUT)
                continue

            current_ids = {d["id"] for d in debuggers}
            new_debuggers = [d for d in debuggers if d["id"] not in known_ids]

            for debugger in new_debuggers:
                ws_url = debugger["webSocketDebuggerUrl"]
                logger.info("New debugger found: %s", debugger["id"])

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
                        logger.info("Successfully injected into %s", debugger["id"])
                    else:
                        logger.debug(
                            "Not a viewer or injection failed for %s", debugger["id"]
                        )
                else:
                    logger.warning("Could not connect to debugger %s", debugger["id"])

            known_ids = current_ids
            await asyncio.sleep(TIMEOUT)

        logger.info("RidiBooks process exited, stopping monitor")
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
        self.command = f'"{path}" --remote-debugging-port={debug_port}'
        self.process = None

    async def __aenter__(self) -> subprocess.Popen:
        """Start the RidiBooks process.

        Returns:
            subprocess.Popen: The process object.
        """
        logger.info("Starting RidiBooks with command: %s", self.command)
        self.process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Start tasks to capture process output
        asyncio.create_task(self._log_process_output(self.process.stdout, logging.INFO))
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
            logger.log(log_level, "RidiBooks: %s", line.strip())

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Terminate the RidiBooks process when exiting context.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        if self.process:
            try:
                logger.info("Terminating RidiBooks process")
                self.process.terminate()
                self.process.wait(timeout=1)
                logger.info("RidiBooks process terminated")
            except subprocess.TimeoutExpired:
                logger.warning("Failed to terminate RidiBooks process gently")
                try:
                    self.process.kill()
                    self.process.wait()
                    logger.info("RidiBooks process killed")
                except subprocess.SubprocessError as e:
                    logger.error("Failed to kill RidiBooks process: %s", e)

        # Ensure all Ridibooks processes are terminated using platform-specific function
        if is_process_running(RIDI_EXE):
            logger.info("Killing all remaining RidiBooks processes")
            terminate_process(RIDI_EXE)


async def main() -> None:
    """Main function - start or connect to RidiBooks and inject custom code."""
    # Initialize debug port and URL
    debug_port = get_free_port()
    logger.info("Debug port: %d", debug_port)
    debug_url = f"http://127.0.0.1:{debug_port}/json"

    try:
        # Always kill any existing RidiBooks process first
        if is_process_running(RIDI_EXE):
            logger.info("RidiBooks is already running, terminating it")
            terminate_process(RIDI_EXE)
            # Wait for the process to terminate
            if not await wait_for(lambda: not is_process_running(RIDI_EXE)):
                raise TimeoutError("Failed to terminate existing RidiBooks.exe")

        # Now start a fresh instance
        ridi_path = get_ridi_path()
        if not ridi_path:
            raise FileNotFoundError(
                "Cannot find RidiBooks.exe, registry value may be broken"
            )

        logger.info("Found RidiBooks at: %s", ridi_path)

        async with RidiProcess(ridi_path, debug_port):
            if not await wait_for(lambda: is_process_running(RIDI_EXE)):
                raise TimeoutError("Start RidiBooks.exe timeout")

            logger.info("RidiBooks started successfully")
            await monitor_debuggers(debug_url)

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        sys.exit(1)
    except TimeoutError as e:
        logger.error("Timeout error: %s", e)
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
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level",
    )
    parser.add_argument(
        "--log-file",
        help="Save logs to file",
    )
    args = parser.parse_args()

    # Configure logger
    setup_logger(args.log_level, args.log_file)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.critical("Unhandled exception: %s", e, exc_info=True)
        sys.exit(1)
