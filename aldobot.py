#!/usr/bin/env python3
"""
CopperHead Bot Template - Your custom Snake game AI.

This bot connects to a CopperHead server and plays Snake autonomously.
Modify the calculate_move() function to implement your own strategy!

QUICK START
-----------
1. Install dependencies:   pip install -r requirements.txt
2. Run:                     python mybot.py --server ws://localhost:8765/ws/

For Codespaces, use the wss:// URL shown in the terminal, e.g.:
    python mybot.py --server wss://your-codespace-url.app.github.dev/ws/

WHAT TO CHANGE
--------------
The calculate_move() function (around line 200) is where your bot decides
which direction to move. The default strategy is simple: chase the nearest
food while avoiding walls and snakes. You can make it smarter!

Ideas for improvement:
  - Avoid getting trapped in dead ends (flood fill)
  - Predict where the opponent will move
  - Use different strategies based on snake length
  - Block the opponent from reaching food
"""

import asyncio
import json
import argparse
import websockets
from collections import deque


# ============================================================================
#  BOT CONFIGURATION - Change these to customize your bot
# ============================================================================

# The CopperHead server to connect to. Set this to your server's URL so you
# don't need to pass --server every time. Use "ws://" for local servers or
# "wss://" for Codespaces/remote servers.
GAME_SERVER = "ws://localhost:8765/ws/"

# Your bot's display name (shown to all players in the tournament)
BOT_NAME = "phantom"

# How your bot appears in logs
BOT_VERSION = "1.0"


# ============================================================================
#  BOT CLASS - Handles connection and game logic
# ============================================================================

class MyBot:
    """A CopperHead bot that connects to the server and plays Snake."""

    def __init__(self, server_url: str, name: str = None):
        self.server_url = server_url
        self.name = name or BOT_NAME
        self.player_id = None
        self.game_state = None
        self.running = False
        self.room_id = None
        # Grid dimensions (updated automatically from server)
        self.grid_width = 30
        self.grid_height = 20

    def log(self, msg: str):
        """Print a message to the console."""
        print(msg.encode("ascii", errors="replace").decode("ascii"))

    # ========================================================================
    #  CONNECTION - You probably don't need to change anything below here
    #  until you get to calculate_move()
    # ========================================================================

    async def wait_for_open_competition(self):
        """Wait until the server is reachable, then return.
        
        Bots always join the lobby regardless of competition state —
        the lobby is always available and the bot will wait there until
        the next competition starts.
        """
        import aiohttp

        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        # Convert ws:// to http:// for the REST API
        http_url = base_url.replace("ws://", "http://").replace("wss://", "https://")

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{http_url}/status") as resp:
                        if resp.status == 200:
                            self.log("Server reachable - joining lobby...")
                            return True
                        else:
                            self.log(f"Server not ready (status {resp.status}), waiting...")
            except Exception as e:
                self.log(f"Cannot reach server: {e}, retrying...")

            await asyncio.sleep(5)

    async def connect(self):
        """Connect to the game server."""
        await self.wait_for_open_competition()

        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        url = f"{base_url}/ws/join"

        try:
            self.log(f"Connecting to {url}...")
            self.ws = await websockets.connect(url)
            self.log("Connected! Joining lobby...")
            # Send join message to enter the lobby
            await self.ws.send(json.dumps({
                "action": "join",
                "name": self.name
            }))
            return True
        except Exception as e:
            self.log(f"Connection failed: {e}")
            return False

    async def play(self):
        """Main game loop. Runs until disconnected or eliminated."""
        if not await self.connect():
            self.log("Failed to connect. Exiting.")
            return

        self.running = True

        try:
            while self.running:
                message = await self.ws.recv()
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.ConnectionClosed:
            self.log("Disconnected from server.")
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.running = False
            try:
                await self.ws.close()
            except Exception:
                pass
            self.log("Bot stopped.")

    async def handle_message(self, data: dict):
        """Process messages from the server and respond appropriately."""
        msg_type = data.get("type")

        if msg_type == "error":
            self.log(f"Server error: {data.get('message', 'Unknown error')}")
            self.running = False

        elif msg_type == "joined":
            # Server assigned us a player ID and room
            self.player_id = data.get("player_id")
            self.room_id = data.get("room_id")
            self.log(f"Joined Arena {self.room_id} as Player {self.player_id}")

            # Tell the server we're ready to play
            await self.ws.send(json.dumps({
                "action": "ready",
                "mode": "two_player",
                "name": self.name
            }))
            self.log(f"Ready! Playing as '{self.name}'")

        elif msg_type == "state":
            # Game state update - this is where we decide our next move
            self.game_state = data.get("game")
            grid = self.game_state.get("grid", {})
            if grid:
                self.grid_width = grid.get("width", self.grid_width)
                self.grid_height = grid.get("height", self.grid_height)

            if self.game_state and self.game_state.get("running"):
                direction = self.calculate_move()
                if direction:
                    await self.ws.send(json.dumps({
                        "action": "move",
                        "direction": direction
                    }))

        elif msg_type == "start":
            self.log("Game started!")

        elif msg_type == "gameover":
            winner = data.get("winner")
            my_wins = data.get("wins", {}).get(str(self.player_id), 0)
            opp_id = 3 - self.player_id
            opp_wins = data.get("wins", {}).get(str(opp_id), 0)
            points_to_win = data.get("points_to_win", 5)

            if winner == self.player_id:
                self.log(f"Won! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")
            elif winner:
                self.log(f"Lost! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")
            else:
                self.log(f"Draw! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")

            # Signal ready for next game in the match
            await self.ws.send(json.dumps({
                "action": "ready",
                "name": self.name
            }))

        elif msg_type == "match_complete":
            winner_id = data.get("winner", {}).get("player_id")
            winner_name = data.get("winner", {}).get("name", "Unknown")
            final_score = data.get("final_score", {})
            my_score = final_score.get(str(self.player_id), 0)
            opp_id = 3 - self.player_id
            opp_score = final_score.get(str(opp_id), 0)

            if winner_id == self.player_id:
                self.log(f"Match won! Final: {my_score}-{opp_score}")
                self.log("Waiting for next round...")
            else:
                self.log(f"Match lost to {winner_name}. Final: {my_score}-{opp_score}")
                self.log("Eliminated. Exiting.")
                self.running = False

        elif msg_type == "match_assigned":
            # Assigned to a new match in the next tournament round
            self.room_id = data.get("room_id")
            self.player_id = data.get("player_id")
            self.game_state = None
            opponent = data.get("opponent", "Opponent")
            self.log(f"Next round! Arena {self.room_id} vs {opponent}")
            # Signal ready to the server
            await self.ws.send(json.dumps({"action": "ready", "name": self.name}))

        elif msg_type in ("lobby_joined", "lobby_update"):
            # In the lobby waiting for the competition to start
            if msg_type == "lobby_joined":
                self.log(f"Joined lobby as '{data.get('name', self.name)}'")

        elif msg_type in ("lobby_left", "lobby_kicked"):
            self.log("Removed from lobby.")
            self.running = False

        elif msg_type == "competition_complete":
            champion = data.get("champion", {}).get("name", "Unknown")
            self.log(f"Tournament complete! Champion: {champion}")
            self.running = False

        elif msg_type == "waiting":
            self.log("Waiting for opponent...")

    # ========================================================================
    #  YOUR AI STRATEGY - Modify calculate_move() to change how your bot plays
    # ========================================================================

    def calculate_move(self) -> str | None:
        """Intelligent move selection using flood fill, BFS pathfinding, and opponent awareness.

        Strategy:
            1. Flood fill each candidate move — heavily penalise moves that trap us
            2. BFS to find true (obstacle-aware) distance to food
            3. Race logic — use actual BFS distance for opponent too
            4. Head-on collision — dodge unless we're longer (then attack)
            5. Opponent trapping — when longer, intercept opponent's path
            6. Tail following — safe fallback to avoid dead ends
            7. Edge avoidance — slight preference for the centre

        Available data:
            self.game_state     - Full game state
            self.player_id      - Our player number (1 or 2)
            self.grid_width     - Width of the game board
            self.grid_height    - Height of the game board
        """
        if not self.game_state:
            return None

        snakes = self.game_state.get("snakes", {})
        my_snake = snakes.get(str(self.player_id))

        if not my_snake or not my_snake.get("body"):
            return None

        head = my_snake["body"][0]
        my_tail = my_snake["body"][-1]
        current_dir = my_snake.get("direction", "right")
        my_length = len(my_snake["body"])

        opp_id = str(3 - self.player_id)
        opp_snake = snakes.get(opp_id)
        opp_head = opp_snake["body"][0] if opp_snake and opp_snake.get("body") else None
        opp_length = len(opp_snake["body"]) if opp_snake and opp_snake.get("body") else 0

        foods = self.game_state.get("foods", [])

        # Occupied cells: all snake bodies minus tails (tails vacate next tick)
        dangerous = set()
        for snake_data in snakes.values():
            body = snake_data.get("body", [])
            for segment in body[:-1]:
                dangerous.add((segment[0], segment[1]))

        directions = {
            "up":    (0, -1),
            "down":  (0,  1),
            "left":  (-1, 0),
            "right": (1,  0),
        }
        dir_vectors = list(directions.values())
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}

        def in_bounds(x, y):
            return 0 <= x < self.grid_width and 0 <= y < self.grid_height

        def is_safe(x, y):
            return in_bounds(x, y) and (x, y) not in dangerous

        def flood_fill(start_x, start_y):
            """BFS flood fill — returns number of reachable cells."""
            visited = {(start_x, start_y)}
            q = deque([(start_x, start_y)])
            while q:
                cx, cy = q.popleft()
                for dx, dy in dir_vectors:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) not in visited and is_safe(nx, ny):
                        visited.add((nx, ny))
                        q.append((nx, ny))
            return len(visited)

        def bfs_dist_to_targets(start_x, start_y, targets):
            """BFS from start — returns {target: distance} for all reachable targets."""
            if not targets:
                return {}
            remaining = set(targets)
            found = {}
            visited = {(start_x, start_y)}
            q = deque([(start_x, start_y, 0)])
            while q and remaining:
                cx, cy, dist = q.popleft()
                if (cx, cy) in remaining:
                    found[(cx, cy)] = dist
                    remaining.discard((cx, cy))
                for dx, dy in dir_vectors:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) not in visited and is_safe(nx, ny):
                        visited.add((nx, ny))
                        q.append((nx, ny, dist + 1))
            return found

        food_targets = {(f["x"], f["y"]) for f in foods}

        # Pre-compute BFS distances for both snakes to all foods
        my_food_dists = bfs_dist_to_targets(head[0], head[1], food_targets)
        opp_food_dists = {}
        if opp_head:
            opp_food_dists = bfs_dist_to_targets(opp_head[0], opp_head[1], food_targets)

        # Cells opponent could reach next tick (for head-on collision detection)
        opp_next = set()
        if opp_head:
            for dx, dy in dir_vectors:
                nx, ny = opp_head[0] + dx, opp_head[1] + dy
                if in_bounds(nx, ny):
                    opp_next.add((nx, ny))

        # Candidate moves (no reversals, no immediate walls/bodies)
        safe_moves = []
        for direction, (dx, dy) in directions.items():
            if direction == opposites.get(current_dir):
                continue
            nx, ny = head[0] + dx, head[1] + dy
            if is_safe(nx, ny):
                safe_moves.append({"direction": direction, "x": nx, "y": ny})

        if not safe_moves:
            # All moves blocked — pick anything valid to avoid reversal crash
            for direction in directions:
                if direction != opposites.get(current_dir):
                    return direction
            return current_dir

        best_dir = None
        best_score = float('-inf')

        hunting_mode = my_length > opp_length + 1  # We're longer — go aggressive

        for move in safe_moves:
            score = 0
            nx, ny = move["x"], move["y"]

            # ── 1. Flood fill: survival first ─────────────────────────────
            reachable = flood_fill(nx, ny)
            if reachable < my_length:
                score -= 50000          # Near-certain death — hard veto
            elif reachable < my_length * 1.5:
                score -= 8000           # Very tight — strongly avoid
            elif reachable < my_length * 2:
                score -= 2000           # Somewhat tight
            else:
                score += min(reachable, 150) * 3   # Capped so food can compete

            # ── 2. 2-step lookahead: count options from next position ─────
            next_safe_count = 0
            for d2, (dx2, dy2) in directions.items():
                if d2 == opposites.get(move["direction"]):
                    continue
                nnx, nny = nx + dx2, ny + dy2
                if is_safe(nnx, nny) and (nnx, nny) != (head[0], head[1]):
                    next_safe_count += 1
            score += next_safe_count * 200  # Reward keeping options open

            # ── 3. Food: score ALL reachable food, pick best ──────────────
            if food_targets:
                move_food_dists = bfs_dist_to_targets(nx, ny, food_targets)
                best_food_score = 0
                for food_pos in food_targets:
                    my_d = move_food_dists.get(food_pos)
                    if my_d is None:
                        continue        # Food unreachable from here — skip
                    opp_d = opp_food_dists.get(food_pos, float('inf'))

                    if (nx, ny) == food_pos:
                        fs = 10000      # Eating food this move — top priority
                    elif my_d <= 2:
                        fs = 7000 - my_d * 300   # Almost there — very aggressive
                    elif my_d < opp_d:
                        fs = (100 - my_d) * 60   # Winning the food race
                    elif my_d == opp_d:
                        fs = (100 - my_d) * 30   # Tied race
                    else:
                        # Even if losing race, still chase — being longer wins fights
                        fs = (100 - my_d) * 15

                    best_food_score = max(best_food_score, fs)
                score += best_food_score

            # ── 4. Head-on collision ──────────────────────────────────────
            if (nx, ny) in opp_next:
                if my_length > opp_length + 1:
                    score += 3000       # Kill shot — actively seek this
                else:
                    score -= 2000       # Tie or loss — avoid

            # ── 5. Hunt mode: when longer, close in on opponent ──────────
            if hunting_mode and opp_head:
                opp_dist_now = abs(head[0] - opp_head[0]) + abs(head[1] - opp_head[1])
                opp_dist_next = abs(nx - opp_head[0]) + abs(ny - opp_head[1])
                if opp_dist_next < opp_dist_now:
                    score += 600        # Closing in on opponent
                # Cut off opponent from their nearest food
                opp_best_food = min(opp_food_dists, key=lambda t: opp_food_dists[t], default=None)
                if opp_best_food:
                    opp_hx, opp_hy = opp_head
                    fx, fy = opp_best_food
                    if (min(opp_hx, fx) <= nx <= max(opp_hx, fx) and
                            min(opp_hy, fy) <= ny <= max(opp_hy, fy)):
                        score += 400    # Blocking opponent's food path

            # ── 6. Tail following (tight spaces only) ────────────────────
            tail_dist = abs(nx - my_tail[0]) + abs(ny - my_tail[1])
            if reachable < my_length * 3:
                score += max(0, 10 - tail_dist) * 8

            # ── 7. Wall avoidance ─────────────────────────────────────────
            edge_dist = min(nx, self.grid_width - 1 - nx,
                            ny, self.grid_height - 1 - ny)
            if edge_dist == 0:
                score -= 300            # On the wall
            elif edge_dist == 1:
                score -= 80             # Adjacent to wall
            else:
                score += edge_dist * 15  # Centre preference

            if score > best_score:
                best_score = score
                best_dir = move["direction"]

        return best_dir


# ============================================================================
#  MAIN - Parse command line arguments and start the bot
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="CopperHead Bot")
    parser.add_argument("--server", "-s", default=GAME_SERVER,
                        help=f"Server WebSocket URL (default: {GAME_SERVER})")
    parser.add_argument("--name", "-n", default=None,
                        help=f"Bot display name (default: {BOT_NAME})")
    parser.add_argument("--difficulty", "-d", type=int, default=5,
                        help="AI difficulty level 1-10 (accepted for compatibility, not yet used)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress console output")
    args = parser.parse_args()

    bot = MyBot(args.server, name=args.name)

    print(f"{bot.name} v{BOT_VERSION}")
    print(f"  Server: {args.server}")
    print()

    await bot.play()


if __name__ == "__main__":
    asyncio.run(main())
