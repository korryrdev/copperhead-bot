---
name: test-my-bot
description: Run the CopperHead bot protocol test suite against a bot file to verify it follows the server protocol correctly.
---

# Test My Bot

Use this skill when the user asks to test, validate, or check their bot.

Examples:
- "test my bot"
- "run the tests"
- "check if my bot works"
- "validate my bot"
- "test mybot.py"
- "run the bot tests"
- "does my bot follow the protocol?"

## Goal

Run the bot protocol test suite (`tests/test_bot_protocol.py`) against the user's bot file. The test suite launches a local CopperHead server, runs the bot against it, and checks protocol compliance.

## Prerequisites

- The `copperhead-server` repo must exist at `../copperhead-server` (sibling directory of `copperhead-bot`).
- Server dependencies will be installed automatically by the test script.
- Bot dependencies must be installed: `pip install -r requirements.txt`

## Procedure

1. Determine which bot file to test. If the user specifies a file (e.g., "test snake_bot.py"), use that. Otherwise, default to `mybot.py`.

2. Verify the bot file exists.

   ```powershell
   Test-Path <bot_file>
   ```

3. Install bot dependencies if needed.

   ```powershell
   Set-Location <copperhead-bot directory>
   pip install -q -r requirements.txt
   ```

4. Kill any leftover test server processes to avoid port conflicts.

   ```powershell
   Get-NetTCPConnection -LocalPort 18765,18766 -ErrorAction SilentlyContinue |
     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
   ```

5. Run the test suite. Use sync mode with a long initial_wait (tests take 2-3 minutes). Wait for the command to complete fully — do not respond until you have the final output.

   ```powershell
   Set-Location <copperhead-bot directory>
   python tests/test_bot_protocol.py --bot <bot_file>
   ```

6. Once the tests finish, display the full results summary to the user. The output ends with a clearly formatted block between `======` lines — show this entire block (from `TEST RESULTS SUMMARY` through the final `---` line) in your response so the user can see each test's PASS/FAIL status. If any tests failed, explain what went wrong and suggest fixes.

## Important notes

- The test suite uses port `18765` (and `18766` for one test) — not the standard `8765` — to avoid conflicts with a running game server.
- Tests take 2-3 minutes to complete. Let the user know this upfront.
- If tests fail, the summary includes the reason for each failure. Help the user understand what went wrong.
- The `--bot` argument accepts any Python bot file that follows the CopperHead bot CLI conventions (`--server`, `--name`, `--difficulty` arguments).
