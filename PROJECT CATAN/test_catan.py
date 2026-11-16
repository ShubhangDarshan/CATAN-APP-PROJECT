"""
test_catan.py - Comprehensive Unit & Integration Test Suite for Catan DOS-Box Edition.
Tests geometry, rules, building constraints, trading initiation restrictions, and database persistence.
"""

import os
import unittest
from catan_constants import (
    BRICK, SHEEP, WOOD, WHEAT, ORE, DESERT,
    HEX_COLORS, PLAYER_COLORS, PROBABILITY_DOTS,
    COST_ROAD, COST_SETTLEMENT, COST_CITY
)
from catan_board import CatanBoard
from catan_model import CatanGame, Player
from catan_db import CatanDatabase


class TestCatanConstants(unittest.TestCase):
    def test_hex_colors(self):
        # Verify required hex colors
        self.assertEqual(HEX_COLORS[BRICK], "#C0392B")      # RED
        self.assertEqual(HEX_COLORS[SHEEP], "#2ECC71")      # LIGHT GREEN
        self.assertEqual(HEX_COLORS[WOOD], "#145A32")       # DARK GREEN
        self.assertEqual(HEX_COLORS[WHEAT], "#F1C40F")      # YELLOW
        self.assertEqual(HEX_COLORS[ORE], "#7F8C8D")        # GREY
        self.assertEqual(HEX_COLORS[DESERT], "#D2B48C")     # KHAKI

    def test_player_colors(self):
        # House colors: RED, BLUE, WHITE, ORANGE
        for color_name in ["RED", "BLUE", "WHITE", "ORANGE"]:
            self.assertIn(color_name, PLAYER_COLORS)
            # Each road, house, or city must have a white outline
            self.assertEqual(PLAYER_COLORS[color_name]["outline"], "#FFFFFF")

    def test_probability_dots(self):
        # 6 and 8 have highest (5 dots), 2 and 12 lowest (1 dot)
        self.assertEqual(PROBABILITY_DOTS[6], 5)
        self.assertEqual(PROBABILITY_DOTS[8], 5)
        self.assertEqual(PROBABILITY_DOTS[2], 1)
        self.assertEqual(PROBABILITY_DOTS[12], 1)
        self.assertEqual(PROBABILITY_DOTS[3], 2)
        self.assertEqual(PROBABILITY_DOTS[11], 2)
        self.assertEqual(PROBABILITY_DOTS[4], 3)
        self.assertEqual(PROBABILITY_DOTS[10], 3)
        self.assertEqual(PROBABILITY_DOTS[5], 4)
        self.assertEqual(PROBABILITY_DOTS[9], 4)


class TestCatanBoard(unittest.TestCase):
    def setUp(self):
        self.board = CatanBoard(radius=52.0, randomize=True, seed=42)

    def test_board_topology(self):
        # 19 Hexes, 54 Vertices, 72 Edges
        self.assertEqual(len(self.board.hexes), 19)
        self.assertEqual(len(self.board.vertices), 54)
        self.assertEqual(len(self.board.edges), 72)

    def test_desert_and_robber(self):
        desert_tiles = [h for h in self.board.hexes.values() if h.resource == DESERT]
        self.assertEqual(len(desert_tiles), 1)
        desert = desert_tiles[0]
        self.assertIsNone(desert.number_token)
        self.assertTrue(desert.has_robber)
        self.assertEqual(desert.color, "#D2B48C")  # Khaki

    def test_number_tokens_count(self):
        tokens = [h.number_token for h in self.board.hexes.values() if h.number_token is not None]
        self.assertEqual(len(tokens), 18)
        # Check standard Catan frequency of 6 and 8
        self.assertEqual(tokens.count(6), 2)
        self.assertEqual(tokens.count(8), 2)
        self.assertEqual(tokens.count(2), 1)
        self.assertEqual(tokens.count(12), 1)


class TestCatanGameRules(unittest.TestCase):
    def setUp(self):
        self.game = CatanGame(seed=101)

    def test_initial_phase(self):
        self.assertEqual(self.game.phase, CatanGame.PHASE_SETUP_1)
        self.assertEqual(self.game.current_player_idx, 0)
        self.assertEqual(self.game.current_player.name, "RED")

    def test_quick_setup(self):
        self.game.quick_auto_setup()
        self.assertEqual(self.game.phase, CatanGame.PHASE_MAIN_ROLL)
        self.assertEqual(self.game.current_player_idx, 0)
        # All 4 players should have 2 settlements and 2 roads
        for p in self.game.players:
            self.assertEqual(len(p.settlement_vids), 2)
            self.assertEqual(len(p.road_eids), 2)
            self.assertGreater(p.total_resources, 0)  # Received starting resources from 2nd settlement

    def test_distance_rule(self):
        # Cannot place two settlements on adjacent vertices
        v0 = 0
        adj_v = self.game.board.vertices[v0].adjacent_vertices[0]
        self.game.vertex_buildings[v0] = {"owner": 0, "type": "settlement"}

        valid, msg = self.game.can_place_settlement_setup(1, adj_v)
        self.assertFalse(valid)
        self.assertIn("Distance Rule", msg)

    def test_dice_roll_and_production(self):
        self.game.quick_auto_setup()
        d1, d2, total = self.game.roll_dice()
        self.assertTrue(1 <= d1 <= 6)
        self.assertTrue(1 <= d2 <= 6)
        self.assertEqual(total, d1 + d2)
        if total != 7:
            self.assertEqual(self.game.phase, CatanGame.PHASE_MAIN_ACTION)
        else:
            self.assertIn(self.game.phase, (CatanGame.PHASE_ROBBER_DISCARD, CatanGame.PHASE_ROBBER_MOVE))

    def test_trading_initiation_active_player_only(self):
        """
        User requirement:
        "The only change I would like to make is to make trading initiation available
        to only the person whose turn is currently being played."
        """
        self.game.quick_auto_setup()
        self.game.phase = CatanGame.PHASE_MAIN_ACTION
        self.game.current_player_idx = 0  # RED is active

        # Active player (RED) can initiate trade
        self.assertTrue(self.game.can_initiate_trade(0))

        # Other players (BLUE, WHITE, ORANGE) CANNOT initiate trade
        self.assertFalse(self.game.can_initiate_trade(1))
        self.assertFalse(self.game.can_initiate_trade(2))
        self.assertFalse(self.game.can_initiate_trade(3))

        # Test trade execution
        self.game.players[0].resources[WOOD] = 3
        self.game.players[1].resources[WOOD] = 0
        self.game.players[1].resources[ORE] = 2

        ok, msg = self.game.execute_trade(0, 1, {WOOD: 2}, {ORE: 1})
        self.assertTrue(ok)
        self.assertEqual(self.game.players[0].resources[WOOD], 1)
        self.assertEqual(self.game.players[0].resources[ORE], 1)
        self.assertEqual(self.game.players[1].resources[WOOD], 2)
        self.assertEqual(self.game.players[1].resources[ORE], 1)

        # Attempt trade by non-active player must fail
        ok2, msg2 = self.game.execute_trade(1, 0, {ORE: 1}, {WOOD: 1})
        self.assertFalse(ok2)
        self.assertIn("ONLY allowed by the active player", msg2)

    def test_resource_bank_initialization(self):
        # 95 resources total, 19 of each
        fresh_game = CatanGame()
        self.assertEqual(fresh_game.total_bank_cards, 95)
        for r in [WOOD, BRICK, SHEEP, WHEAT, ORE]:
            self.assertEqual(fresh_game.bank[r], 19)

    def test_bank_trade_standard_4_to_1(self):
        self.game.quick_auto_setup()
        self.game.phase = CatanGame.PHASE_MAIN_ACTION
        self.game.current_player_idx = 0

        # Give active player 4 wood
        self.game.players[0].resources[WOOD] = 4
        self.game.bank[ORE] = 10
        bank_wood_before = self.game.bank[WOOD]
        bank_ore_before = self.game.bank[ORE]

        # Standard bank trade without ports: ratio is 4:1
        ratio, desc = self.game.get_best_bank_ratio(0, WOOD)
        # If player happened to hit a 3:1 or 2:1 port in auto-setup, ratio might be 3 or 2
        # Otherwise standard is 4
        give_amt = ratio
        ok, msg = self.game.execute_bank_trade(0, WOOD, give_amt, ORE)
        self.assertTrue(ok)
        self.assertEqual(self.game.players[0].resources[WOOD], 4 - give_amt)
        self.assertGreaterEqual(self.game.players[0].resources[ORE], 1)
        self.assertEqual(self.game.bank[WOOD], bank_wood_before + give_amt)
        self.assertEqual(self.game.bank[ORE], bank_ore_before - 1)

    def test_port_trade_specific_and_generic(self):
        # Create fresh game without buildings
        game = CatanGame()
        game.phase = CatanGame.PHASE_MAIN_ACTION
        game.current_player_idx = 0

        # Find a 2:1 brick port vertex and a 3:1 port vertex
        brick_port_vids = [v for v, vert in game.board.vertices.items() if vert.port_type == BRICK]
        generic_port_vids = [v for v, vert in game.board.vertices.items() if vert.port_type == "3:1"]

        self.assertGreater(len(brick_port_vids), 0)
        self.assertGreater(len(generic_port_vids), 0)

        # Before building on port: default is 4:1
        self.assertEqual(game.get_best_bank_ratio(0, BRICK)[0], 4)
        self.assertEqual(game.get_best_bank_ratio(0, WOOD)[0], 4)

        # Build settlement on 2:1 brick port vertex
        b_vid = brick_port_vids[0]
        game.vertex_buildings[b_vid] = {"owner": 0, "type": "settlement"}
        game.players[0].settlement_vids.append(b_vid)

        # Brick should now be 2:1!
        ratio_brick, desc_brick = game.get_best_bank_ratio(0, BRICK)
        self.assertEqual(ratio_brick, 2)
        self.assertIn("2:1", desc_brick)

        # Wood is still 4:1
        ratio_wood, _ = game.get_best_bank_ratio(0, WOOD)
        self.assertEqual(ratio_wood, 4)

        # Now build on 3:1 generic port
        g_vid = generic_port_vids[0]
        game.vertex_buildings[g_vid] = {"owner": 0, "type": "settlement"}
        game.players[0].settlement_vids.append(g_vid)

        # Wood should now unlock 3:1!
        ratio_wood_after, desc_wood = game.get_best_bank_ratio(0, WOOD)
        self.assertEqual(ratio_wood_after, 3)
        self.assertIn("3:1", desc_wood)

        # Brick remains 2:1 (better than 3:1)
        self.assertEqual(game.get_best_bank_ratio(0, BRICK)[0], 2)

        # Test executing 2:1 brick trade with bank
        game.players[0].resources[BRICK] = 2
        game.bank[WHEAT] = 10
        ok, msg = game.execute_bank_trade(0, BRICK, 2, WHEAT)
        self.assertTrue(ok)
        self.assertEqual(game.players[0].resources[BRICK], 0)
        self.assertEqual(game.players[0].resources[WHEAT], 1)


class TestCatanDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_catan.db")
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = CatanDatabase(db_path=self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_save_and_resume_game(self):
        game = CatanGame(seed=999)
        game.quick_auto_setup()
        game.roll_dice()
        game.players[0].resources[WHEAT] = 42
        game.bank[WOOD] = 7
        game.bank[ORE] = 13

        # Save game to database
        saved_id = self.db.save_game(game, slot_name="Test Resume Slot")
        self.assertTrue(self.db.has_resumable_game())

        # Resume / Load game from database
        resumed_game = self.db.load_game(saved_id)
        self.assertIsNotNone(resumed_game)
        self.assertEqual(resumed_game.turn_number, game.turn_number)
        self.assertEqual(resumed_game.current_player_idx, game.current_player_idx)
        self.assertEqual(resumed_game.players[0].resources[WHEAT], 42)
        self.assertEqual(resumed_game.bank[WOOD], 7)
        self.assertEqual(resumed_game.bank[ORE], 13)
        self.assertEqual(len(resumed_game.vertex_buildings), len(game.vertex_buildings))
        self.assertEqual(len(resumed_game.edge_roads), len(game.edge_roads))


if __name__ == "__main__":
    unittest.main()
