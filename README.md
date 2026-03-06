# CopperHead Bot

Version: 4.0.0

A starter template for building your own AI bot to compete in [CopperHead](https://github.com/revodavid/copperhead-server) Snake tournaments.

For a video guide on building your bot, watch: [How to Build Your Own CopperHead Bot](https://youtu.be/qSY4JtkZAiY).

## What You'll Need

1. A running CopperHead Server for your bot to play on. You can launch one by following the instructions at the [`copperhead-server`](https://github.com/revodavid/copperhead-server) repository.

2. An environment to run your bot's code. You can use CodeSpaces on this repository, or your own machine with Python 3.10+ installed.

3. The [CopperHead client](https://github.com/revodavid/copperhead-client) web app to watch your bot play. You can use the "Play Now" link that appears in the CopperHead Server CodeSpace to open the client in your browser.

## Quick Start

### 1. Set up your environment

You can develop your bot in **GitHub Codespaces** (recommended) or locally.

**Option A: GitHub Codespaces** (no setup required)
- Fork this repository and open it in a Codespace.
- Dependencies are installed automatically.

**Option B: Local development**
- Make sure you have Python 3.10+ installed.
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Test the basic bot

To start with, the file `mybot.py` implements a simplistic bot. Run it and join the CopperHead tournament server with:
```bash
python mybot.py --server wss://your-codespace-url.app.github.dev/ws/
```

You can find the tournament server URL at the bottom of the lobby screen in the CopperHead Client webpage. It will look like `wss://your-codespace-url.app.github.dev/ws/`.

Your bot will join the server and play matches until the tournament is complete. You will need to relaunch your bot to join a new tournament after the current one finishes.

### 3. Customize your bot

#### Using GitHub Copilot CLI (recommended)

The easiest way to improve your bot is with **GitHub Copilot CLI** — just describe what you want in plain English. In your Codespace terminal, run:

```bash
copilot
```

This starts an interactive session where you can ask Copilot to modify your code. For example, try prompts like:

- *Name my bot 'Slytherin'*
- *Make my bot prioritize eating grapes over any other food*
- *Add flood fill to mybot.py so my snake avoids moving into dead ends*
- *Make my bot play more aggressively when it's longer than the opponent*
- *Add a strategy to mybot.py that blocks the opponent from reaching food*

Copilot CLI understands your code and can make changes directly to `mybot.py`. You can review each change before accepting it, and keep iterating until your bot plays the way you want.

> **Tip:** You don't need to be an expert programmer — just describe the *behavior* you want and let Copilot handle the code!

[GitHub Copilot](https://github.com/features/copilot) also works in the GitHub web editor and in VS Code with inline suggestions.

#### Manual development

Open `mybot.py` and find the `calculate_move()` function (around line 200). This is where your bot decides which direction to move each tick. The default strategy is simple — chase food and avoid walls. You can do much better!

**Example — Make your bot more aggressive about food:**

Find this section in `calculate_move()`:
```python
# Big bonus for capturing food
if food and new_x == food[0] and new_y == food[1]:
    score += 1000  # Always prioritize eating
```

Change it to weight food even more heavily:
```python
# VERY aggressive food pursuit
if food and new_x == food[0] and new_y == food[1]:
    score += 5000  # Food is life!
```

### 4. Test your upgraded bot

Make sure your CopperHead Server is running and ready to accept players. The examples below assume the server is running on `localhost` port 8765; replace with the actual server URL and port as required.

#### Option A: Use the server API to spawn an opponent

This is the easiest way to quickly test your bot. Use the server's `/add_bot` API to spawn an opponent:

```bash
# Spawn a CopperBot opponent
curl -X POST "http://localhost:8765/add_bot?difficulty=5"

# Then run your bot
python mybot.py --server ws://localhost:8765/ws/
```

Or from the client UI, click "Add Bot" to spawn a CopperBot, then run your bot to join as the second player.

#### Option B: Test in a competition

For tournament-style testing with multiple bots:

1. Start a CopperHead server (or connect to an existing one)
2. Run your bot:
   ```bash
   python mybot.py --server ws://localhost:8765/ws/
   ```
3. Your bot will wait for another player (human or bot) to join

**Tip**: Run two instances of your bot to watch them compete against each other!

### 5. Iterate and improve

Watch your bot play and identify weaknesses. See [Strategy Ideas](#strategy-ideas) below for ways to improve. Keep using Copilot CLI prompts or manual edits to refine your bot's behavior, then relaunch to test.

## Bot Command Line Options

Your bot must accept the following command-line options:

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--server` | `-s` | `ws://localhost:8765/ws/` | Server WebSocket URL |
| `--name` | `-n` | `MyBot` | Your bot's display name |
| `--difficulty` | `-d` | `5` | AI difficulty level (1-10) — 1 should be the least capable and 10 the smartest. For the default `mybot.py` all difficulty levels are the same |
| `--quiet` | `-q` | `false` | Suppress console output |

## In Detail: How Bots Work

Your bot connects to a CopperHead server via WebSocket and plays Snake automatically. Every game tick, the server sends the current game state and your bot responds with a direction to move.

### Bot Architecture

CopperHead bots consist of three main components:

1. **Connection Handler**: Manages the WebSocket connection to the server, handles joining competitions, and processes incoming/outgoing messages.

2. **Message Processor**: Receives game state updates from the server and dispatches appropriate responses (ready signals, movement commands).

3. **AI Logic**: The `calculate_move()` function that analyzes the current game state and decides which direction to move.

### Key Functions

| Function | Purpose |
|----------|---------|
| `connect()` | Establishes WebSocket connection to the server |
| `play()` | Main game loop — receives messages and calls handlers |
| `handle_message()` | Processes server messages and triggers appropriate actions |
| `calculate_move()` | **The AI brain** — decides which direction to move |

### Server Messages

The server sends JSON messages to connected clients. Each message has a `type` field:

| Message Type | When Sent | Key Data |
|--------------|-----------|----------|
| `lobby_joined` | After sending `join` action | Confirmation that you've joined the lobby |
| `lobby_update` | Lobby state changes | Current lobby players and slot assignments |
| `match_assigned` | Competition starts or next round | `player_id`, `room_id`, `opponent` — send `ready` to begin |
| `waiting` | Waiting for opponent | Indicates you're waiting for another player to join |
| `start` | Game begins | `mode`, `room_id` — the game is starting |
| `state` | Every game tick | `game` — complete game state (see below) |
| `gameover` | A game ends | `winner`, `wins`, `points_to_win` — who won and current scores |
| `match_complete` | Match ends | `winner`, `final_score` — who won the match |
| `competition_complete` | Tournament ends | `champion` — the overall winner |
| `error` | Something went wrong | `message` — error description |

### Game State

Each tick, the `state` message includes a `game` object:

```json
{
  "running": true,
  "grid": {"width": 30, "height": 20},
  "snakes": {
    "1": {
      "body": [[10, 5], [9, 5], [8, 5]],
      "direction": "right",
      "alive": true,
      "buff": "default"
    },
    "2": {
      "body": [[20, 15], [21, 15]],
      "direction": "left",
      "alive": true,
      "buff": "speed"
    }
  },
  "foods": [
    {"x": 15, "y": 10, "type": "apple", "lifetime": null}
  ]
}
```

- **running**: Boolean — is the game currently active?
- **grid**: Object with `width` and `height` of the game board. `(0, 0)` is the top-left corner; `y` increases downward.
- **snakes**: Object with player IDs as keys, each containing:
  - **body**: Array of `[x, y]` coordinates (head is the first element)
  - **direction**: Current movement direction (`"up"`, `"down"`, `"left"`, `"right"`)
  - **alive**: Boolean — is this snake still alive?
  - **buff**: Current active buff (`"default"`, `"speed"`, `"shield"`, `"inversion"`, `"lucky"`, `"slow"`, `"scissors"`, `"ghost"`)
- **foods**: Array of food items, each with:
  - **x**, **y**: Coordinates of the food
  - **type**: Fruit type (`"apple"`, `"orange"`, `"lemon"`, `"grapes"`, `"strawberry"`, `"banana"`, `"peach"`, `"cherry"`, `"watermelon"`, `"kiwi"`)
  - **lifetime**: Ticks remaining before fruit expires, or `null`. Only reported when the fruit is about to expire (within the server's `fruit_warning` threshold). A value of `null` means the fruit either never expires or is not yet close to expiring.

### Bot Commands

Bots send JSON messages to control their snake:

| Action | Format | Description |
|--------|--------|-------------|
| Join | `{"action": "join", "name": "MyBot"}` | Join the lobby |
| Ready | `{"action": "ready", "name": "MyBot"}` | Signal ready for a match |
| Move | `{"action": "move", "direction": "up"}` | Change snake direction |

Valid directions: `"up"`, `"down"`, `"left"`, `"right"`

**Note**: You cannot reverse direction (e.g., go from `"left"` to `"right"` directly). The server will ignore invalid moves. If you hit a wall or a snake (including yourself), you lose the point. Eating food (especially apples 🍎) makes your snake grow longer.

### Tournament Flow

1. Your bot joins a tournament and waits for an opponent.
2. Matches are best-of-N games (set by the server).
3. Match winners advance to the next round.
4. Losers are eliminated. The last bot standing wins! 🏆

## Strategy Ideas

Here are some ways to improve your bot beyond the basic "chase food" strategy:

- **Flood fill**: Before moving, count how many squares are reachable from each direction. Avoid moves that lead into small enclosed spaces.
- **Opponent prediction**: Look at the opponent's direction and predict where they'll go. Avoid head-on collisions (unless you're longer!).
- **Food blocking**: Position yourself between the opponent and the food.
- **Length awareness**: Play more aggressively when you're longer than your opponent, more defensively when shorter.
- **Tail chasing**: When no food is nearby, follow your own tail to stay safe.

## Bot API Reference

### RobotPlayer Class

```python
RobotPlayer(server_url: str, difficulty: int = 5, quiet: bool = False)
```

- **server_url**: WebSocket URL of the CopperHead server
- **difficulty**: 1-10, affects how often the bot makes suboptimal moves
- **quiet**: If True, suppresses log output

#### Key Methods

**`async connect()`**
Connects to the server and sends the `join` action to enter the lobby. Returns `True` on success.

**`async play()`**
Main game loop. Call this to start playing. Runs until disconnected or eliminated.

**`async handle_message(data: dict)`**
Processes incoming server messages. Override this to add custom message handling.

**`calculate_move() -> str | None`**
Returns the next move direction. **This is the main function to customize for your AI strategy.**

### Helper Functions

The default bot includes these helper functions you can use in `calculate_move()`:

**`is_safe(x, y) -> bool`**
Returns True if the position is not a wall and not occupied by any snake.

**`count_safe_neighbors(x, y) -> int`**
Returns how many adjacent squares are safe (0-4). Useful for avoiding traps.

### Grid Dimensions

The bot automatically receives grid dimensions from the server via the game state. These are stored as instance variables:

```python
self.grid_width   # Game board width (default: 30)
self.grid_height  # Game board height (default: 20)
```

These values are updated automatically when the first game state is received, so your bot will work correctly regardless of server configuration.

### Example: Simple Wall-Avoiding Bot

Here's a minimal `calculate_move()` implementation:

```python
def calculate_move(self) -> str | None:
    if not self.game_state:
        return None
    
    snakes = self.game_state.get("snakes", {})
    my_snake = snakes.get(str(self.player_id))
    if not my_snake or not my_snake.get("body"):
        return None
    
    head = my_snake["body"][0]
    current_dir = my_snake.get("direction", "right")
    
    # Build set of dangerous positions
    dangerous = set()
    for snake_data in snakes.values():
        for segment in snake_data.get("body", []):
            dangerous.add((segment[0], segment[1]))
    
    # Try each direction, pick the first safe one
    directions = ["up", "down", "left", "right"]
    opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
    deltas = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    
    for d in directions:
        if d == opposites[current_dir]:
            continue  # Can't reverse
        dx, dy = deltas[d]
        new_x, new_y = head[0] + dx, head[1] + dy
        
        # Check bounds using instance variables
        if new_x < 0 or new_x >= self.grid_width or new_y < 0 or new_y >= self.grid_height:
            continue
        # Check collision
        if (new_x, new_y) in dangerous:
            continue
        
        return d  # First safe direction
    
    return current_dir  # No safe move, keep going
```

This simple bot just avoids walls and other snakes, without seeking food. Use it as a starting point and add your own strategy!

## Server Reference

For full details on the game rules, server messages, and competition logic, see the [CopperHead Server documentation](https://github.com/revodavid/copperhead-server):

- [How to Build Your Own Bot](https://github.com/revodavid/copperhead-server/blob/main/How-To-Build-Your-Own-Bot.md) — full message protocol reference
- [Game Rules](https://github.com/revodavid/copperhead-server/blob/main/game-rules.md) — collision rules, food types, and buffs
- [Competition Logic](https://github.com/revodavid/copperhead-server/blob/main/competition-logic.md) — tournament format and matchmaking
