#!/usr/bin/env python3
"""
Integration tests for CopperHead bot protocol compliance.

Validates that a bot correctly follows the CopperHead WebSocket protocol
by running it against a local CopperHead server instance.

The test suite launches a CopperHead server as a subprocess, then runs
the bot-under-test (also as a subprocess) and verifies correct behavior
by observing server state via the HTTP API.

Usage:
    python tests/test_bot_protocol.py                       # Test mybot.py (default)
    python tests/test_bot_protocol.py --bot path/to/bot.py  # Test any bot

Requirements:
    - copperhead-server must be in ../copperhead-server (sibling directory)
    - Bot dependencies installed:  pip install -r requirements.txt
"""

import sys
import os
import subprocess
import time
import json
import unittest
import warnings
from urllib.request import urlopen, Request
from urllib.error import URLError

# ============================================================================
#  Path Configuration
# ============================================================================

# Resolve paths relative to this test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.dirname(TEST_DIR)                          # copperhead-bot/
SERVER_DIR = os.path.join(os.path.dirname(BOT_DIR), "copperhead-server")
SETTINGS_FILE = os.path.join(BOT_DIR, "server-settings.test.json")

# Default bot file to test (can be overridden with --bot CLI argument)
BOT_FILE = os.path.join(BOT_DIR, "mybot.py")

# Server config — use a non-standard port to avoid conflicts
SERVER_PORT = 18765
SERVER_URL = f"http://localhost:{SERVER_PORT}"
WS_URL = f"ws://localhost:{SERVER_PORT}/ws/"

# Timeouts (in seconds)
SERVER_START_TIMEOUT = 30
TOURNAMENT_TIMEOUT = 120
POLL_INTERVAL = 1


# ============================================================================
#  Helper Functions
# ============================================================================

def log(msg: str):
    """Print a timestamped log message."""
    print(f"  [test] {msg}")


def get_json(path: str) -> dict | None:
    """GET a JSON endpoint from the test server. Returns parsed dict or None."""
    try:
        with urlopen(f"{SERVER_URL}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def wait_for_server(timeout: int = SERVER_START_TIMEOUT):
    """Block until the server responds to /status, or raise on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_json("/status"):
            return
        time.sleep(1)
    raise RuntimeError(f"Server did not become ready within {timeout}s")


def wait_for_competition_state(target_state: str, timeout: int = TOURNAMENT_TIMEOUT) -> dict:
    """Wait for the competition to reach a specific state. Returns the competition data."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        comp = get_json("/competition")
        if comp and comp.get("state") == target_state:
            return comp
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Competition did not reach state '{target_state}' within {timeout}s"
    )


def wait_for_lobby_players(count: int, timeout: int = 30) -> dict:
    """Wait until the lobby has at least `count` players."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        lobby = get_json("/lobby")
        if lobby and len(lobby.get("players", [])) >= count:
            return lobby
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Expected {count} lobby players within {timeout}s")


def wait_for_competition_players(count: int, timeout: int = 30) -> dict:
    """Wait until the competition has at least `count` players registered."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        comp = get_json("/competition")
        if comp and comp.get("players", 0) >= count:
            return comp
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Expected {count} competition players within {timeout}s")


def start_server(port: int = SERVER_PORT) -> subprocess.Popen:
    """Start the CopperHead server as a subprocess and wait until it's ready."""
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", SETTINGS_FILE, "--port", str(port)],
        cwd=SERVER_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def stop_process(proc: subprocess.Popen, timeout: int = 10):
    """Kill a subprocess and wait for it to exit."""
    if proc and proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass


# ============================================================================
#  Test Class
# ============================================================================

class TestBotProtocol(unittest.TestCase):
    """Integration tests for CopperHead bot protocol compliance.

    Tests that a bot correctly follows the server's WebSocket protocol
    by running it against a real CopperHead server instance. Each test
    launches bot subprocesses, observes server state via the HTTP API,
    and verifies the bot behaves correctly.

    The server is started once for the entire test class. Between tests,
    bot processes are killed and the competition is allowed to reset.
    """

    server_proc = None

    @classmethod
    def setUpClass(cls):
        """Start the CopperHead server and install dependencies."""
        # Verify required directories and files exist
        if not os.path.isdir(SERVER_DIR):
            raise RuntimeError(
                f"CopperHead server not found at {SERVER_DIR}.\n"
                "The server repo must be a sibling directory of copperhead-bot."
            )
        if not os.path.isfile(BOT_FILE):
            raise RuntimeError(f"Bot file not found: {BOT_FILE}")
        if not os.path.isfile(SETTINGS_FILE):
            raise RuntimeError(f"Test settings not found: {SETTINGS_FILE}")

        # Install server dependencies
        log("Installing server dependencies...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r",
             os.path.join(SERVER_DIR, "requirements.txt")],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install server deps: {result.stderr}")

        # Start the server
        log(f"Starting server on port {SERVER_PORT}...")
        cls.server_proc = start_server(SERVER_PORT)
        try:
            wait_for_server()
        except RuntimeError:
            stop_process(cls.server_proc)
            raise
        log(f"Server ready (PID {cls.server_proc.pid}).")

    @classmethod
    def tearDownClass(cls):
        """Stop the server after all tests complete."""
        stop_process(cls.server_proc)
        log("Server stopped.")

    def setUp(self):
        """Prepare for each test: track bot processes and ensure clean state."""
        self.bot_procs = []
        self._wait_for_clean_state()

    def tearDown(self):
        """Kill all bot processes and wait for competition to reset."""
        for proc in self.bot_procs:
            # Close stdout/stderr pipes to avoid ResourceWarning noise
            for pipe in (proc.stdout, proc.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
            stop_process(proc, timeout=5)
        # Wait for the competition to reset (reset_delay is 3s in test config)
        time.sleep(5)

    def _wait_for_clean_state(self, timeout: int = 30):
        """Wait until the server is back to waiting_for_players with no players."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            comp = get_json("/competition")
            status = get_json("/status")
            lobby = get_json("/lobby")
            if (comp and comp.get("state") == "waiting_for_players"
                    and status and status.get("total_players", 99) == 0
                    and lobby and len(lobby.get("players", [999])) == 0):
                return
            time.sleep(1)
        log("Warning: could not reach clean state, proceeding anyway")

    def _start_bot(self, name: str = None, extra_args: list = None) -> subprocess.Popen:
        """Start a bot subprocess and track it for cleanup.

        Args:
            name: Bot display name (passed as --name)
            extra_args: Additional CLI arguments to pass to the bot
        """
        cmd = [sys.executable, "-u", BOT_FILE, "--server", WS_URL]
        if name:
            cmd += ["--name", name]
        if extra_args:
            cmd += extra_args
        proc = subprocess.Popen(
            cmd, cwd=BOT_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.bot_procs.append(proc)
        return proc

    # ====================================================================
    #  Test: Bot connects and joins the lobby
    # ====================================================================

    def test_01_bot_joins_lobby(self):
        """Bot connects to the server and appears in the lobby."""
        self._start_bot(name="LobbyTestBot")

        # The bot should appear in the lobby's player list
        lobby = wait_for_lobby_players(1, timeout=15)
        player_names = [p.get("name") for p in lobby.get("players", [])]
        self.assertIn(
            "LobbyTestBot", player_names,
            "Bot should appear in lobby player list after joining"
        )

    # ====================================================================
    #  Test: Bot accepts --difficulty flag without error
    # ====================================================================

    def test_02_bot_accepts_difficulty_flag(self):
        """Bot accepts the --difficulty CLI flag without crashing.

        All bots must accept --server, --name, and --difficulty arguments
        (per the CopperHead bot specification), even if they don't use them.
        """
        bot = self._start_bot(name="DifficultyBot", extra_args=["--difficulty", "7"])

        # Bot should connect and join the lobby without crashing
        lobby = wait_for_lobby_players(1, timeout=15)
        player_names = [p.get("name") for p in lobby.get("players", [])]
        self.assertIn("DifficultyBot", player_names,
                      "Bot should join lobby when --difficulty is passed")

        # Verify the bot process hasn't crashed
        self.assertIsNone(bot.poll(), "Bot should still be running (not crashed)")

    # ====================================================================
    #  Test: Bot's custom name appears in tournament results
    # ====================================================================

    def test_03_bot_name_in_tournament_results(self):
        """Bot's custom name appears as the champion in tournament results."""
        name_a = "NameTest_Alpha"
        name_b = "NameTest_Beta"
        self._start_bot(name=name_a)
        self._start_bot(name=name_b)

        # Wait for tournament to complete (bots join lobby and auto-start)
        comp = wait_for_competition_state("complete", timeout=TOURNAMENT_TIMEOUT)

        # The champion should be one of our named bots
        champion = comp.get("champion")
        self.assertIn(
            champion, [name_a, name_b],
            f"Champion '{champion}' should be one of our named bots"
        )

    # ====================================================================
    #  Test: Full tournament lifecycle
    # ====================================================================

    def test_04_full_tournament_lifecycle(self):
        """Two bots complete a full tournament, validating the entire protocol.

        This is the core integration test. It verifies that the bot:
        1. Connects and joins the lobby (sends 'join' action)
        2. Sends 'ready' when assigned to a match
        3. Sends valid 'move' actions during gameplay
        4. Sends 'ready' again after each game-over
        5. Handles match_complete correctly (winner waits, loser exits)
        6. Handles competition_complete correctly (winner exits)

        If ANY of these protocol steps fails, the tournament cannot
        complete and this test will time out.
        """
        bot1 = self._start_bot(name="Lifecycle_A")
        bot2 = self._start_bot(name="Lifecycle_B")

        # Both bots join the lobby → auto-start → competition runs
        wait_for_competition_state("in_progress", timeout=30)

        comp = wait_for_competition_state("complete", timeout=TOURNAMENT_TIMEOUT)
        self.assertIsNotNone(comp.get("champion"),
                             "Tournament should declare a champion")

        # Both bots should exit cleanly after the tournament
        for i, bot in enumerate([bot1, bot2], 1):
            try:
                bot.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
            self.assertIsNotNone(
                bot.poll(),
                f"Bot {i} should exit after tournament ends"
            )

    # ====================================================================
    #  Test: Bot exits cleanly (no error output)
    # ====================================================================

    def test_05_bot_exits_without_errors(self):
        """Bot processes exit with no unexpected errors on stderr."""
        bot1 = self._start_bot(name="ErrorCheck_A")
        bot2 = self._start_bot(name="ErrorCheck_B")

        # Run tournament to completion
        wait_for_competition_state("in_progress", timeout=30)
        wait_for_competition_state("complete", timeout=TOURNAMENT_TIMEOUT)

        # Wait for bots to exit and capture stderr
        for i, bot in enumerate([bot1, bot2], 1):
            try:
                bot.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass

            _, stderr = bot.communicate(timeout=5)
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            # Stderr should be empty (no Python tracebacks or unhandled errors)
            # Filter out known benign messages (e.g., deprecation warnings)
            error_lines = [
                line for line in stderr_text.splitlines()
                if line.strip()
                and "DeprecationWarning" not in line
                and "RuntimeWarning" not in line
            ]
            self.assertEqual(
                len(error_lines), 0,
                f"Bot {i} had unexpected stderr output:\n{stderr_text}"
            )

    # ====================================================================
    #  Test: Bot handles server shutdown gracefully
    # ====================================================================

    def test_06_bot_handles_server_shutdown(self):
        """Bot exits gracefully when the server shuts down unexpectedly.

        Uses a separate temporary server instance (on a different port)
        so the main test server is unaffected.
        """
        temp_port = SERVER_PORT + 1
        temp_ws = f"ws://localhost:{temp_port}/ws/"
        temp_http = f"http://localhost:{temp_port}"

        # Start a temporary server on a different port
        temp_proc = start_server(temp_port)
        try:
            # Wait for temp server to be ready
            deadline = time.time() + SERVER_START_TIMEOUT
            while time.time() < deadline:
                try:
                    with urlopen(f"{temp_http}/status", timeout=2):
                        break
                except Exception:
                    time.sleep(1)
            else:
                self.fail("Temporary server did not start")

            # Start a bot connected to the temp server
            cmd = [sys.executable, "-u", BOT_FILE,
                   "--server", temp_ws, "--name", "ShutdownTestBot"]
            bot = subprocess.Popen(
                cmd, cwd=BOT_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.bot_procs.append(bot)

            # Give the bot time to connect
            time.sleep(3)
            self.assertIsNone(bot.poll(), "Bot should be running after connecting")

            # Kill the server — bot should detect the disconnection and exit
            temp_proc.kill()
            temp_proc.wait(timeout=5)

            # Bot should exit within a reasonable time
            try:
                bot.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass

            self.assertIsNotNone(
                bot.poll(),
                "Bot should exit when the server shuts down"
            )

        finally:
            stop_process(temp_proc)


# ============================================================================
#  Custom Test Runner — prints a beginner-friendly summary at the end
# ============================================================================

# Short descriptions shown in the summary table (keyed by test method name)
TEST_DESCRIPTIONS = {
    "test_01_bot_joins_lobby":
        "Bot connects to server and joins the lobby",
    "test_02_bot_accepts_difficulty_flag":
        "Bot accepts the --difficulty CLI flag",
    "test_03_bot_name_in_tournament_results":
        "Bot's custom name appears in tournament results",
    "test_04_full_tournament_lifecycle":
        "Full tournament lifecycle (join \u2192 ready \u2192 moves \u2192 gameover \u2192 match \u2192 exit)",
    "test_05_bot_exits_without_errors":
        "Bot exits cleanly with no errors on stderr",
    "test_06_bot_handles_server_shutdown":
        "Bot exits gracefully when server shuts down",
}


class SummaryResult(unittest.TextTestResult):
    """Collects test outcomes for a summary table printed at the end."""

    def __init__(self, stream, descriptions, verbosity):
        # Always run with minimal verbosity — we print our own summary
        super().__init__(stream, descriptions, verbosity=1)
        self.outcomes = []   # list of (test_name, status, detail)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append((test._testMethodName, "PASS", ""))

    def addError(self, test, err):
        super().addError(test, err)
        # Extract just the last line of the traceback (the exception message)
        detail = self._exc_info_to_string(err, test).strip().splitlines()[-1]
        self.outcomes.append((test._testMethodName, "FAIL", detail))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        detail = self._exc_info_to_string(err, test).strip().splitlines()[-1]
        self.outcomes.append((test._testMethodName, "FAIL", detail))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes.append((test._testMethodName, "SKIP", reason))


class SummaryRunner(unittest.TextTestRunner):
    """Test runner that prints a clean summary table after all tests."""

    resultclass = SummaryResult

    def __init__(self, **kwargs):
        # Send unittest's built-in output to devnull — we print our own summary
        kwargs["verbosity"] = 0
        kwargs["stream"] = open(os.devnull, "w")
        super().__init__(**kwargs)

    def run(self, test):
        result = super().run(test)
        self._print_summary(result)
        return result

    def _print_summary(self, result):
        print()
        print("=" * 70)
        print("  TEST RESULTS SUMMARY")
        print("=" * 70)
        print()

        passed = 0
        failed = 0
        skipped = 0

        for test_name, status, detail in result.outcomes:
            description = TEST_DESCRIPTIONS.get(test_name, test_name)
            if status == "PASS":
                icon = "PASS"
                passed += 1
            elif status == "SKIP":
                icon = "SKIP"
                skipped += 1
            else:
                icon = "FAIL"
                failed += 1

            print(f"  [{icon}]  {description}")
            if detail:
                print(f"          Reason: {detail}")

        print()
        print("-" * 70)
        total = passed + failed + skipped
        parts = [f"{passed} passed"]
        if failed:
            parts.append(f"{failed} FAILED")
        if skipped:
            parts.append(f"{skipped} skipped")
        print(f"  {total} tests: {', '.join(parts)}")

        if failed == 0:
            print("  Bot protocol compliance: ALL CHECKS PASSED")
        else:
            print("  Bot protocol compliance: SOME CHECKS FAILED")
        print("-" * 70)
        print()


# ============================================================================
#  CLI Argument Handling
# ============================================================================

def parse_bot_arg():
    """Extract --bot argument before passing remaining args to unittest.

    This allows running:
        python tests/test_bot_protocol.py --bot path/to/bot.py -v

    The --bot argument is consumed here; everything else goes to unittest.
    """
    bot_path = None
    remaining = []
    i = 0
    args = sys.argv[1:]
    while i < len(args):
        if args[i] == "--bot" and i + 1 < len(args):
            bot_path = args[i + 1]
            i += 2
        else:
            remaining.append(args[i])
            i += 1
    return bot_path, remaining


if __name__ == "__main__":
    # Suppress ResourceWarning from subprocess pipes (noisy, not actionable)
    warnings.filterwarnings("ignore", category=ResourceWarning)

    bot_path, remaining_args = parse_bot_arg()
    if bot_path:
        BOT_FILE = os.path.abspath(bot_path)
        if not os.path.isfile(BOT_FILE):
            print(f"Error: Bot file not found: {BOT_FILE}")
            sys.exit(1)
    log(f"Bot under test: {BOT_FILE}")
    log(f"Server directory: {SERVER_DIR}")
    log(f"Test settings: {SETTINGS_FILE}")
    print()

    # Pass remaining args to unittest (e.g., --failfast)
    sys.argv = [sys.argv[0]] + remaining_args
    unittest.main(testRunner=SummaryRunner)
