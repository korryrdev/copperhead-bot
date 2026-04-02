# Aldobot AI Strategy Guide

This document outlines the advanced AI improvements built into `aldobot.py` for the CopperHead multiplayer snake tournament. The default greedy algorithm has been replaced with a deterministic, highly-survivable heuristic model.

## The Four-Priority Strategy Framework

Aldobot evaluates every possible move (Up, Down, Left, Right) simultaneously by passing them through four rigorous, ordered priority tiers:

### Priority 1: Flood Fill for Flawless Survival (The Filter)
Before committing to any action, Aldobot runs a Breadth-First-Search (BFS) **Flood Fill** algorithm to count the number of currently safe, navigable grid cells each immediate turn offers. 
- Any route that leads to fewer safe tiles than the current `len(aldobot)` is immediately flagged as a "Dead End" and aggressively discarded. 
- **Infinite Tail Safety:** If the flood fill radar touches Aldobot's own tail, it instantly registers the corridor as infinitely safe (`10000` safe tiles). This completely eliminates the panicky false-positive "dead end" calculation that occurs when the bot is coiled.

### Priority 2: Aggressive Opponent Hunting
Aldobot actively weaponizes its size. It constantly compares its own length to the remaining opponents on the board.
- If Aldobot is strictly longer than an opponent by at least `+2` lengths, it initiates Hunting Mode.
- If the victim is within a Manhattan distance of 3 tiles, Aldobot intercepts and biases its routing towards minimizing the distance to the opponent's head, forcibly orchestrating a head-to-head collision where the smaller opponent is destroyed.

### Priority 3: Optimal Food Routing with Competitive Racing (BFS)
Rather than traveling in blind cardinal straight lines, Aldobot uses full **Breadth-First Search (BFS)** to map the obstacle-aware absolute shortest path to all existing food items.
- **Competitive Food Stealing**: It calculates the opponent's absolute shortest path to the exact same fruit. If Aldobot is closer, it massively prioritizes the route. If the opponent is closer, Aldobot mathematically abandons it to hunt across the board for uncontested fruit. Ties are dynamically broken based on who has the strict size advantage!
- **Graceful Uncoiling / Loop Breaking:** If Aldobot discovers multiple paths that lead to the nearest food in the exact same number of steps, it utilizes the safe area map from Priority 1 to break the tie—always opting for the path with the widest open space to efficiently uncoil itself.  

### Priority 4: Tail Chasing (Stalling Protocol)
If all paths to food are blocked or if reaching food requires navigating into an imminent dead end, Aldobot defaults to stalling natively. 
- It maps the optimal BFS route to its own tail (or an opponent's tail). Following its own vacating tail ensures it wastes maximum time, surviving until the board shifts and obstacles unfreeze.

## Key Bug Fixes Summarized
* **The "Fruit Looping" Error Fixed:** The previous template or iteration would get trapped perpetually circling a fruit it deemed "unsafe". By updating the flood fill algorithm to natively understand that moving forward physically vacates the tail space, Aldobot now correctly recognizes its own coils as traversable space and confidently eats the food rather than pacing around it defensively.
