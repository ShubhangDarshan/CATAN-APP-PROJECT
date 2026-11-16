"""
catan_db.py - SQLite Database persistence layer for Catan DOS-Box Edition.
Allows seamless saving, resuming, and restoring games across application restarts.
"""

import sqlite3
import json
import os
import datetime
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional, Any
from catan_constants import (
    WOOD, BRICK, SHEEP, WHEAT, ORE, DESERT,
    PLAYER_NAMES
)
from catan_board import CatanBoard, HexTile
from catan_model import CatanGame, Player

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catan_game.db")


class CatanDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Games meta-table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                phase TEXT NOT NULL,
                current_player_idx INTEGER NOT NULL,
                turn_number INTEGER NOT NULL,
                dice1 INTEGER NOT NULL,
                dice2 INTEGER NOT NULL,
                has_rolled INTEGER NOT NULL,
                setup_step_index INTEGER NOT NULL,
                setup_sub_action TEXT NOT NULL,
                setup_last_settlement_vid INTEGER,
                robber_hex_id INTEGER NOT NULL,
                winner_id INTEGER,
                seed INTEGER,
                dev_deck TEXT NOT NULL,
                bank_wood INTEGER DEFAULT 19,
                bank_brick INTEGER DEFAULT 19,
                bank_sheep INTEGER DEFAULT 19,
                bank_wheat INTEGER DEFAULT 19,
                bank_ore INTEGER DEFAULT 19
            );
            """)

            # Migration: Ensure bank columns exist if table was already created
            cursor.execute("PRAGMA table_info(games)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            for r in [WOOD, BRICK, SHEEP, WHEAT, ORE]:
                col_name = f"bank_{r}"
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE games ADD COLUMN {col_name} INTEGER DEFAULT 19")

            # Hexes table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hexes (
                game_id INTEGER NOT NULL,
                hex_id INTEGER NOT NULL,
                row INTEGER NOT NULL,
                col INTEGER NOT NULL,
                resource TEXT NOT NULL,
                number_token INTEGER,
                has_robber INTEGER NOT NULL,
                PRIMARY KEY (game_id, hex_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            );
            """)

            # Vertices table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vertices (
                game_id INTEGER NOT NULL,
                vertex_id INTEGER NOT NULL,
                owner_id INTEGER,
                building_type TEXT,
                PRIMARY KEY (game_id, vertex_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            );
            """)

            # Edges table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                game_id INTEGER NOT NULL,
                edge_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                PRIMARY KEY (game_id, edge_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            );
            """)

            # Players table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color_name TEXT NOT NULL,
                wood INTEGER NOT NULL,
                brick INTEGER NOT NULL,
                sheep INTEGER NOT NULL,
                wheat INTEGER NOT NULL,
                ore INTEGER NOT NULL,
                dev_cards TEXT NOT NULL,
                played_knights INTEGER NOT NULL,
                has_longest_road INTEGER NOT NULL,
                has_largest_army INTEGER NOT NULL,
                PRIMARY KEY (game_id, player_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            );
            """)

            # Game Logs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                log_order INTEGER NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            );
            """)

            # Metadata table (e.g., active_game_id)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)

            conn.commit()

    def save_game(self, game: CatanGame, slot_name: str = "Auto-Save", game_id: Optional[int] = None) -> int:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if updating an existing record or creating a new one
            if game_id is not None:
                cursor.execute("SELECT game_id FROM games WHERE game_id = ?", (game_id,))
                row = cursor.fetchone()
                if row:
                    target_id = game_id
                    cursor.execute("""
                    UPDATE games SET
                        name = ?, updated_at = ?, phase = ?, current_player_idx = ?,
                        turn_number = ?, dice1 = ?, dice2 = ?, has_rolled = ?,
                        setup_step_index = ?, setup_sub_action = ?, setup_last_settlement_vid = ?,
                        robber_hex_id = ?, winner_id = ?, seed = ?, dev_deck = ?,
                        bank_wood = ?, bank_brick = ?, bank_sheep = ?, bank_wheat = ?, bank_ore = ?
                    WHERE game_id = ?
                    """, (
                        slot_name, now_str, game.phase, game.current_player_idx,
                        game.turn_number, game.dice[0], game.dice[1], 1 if game.has_rolled else 0,
                        game.setup_step_index, game.setup_sub_action, game.setup_last_settlement_vid,
                        game.robber_hex_id, game.winner.player_id if game.winner else None,
                        game.seed, json.dumps(game.dev_deck),
                        game.bank[WOOD], game.bank[BRICK], game.bank[SHEEP], game.bank[WHEAT], game.bank[ORE],
                        target_id
                    ))
                    # Clear child tables to overwrite
                    cursor.execute("DELETE FROM hexes WHERE game_id = ?", (target_id,))
                    cursor.execute("DELETE FROM vertices WHERE game_id = ?", (target_id,))
                    cursor.execute("DELETE FROM edges WHERE game_id = ?", (target_id,))
                    cursor.execute("DELETE FROM players WHERE game_id = ?", (target_id,))
                    cursor.execute("DELETE FROM game_logs WHERE game_id = ?", (target_id,))
                else:
                    target_id = None
            else:
                target_id = None

            if target_id is None:
                cursor.execute("""
                INSERT INTO games (
                    name, created_at, updated_at, phase, current_player_idx,
                    turn_number, dice1, dice2, has_rolled,
                    setup_step_index, setup_sub_action, setup_last_settlement_vid,
                    robber_hex_id, winner_id, seed, dev_deck,
                    bank_wood, bank_brick, bank_sheep, bank_wheat, bank_ore
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    slot_name, now_str, now_str, game.phase, game.current_player_idx,
                    game.turn_number, game.dice[0], game.dice[1], 1 if game.has_rolled else 0,
                    game.setup_step_index, game.setup_sub_action, game.setup_last_settlement_vid,
                    game.robber_hex_id, game.winner.player_id if game.winner else None,
                    game.seed, json.dumps(game.dev_deck),
                    game.bank[WOOD], game.bank[BRICK], game.bank[SHEEP], game.bank[WHEAT], game.bank[ORE]
                ))
                target_id = cursor.lastrowid

            # Save Hexes
            for hid, htile in game.board.hexes.items():
                cursor.execute("""
                INSERT INTO hexes (game_id, hex_id, row, col, resource, number_token, has_robber)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_id, hid, htile.row, htile.col, htile.resource,
                    htile.number_token, 1 if htile.has_robber else 0
                ))

            # Save Vertices (occupied ones)
            for vid, b in game.vertex_buildings.items():
                cursor.execute("""
                INSERT INTO vertices (game_id, vertex_id, owner_id, building_type)
                VALUES (?, ?, ?, ?)
                """, (target_id, vid, b["owner"], b["type"]))

            # Save Edges (roads)
            for eid, owner in game.edge_roads.items():
                cursor.execute("""
                INSERT INTO edges (game_id, edge_id, owner_id)
                VALUES (?, ?, ?)
                """, (target_id, eid, owner))

            # Save Players
            for p in game.players:
                cursor.execute("""
                INSERT INTO players (
                    game_id, player_id, name, color_name, wood, brick, sheep, wheat, ore,
                    dev_cards, played_knights, has_longest_road, has_largest_army
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_id, p.player_id, p.name, p.color_name,
                    p.resources[WOOD], p.resources[BRICK], p.resources[SHEEP],
                    p.resources[WHEAT], p.resources[ORE], json.dumps(p.dev_cards),
                    p.played_knights, 1 if p.has_longest_road else 0, 1 if p.has_largest_army else 0
                ))

            # Save Logs (last 50 logs)
            recent_logs = game.logs[-50:]
            for idx, msg in enumerate(recent_logs):
                cursor.execute("""
                INSERT INTO game_logs (game_id, log_order, message)
                VALUES (?, ?, ?)
                """, (target_id, idx, msg))

            # Update active game ID in metadata
            cursor.execute("""
            INSERT INTO metadata (key, value) VALUES ('active_game_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (str(target_id),))

            conn.commit()
            return target_id

    def load_game(self, game_id: Optional[int] = None) -> Optional[CatanGame]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Determine game_id
            if game_id is None:
                cursor.execute("SELECT value FROM metadata WHERE key = 'active_game_id'")
                row = cursor.fetchone()
                if row:
                    game_id = int(row["value"])
                else:
                    # Fallback to most recent game
                    cursor.execute("SELECT game_id FROM games ORDER BY updated_at DESC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        game_id = row["game_id"]
                    else:
                        return None

            # Load game metadata
            cursor.execute("SELECT * FROM games WHERE game_id = ?", (game_id,))
            g_row = cursor.fetchone()
            if not g_row:
                return None

            # Reconstruct CatanBoard using the saved hexes
            board = CatanBoard(radius=52.0, randomize=False)
            cursor.execute("SELECT * FROM hexes WHERE game_id = ? ORDER BY hex_id ASC", (game_id,))
            hex_rows = cursor.fetchall()
            for h in hex_rows:
                hid = h["hex_id"]
                if hid in board.hexes:
                    tile = board.hexes[hid]
                    tile.resource = h["resource"]
                    tile.number_token = h["number_token"]
                    tile.has_robber = bool(h["has_robber"])

            robber_hid = g_row["robber_hex_id"]
            board.robber_hex_id = robber_hid
            for hid, tile in board.hexes.items():
                tile.has_robber = (hid == robber_hid)

            # Create game instance
            game = CatanGame(board=board, seed=g_row["seed"])
            game.phase = g_row["phase"]
            game.current_player_idx = g_row["current_player_idx"]
            game.turn_number = g_row["turn_number"]
            game.dice = (g_row["dice1"], g_row["dice2"])
            game.has_rolled = bool(g_row["has_rolled"])
            game.setup_step_index = g_row["setup_step_index"]
            game.setup_sub_action = g_row["setup_sub_action"]
            game.setup_last_settlement_vid = g_row["setup_last_settlement_vid"]
            game.robber_hex_id = robber_hid
            game.dev_deck = json.loads(g_row["dev_deck"])

            # Load bank inventory if present
            for r in [WOOD, BRICK, SHEEP, WHEAT, ORE]:
                col = f"bank_{r}"
                if col in g_row.keys():
                    game.bank[r] = g_row[col]

            # Load Players
            cursor.execute("SELECT * FROM players WHERE game_id = ? ORDER BY player_id ASC", (game_id,))
            p_rows = cursor.fetchall()
            game.players = []
            for pr in p_rows:
                p = Player(pr["player_id"], pr["name"], pr["color_name"])
                p.resources[WOOD] = pr["wood"]
                p.resources[BRICK] = pr["brick"]
                p.resources[SHEEP] = pr["sheep"]
                p.resources[WHEAT] = pr["wheat"]
                p.resources[ORE] = pr["ore"]
                p.dev_cards = json.loads(pr["dev_cards"])
                p.played_knights = pr["played_knights"]
                p.has_longest_road = bool(pr["has_longest_road"])
                p.has_largest_army = bool(pr["has_largest_army"])
                game.players.append(p)

            # Load Vertices
            game.vertex_buildings = {}
            cursor.execute("SELECT * FROM vertices WHERE game_id = ?", (game_id,))
            for vr in cursor.fetchall():
                vid = vr["vertex_id"]
                owner = vr["owner_id"]
                btype = vr["building_type"]
                game.vertex_buildings[vid] = {"owner": owner, "type": btype}
                if btype == "city":
                    game.players[owner].city_vids.append(vid)
                else:
                    game.players[owner].settlement_vids.append(vid)

            # Load Edges (Roads)
            game.edge_roads = {}
            cursor.execute("SELECT * FROM edges WHERE game_id = ?", (game_id,))
            for er in cursor.fetchall():
                eid = er["edge_id"]
                owner = er["owner_id"]
                game.edge_roads[eid] = owner
                game.players[owner].road_eids.append(eid)

            # Load Winner if any
            if g_row["winner_id"] is not None:
                game.winner = game.players[g_row["winner_id"]]

            # Load Logs
            cursor.execute("SELECT * FROM game_logs WHERE game_id = ? ORDER BY log_order ASC", (game_id,))
            log_rows = cursor.fetchall()
            if log_rows:
                game.logs = [lr["message"] for lr in log_rows]

            return game

    def list_saved_games(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT game_id, name, created_at, updated_at, phase, current_player_idx, turn_number
            FROM games ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def has_resumable_game(self) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS cnt FROM games")
            row = cursor.fetchone()
            return row["cnt"] > 0

    def delete_saved_game(self, game_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
            conn.commit()
