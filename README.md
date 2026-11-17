# SETTLERS OF CATAN (DOS-BOX EDITION)

> A retro DOS-Box styled desktop recreation of the legendary board game **Settlers of Catan** built in Python with Tkinter and SQLite persistence.

---

## 1. Features & Aesthetics

* **Old DOS-Box UI-esque Feel**: Deep classic DOS blue/black palette (`#0A0E1A`, `#000084`), ASCII/Unicode framing (`╔═╗`, `║ ║`, `╚═╝`), beveled retro push-buttons, and an authentic phosphor green scrolling action terminal.
* **Universal Monospace Typography**: All information across the board, HUDs, dialogs, and logs is rendered using crisp monospace fonts (`Consolas` / `Courier New`).
* **Strict Hexagon Color Convention**:
  * <span style="color:#C0392B;font-weight:bold;">RED</span>: **Brick** (Hill)
  * <span style="color:#2ECC71;font-weight:bold;">LIGHT GREEN</span>: **Sheep** (Pasture)
  * <span style="color:#145A32;font-weight:bold;">DARK GREEN</span>: **Wood** (Forest)
  * <span style="color:#F1C40F;font-weight:bold;">YELLOW</span>: **Wheat** (Field)
  * <span style="color:#7F8C8D;font-weight:bold;">GREY</span>: **Ore** (Mountain)
  * <span style="color:#D2B48C;font-weight:bold;">KHAKI</span>: **Robber's Hexagon** (Desert)
* **Corner Dice Display**: The rolled 2d6 result is prominently displayed in the upper corner of the screen with two animated 2D dice faces featuring authentic pip dots and the total sum.
* **White Font & Probability Dots**: Every resource hex displays its rolled number in bold **white font** (`#FFFFFF`), with white probability dots below indicating the statistical likelihood of that roll (6 and 8 having 5 dots, 2 and 12 having 1 dot).
* **Resource Bank Display (95 Cards Total, 19 of Each Type)**: Dedicated real-time DOS UI element tracking and displaying all available cards in the Bank:
  * 19 Wood, 19 Brick, 19 Sheep, 19 Wheat, 19 Ore.
  * Real-time counters update as cards are produced, spent on buildings, traded, and discarded.
* **Bank Trading (4:1) & Coastal Trading Ports (3:1 and 2:1)**:
  * **Default Bank Trading**: Trade 4 of any single resource for 1 of any resource from the Bank.
  * **Generic Trading Ports (3:1 ?)**: Build on a generic coastal harbor to trade 3 of ANY resource for 1 of any resource from the Bank.
  * **Specific Trading Ports (2:1)**: Build on a specialized coastal harbor (Wood, Brick, Sheep, Wheat, Ore) to trade 2 of THAT resource for 1 of any resource from the Bank!
  * **Visual Docks on Board Canvas**: The 9 harbors are rendered directly offshore with wooden docks connecting to coastal intersections and color-coded port signs that illuminate when claimed.
* **Local Pass-and-Play System**: Supports 4 local players taking turns on the same desktop machine:
  * House Colors: **RED**, **BLUE**, **WHITE**, **ORANGE**.
  * **White Outlines**: Every single road, settlement (house), and city piece is drawn with a crisp white outline (`#FFFFFF`, width 2) for maximum retro clarity.
* **Trading System (Active Player Initiation Only)**: Players can negotiate and exchange resources. Trading initiation is strictly reserved for the player whose turn is currently being played. Offers prompt the recipient with an interactive pass-and-play acceptance dialog.
* **Full SQL Database Persistence**: All game state, board configurations, player hands, buildings, roads, resource bank inventory, and action logs are continuously auto-saved to an SQLite database (`catan_game.db`). Closing and reopening the application immediately resumes the ongoing match!

---

## 2. Requirements & How to Run

### System Requirements
* **Operating System**: Windows, macOS, or Linux.
* **Python**: Python 3.8 or higher (fully compatible with Python 3.14+).
* **Dependencies**: **Zero third-party packages required!** The game runs strictly on Python's standard library (`tkinter`, `sqlite3`, `json`, `math`, `random`).

### Quick Start
1. Open PowerShell or Command Prompt.
2. Navigate to the game directory:
   ```powershell
   cd "D:\Games\PROJECT CATAN"
   ```
3. Run the application:
   ```powershell
   python main.py
   ```
   *(Alternatively, on Windows you can double-click `run_game.bat` or `main.py` directly).*

---

## 3. Rules of the Game

### Objective
The first player to reach **10 Victory Points (VP)** wins the game immediately!
Victory Points are earned through:
* **Settlement**: 1 Victory Point
* **City**: 2 Victory Points
* **Longest Road** (continuous route of 5+ roads): 2 Victory Points
* **Largest Army** (3+ Knight cards played): 2 Victory Points
* **Victory Point Development Cards**: 1 Victory Point each

---

### Setup Phase (Snake Draft)
At the start of the match, players take turns placing two starting settlements and two starting roads in snake order:
1. **Round 1**: `RED` → `BLUE` → `WHITE` → `ORANGE`.
   * Each player places 1 settlement on an unoccupied intersection, followed by 1 road connected to that settlement.
2. **Round 2 (Reverse)**: `ORANGE` → `WHITE` → `BLUE` → `RED`.
   * Each player places their 2nd settlement, followed by 1 connected road.
   * **Starting Resources**: Upon placing their second settlement, each player immediately receives 1 resource card from every resource hex bordering that second settlement!
3. After `RED` finishes Round 2, the main game commences with `RED` taking Turn 1.

*(Tip: Click **[QUICK AUTO-SETUP]** during setup if you wish to instantly generate a balanced starting board).*

---

### Turn Structure
On each turn, the active player completes three steps:

#### Step 1: Roll the Dice (2d6)
* The active player clicks **[ROLL DICE]** or presses `R`.
* The corner dice widget animates and reveals the two dice faces.
* **If a 7 is rolled**:
  * **Discard Penalty**: Any player holding more than 7 resource cards in their hand must discard half of their cards (rounded down).
  * **Move the Robber**: The active player clicks any hexagon on the board to relocate the Robber piece. The chosen hex will no longer produce any resources while the robber is present.
  * **Steal**: If one or more opponents have settlements or cities adjacent to that hex, the active player steals 1 random resource card from one of those opponents.
* **If 2 through 12 is rolled**:
  * Every hex tile matching that number yields resources to all adjacent settlements and cities (unless blocked by the Robber).
  * Each adjacent **Settlement** produces **1 resource**.
  * Each adjacent **City** produces **2 resources**.

#### Step 2: Trade & Actions (In Any Order)
* **Build Road** (`Cost: 1 Wood + 1 Brick`):
  * Must connect to an existing road, settlement, or city of your color.
  * Maximum 15 roads per player.
* **Build Settlement** (`Cost: 1 Wood + 1 Brick + 1 Sheep + 1 Wheat`):
  * Must be built on an empty intersection connected to your road network.
  * **Distance Rule**: You cannot build a settlement if ANY adjacent intersection (1 road segment away) contains a settlement or city belonging to ANY player.
  * Maximum 5 settlements per player (1 VP each).
* **Upgrade to City** (`Cost: 2 Wheat + 3 Ore`):
  * Upgrades one of your existing settlements into a city.
  * Doubles the resource yield of that intersection (2 VP each).
  * Maximum 4 cities per player.
* **Buy Development Card** (`Cost: 1 Sheep + 1 Wheat + 1 Ore`):
  * Draws a card from the deck: *Knight*, *Victory Point*, *Road Building*, *Year of Plenty*, or *Monopoly*.
* **Trade Resources**:
  * Click **[T] TRADE RESOURCES** to open the Trading Post.
  * **Strict Turn Rule**: Trading initiation is available **only to the active player** whose turn is currently being played.
  * **Bank & Coastal Port Trading**:
    * **Standard 4:1 Bank Trade**: Any active player can trade 4 identical cards of any resource to the Bank for 1 card of any desired resource.
    * **Generic 3:1 Harbor Port**: A player with a settlement or city touching a `[3:1 ?]` port can trade 3 identical cards of ANY resource for 1 card from the Bank.
    * **Specific 2:1 Harbor Port**: A player with a settlement or city touching a specific 2:1 port (Wood, Brick, Sheep, Wheat, or Ore) can trade only 2 cards of that matching resource for 1 card of any desired resource from the Bank!
    * In the Trading Post dialog, the active player's unlocked trade rates are dynamically displayed and verified against the Bank's current inventory.
  * **Player-to-Player Trading**: Offer any combination of resources to another player in exchange for what you need. The recipient receives a pass-and-play confirmation dialog with `[ACCEPT]` and `[REJECT]`.

#### Step 3: End Turn
* Click **[E] END TURN** (or press `E`).
* Controls pass to the next player in clockwise order (`RED` → `BLUE` → `WHITE` → `ORANGE` → `RED`).

---

## 4. Probability Dots Reference

When two standard 6-sided dice are rolled, the probability of rolling each number is reflected by the white dots printed below each number:

| Number | Combinations | Probability | White Dots Display |
| :---: | :---: | :---: | :---: |
| **2** | `(1,1)` | 1/36 (2.78%) | `•` *(Lowest)* |
| **3** | `(1,2), (2,1)` | 2/36 (5.56%) | `••` |
| **4** | `(1,3), (2,2), (3,1)` | 3/36 (8.33%) | `•••` |
| **5** | `(1,4), (2,3), (3,2), (4,1)` | 4/36 (11.11%) | `••••` |
| **6** | `(1,5), (2,4), (3,3), (4,2), (5,1)` | 5/36 (13.89%) | `•••••` *(Highest)* |
| **8** | `(2,6), (3,5), (4,4), (5,3), (6,2)` | 5/36 (13.89%) | `•••••` *(Highest)* |
| **9** | `(3,6), (4,5), (5,4), (6,3)` | 4/36 (11.11%) | `••••` |
| **10** | `(4,6), (5,5), (6,4)` | 3/36 (8.33%) | `•••` |
| **11** | `(5,6), (6,5)` | 2/36 (5.56%) | `••` |
| **12** | `(6,6)` | 1/36 (2.78%) | `•` *(Lowest)* |
| **Desert** | *None* | 0/36 | *Robber's Hexagon (Khaki)* |

---

## 5. Keyboard Shortcuts

| Shortcut | Action | Description |
| :---: | :---: | :--- |
| `R` | **Roll Dice** | Rolls 2d6 in the roll phase |
| `B` | **Build Road** | Enters road placement mode |
| `S` | **Build Settlement** | Enters settlement placement mode |
| `C` | **Upgrade City** | Enters city upgrade mode |
| `T` | **Trade Resources** | Opens the trading post (active player only) |
| `E` | **End Turn** | Passes control to the next player |
| `Esc` | **Cancel Action** | Cancels current placement / targeting mode |
| `F1` | **Rules & Guide** | Opens the in-game DOS reference manual |
| `F2` | **Save Game** | Opens the database save manager |

---

## 6. SQL Database & Persistence

The game uses an embedded SQLite database (`catan_game.db`):
* **Automatic Auto-Save**: Every single dice roll, placement, building action, trade, and turn transition is written transactionally to the database.
* **Resume Support**: If you exit the game at any moment (via `[QUIT]`, window close, or system restart), relaunching the game will seamlessly restore the exact board state, all players' hands, VP counters, dice roll, and terminal logs.
* **Custom Save Slots**: Click **[SAVE GAME]** to store named checkpoints (e.g., "Friday Game Turn 12") or **[LOAD GAME]** to resume any previous match.

---

## 7. Project Architecture

```
D:\Games\PROJECT CATAN\
├── main.py              # Application entry point & DPI bootstrap
├── catan_gui.py         # Tkinter GUI, DOS widgets, canvas renderer & trade dialogs
├── catan_model.py       # Core Catan engine, player states & game rules
├── catan_board.py       # 19-hex board graph topology, coordinates & geometry
├── catan_db.py          # SQLite persistence layer for save/resume
├── catan_constants.py   # DOS palette, hexagon colors, building costs & fonts
├── test_catan.py        # Automated unit and integration test suite
├── run_game.bat         # Windows batch launcher
└── README.md            # Comprehensive game manual and documentation
```

---

*Enjoy Settlers of Catan in authentic retro DOS style!*
