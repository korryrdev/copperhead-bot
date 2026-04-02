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

    def get_safe_neighbors(self, cx, cy, dangerous):
        """Returns valid adjacent tiles ignoring walls and dangerous cells."""
        moves = []
        for direction, (dx, dy) in {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.items():
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.grid_width and 0 <= ny < self.grid_height:
                if (nx, ny) not in dangerous:
                    moves.append((nx, ny, direction))
        return moves

    def flood_fill(self, start_x, start_y, dangerous, my_tail=None):
        """BFS flood fill to count connected safe space. Returns 10000 if it can reach its own tail."""
        visited = {(start_x, start_y)}
        q = deque([(start_x, start_y)])
        while q:
            cx, cy = q.popleft()
            if my_tail and (cx, cy) == tuple(my_tail):
                return 10000
            for nx, ny, _ in self.get_safe_neighbors(cx, cy, dangerous):
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny))
        return len(visited)

    def bfs_shortest_path(self, start_x, start_y, targets, dangerous):
        """Find the absolute shortest safe path to any of the targets. Returns shortest distance or None."""
        if not targets:
            return None
        visited = {(start_x, start_y)}
        q = deque([(start_x, start_y, 0)])
        shortest = None
        while q:
            cx, cy, dist = q.popleft()
            if (cx, cy) in targets:
                if shortest is None or dist < shortest:
                    shortest = dist
            for nx, ny, _ in self.get_safe_neighbors(cx, cy, dangerous):
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny, dist + 1))
        return shortest

    def calculate_move(self) -> str | None:
        """Intelligent move selection using exactly four priorities:
        1. Flood Fill Survival
        2. Aggressive Opponent Hunting
        3. Optimal Food Routing
        4. Tail Chasing
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
        opp_tail = opp_snake["body"][-1] if opp_snake and opp_snake.get("body") else None

        foods = self.game_state.get("foods", [])

        # Calculate dangerous cells
        dangerous = set()
        for s_id, snake_data in snakes.items():
            if not snake_data.get("alive", True):
                continue
            body = snake_data.get("body", [])
            # Tail becomes free next tick unless snake eats, assume free for more aggression
            for segment in body[:-1]:
                dangerous.add((segment[0], segment[1]))
                
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
        
        # Candidate moves (no immediate reversals, walls, or bodies)
        valid_moves = []
        for nx, ny, direction in self.get_safe_neighbors(head[0], head[1], dangerous):
            if direction != opposites.get(current_dir):
                valid_moves.append({"x": nx, "y": ny, "direction": direction})
                
        if not valid_moves:
            # Revert to any valid available move to avoid direct reversal crash
            for direction in ["up", "down", "left", "right"]:
                if direction != opposites.get(current_dir):
                    return direction
            return current_dir

        # Move options with scores/properties
        options = []
        for move in valid_moves:
            nx, ny = move["x"], move["y"]
            safe_area = self.flood_fill(nx, ny, dangerous, my_tail=my_tail)
            options.append({
                "move": move,
                "safe_area": safe_area,
                "nx": nx,
                "ny": ny,
                "direction": move["direction"]
            })
            
        # -- Priority 1: Flood Fill for Flawless Survival --
        # Filter moves that lead to dead ends (safe cells < my_length)
        survivable_options = [opt for opt in options if opt["safe_area"] >= my_length]
        if not survivable_options:
            # If all are dead ends, pick the one with max safe area to stall
            best_die_opt = max(options, key=lambda opt: opt["safe_area"])
            return best_die_opt["direction"]
            
        options = survivable_options
        
        # -- Priority 2: Aggressive Opponent Hunting --
        if my_length > opp_length and opp_head:
            dist_to_opp = abs(head[0] - opp_head[0]) + abs(head[1] - opp_head[1])
            if dist_to_opp <= 3:
                # We are close and strictly longer. Bias towards minimizing next distance
                best_hunt_opt = min(options, key=lambda opt: abs(opt["nx"] - opp_head[0]) + abs(opt["ny"] - opp_head[1]))
                return best_hunt_opt["direction"]

        # -- Priority 3: Optimal Food Routing with Competitive Racing (A* / BFS) --
        food_targets = {(f["x"], f["y"]) for f in foods}
        
        # Calculate opponent's distance to each food item 
        opp_food_dists = {}
        if opp_head:
            for fx, fy in food_targets:
                d = self.bfs_shortest_path(opp_head[0], opp_head[1], {(fx, fy)}, dangerous)
                opp_food_dists[(fx, fy)] = d if d is not None else float('inf')
                
        best_food_score = float('-inf')
        best_food_opts = []
        
        for opt in options:
            for fx, fy in food_targets:
                my_d = self.bfs_shortest_path(opt["nx"], opt["ny"], {(fx, fy)}, dangerous)
                if my_d is not None:
                    opp_d = opp_food_dists.get((fx, fy), float('inf'))
                    
                    # Base score: closer is better
                    score = 1000 - (my_d * 10)
                    
                    if my_d < opp_d:
                        score += 500  # We are closer, big bonus to secure it
                        if opp_d - my_d <= 2:
                            score += 200 # We can steal it right in front of them
                    elif my_d == opp_d:
                        if my_length > opp_length:
                            score += 300 # We survive collision, win the tie
                        else:
                            score -= 300 # They win the tie, avoid
                    else:
                        score -= 800  # They are closer, actively pursue other food if possible

                    if score > best_food_score:
                        best_food_score = score
                        best_food_opts = [opt]
                    elif score == best_food_score:
                        best_food_opts.append(opt)
                
        if best_food_opts:
            # Tie breaker: pick the one with the most safe_area to avoid circling
            best_food_opt = max(best_food_opts, key=lambda o: o["safe_area"])
            return best_food_opt["direction"]
            
        # -- Priority 4: Tail Chasing (Stalling Strategy) --
        tails = set()
        if my_tail:
            tails.add(tuple(my_tail))
        if opp_tail:
            tails.add(tuple(opp_tail))
            
        best_tail_dist = float('inf')
        best_tail_opts = []
        for opt in options:
            dist = self.bfs_shortest_path(opt["nx"], opt["ny"], tails, dangerous)
            if dist is not None:
                if dist < best_tail_dist:
                    best_tail_dist = dist
                    best_tail_opts = [opt]
                elif dist == best_tail_dist:
                    best_tail_opts.append(opt)
                
        if best_tail_opts:
            best_tail_opt = max(best_tail_opts, key=lambda o: o["safe_area"])
            return best_tail_opt["direction"]
            
        # Fallback: Just return any safe survivable option
        return options[0]["direction"]


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
