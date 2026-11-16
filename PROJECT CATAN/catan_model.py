"""
catan_model.py - Core game state, rules engine, turn phases, and validation for Catan DOS-Box Edition.
"""

import random
from typing import Dict, List, Tuple, Optional, Set, Any
from catan_constants import (
    BRICK, SHEEP, WOOD, WHEAT, ORE, DESERT, RESOURCES, RESOURCE_NAMES,
    PLAYER_NAMES, PLAYER_COLORS,
    COST_ROAD, COST_SETTLEMENT, COST_CITY, COST_DEV_CARD,
    DEV_CARD_DECK, CARD_KNIGHT, CARD_VICTORY_POINT, CARD_ROAD_BUILDING,
    CARD_YEAR_OF_PLENTY, CARD_MONOPOLY, WINNING_VICTORY_POINTS
)
from catan_board import CatanBoard


class Player:
    def __init__(self, player_id: int, name: str, color_name: str):
        self.player_id = player_id
        self.name = name
        self.color_name = color_name
        self.color_info = PLAYER_COLORS[color_name]
        self.resources: Dict[str, int] = {
            WOOD: 0,
            BRICK: 0,
            SHEEP: 0,
            WHEAT: 0,
            ORE: 0,
        }
        self.settlement_vids: List[int] = []
        self.city_vids: List[int] = []
        self.road_eids: List[int] = []

        self.dev_cards: List[str] = []
        self.played_knights: int = 0
        self.has_longest_road: bool = False
        self.has_largest_army: bool = False

    @property
    def total_resources(self) -> int:
        return sum(self.resources.values())

    @property
    def victory_points(self) -> int:
        vp = len(self.settlement_vids) * 1 + len(self.city_vids) * 2
        # VP cards
        vp += sum(1 for c in self.dev_cards if c == CARD_VICTORY_POINT)
        if self.has_longest_road:
            vp += 2
        if self.has_largest_army:
            vp += 2
        return vp

    def can_afford(self, cost: Dict[str, int]) -> bool:
        return all(self.resources.get(res, 0) >= amount for res, amount in cost.items())

    def deduct_cost(self, cost: Dict[str, int]):
        for res, amount in cost.items():
            self.resources[res] = max(0, self.resources.get(res, 0) - amount)

    def add_resources(self, delta: Dict[str, int]):
        for res, amount in delta.items():
            self.resources[res] = self.resources.get(res, 0) + amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "color_name": self.color_name,
            "resources": dict(self.resources),
            "settlements": list(self.settlement_vids),
            "cities": list(self.city_vids),
            "roads": list(self.road_eids),
            "dev_cards": list(self.dev_cards),
            "played_knights": self.played_knights,
            "has_longest_road": self.has_longest_road,
            "has_largest_army": self.has_largest_army,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        p = cls(data["player_id"], data["name"], data["color_name"])
        p.resources = dict(data["resources"])
        p.settlement_vids = list(data.get("settlements", []))
        p.city_vids = list(data.get("cities", []))
        p.road_eids = list(data.get("roads", []))
        p.dev_cards = list(data.get("dev_cards", []))
        p.played_knights = data.get("played_knights", 0)
        p.has_longest_road = data.get("has_longest_road", False)
        p.has_largest_army = data.get("has_largest_army", False)
        return p


class CatanGame:
    # Game Phase Constants
    PHASE_SETUP_1 = "SETUP_1"          # Round 1: P0 -> P1 -> P2 -> P3 (Settlement + Road)
    PHASE_SETUP_2 = "SETUP_2"          # Round 2: P3 -> P2 -> P1 -> P0 (Settlement + Road + starting resources)
    PHASE_MAIN_ROLL = "MAIN_ROLL"      # Active player must roll dice
    PHASE_MAIN_ACTION = "MAIN_ACTION"  # Build, Trade, Dev Cards, End Turn
    PHASE_ROBBER_DISCARD = "ROBBER_DISCARD"
    PHASE_ROBBER_MOVE = "ROBBER_MOVE"
    PHASE_ROBBER_STEAL = "ROBBER_STEAL"
    PHASE_GAME_OVER = "GAME_OVER"

    def __init__(self, board: Optional[CatanBoard] = None, seed: Optional[int] = None):
        self.seed = seed
        self.board = board if board is not None else CatanBoard(randomize=True, seed=seed)
        self.rng = random.Random(seed)

        # 4 Local Pass-and-Play Players
        self.players: List[Player] = [
            Player(0, "RED", "RED"),
            Player(1, "BLUE", "BLUE"),
            Player(2, "WHITE", "WHITE"),
            Player(3, "ORANGE", "ORANGE"),
        ]

        # Board Occupancy
        # vertex_buildings: vertex_id -> {"owner": player_id, "type": "settlement" | "city"}
        self.vertex_buildings: Dict[int, Dict[str, Any]] = {}
        # edge_roads: edge_id -> player_id
        self.edge_roads: Dict[int, int] = {}

        # Dev Cards Deck
        self.dev_deck: List[str] = list(DEV_CARD_DECK)
        self.rng.shuffle(self.dev_deck)

        # Game State
        self.phase: str = self.PHASE_SETUP_1
        self.current_player_idx: int = 0
        self.turn_number: int = 1
        self.dice: Tuple[int, int] = (1, 1)
        self.has_rolled: bool = False

        # Setup sequence state: list of player indices
        # Round 1: 0, 1, 2, 3
        # Round 2: 3, 2, 1, 0
        self.setup_order: List[int] = [0, 1, 2, 3, 3, 2, 1, 0]
        self.setup_step_index: int = 0
        self.setup_sub_action: str = "SETTLEMENT"  # "SETTLEMENT" then "ROAD"
        self.setup_last_settlement_vid: Optional[int] = None

        # Robber resolution state
        self.robber_hex_id: int = self.board.robber_hex_id
        self.robber_discard_queue: List[int] = []
        self.robber_potential_victims: List[int] = []

        # Resource Bank (Total 95 resource cards, 19 of each type)
        self.bank: Dict[str, int] = {
            WOOD: 19,
            BRICK: 19,
            SHEEP: 19,
            WHEAT: 19,
            ORE: 19,
        }

        # Action Log History
        self.logs: List[str] = [
            "*** WELCOME TO SETTLERS OF CATAN [DOS-BOX EDITION] ***",
            "Snake Setup Round 1: Player RED, place your first Settlement."
        ]
        self.winner: Optional[Player] = None

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_idx]

    @property
    def total_bank_cards(self) -> int:
        return sum(self.bank.values())

    def log(self, message: str):
        self.logs.append(message)

    # -------------------------------------------------------------------------
    # SETUP PHASE METHODS
    # -------------------------------------------------------------------------
    def place_setup_settlement(self, vertex_id: int) -> Tuple[bool, str]:
        if self.phase not in (self.PHASE_SETUP_1, self.PHASE_SETUP_2):
            return False, "Not in setup phase."
        if self.setup_sub_action != "SETTLEMENT":
            return False, "You must place a road attached to your settlement first."

        p = self.current_player
        valid, msg = self.can_place_settlement_setup(p.player_id, vertex_id)
        if not valid:
            return False, msg

        # Place settlement
        self.vertex_buildings[vertex_id] = {"owner": p.player_id, "type": "settlement"}
        p.settlement_vids.append(vertex_id)
        self.setup_last_settlement_vid = vertex_id
        self.setup_sub_action = "ROAD"

        # If in Round 2, grant starting resources from adjacent hexes (from Bank)!
        if self.phase == self.PHASE_SETUP_2:
            received: Dict[str, int] = {}
            for hid in self.board.vertices[vertex_id].adjacent_hexes:
                res = self.board.hexes[hid].resource
                if res != DESERT:
                    if self.bank.get(res, 0) > 0:
                        self.bank[res] -= 1
                        p.resources[res] = p.resources.get(res, 0) + 1
                        received[res] = received.get(res, 0) + 1
            rec_str = ", ".join(f"{count} {RESOURCE_NAMES[r]}" for r, count in received.items()) or "None"
            self.log(f"{p.name} placed 2nd Settlement at #{vertex_id}. Received: {rec_str}")
        else:
            self.log(f"{p.name} placed Settlement at #{vertex_id}.")

        self.log(f"{p.name}, now place a Road adjacent to this settlement.")
        return True, "Settlement placed! Now place an adjacent road."

    def place_setup_road(self, edge_id: int) -> Tuple[bool, str]:
        if self.phase not in (self.PHASE_SETUP_1, self.PHASE_SETUP_2):
            return False, "Not in setup phase."
        if self.setup_sub_action != "ROAD":
            return False, "You must place a settlement first."

        p = self.current_player
        valid, msg = self.can_place_road_setup(p.player_id, edge_id)
        if not valid:
            return False, msg

        # Place road
        self.edge_roads[edge_id] = p.player_id
        p.road_eids.append(edge_id)
        self.log(f"{p.name} placed Road at Edge #{edge_id}.")

        # Advance setup step
        self.setup_step_index += 1
        if self.setup_step_index < len(self.setup_order):
            next_p_idx = self.setup_order[self.setup_step_index]
            self.current_player_idx = next_p_idx
            self.setup_sub_action = "SETTLEMENT"
            self.setup_last_settlement_vid = None

            if self.setup_step_index >= 4:
                self.phase = self.PHASE_SETUP_2
                self.log(f">>> Setup Round 2: {self.current_player.name}, place your 2nd Settlement.")
            else:
                self.log(f">>> Setup Round 1: {self.current_player.name}, place your Settlement.")
        else:
            # Setup Complete! Transition to Main Game Phase
            self.phase = self.PHASE_MAIN_ROLL
            self.current_player_idx = 0
            self.turn_number = 1
            self.has_rolled = False
            self.log("==================================================")
            self.log("SETUP COMPLETE! THE SETTLERS OF CATAN BEGINS!")
            self.log(f">>> TURN 1: {self.current_player.name}'s turn. Please ROLL DICE (Press [R]).")

        return True, "Road placed successfully!"

    def can_place_settlement_setup(self, player_id: int, vertex_id: int) -> Tuple[bool, str]:
        if vertex_id in self.vertex_buildings:
            return False, "Intersection is already occupied!"
        # Distance rule: adjacent vertices must be empty
        for neighbor_vid in self.board.vertices[vertex_id].adjacent_vertices:
            if neighbor_vid in self.vertex_buildings:
                return False, "Distance Rule: Cannot build within 1 road of another building!"
        return True, "Valid position."

    def can_place_road_setup(self, player_id: int, edge_id: int) -> Tuple[bool, str]:
        if edge_id in self.edge_roads:
            return False, "Edge already has a road!"
        if self.setup_last_settlement_vid is None:
            return False, "No active settlement to connect to."
        edge = self.board.edges[edge_id]
        if edge.v1 != self.setup_last_settlement_vid and edge.v2 != self.setup_last_settlement_vid:
            return False, "Road must connect directly to the settlement you just built!"
        return True, "Valid position."

    # -------------------------------------------------------------------------
    # MAIN GAME TURN FLOW & DICE ROLL
    # -------------------------------------------------------------------------
    def roll_dice(self) -> Tuple[int, int, int]:
        """Rolls 2d6 and returns (die1, die2, total). Distributes resources or triggers robber."""
        if self.phase != self.PHASE_MAIN_ROLL:
            raise ValueError("Dice can only be rolled during the roll phase.")

        d1 = self.rng.randint(1, 6)
        d2 = self.rng.randint(1, 6)
        total = d1 + d2
        self.dice = (d1, d2)
        self.has_rolled = True

        p = self.current_player
        self.log(f"{p.name} rolled [{d1}] + [{d2}] = {total}!")

        if total == 7:
            self._handle_roll_seven()
        else:
            self._distribute_resources(total)
            self.phase = self.PHASE_MAIN_ACTION

        return d1, d2, total

    def _handle_roll_seven(self):
        self.log(">>> A 7 WAS ROLLED! THE ROBBER IS ACTIVATED! <<<")
        # Check players who have > 7 cards
        self.robber_discard_queue = []
        for pl in self.players:
            if pl.total_resources > 7:
                self.robber_discard_queue.append(pl.player_id)

        if self.robber_discard_queue:
            self.phase = self.PHASE_ROBBER_DISCARD
            self._process_next_discard()
        else:
            self.phase = self.PHASE_ROBBER_MOVE
            self.log(f"{self.current_player.name}, click any hexagon to move the Robber.")

    def _process_next_discard(self):
        if not self.robber_discard_queue:
            self.phase = self.PHASE_ROBBER_MOVE
            self.log(f"{self.current_player.name}, click any hexagon to move the Robber.")
            return

        pid = self.robber_discard_queue[0]
        pl = self.players[pid]
        discard_count = pl.total_resources // 2
        # Automatically or promptingly discard cards
        self._auto_discard(pl, discard_count)
        self.robber_discard_queue.pop(0)
        self._process_next_discard()

    def _auto_discard(self, player: Player, count: int):
        """Discards cards proportionally/fairly when 7 is rolled, returning them to the Bank."""
        discarded: Dict[str, int] = {}
        for _ in range(count):
            available = [r for r, amt in player.resources.items() if amt > 0]
            if not available:
                break
            chosen = self.rng.choice(available)
            player.resources[chosen] -= 1
            discarded[chosen] = discarded.get(chosen, 0) + 1
            self.bank[chosen] += 1
        d_str = ", ".join(f"{cnt} {RESOURCE_NAMES[r]}" for r, cnt in discarded.items())
        self.log(f"Robber penalty: {player.name} had >7 cards and discarded {count} cards to Bank: {d_str}")

    def move_robber(self, target_hex_id: int) -> Tuple[bool, str]:
        if self.phase != self.PHASE_ROBBER_MOVE:
            return False, "Not in Robber movement phase."
        if target_hex_id == self.robber_hex_id:
            return False, "The Robber must move to a different hexagon!"
        if target_hex_id not in self.board.hexes:
            return False, "Invalid hexagon."

        # Move robber
        old_hex = self.board.hexes[self.robber_hex_id]
        old_hex.has_robber = False
        new_hex = self.board.hexes[target_hex_id]
        new_hex.has_robber = True
        self.robber_hex_id = target_hex_id

        p = self.current_player
        self.log(f"{p.name} relocated the Robber to Hex #{target_hex_id} ({RESOURCE_NAMES[new_hex.resource]}).")

        # Find potential victims (other players with settlements/cities on this hex)
        victims = set()
        for vid in new_hex.vertex_ids:
            if vid in self.vertex_buildings:
                owner = self.vertex_buildings[vid]["owner"]
                if owner != p.player_id and self.players[owner].total_resources > 0:
                    victims.add(owner)

        self.robber_potential_victims = list(victims)
        if self.robber_potential_victims:
            # If exactly 1 victim, steal automatically from them
            if len(self.robber_potential_victims) == 1:
                victim_id = self.robber_potential_victims[0]
                self.steal_card(victim_id)
            else:
                self.phase = self.PHASE_ROBBER_STEAL
                victim_names = ", ".join(self.players[v].name for v in self.robber_potential_victims)
                self.log(f"Choose an opponent to steal 1 resource from: [{victim_names}]")
                return True, f"Robber moved! Choose victim: {victim_names}"
        else:
            self.log("No opponents adjacent with cards to steal.")
            self.phase = self.PHASE_MAIN_ACTION

        return True, "Robber moved successfully!"

    def steal_card(self, victim_id: int) -> Tuple[bool, str]:
        if victim_id not in self.robber_potential_victims:
            return False, "Invalid victim choice."

        victim = self.players[victim_id]
        available_res = []
        for r, amt in victim.resources.items():
            available_res.extend([r] * amt)

        if not available_res:
            self.log(f"{victim.name} has no cards to steal.")
            self.phase = self.PHASE_MAIN_ACTION
            return True, "Victim had no cards."

        stolen = self.rng.choice(available_res)
        victim.resources[stolen] -= 1
        self.current_player.resources[stolen] += 1
        self.log(f"{self.current_player.name} stole 1 random resource card from {victim.name}!")
        self.phase = self.PHASE_MAIN_ACTION
        return True, f"Stole 1 resource from {victim.name}."

    def _distribute_resources(self, roll_number: int):
        """Distributes resources to all settlements (1) and cities (2) for the roll number from the Bank."""
        total_demand: Dict[str, int] = {}
        demands: Dict[str, List[Tuple[int, int]]] = {}

        for hid, htile in self.board.hexes.items():
            if htile.number_token == roll_number:
                if htile.has_robber:
                    self.log(f"Hex #{hid} ({RESOURCE_NAMES[htile.resource]}) is blocked by the ROBBER! No yield.")
                    continue
                res = htile.resource
                for vid in htile.vertex_ids:
                    if vid in self.vertex_buildings:
                        b = self.vertex_buildings[vid]
                        owner = b["owner"]
                        yield_amt = 2 if b["type"] == "city" else 1
                        total_demand[res] = total_demand.get(res, 0) + yield_amt
                        demands.setdefault(res, []).append((owner, yield_amt))

        gains_per_player: Dict[int, Dict[str, int]] = {i: {} for i in range(4)}
        for res, entries in demands.items():
            needed = total_demand[res]
            avail = self.bank.get(res, 0)
            if avail >= needed:
                self.bank[res] -= needed
                for pid, amt in entries:
                    self.players[pid].resources[res] += amt
                    gains_per_player[pid][res] = gains_per_player[pid].get(res, 0) + amt
            else:
                self.log(f"BANK SHORTAGE: Only {avail} {RESOURCE_NAMES[res]} in Bank (needed {needed})! No {RESOURCE_NAMES[res]} distributed on this roll.")

        # Log summary of production
        any_yield = False
        for pid, gains in gains_per_player.items():
            if gains:
                any_yield = True
                pl = self.players[pid]
                summary = ", ".join(f"{amt} {RESOURCE_NAMES[r]}" for r, amt in gains.items())
                self.log(f"+ {pl.name} received: {summary}")
        if not any_yield and not any(total_demand.values()):
            self.log(f"No settlements or cities produced resources on {roll_number}.")

    # -------------------------------------------------------------------------
    # MAIN ACTIONS: BUILDING & BUYING
    # -------------------------------------------------------------------------
    def can_build_road(self, player_id: int, edge_id: int) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Not in action phase."
        if player_id != self.current_player_idx:
            return False, "It is not your turn!"
        if edge_id in self.edge_roads:
            return False, "Road already exists here!"
        p = self.players[player_id]
        if not p.can_afford(COST_ROAD):
            return False, "Cannot afford Road (Cost: 1 Wood, 1 Brick)."
        if len(p.road_eids) >= 15:
            return False, "Maximum 15 roads built."

        # Must connect to an existing road, settlement, or city of this player
        edge = self.board.edges[edge_id]
        connected = False

        for vid in (edge.v1, edge.v2):
            if vid in self.vertex_buildings and self.vertex_buildings[vid]["owner"] == player_id:
                connected = True
                break
            # Or connected to another of player's roads, provided no enemy settlement blocks it
            is_enemy_building = (vid in self.vertex_buildings and self.vertex_buildings[vid]["owner"] != player_id)
            if not is_enemy_building:
                for adj_eid in self.board.vertices[vid].adjacent_edges:
                    if adj_eid in self.edge_roads and self.edge_roads[adj_eid] == player_id:
                        connected = True
                        break
            if connected:
                break

        if not connected:
            return False, "Road must connect to your existing roads or settlements!"
        return True, "Valid road placement."

    def build_road(self, player_id: int, edge_id: int) -> Tuple[bool, str]:
        valid, msg = self.can_build_road(player_id, edge_id)
        if not valid:
            return False, msg

        p = self.players[player_id]
        p.deduct_cost(COST_ROAD)
        for r, amt in COST_ROAD.items():
            self.bank[r] += amt
        self.edge_roads[edge_id] = player_id
        p.road_eids.append(edge_id)
        self.log(f"{p.name} built a Road at Edge #{edge_id}.")

        self._check_longest_road()
        self._check_victory()
        return True, "Road built!"

    def can_build_settlement(self, player_id: int, vertex_id: int) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Not in action phase."
        if player_id != self.current_player_idx:
            return False, "It is not your turn!"
        if vertex_id in self.vertex_buildings:
            return False, "Intersection already occupied!"
        p = self.players[player_id]
        if not p.can_afford(COST_SETTLEMENT):
            return False, "Cannot afford Settlement (Cost: 1 Wood, 1 Brick, 1 Sheep, 1 Wheat)."
        if len(p.settlement_vids) >= 5:
            return False, "Maximum 5 settlements built."

        # Distance rule
        for n_vid in self.board.vertices[vertex_id].adjacent_vertices:
            if n_vid in self.vertex_buildings:
                return False, "Distance Rule: Cannot build within 1 road of another building!"

        # Must connect to own road
        connected = False
        for eid in self.board.vertices[vertex_id].adjacent_edges:
            if eid in self.edge_roads and self.edge_roads[eid] == player_id:
                connected = True
                break
        if not connected:
            return False, "Settlement must connect to one of your roads!"

        return True, "Valid settlement placement."

    def build_settlement(self, player_id: int, vertex_id: int) -> Tuple[bool, str]:
        valid, msg = self.can_build_settlement(player_id, vertex_id)
        if not valid:
            return False, msg

        p = self.players[player_id]
        p.deduct_cost(COST_SETTLEMENT)
        for r, amt in COST_SETTLEMENT.items():
            self.bank[r] += amt
        self.vertex_buildings[vertex_id] = {"owner": player_id, "type": "settlement"}
        p.settlement_vids.append(vertex_id)
        self.log(f"{p.name} built a Settlement at Intersection #{vertex_id}! (+1 Victory Point)")

        self._check_victory()
        return True, "Settlement built!"

    def can_build_city(self, player_id: int, vertex_id: int) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Not in action phase."
        if player_id != self.current_player_idx:
            return False, "It is not your turn!"
        if vertex_id not in self.vertex_buildings:
            return False, "You must upgrade an existing settlement."
        b = self.vertex_buildings[vertex_id]
        if b["owner"] != player_id:
            return False, "You do not own this settlement."
        if b["type"] == "city":
            return False, "This is already a city!"
        p = self.players[player_id]
        if not p.can_afford(COST_CITY):
            return False, "Cannot afford City (Cost: 2 Wheat, 3 Ore)."
        if len(p.city_vids) >= 4:
            return False, "Maximum 4 cities built."
        return True, "Valid city upgrade."

    def build_city(self, player_id: int, vertex_id: int) -> Tuple[bool, str]:
        valid, msg = self.can_build_city(player_id, vertex_id)
        if not valid:
            return False, msg

        p = self.players[player_id]
        p.deduct_cost(COST_CITY)
        for r, amt in COST_CITY.items():
            self.bank[r] += amt
        self.vertex_buildings[vertex_id]["type"] = "city"
        p.settlement_vids.remove(vertex_id)
        p.city_vids.append(vertex_id)
        self.log(f"{p.name} upgraded Settlement #{vertex_id} to a CITY! (+1 Victory Point)")

        self._check_victory()
        return True, "City built!"

    def buy_dev_card(self, player_id: int) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Not in action phase."
        if player_id != self.current_player_idx:
            return False, "It is not your turn!"
        p = self.players[player_id]
        if not p.can_afford(COST_DEV_CARD):
            return False, "Cannot afford Dev Card (Cost: 1 Sheep, 1 Wheat, 1 Ore)."
        if not self.dev_deck:
            return False, "No Development Cards left in the deck!"

        p.deduct_cost(COST_DEV_CARD)
        for r, amt in COST_DEV_CARD.items():
            self.bank[r] += amt
        card = self.dev_deck.pop()
        p.dev_cards.append(card)
        self.log(f"{p.name} bought a Development Card: [{card}].")
        self._check_victory()
        return True, f"Bought {card}!"

    def play_dev_card(self, player_id: int, card_name: str, **kwargs) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Not in action phase."
        if player_id != self.current_player_idx:
            return False, "It is not your turn!"
        p = self.players[player_id]
        if card_name not in p.dev_cards:
            return False, f"You don't hold {card_name}."

        if card_name == CARD_KNIGHT:
            p.dev_cards.remove(card_name)
            p.played_knights += 1
            self.log(f"{p.name} played a KNIGHT! Relocate the robber.")
            self._check_largest_army()
            self.phase = self.PHASE_ROBBER_MOVE
            return True, "Knight played! Move the Robber."

        elif card_name == CARD_YEAR_OF_PLENTY:
            r1 = kwargs.get("resource1", WOOD)
            r2 = kwargs.get("resource2", BRICK)
            if self.bank.get(r1, 0) < 1 or self.bank.get(r2, 0) < 1:
                return False, "Not enough cards of requested type in the Bank!"
            p.dev_cards.remove(card_name)
            self.bank[r1] -= 1
            self.bank[r2] -= 1
            p.resources[r1] += 1
            p.resources[r2] += 1
            self.log(f"{p.name} played YEAR OF PLENTY! Received: 1 {RESOURCE_NAMES[r1]}, 1 {RESOURCE_NAMES[r2]} from Bank.")
            return True, "Year of Plenty played!"

        elif card_name == CARD_MONOPOLY:
            res = kwargs.get("resource", WOOD)
            p.dev_cards.remove(card_name)
            total_stolen = 0
            for other_p in self.players:
                if other_p.player_id != player_id:
                    amt = other_p.resources.get(res, 0)
                    if amt > 0:
                        other_p.resources[res] = 0
                        total_stolen += amt
            p.resources[res] += total_stolen
            self.log(f"{p.name} played MONOPOLY on {RESOURCE_NAMES[res]}! Seized {total_stolen} cards from opponents.")
            return True, f"Monopoly claimed {total_stolen} {RESOURCE_NAMES[res]}!"

        elif card_name == CARD_ROAD_BUILDING:
            p.dev_cards.remove(card_name)
            # Give materials for 2 free roads
            p.resources[WOOD] += 2
            p.resources[BRICK] += 2
            self.log(f"{p.name} played ROAD BUILDING! Received materials for 2 free roads.")
            return True, "Road Building played!"

        elif card_name == CARD_VICTORY_POINT:
            return False, "Victory Point cards are kept hidden until the end of the game!"

        return False, "Unknown card."

    # -------------------------------------------------------------------------
    # TRADING SYSTEM
    # User requirement:
    # "The only change I would like to make is to make trading initiation available
    # to only the person whose turn is currently being played."
    # -------------------------------------------------------------------------
    def can_initiate_trade(self, player_id: int) -> bool:
        """Strictly verifies that only the active player on their turn can initiate trade."""
        return (self.phase == self.PHASE_MAIN_ACTION) and (player_id == self.current_player_idx)

    def execute_trade(self, proposer_id: int, partner_id: int,
                      offer: Dict[str, int], request: Dict[str, int]) -> Tuple[bool, str]:
        """Atomically executes a player-to-player trade."""
        if not self.can_initiate_trade(proposer_id):
            return False, "Trading initiation is ONLY allowed by the active player on their turn!"

        if partner_id == proposer_id:
            return False, "Cannot trade with yourself!"
        if partner_id not in (0, 1, 2, 3):
            return False, "Invalid trade partner."

        p_proposer = self.players[proposer_id]
        p_partner = self.players[partner_id]

        # Validate proposer has offered cards
        if not p_proposer.can_afford(offer):
            return False, f"{p_proposer.name} does not have the offered resources!"

        # Validate partner has requested cards
        if not p_partner.can_afford(request):
            return False, f"{p_partner.name} does not have the requested resources!"

        if sum(offer.values()) == 0 and sum(request.values()) == 0:
            return False, "Trade offer cannot be empty!"

        # Execute atomic exchange
        p_proposer.deduct_cost(offer)
        p_partner.add_resources(offer)

        p_partner.deduct_cost(request)
        p_proposer.add_resources(request)

        off_str = ", ".join(f"{cnt} {RESOURCE_NAMES[r]}" for r, cnt in offer.items() if cnt > 0) or "Nothing"
        req_str = ", ".join(f"{cnt} {RESOURCE_NAMES[r]}" for r, cnt in request.items() if cnt > 0) or "Nothing"

        self.log(f"TRADE EXECUTED: {p_proposer.name} gave [{off_str}] to {p_partner.name} for [{req_str}].")
        return True, "Trade completed successfully!"

    def execute_bank_trade(self, player_id: int, give_resource: str, give_amount: int,
                           get_resource: str) -> Tuple[bool, str]:
        """
        Bank / Port trade:
        - 4:1 default bank trade
        - 3:1 generic port trade
        - 2:1 specific resource port trade
        """
        if not self.can_initiate_trade(player_id):
            return False, "Bank trade initiation is ONLY allowed by the active player on their turn!"

        p = self.players[player_id]
        ratio, port_desc = self.get_best_bank_ratio(player_id, give_resource)

        if give_amount < ratio:
            return False, f"Trade requires {ratio}:1 ratio for {RESOURCE_NAMES[give_resource]} ({port_desc})!"
        if p.resources.get(give_resource, 0) < give_amount:
            return False, f"You do not have enough {RESOURCE_NAMES[give_resource]} (need {give_amount}, have {p.resources.get(give_resource, 0)})!"
        if self.bank.get(get_resource, 0) < 1:
            return False, f"The Bank has 0 {RESOURCE_NAMES[get_resource]} available!"

        # Atomic transaction between Player and Bank
        p.resources[give_resource] -= give_amount
        self.bank[give_resource] += give_amount

        self.bank[get_resource] -= 1
        p.resources[get_resource] += 1

        self.log(f"BANK TRADE: {p.name} traded {give_amount} {RESOURCE_NAMES[give_resource]} for 1 {RESOURCE_NAMES[get_resource]} ({port_desc}).")
        return True, f"Traded {give_amount} {RESOURCE_NAMES[give_resource]} for 1 {RESOURCE_NAMES[get_resource]} ({port_desc})!"

    def get_best_bank_ratio(self, player_id: int, resource: str) -> Tuple[int, str]:
        """
        Calculates best trade ratio with bank:
        - 2:1 if player has a settlement/city on a 2:1 port matching this resource
        - 3:1 if player has a settlement/city on a 3:1 generic port
        - 4:1 standard default bank trade
        """
        p = self.players[player_id]
        has_3_1 = False
        all_vids = p.settlement_vids + p.city_vids

        for vid in all_vids:
            ptype = self.board.vertices[vid].port_type
            if ptype == resource:
                return 2, f"2:1 {RESOURCE_NAMES[resource]} Port"
            elif ptype == "3:1":
                has_3_1 = True

        if has_3_1:
            return 3, "3:1 Generic Port"
        return 4, "Standard 4:1 Bank"

    def get_bank_ratio_num(self, player_id: int, resource: str) -> int:
        ratio, _ = self.get_best_bank_ratio(player_id, resource)
        return ratio

    def get_player_unlocked_rates(self, player_id: int) -> Dict[str, Tuple[int, str]]:
        return {r: self.get_best_bank_ratio(player_id, r) for r in RESOURCES}

    # -------------------------------------------------------------------------
    # VICTORY & TURN TRANSITIONS
    # -------------------------------------------------------------------------
    def end_turn(self) -> Tuple[bool, str]:
        if self.phase != self.PHASE_MAIN_ACTION:
            return False, "Cannot end turn right now."

        # Advance to next player
        self.current_player_idx = (self.current_player_idx + 1) % 4
        if self.current_player_idx == 0:
            self.turn_number += 1

        self.phase = self.PHASE_MAIN_ROLL
        self.has_rolled = False

        next_p = self.current_player
        self.log(f"--- Turn passed to {next_p.name} (Turn {self.turn_number}) ---")
        self.log(f"{next_p.name}, please ROLL DICE (Press [R]).")
        return True, f"Turn passed to {next_p.name}."

    def _check_victory(self):
        for p in self.players:
            if p.victory_points >= WINNING_VICTORY_POINTS:
                self.phase = self.PHASE_GAME_OVER
                self.winner = p
                self.log(f"**************************************************")
                self.log(f"*** VICTORY! PLAYER {p.name} HAS WON THE GAME! ***")
                self.log(f"*** Final Score: {p.victory_points} Victory Points! ***")
                self.log(f"**************************************************")
                break

    def _check_largest_army(self):
        current_leader = next((p for p in self.players if p.has_largest_army), None)
        min_army = current_leader.played_knights if current_leader else 2

        best_player = None
        for p in self.players:
            if p.played_knights > min_army:
                best_player = p
                min_army = p.played_knights

        if best_player and best_player != current_leader:
            if current_leader:
                current_leader.has_largest_army = False
            best_player.has_largest_army = True
            self.log(f"*** {best_player.name} claimed the LARGEST ARMY! (+2 Victory Points) ***")

    def _check_longest_road(self):
        # Calculate longest continuous road for each player (min 5 roads)
        best_len = 4
        current_holder = next((p for p in self.players if p.has_longest_road), None)
        if current_holder:
            best_len = self._calc_longest_road(current_holder.player_id)

        candidate = None
        for p in self.players:
            l = self._calc_longest_road(p.player_id)
            if l > best_len:
                candidate = p
                best_len = l

        if candidate and candidate != current_holder:
            if current_holder:
                current_holder.has_longest_road = False
            candidate.has_longest_road = True
            self.log(f"*** {candidate.name} claimed the LONGEST ROAD ({best_len} segments)! (+2 Victory Points) ***")

    def _calc_longest_road(self, player_id: int) -> int:
        p_roads = [eid for eid, owner in self.edge_roads.items() if owner == player_id]
        if len(p_roads) < 5:
            return len(p_roads)

        # Graph DFS to find maximum simple path of edges
        adj_e: Dict[int, List[int]] = {eid: [] for eid in p_roads}
        for i, e1 in enumerate(p_roads):
            v1_a, v1_b = self.board.edges[e1].v1, self.board.edges[e1].v2
            for e2 in p_roads[i + 1:]:
                v2_a, v2_b = self.board.edges[e2].v1, self.board.edges[e2].v2
                # Connected if they share a vertex not blocked by opponent
                shared = {v1_a, v1_b}.intersection({v2_a, v2_b})
                if shared:
                    sv = list(shared)[0]
                    # Blocked if opponent settlement/city is here
                    if sv in self.vertex_buildings and self.vertex_buildings[sv]["owner"] != player_id:
                        continue
                    adj_e[e1].append(e2)
                    adj_e[e2].append(e1)

        max_len = 0
        def dfs(curr_e: int, visited: Set[int]) -> int:
            length = 1
            for nxt_e in adj_e.get(curr_e, []):
                if nxt_e not in visited:
                    visited.add(nxt_e)
                    length = max(length, 1 + dfs(nxt_e, visited))
                    visited.remove(nxt_e)
            return length

        for start_e in p_roads:
            max_len = max(max_len, dfs(start_e, {start_e}))
        return max_len

    # -------------------------------------------------------------------------
    # QUICK SETUP HELPER (For instant testing / quick start)
    # -------------------------------------------------------------------------
    def quick_auto_setup(self):
        """Automatically assigns 2 legal starting settlements and roads to all players."""
        if self.phase not in (self.PHASE_SETUP_1, self.PHASE_SETUP_2):
            return

        while self.phase in (self.PHASE_SETUP_1, self.PHASE_SETUP_2):
            p = self.current_player
            if self.setup_sub_action == "SETTLEMENT":
                # Find any valid vertex
                valid_vids = [vid for vid in self.board.vertices if self.can_place_settlement_setup(p.player_id, vid)[0]]
                if valid_vids:
                    chosen_vid = self.rng.choice(valid_vids)
                    self.place_setup_settlement(chosen_vid)
                else:
                    break
            elif self.setup_sub_action == "ROAD":
                # Find any valid road attached to last settlement
                valid_eids = [eid for eid in self.board.vertices[self.setup_last_settlement_vid].adjacent_edges
                              if self.can_place_road_setup(p.player_id, eid)[0]]
                if valid_eids:
                    chosen_eid = self.rng.choice(valid_eids)
                    self.place_setup_road(chosen_eid)
                else:
                    break
