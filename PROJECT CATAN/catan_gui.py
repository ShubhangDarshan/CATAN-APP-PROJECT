"""
catan_gui.py - Old DOSBox UI-esque Tkinter GUI for Catan Desktop.
Features retro monospace aesthetics, hexagon color coding, dice faces in corner,
probability dots, local pass-and-play, white-outlined pieces, active-player-only trading,
and SQLite persistence.
"""

import math
import random
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple, Optional, Any, Callable

from catan_constants import (
    BRICK, SHEEP, WOOD, WHEAT, ORE, DESERT, RESOURCES, RESOURCE_NAMES,
    HEX_COLORS, PLAYER_COLORS, PLAYER_NAMES, PROBABILITY_DOTS,
    COST_ROAD, COST_SETTLEMENT, COST_CITY, COST_DEV_CARD,
    DOS_BG_DARK, DOS_BG_PANEL, DOS_BG_BOARD, DOS_NAVY,
    DOS_CYAN, DOS_YELLOW, DOS_GREEN, DOS_RED, DOS_WHITE, DOS_GREY, DOS_DARK_GREY,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_TINY,
    FONT_DICE, FONT_HEX_NUM, FONT_HEX_DOTS, DOS_FONT_FAMILY
)
from catan_board import CatanBoard
from catan_model import CatanGame, Player
from catan_db import CatanDatabase


# =============================================================================
# RETRO DOS WIDGETS
# =============================================================================

class DOSButton(tk.Button):
    """Retro styled DOS push-button with bracketed labels and keyboard focus states."""
    def __init__(self, master=None, text="", command=None, bg=DOS_NAVY, fg=DOS_WHITE,
                 activebackground=DOS_CYAN, activeforeground="#000000",
                 font=FONT_BODY_BOLD, width=None, **kwargs):
        display_text = f"[{text}]" if not (text.startswith("[") and text.endswith("]")) else text
        super().__init__(
            master, text=display_text, command=command,
            bg=bg, fg=fg, activebackground=activebackground, activeforeground=activeforeground,
            font=font, relief="raised", bd=2, highlightthickness=1,
            highlightbackground=DOS_CYAN, highlightcolor=DOS_YELLOW,
            cursor="hand2", padx=6, pady=3, width=width, **kwargs
        )
        self.default_bg = bg
        self.default_fg = fg
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        if self["state"] != "disabled":
            self.configure(bg="#0000CC", fg=DOS_YELLOW)

    def _on_leave(self, e):
        if self["state"] != "disabled":
            self.configure(bg=self.default_bg, fg=self.default_fg)


class CornerDiceWidget(tk.Canvas):
    """
    Renders 2 graphical dice cubes in the corner of the screen with authentic
    pips and roll animations.
    """
    def __init__(self, master, width=170, height=85, **kwargs):
        super().__init__(
            master, width=width, height=height, bg=DOS_BG_PANEL,
            highlightthickness=2, highlightbackground=DOS_CYAN, **kwargs
        )
        self.die1 = 1
        self.die2 = 1
        self.rolling = False
        self._draw_widget()

    def set_dice(self, d1: int, d2: int):
        self.die1 = d1
        self.die2 = d2
        self._draw_widget()

    def animate_roll(self, final_d1: int, final_d2: int, callback: Optional[Callable] = None):
        """Runs a fast 8-frame retro roll flicker before landing on final roll."""
        self.rolling = True
        frames = 8

        def _step(f: int):
            if f < frames:
                self.die1 = random.randint(1, 6)
                self.die2 = random.randint(1, 6)
                self._draw_widget()
                self.after(35, _step, f + 1)
            else:
                self.die1 = final_d1
                self.die2 = final_d2
                self.rolling = False
                self._draw_widget()
                if callback:
                    callback()

        _step(0)

    def _draw_widget(self):
        self.delete("all")
        # Corner Header
        self.create_text(85, 10, text="═╡ DICE ROLL ╞═", fill=DOS_CYAN, font=FONT_TINY)

        # Die 1 Face (Left)
        self._draw_die_face(20, 22, 38, self.die1)

        # Plus Sign
        self.create_text(74, 41, text="+", fill=DOS_WHITE, font=FONT_DICE)

        # Die 2 Face (Right)
        self._draw_die_face(88, 22, 38, self.die2)

        # Total Banner
        total = self.die1 + self.die2
        self.create_text(85, 71, text=f"SUM: [{total:2d}]", fill=DOS_YELLOW, font=FONT_BODY_BOLD)

    def _draw_die_face(self, x: float, y: float, size: float, value: int):
        # White die cube with black outline
        self.create_rectangle(x, y, x + size, y + size, fill="#F8F9FA", outline="#111111", width=2)
        r = 2.6
        cx, cy = x + size / 2, y + size / 2
        d = size * 0.26

        pips = {
            1: [(cx, cy)],
            2: [(cx - d, cy - d), (cx + d, cy + d)],
            3: [(cx - d, cy - d), (cx, cy), (cx + d, cy + d)],
            4: [(cx - d, cy - d), (cx + d, cy - d), (cx - d, cy + d), (cx + d, cy + d)],
            5: [(cx - d, cy - d), (cx + d, cy - d), (cx, cy), (cx - d, cy + d), (cx + d, cy + d)],
            6: [(cx - d, cy - d), (cx - d, cy), (cx - d, cy + d),
                (cx + d, cy - d), (cx + d, cy), (cx + d, cy + d)],
        }
        for px, py in pips.get(value, []):
            self.create_oval(px - r, py - r, px + r, py + r, fill="#111111", outline="#111111")


# =============================================================================
# MAIN GUI WINDOW
# =============================================================================

class CatanGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SETTLERS OF CATAN  --  [DOS-BOX EDITION]")
        self.root.geometry("1300x820")
        self.root.minsize(1100, 720)
        self.root.configure(bg=DOS_BG_DARK)

        # Database Manager
        self.db = CatanDatabase()

        # Interaction Mode: None, "BUILD_ROAD", "BUILD_SETTLEMENT", "BUILD_CITY", "MOVE_ROBBER", "STEAL"
        self.mode: Optional[str] = None

        # Game Engine
        self.game = self._init_game_session()

        # Build UI Layout
        self._create_menu_bar()
        self._create_main_layout()
        self._bind_keyboard_shortcuts()

        # Initial Render
        self.refresh_all()

        # Prompt startup status
        if self.game.turn_number > 1 or self.game.phase not in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2):
            self.log_message(f"Resumed active game from SQL Database (Turn {self.game.turn_number}).")

    def _init_game_session(self) -> CatanGame:
        """Loads last active game from database, or starts fresh game."""
        if self.db.has_resumable_game():
            loaded = self.db.load_game()
            if loaded:
                return loaded
        new_g = CatanGame()
        self.db.save_game(new_g, slot_name="Active Session")
        return new_g

    # -------------------------------------------------------------------------
    # TOP HEADER & MENU BAR
    # -------------------------------------------------------------------------
    def _create_menu_bar(self):
        header_frame = tk.Frame(self.root, bg=DOS_NAVY, bd=2, relief="ridge")
        header_frame.pack(side="top", fill="x", padx=4, pady=(4, 2))

        # Title Label
        title_label = tk.Label(
            header_frame,
            text=" ╔═══[ SETTLERS OF CATAN : DOS-BOX EDITION v1.0 ]═══╗",
            bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_TITLE
        )
        title_label.pack(side="left", padx=8, pady=4)

        # Top Buttons
        btn_box = tk.Frame(header_frame, bg=DOS_NAVY)
        btn_box.pack(side="right", padx=6, pady=4)

        DOSButton(btn_box, text="NEW GAME", command=self.on_new_game).pack(side="left", padx=3)
        DOSButton(btn_box, text="SAVE GAME", command=self.on_save_game).pack(side="left", padx=3)
        DOSButton(btn_box, text="LOAD GAME", command=self.on_load_game).pack(side="left", padx=3)
        DOSButton(btn_box, text="RULES (F1)", command=self.on_show_rules).pack(side="left", padx=3)
        DOSButton(btn_box, text="QUIT", command=self.on_quit, bg="#770000", fg=DOS_WHITE).pack(side="left", padx=3)

    # -------------------------------------------------------------------------
    # MAIN PANES LAYOUT
    # -------------------------------------------------------------------------
    def _create_main_layout(self):
        main_container = tk.Frame(self.root, bg=DOS_BG_DARK)
        main_container.pack(side="top", fill="both", expand=True, padx=4, pady=2)

        # 1. Left Pane: Local Pass-and-Play Player HUDs
        self.left_pane = tk.Frame(main_container, bg=DOS_BG_PANEL, bd=2, relief="ridge", width=290)
        self.left_pane.pack(side="left", fill="y", padx=2, pady=2)
        self.left_pane.pack_propagate(False)
        self._build_player_hud()

        # 2. Center Pane: Hexagonal Catan Board Canvas
        self.center_pane = tk.Frame(main_container, bg=DOS_BG_BOARD, bd=2, relief="ridge")
        self.center_pane.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        self.canvas = tk.Canvas(
            self.center_pane, bg=DOS_BG_BOARD, highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw_board())
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)

        # 3. Right Pane: Dice Corner Widget, Turn Controls & Terminal Log
        self.right_pane = tk.Frame(main_container, bg=DOS_BG_PANEL, bd=2, relief="ridge", width=340)
        self.right_pane.pack(side="right", fill="y", padx=2, pady=2)
        self.right_pane.pack_propagate(False)
        self._build_control_panel()

        # 4. Bottom Status Line (DOS Key shortcuts)
        self.status_bar = tk.Label(
            self.root,
            text="[F1] Rules  [R] Roll  [B] Road  [S] Settl  [C] City  [T] Trade  [E] End Turn  [F2] Save",
            bg=DOS_NAVY, fg=DOS_CYAN, font=FONT_TINY, anchor="w", bd=1, relief="sunken"
        )
        self.status_bar.pack(side="bottom", fill="x", padx=4, pady=(2, 4))

    # -------------------------------------------------------------------------
    # LEFT PANE: PLAYER HUD (PASS-AND-PLAY)
    # -------------------------------------------------------------------------
    def _build_player_hud(self):
        # Header
        lbl = tk.Label(self.left_pane, text="╔═══[ PLAYERS ]═══╗", bg=DOS_BG_PANEL, fg=DOS_CYAN, font=FONT_SUBTITLE)
        lbl.pack(side="top", fill="x", pady=(6, 4))

        self.player_cards: List[tk.Frame] = []
        self.player_labels: List[Dict[str, tk.Label]] = []

        for p in self.game.players:
            p_frame = tk.Frame(self.left_pane, bg="#0C1420", bd=2, relief="groove")
            p_frame.pack(fill="x", padx=6, pady=4)
            self.player_cards.append(p_frame)

            # Name and VP line
            top_line = tk.Frame(p_frame, bg="#0C1420")
            top_line.pack(fill="x", padx=4, pady=2)

            name_lbl = tk.Label(
                top_line, text=f"● {p.name}", bg="#0C1420",
                fg=p.color_info["text"], font=FONT_BODY_BOLD
            )
            name_lbl.pack(side="left")

            vp_lbl = tk.Label(top_line, text="0 VP", bg="#0C1420", fg=DOS_YELLOW, font=FONT_BODY_BOLD)
            vp_lbl.pack(side="right")

            # Resources breakdown
            res_frame = tk.Frame(p_frame, bg="#0C1420")
            res_frame.pack(fill="x", padx=4, pady=2)

            res_lbl = tk.Label(
                res_frame,
                text="W:0 B:0 S:0 H:0 O:0",
                bg="#0C1420", fg=DOS_WHITE, font=FONT_SMALL, justify="left"
            )
            res_lbl.pack(side="left")

            tot_lbl = tk.Label(res_frame, text="Cards: 0", bg="#0C1420", fg=DOS_GREY, font=FONT_TINY)
            tot_lbl.pack(side="right")

            # Pieces status
            pcs_lbl = tk.Label(
                p_frame, text="Roads: 0  Houses: 0  Cities: 0",
                bg="#0C1420", fg="#88AACC", font=FONT_TINY
            )
            pcs_lbl.pack(fill="x", padx=4, pady=(0, 3))

            self.player_labels.append({
                "name": name_lbl,
                "vp": vp_lbl,
                "res": res_lbl,
                "tot": tot_lbl,
                "pcs": pcs_lbl,
            })

        # RESOURCE BANK UI ELEMENT
        # Display the number of cards available in the bank (total 95 resources, 19 of each type)
        bank_box = tk.Frame(self.left_pane, bg="#08101E", bd=2, relief="ridge", highlightbackground=DOS_CYAN, highlightthickness=1)
        bank_box.pack(fill="x", padx=6, pady=(6, 4))

        tk.Label(
            bank_box, text="═╡ RESOURCE BANK (95 CARDS) ╞═",
            bg="#08101E", fg=DOS_CYAN, font=FONT_TINY
        ).pack(pady=(3, 1))

        self.bank_total_lbl = tk.Label(
            bank_box, text="TOTAL IN BANK: [ 95 / 95 ]",
            bg="#08101E", fg=DOS_YELLOW, font=FONT_BODY_BOLD
        )
        self.bank_total_lbl.pack(pady=(0, 2))

        self.bank_res_labels: Dict[str, tk.Label] = {}
        bank_items = [
            (WOOD, "WOOD  (Dk Grn)", "#55FF55"),
            (BRICK, "BRICK (Red)   ", "#FF6B6B"),
            (SHEEP, "SHEEP (Lt Grn)", "#55FF55"),
            (WHEAT, "WHEAT (Yellow)", "#FFFF55"),
            (ORE, "ORE   (Grey)  ", "#BBBBBB"),
        ]

        for r_key, r_name, text_color in bank_items:
            row = tk.Frame(bank_box, bg="#08101E")
            row.pack(fill="x", padx=8, pady=1)

            lbl_name = tk.Label(
                row, text=f"■ {r_name}:",
                bg="#08101E", fg=text_color, font=FONT_TINY, anchor="w", width=15
            )
            lbl_name.pack(side="left")

            lbl_val = tk.Label(
                row, text="19 / 19",
                bg="#08101E", fg=DOS_WHITE, font=FONT_TINY, anchor="e"
            )
            lbl_val.pack(side="right")
            self.bank_res_labels[r_key] = lbl_val

        # Resource Color Guide
        guide_box = tk.Frame(self.left_pane, bg=DOS_BG_PANEL, bd=1, relief="ridge")
        guide_box.pack(fill="x", padx=6, pady=(6, 4), side="bottom")

        tk.Label(guide_box, text="─ RESOURCE COLORS ─", bg=DOS_BG_PANEL, fg=DOS_CYAN, font=FONT_TINY).pack()
        guides = [
            ("BRICK (Hill): RED", HEX_COLORS[BRICK]),
            ("SHEEP (Pasture): LT GREEN", HEX_COLORS[SHEEP]),
            ("WOOD (Forest): DK GREEN", HEX_COLORS[WOOD]),
            ("WHEAT (Field): YELLOW", HEX_COLORS[WHEAT]),
            ("ORE (Mountain): GREY", HEX_COLORS[ORE]),
            ("DESERT (Robber): KHAKI", HEX_COLORS[DESERT]),
        ]
        for g_text, g_col in guides:
            row = tk.Frame(guide_box, bg=DOS_BG_PANEL)
            row.pack(fill="x", padx=4, pady=1)
            tk.Label(row, text="■", fg=g_col, bg=DOS_BG_PANEL, font=FONT_TINY).pack(side="left")
            tk.Label(row, text=g_text, fg=DOS_WHITE, bg=DOS_BG_PANEL, font=FONT_TINY).pack(side="left", padx=3)

    # -------------------------------------------------------------------------
    # RIGHT PANE: DICE CORNER WIDGET, CONTROLS & LOG
    # -------------------------------------------------------------------------
    def _build_control_panel(self):
        # 1. Corner Dice Widget (Prominently placed at the top corner!)
        dice_frame = tk.Frame(self.right_pane, bg=DOS_BG_PANEL)
        dice_frame.pack(side="top", fill="x", padx=6, pady=4)

        self.corner_dice = CornerDiceWidget(dice_frame)
        self.corner_dice.pack(pady=2)

        # 2. Turn / Phase Status Banner
        self.turn_status_box = tk.Label(
            self.right_pane,
            text=">>> CURRENT: RED <<<\nPHASE: ROLL DICE",
            bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_BODY_BOLD,
            bd=2, relief="ridge", pady=4
        )
        self.turn_status_box.pack(fill="x", padx=6, pady=4)

        # 3. Action Buttons
        act_box = tk.Frame(self.right_pane, bg=DOS_BG_PANEL)
        act_box.pack(fill="x", padx=6, pady=2)

        self.btn_roll = DOSButton(act_box, text="[R] ROLL DICE", command=self.on_roll_dice, bg="#004400")
        self.btn_roll.pack(fill="x", pady=2)

        self.btn_road = DOSButton(act_box, text="[B] BUILD ROAD (1W 1B)", command=self.on_start_build_road)
        self.btn_road.pack(fill="x", pady=2)

        self.btn_settle = DOSButton(act_box, text="[S] BUILD SETTLEMENT (1W 1B 1S 1H)", command=self.on_start_build_settlement)
        self.btn_settle.pack(fill="x", pady=2)

        self.btn_city = DOSButton(act_box, text="[C] UPGRADE CITY (2H 3O)", command=self.on_start_build_city)
        self.btn_city.pack(fill="x", pady=2)

        self.btn_trade = DOSButton(act_box, text="[T] TRADE RESOURCES", command=self.on_open_trade_menu, bg="#664400")
        self.btn_trade.pack(fill="x", pady=2)

        self.btn_dev = DOSButton(act_box, text="BUY DEV CARD (1S 1H 1O)", command=self.on_buy_dev_card)
        self.btn_dev.pack(fill="x", pady=2)

        self.btn_quick_setup = DOSButton(act_box, text="QUICK AUTO-SETUP", command=self.on_quick_setup, bg="#2A2A5A")
        self.btn_quick_setup.pack(fill="x", pady=2)

        self.btn_end_turn = DOSButton(act_box, text="[E] END TURN", command=self.on_end_turn, bg="#771111")
        self.btn_end_turn.pack(fill="x", pady=3)

        # 4. Action Mode Cancel Button (Visible during targeting)
        self.btn_cancel_mode = DOSButton(
            act_box, text="CANCEL ACTION", command=self.cancel_mode,
            bg="#990000", fg=DOS_YELLOW
        )

        # 5. DOS Terminal Log
        log_header = tk.Label(self.right_pane, text="═╡ ACTION LOG ╞═", bg=DOS_BG_PANEL, fg=DOS_GREEN, font=FONT_TINY)
        log_header.pack(fill="x", padx=6, pady=(4, 0))

        log_container = tk.Frame(self.right_pane, bg="#000000", bd=2, relief="sunken")
        log_container.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.log_text = tk.Text(
            log_container, bg="#050805", fg=DOS_GREEN, insertbackground=DOS_GREEN,
            font=FONT_TINY, wrap="word", height=9, bd=0
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = tk.Scrollbar(log_container, command=self.log_text.yview, bg=DOS_BG_DARK)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    # -------------------------------------------------------------------------
    # REFRESH HUD & UI CONTROLS
    # -------------------------------------------------------------------------
    def refresh_all(self):
        # Update Player HUDs
        for idx, p in enumerate(self.game.players):
            is_active = (idx == self.game.current_player_idx)
            card_frame = self.player_cards[idx]
            lbls = self.player_labels[idx]

            # Highlight active player in pass-and-play
            if is_active:
                card_frame.configure(bg="#002244", bd=2, relief="solid", highlightbackground=DOS_CYAN, highlightthickness=1)
                lbls["name"].configure(text=f"► {p.name} (ACTIVE)", bg="#002244")
            else:
                card_frame.configure(bg="#0C1420", bd=2, relief="groove", highlightthickness=0)
                lbls["name"].configure(text=f"● {p.name}", bg="#0C1420")

            lbls["vp"].configure(text=f"{p.victory_points} VP", bg="#002244" if is_active else "#0C1420")
            lbls["res"].configure(
                text=f"W:{p.resources[WOOD]} B:{p.resources[BRICK]} S:{p.resources[SHEEP]} H:{p.resources[WHEAT]} O:{p.resources[ORE]}",
                bg="#002244" if is_active else "#0C1420"
            )
            lbls["tot"].configure(text=f"Cards:{p.total_resources}", bg="#002244" if is_active else "#0C1420")
            lbls["pcs"].configure(
                text=f"R:{len(p.road_eids)}/15  H:{len(p.settlement_vids)}/5  C:{len(p.city_vids)}/4",
                bg="#002244" if is_active else "#0C1420"
            )

        # Update Resource Bank UI Element
        tot_avail = self.game.total_bank_cards
        self.bank_total_lbl.configure(text=f"TOTAL IN BANK: [ {tot_avail:2d} / 95 ]")
        for r_key, lbl in self.bank_res_labels.items():
            amt = self.game.bank.get(r_key, 0)
            lbl.configure(text=f"{amt:2d} / 19")

        # Update Turn Banner
        curr = self.game.current_player
        phase_str = self.game.phase.replace("_", " ")
        if self.game.phase in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2):
            sub = "CLICK A VERTEX TO BUILD SETTLEMENT" if self.game.setup_sub_action == "SETTLEMENT" else "CLICK AN ADJACENT EDGE TO BUILD ROAD"
            self.turn_status_box.configure(
                text=f">>> SETUP : {curr.name} <<<\n{sub}",
                bg="#332200", fg=DOS_YELLOW
            )
        elif self.game.phase == CatanGame.PHASE_MAIN_ROLL:
            self.turn_status_box.configure(
                text=f">>> TURN {self.game.turn_number}: {curr.name} <<<\nPHASE: ROLL DICE [R]",
                bg=DOS_NAVY, fg=DOS_YELLOW
            )
        elif self.game.phase == CatanGame.PHASE_ROBBER_MOVE:
            self.turn_status_box.configure(
                text=f">>> {curr.name} <<<\nCLICK ANY HEX TO MOVE ROBBER",
                bg="#551100", fg=DOS_YELLOW
            )
        elif self.game.phase == CatanGame.PHASE_ROBBER_STEAL:
            self.turn_status_box.configure(
                text=f">>> {curr.name} <<<\nSELECT VICTIM TO STEAL FROM",
                bg="#551100", fg=DOS_YELLOW
            )
        elif self.game.phase == CatanGame.PHASE_GAME_OVER:
            self.turn_status_box.configure(
                text=f"*** GAME OVER ***\nWINNER: {self.game.winner.name} ({self.game.winner.victory_points} VP)!",
                bg="#004400", fg=DOS_YELLOW
            )
        else:
            self.turn_status_box.configure(
                text=f">>> TURN {self.game.turn_number}: {curr.name} <<<\nPHASE: ACTION (BUILD / TRADE / END)",
                bg="#002244", fg=DOS_CYAN
            )

        # Control Buttons Enable / Disable
        is_setup = self.game.phase in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2)
        is_roll = (self.game.phase == CatanGame.PHASE_MAIN_ROLL)
        is_action = (self.game.phase == CatanGame.PHASE_MAIN_ACTION)

        self.btn_roll["state"] = "normal" if is_roll else "disabled"
        self.btn_road["state"] = "normal" if (is_action and curr.can_afford(COST_ROAD)) else "disabled"
        self.btn_settle["state"] = "normal" if (is_action and curr.can_afford(COST_SETTLEMENT)) else "disabled"
        self.btn_city["state"] = "normal" if (is_action and curr.can_afford(COST_CITY)) else "disabled"

        # Trading initiation: STRICTLY available ONLY to current active player on their turn
        can_trade = self.game.can_initiate_trade(self.game.current_player_idx)
        self.btn_trade["state"] = "normal" if can_trade else "disabled"

        self.btn_dev["state"] = "normal" if (is_action and curr.can_afford(COST_DEV_CARD) and self.game.dev_deck) else "disabled"
        self.btn_end_turn["state"] = "normal" if is_action else "disabled"

        if is_setup:
            self.btn_quick_setup.pack(fill="x", pady=2)
        else:
            self.btn_quick_setup.pack_forget()

        # Mode Cancel Button
        if self.mode:
            self.btn_cancel_mode.pack(fill="x", pady=2)
        else:
            self.btn_cancel_mode.pack_forget()

        # Sync Corner Dice
        self.corner_dice.set_dice(self.game.dice[0], self.game.dice[1])

        # Redraw Board Canvas
        self.redraw_board()

        # Refresh Action Terminal Log
        self.refresh_log()

    def refresh_log(self):
        self.log_text.delete("1.0", "end")
        for msg in self.game.logs[-50:]:
            self.log_text.insert("end", f"> {msg}\n")
        self.log_text.see("end")

    def log_message(self, msg: str):
        self.game.log(msg)
        self.refresh_log()
        self.auto_save()

    def auto_save(self):
        try:
            self.db.save_game(self.game, slot_name="Auto-Save")
        except Exception as ex:
            print("Auto-save notice:", ex)

    # -------------------------------------------------------------------------
    # BOARD DRAWING (HEXAGONS, WHITE NUMBERS, DOTS, ROADS, SETTLEMENTS, CITIES)
    # -------------------------------------------------------------------------
    def redraw_board(self):
        canvas = self.canvas
        canvas.delete("all")

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        # Center Board Coordinates
        cx_offset = cw / 2.0
        cy_offset = ch / 2.0 - 15.0

        # Draw Retro Water Ripple Waves on ocean canvas
        self._draw_ocean_waves(cw, ch)

        # 1. DRAW HEXAGONS
        # Exact Colors as specified:
        # RED: Brick
        # LIGHT GREEN: Sheep
        # DARK GREEN: Wood
        # YELLOW: Wheat
        # GREY: Ore
        # KHAKI: Robber's hexagon (Desert)
        for hid, htile in self.game.board.hexes.items():
            verts = [(self.game.board.vertices[vid].x + cx_offset,
                      self.game.board.vertices[vid].y + cy_offset)
                     for vid in htile.vertex_ids]
            flat_verts = [coord for pt in verts for coord in pt]

            # Hexagon body with 2px dark outline
            canvas.create_polygon(
                flat_verts, fill=htile.color, outline="#181818", width=2,
                tags=("hex", f"hex_{hid}")
            )

            # Center coordinates
            hx = htile.center_x + cx_offset
            hy = htile.center_y + cy_offset

            # NUMBER TOKEN & PROBABILITY DOTS
            # "print the numbers on each square with a white font, along with dots below
            # the numbers representing the probability of that number occurring
            # (6 and 8 having the highest, 2 and 12 the lowest)"
            if htile.number_token is not None:
                # White font number with subtle dark backing token for 100% legibility on light hexes
                canvas.create_oval(
                    hx - 18, hy - 18, hx + 18, hy + 18,
                    fill="#1A1A1A", outline="#FFFFFF", width=1.5
                )

                # Number printed with white font
                canvas.create_text(
                    hx, hy - 5, text=str(htile.number_token),
                    fill=DOS_WHITE, font=FONT_HEX_NUM
                )

                # Dots below number printed with white font
                dots_count = htile.probability_dots
                dots_str = "•" * dots_count
                canvas.create_text(
                    hx, hy + 9, text=dots_str,
                    fill=DOS_WHITE, font=FONT_HEX_DOTS
                )

            # ROBBER TOKEN
            # "and a Khaki colored hexagon for the robber's hexagon."
            if htile.has_robber:
                robber_y = hy if htile.number_token is None else hy - 26
                # Retro DOS Robber Pawn
                canvas.create_oval(
                    hx - 14, robber_y - 12, hx + 14, robber_y + 12,
                    fill="#111111", outline=DOS_RED, width=2
                )
                canvas.create_text(
                    hx, robber_y, text="ROBBER",
                    fill=DOS_YELLOW, font=FONT_TINY
                )

        # 2. DRAW COASTAL TRADING PORTS (3:1 and 2:1)
        self._draw_coastal_ports(canvas, cx_offset, cy_offset)

        # 3. DRAW ROADS
        # "Each road, house, or city of the specific color should also have a white outline."
        for eid, owner_id in self.game.edge_roads.items():
            edge = self.game.board.edges[eid]
            v1 = self.game.board.vertices[edge.v1]
            v2 = self.game.board.vertices[edge.v2]
            p_color = self.game.players[owner_id].color_info["fill"]
            self._draw_road_piece(
                canvas,
                v1.x + cx_offset, v1.y + cy_offset,
                v2.x + cx_offset, v2.y + cy_offset,
                color=p_color
            )

        # 3. DRAW SETTLEMENTS & CITIES
        # "Each road, house, or city of the specific color should also have a white outline."
        for vid, b in self.game.vertex_buildings.items():
            v = self.game.board.vertices[vid]
            vx = v.x + cx_offset
            vy = v.y + cy_offset
            owner_id = b["owner"]
            p_color = self.game.players[owner_id].color_info["fill"]

            if b["type"] == "city":
                self._draw_city_piece(canvas, vx, vy, color=p_color)
            else:
                self._draw_settlement_piece(canvas, vx, vy, color=p_color)

        # 4. DRAW INTERACTION OVERLAYS (Targeting mode highlights)
        self._draw_interaction_overlays(cx_offset, cy_offset)

    def _draw_ocean_waves(self, cw: float, ch: float):
        for y in range(25, int(ch), 45):
            for x in range(20, int(cw), 90):
                self.canvas.create_text(
                    x, y, text="~ ~", fill="#002850", font=FONT_TINY
                )

    def _draw_coastal_ports(self, canvas: tk.Canvas, cx_offset: float, cy_offset: float):
        """Draws the 9 coastal trading ports (3:1 generic and 2:1 resource-specific) with pier docks."""
        for eid, edge in self.game.board.edges.items():
            if not edge.is_port or not edge.adjacent_hexes:
                continue

            v1 = self.game.board.vertices[edge.v1]
            v2 = self.game.board.vertices[edge.v2]
            sx1, sy1 = v1.x + cx_offset, v1.y + cy_offset
            sx2, sy2 = v2.x + cx_offset, v2.y + cy_offset

            # Adjacent land hex
            hid = edge.adjacent_hexes[0]
            htile = self.game.board.hexes[hid]
            shx, shy = htile.center_x + cx_offset, htile.center_y + cy_offset

            # Midpoint of coastal edge
            mx, my = (sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0

            # Normal pointing out into the sea
            dx = mx - shx
            dy = my - shy
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            ux, uy = dx / dist, dy / dist
            px = mx + ux * 26.0
            py = my + uy * 26.0

            # Check if any player owns a settlement or city on either vertex
            port_owner_id = None
            if edge.v1 in self.game.vertex_buildings:
                port_owner_id = self.game.vertex_buildings[edge.v1]["owner"]
            elif edge.v2 in self.game.vertex_buildings:
                port_owner_id = self.game.vertex_buildings[edge.v2]["owner"]

            # Draw wooden pier lines from coastal vertices out to the port badge
            canvas.create_line(sx1, sy1, px, py, fill="#8B5A2B", width=2, dash=(2, 2))
            canvas.create_line(sx2, sy2, px, py, fill="#8B5A2B", width=2, dash=(2, 2))

            # Determine badge styling and label
            ptype = edge.port_type
            if ptype == "3:1":
                badge_bg = "#112233"
                badge_txt = "3:1 ?"
                badge_text_col = DOS_WHITE
            else:
                badge_bg = HEX_COLORS.get(ptype, "#333333")
                badge_txt = f"2:1 {RESOURCE_NAMES[ptype][:3].upper()}"
                badge_text_col = DOS_WHITE

            # Highlight border if owned by a player
            if port_owner_id is not None:
                owner_color = self.game.players[port_owner_id].color_info["fill"]
                badge_outline = owner_color
                border_width = 2
            else:
                badge_outline = DOS_WHITE
                border_width = 1.5

            bw, bh = 26, 9
            canvas.create_rectangle(
                px - bw, py - bh, px + bw, py + bh,
                fill=badge_bg, outline=badge_outline, width=border_width
            )
            canvas.create_text(
                px, py, text=badge_txt,
                fill=badge_text_col, font=FONT_TINY
            )

    def _draw_road_piece(self, canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, color: str):
        """Draws a road polygon with player color and white outline."""
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            return

        nx = -dy / length * 3.5
        ny = dx / length * 3.5
        ux = dx / length * 5.0
        uy = dy / length * 5.0

        pts = [
            x1 + ux + nx, y1 + uy + ny,
            x2 - ux + nx, y2 - uy + ny,
            x2 - ux - nx, y2 - uy - ny,
            x1 + ux - nx, y1 + uy - ny,
        ]
        # Filled with player color AND has a crisp white outline
        canvas.create_polygon(pts, fill=color, outline=DOS_WHITE, width=2)

    def _draw_settlement_piece(self, canvas: tk.Canvas, vx: float, vy: float, color: str):
        """Draws a house polygon with player color and white outline."""
        # House shaped polygon (pitched roof + square base)
        pts = [
            vx, vy - 11,            # Roof peak
            vx + 9, vy - 3,         # Right eave
            vx + 9, vy + 9,         # Bottom right
            vx - 9, vy + 9,         # Bottom left
            vx - 9, vy - 3,         # Left eave
        ]
        canvas.create_polygon(pts, fill=color, outline=DOS_WHITE, width=2)

    def _draw_city_piece(self, canvas: tk.Canvas, vx: float, vy: float, color: str):
        """Draws a city/castle polygon with player color and white outline."""
        # Fortified city polygon (tower + rooftop base)
        pts = [
            vx - 12, vy + 10,       # Bottom left
            vx + 13, vy + 10,       # Bottom right
            vx + 13, vy - 2,        # Right wall top
            vx + 4, vy - 2,         # Inner corner
            vx + 4, vy - 12,        # Tower top right
            vx - 4, vy - 12,        # Tower top left
            vx - 4, vy - 4,         # Left roof
            vx - 12, vy - 4,        # Left wall top
        ]
        canvas.create_polygon(pts, fill=color, outline=DOS_WHITE, width=2)

    def _draw_interaction_overlays(self, cx_offset: float, cy_offset: float):
        canvas = self.canvas
        curr_p = self.game.current_player

        # A. Setup Phase Highlighting
        if self.game.phase in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2):
            if self.game.setup_sub_action == "SETTLEMENT":
                # Highlight legal settlement vertices
                for vid, v in self.game.board.vertices.items():
                    valid, _ = self.game.can_place_settlement_setup(curr_p.player_id, vid)
                    if valid:
                        vx, vy = v.x + cx_offset, v.y + cy_offset
                        canvas.create_oval(
                            vx - 8, vy - 8, vx + 8, vy + 8,
                            fill="#00FFCC", outline=DOS_WHITE, width=2,
                            tags=("clickable_vertex", f"v_{vid}")
                        )
            elif self.game.setup_sub_action == "ROAD":
                # Highlight legal road edges attached to the settlement
                last_vid = self.game.setup_last_settlement_vid
                if last_vid is not None:
                    for eid in self.game.board.vertices[last_vid].adjacent_edges:
                        valid, _ = self.game.can_place_road_setup(curr_p.player_id, eid)
                        if valid:
                            edge = self.game.board.edges[eid]
                            v1 = self.game.board.vertices[edge.v1]
                            v2 = self.game.board.vertices[edge.v2]
                            canvas.create_line(
                                v1.x + cx_offset, v1.y + cy_offset,
                                v2.x + cx_offset, v2.y + cy_offset,
                                fill=DOS_YELLOW, width=4, dash=(4, 3),
                                tags=("clickable_edge", f"e_{eid}")
                            )

        # B. Mode Highlighting
        elif self.mode == "BUILD_ROAD":
            for eid in self.game.board.edges:
                valid, _ = self.game.can_build_road(curr_p.player_id, eid)
                if valid:
                    edge = self.game.board.edges[eid]
                    v1 = self.game.board.vertices[edge.v1]
                    v2 = self.game.board.vertices[edge.v2]
                    canvas.create_line(
                        v1.x + cx_offset, v1.y + cy_offset,
                        v2.x + cx_offset, v2.y + cy_offset,
                        fill=DOS_CYAN, width=5, dash=(4, 2),
                        tags=("clickable_edge", f"e_{eid}")
                    )

        elif self.mode == "BUILD_SETTLEMENT":
            for vid in self.game.board.vertices:
                valid, _ = self.game.can_build_settlement(curr_p.player_id, vid)
                if valid:
                    v = self.game.board.vertices[vid]
                    vx, vy = v.x + cx_offset, v.y + cy_offset
                    canvas.create_oval(
                        vx - 9, vy - 9, vx + 9, vy + 9,
                        fill=DOS_CYAN, outline=DOS_WHITE, width=2,
                        tags=("clickable_vertex", f"v_{vid}")
                    )

        elif self.mode == "BUILD_CITY":
            for vid in curr_p.settlement_vids:
                v = self.game.board.vertices[vid]
                vx, vy = v.x + cx_offset, v.y + cy_offset
                canvas.create_oval(
                    vx - 12, vy - 12, vx + 12, vy + 12,
                    fill=DOS_YELLOW, outline=DOS_WHITE, width=2,
                    tags=("clickable_vertex", f"v_{vid}")
                )

        elif self.mode == "MOVE_ROBBER" or self.game.phase == CatanGame.PHASE_ROBBER_MOVE:
            for hid, htile in self.game.board.hexes.items():
                if hid != self.game.robber_hex_id:
                    hx, hy = htile.center_x + cx_offset, htile.center_y + cy_offset
                    canvas.create_oval(
                        hx - 12, hy - 12, hx + 12, hy + 12,
                        fill="#FFAA00", outline=DOS_WHITE, width=2,
                        tags=("clickable_hex", f"h_{hid}")
                    )

    # -------------------------------------------------------------------------
    # CANVAS CLICK & INTERACTION HANDLERS
    # -------------------------------------------------------------------------
    def on_canvas_motion(self, event):
        # Cursor change on hover
        pass

    def on_canvas_click(self, event):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        board_x = event.x - (cw / 2.0)
        board_y = event.y - (ch / 2.0 - 15.0)

        # 1. SETUP PHASE CLICKS
        if self.game.phase in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2):
            if self.game.setup_sub_action == "SETTLEMENT":
                vid = self.game.board.get_vertex_at_point(board_x, board_y, tolerance=15.0)
                if vid is not None:
                    ok, msg = self.game.place_setup_settlement(vid)
                    if ok:
                        self.refresh_all()
                        self.auto_save()
                    else:
                        messagebox.showwarning("Setup Settlement", msg)
                return

            elif self.game.setup_sub_action == "ROAD":
                eid = self.game.board.get_edge_at_point(board_x, board_y, tolerance=14.0)
                if eid is not None:
                    ok, msg = self.game.place_setup_road(eid)
                    if ok:
                        self.refresh_all()
                        self.auto_save()
                        self._prompt_pass_turn_if_needed()
                    else:
                        messagebox.showwarning("Setup Road", msg)
                return

        # 2. ROBBER MOVEMENT CLICK
        if self.mode == "MOVE_ROBBER" or self.game.phase == CatanGame.PHASE_ROBBER_MOVE:
            hid = self.game.board.get_hex_at_point(board_x, board_y, tolerance=42.0)
            if hid is not None:
                ok, msg = self.game.move_robber(hid)
                self.mode = None
                self.refresh_all()
                self.auto_save()
                if not ok:
                    messagebox.showwarning("Move Robber", msg)
                elif self.game.phase == CatanGame.PHASE_ROBBER_STEAL:
                    self.prompt_steal_dialog()
            return

        # 3. BUILD ROAD MODE
        if self.mode == "BUILD_ROAD":
            eid = self.game.board.get_edge_at_point(board_x, board_y, tolerance=14.0)
            if eid is not None:
                ok, msg = self.game.build_road(self.game.current_player_idx, eid)
                if ok:
                    self.mode = None
                    self.refresh_all()
                    self.auto_save()
                else:
                    messagebox.showwarning("Build Road", msg)
            return

        # 4. BUILD SETTLEMENT MODE
        if self.mode == "BUILD_SETTLEMENT":
            vid = self.game.board.get_vertex_at_point(board_x, board_y, tolerance=15.0)
            if vid is not None:
                ok, msg = self.game.build_settlement(self.game.current_player_idx, vid)
                if ok:
                    self.mode = None
                    self.refresh_all()
                    self.auto_save()
                else:
                    messagebox.showwarning("Build Settlement", msg)
            return

        # 5. BUILD CITY MODE
        if self.mode == "BUILD_CITY":
            vid = self.game.board.get_vertex_at_point(board_x, board_y, tolerance=15.0)
            if vid is not None:
                ok, msg = self.game.build_city(self.game.current_player_idx, vid)
                if ok:
                    self.mode = None
                    self.refresh_all()
                    self.auto_save()
                else:
                    messagebox.showwarning("Upgrade City", msg)
            return

    # -------------------------------------------------------------------------
    # GAME ACTION HANDLERS
    # -------------------------------------------------------------------------
    def on_roll_dice(self):
        if self.game.phase != CatanGame.PHASE_MAIN_ROLL:
            return

        # Disable roll button immediately to prevent double click
        self.btn_roll["state"] = "disabled"

        # Determine roll values
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        # Animate the corner dice widget!
        def _on_roll_finished():
            # Apply roll to game engine
            self.game.dice = (d1, d2)
            self.game.has_rolled = True
            total = d1 + d2
            p = self.game.current_player
            self.game.log(f"{p.name} rolled [{d1}] + [{d2}] = {total}!")

            if total == 7:
                self.game._handle_roll_seven()
            else:
                self.game._distribute_resources(total)
                self.game.phase = CatanGame.PHASE_MAIN_ACTION

            self.refresh_all()
            self.auto_save()

            if self.game.phase == CatanGame.PHASE_ROBBER_MOVE:
                self.mode = "MOVE_ROBBER"
                self.refresh_all()

        self.corner_dice.animate_roll(d1, d2, callback=_on_roll_finished)

    def on_start_build_road(self):
        if self.game.phase != CatanGame.PHASE_MAIN_ACTION:
            return
        self.mode = "BUILD_ROAD"
        self.log_message(f"{self.game.current_player.name}: Click a highlighted edge to build your Road.")
        self.refresh_all()

    def on_start_build_settlement(self):
        if self.game.phase != CatanGame.PHASE_MAIN_ACTION:
            return
        self.mode = "BUILD_SETTLEMENT"
        self.log_message(f"{self.game.current_player.name}: Click a highlighted vertex to build your Settlement.")
        self.refresh_all()

    def on_start_build_city(self):
        if self.game.phase != CatanGame.PHASE_MAIN_ACTION:
            return
        self.mode = "BUILD_CITY"
        self.log_message(f"{self.game.current_player.name}: Click an existing Settlement to upgrade to a City.")
        self.refresh_all()

    def cancel_mode(self):
        self.mode = None
        self.refresh_all()

    def on_buy_dev_card(self):
        ok, msg = self.game.buy_dev_card(self.game.current_player_idx)
        if ok:
            messagebox.showinfo("Development Card", f"You drew: {msg}")
            self.refresh_all()
            self.auto_save()
        else:
            messagebox.showwarning("Development Card", msg)

    def on_end_turn(self):
        if self.game.phase != CatanGame.PHASE_MAIN_ACTION:
            return
        self.mode = None
        ok, msg = self.game.end_turn()
        if ok:
            self.refresh_all()
            self.auto_save()
            self._prompt_pass_turn_if_needed()

    def on_quick_setup(self):
        if self.game.phase in (CatanGame.PHASE_SETUP_1, CatanGame.PHASE_SETUP_2):
            self.game.quick_auto_setup()
            self.refresh_all()
            self.auto_save()

    def _prompt_pass_turn_if_needed(self):
        """Pass-and-play notification for next player."""
        curr = self.game.current_player
        msg = f"Turn passed to Player [{curr.name}].\n\nPlease pass controls to {curr.name} and click OK to proceed."
        messagebox.showinfo(f"PASS AND PLAY: {curr.name}'s TURN", msg)

    # -------------------------------------------------------------------------
    # TRADING SYSTEM (INITIATION AVAILABLE ONLY TO ACTIVE PLAYER)
    # -------------------------------------------------------------------------
    def on_open_trade_menu(self):
        curr_p = self.game.current_player
        # Verify requirement: Trading initiation available ONLY to active player
        if not self.game.can_initiate_trade(curr_p.player_id):
            messagebox.showwarning("Trade Restriction", "Trading initiation is ONLY available to the active player whose turn is currently being played!")
            return

        TradeDialog(self.root, self.game, self._on_trade_executed)

    def _on_trade_executed(self):
        self.refresh_all()
        self.auto_save()

    # -------------------------------------------------------------------------
    # ROBBER STEAL DIALOG
    # -------------------------------------------------------------------------
    def prompt_steal_dialog(self):
        if not self.game.robber_potential_victims:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("ROBBER: STEAL RESOURCE")
        dialog.geometry("380x240")
        dialog.configure(bg=DOS_NAVY)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog, text="══╡ SELECT VICTIM ╞══",
            bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_SUBTITLE
        ).pack(pady=8)

        tk.Label(
            dialog,
            text=f"{self.game.current_player.name}, choose an opponent to steal 1 card from:",
            bg=DOS_NAVY, fg=DOS_WHITE, font=FONT_SMALL, wraplength=340
        ).pack(pady=4)

        for vid in self.game.robber_potential_victims:
            victim = self.game.players[vid]
            btn_text = f"STEAL FROM {victim.name} ({victim.total_resources} cards)"
            def _steal(v_id=vid):
                self.game.steal_card(v_id)
                dialog.destroy()
                self.refresh_all()
                self.auto_save()

            DOSButton(dialog, text=btn_text, command=_steal, bg="#551111").pack(fill="x", padx=20, pady=4)

    # -------------------------------------------------------------------------
    # TOP MENU ACTIONS (NEW, SAVE, LOAD, RULES, QUIT)
    # -------------------------------------------------------------------------
    def on_new_game(self):
        if messagebox.askyesno("New Game", "Start a new Catan game? Any unsaved progress will be replaced."):
            self.mode = None
            self.game = CatanGame()
            self.db.save_game(self.game, slot_name="Active Session")
            self.refresh_all()
            self.log_message("Started a new Catan game session.")

    def on_save_game(self):
        SaveLoadDialog(self.root, self.db, self.game, mode="SAVE", on_load_cb=self._on_game_loaded)

    def on_load_game(self):
        SaveLoadDialog(self.root, self.db, self.game, mode="LOAD", on_load_cb=self._on_game_loaded)

    def _on_game_loaded(self, loaded_game: CatanGame):
        self.game = loaded_game
        self.mode = None
        self.refresh_all()
        self.log_message(f"Loaded game from database (Turn {self.game.turn_number}).")

    def on_show_rules(self):
        RulesHelpDialog(self.root)

    def on_quit(self):
        if messagebox.askyesno("Exit Catan", "Exit to DOS? Game state is saved in the SQL database."):
            self.auto_save()
            self.root.destroy()

    # -------------------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # -------------------------------------------------------------------------
    def _bind_keyboard_shortcuts(self):
        self.root.bind("<r>", lambda e: self.on_roll_dice())
        self.root.bind("<R>", lambda e: self.on_roll_dice())
        self.root.bind("<b>", lambda e: self.on_start_build_road())
        self.root.bind("<B>", lambda e: self.on_start_build_road())
        self.root.bind("<s>", lambda e: self.on_start_build_settlement())
        self.root.bind("<S>", lambda e: self.on_start_build_settlement())
        self.root.bind("<c>", lambda e: self.on_start_build_city())
        self.root.bind("<C>", lambda e: self.on_start_build_city())
        self.root.bind("<t>", lambda e: self.on_open_trade_menu())
        self.root.bind("<T>", lambda e: self.on_open_trade_menu())
        self.root.bind("<e>", lambda e: self.on_end_turn())
        self.root.bind("<E>", lambda e: self.on_end_turn())
        self.root.bind("<F1>", lambda e: self.on_show_rules())
        self.root.bind("<F2>", lambda e: self.on_save_game())
        self.root.bind("<Escape>", lambda e: self.cancel_mode())


# =============================================================================
# TRADING DIALOG (ACTIVE PLAYER INITIATION ONLY)
# =============================================================================

class TradeDialog(tk.Toplevel):
    def __init__(self, master, game: CatanGame, callback: Callable):
        super().__init__(master)
        self.title("CATAN TRADING POST [DOS-BOX]")
        self.geometry("640x520")
        self.configure(bg=DOS_NAVY)
        self.transient(master)
        self.grab_set()

        self.game = game
        self.callback = callback
        self.active_player = game.current_player

        self.partner_var = tk.StringVar(value="BANK")
        self.offer_vars: Dict[str, tk.IntVar] = {r: tk.IntVar(value=0) for r in RESOURCES}
        self.request_vars: Dict[str, tk.IntVar] = {r: tk.IntVar(value=0) for r in RESOURCES}
        self.offer_hint_labels: Dict[str, tk.Label] = {}
        self.req_hint_labels: Dict[str, tk.Label] = {}

        self._build_ui()

    def _build_ui(self):
        # Header
        tk.Label(
            self, text="╔═════════════[ CATAN TRADING POST ]═════════════╗",
            bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_TITLE
        ).pack(pady=(8, 2))

        tk.Label(
            self, text=f"Initiator: {self.active_player.name} (Active Player)",
            bg=DOS_NAVY, fg=DOS_CYAN, font=FONT_BODY_BOLD
        ).pack(pady=(0, 6))

        # Select Trading Partner
        partner_frame = tk.Frame(self, bg=DOS_NAVY, bd=1, relief="ridge")
        partner_frame.pack(fill="x", padx=16, pady=4)

        tk.Label(
            partner_frame, text="TRADE WITH:",
            bg=DOS_NAVY, fg=DOS_WHITE, font=FONT_BODY_BOLD
        ).pack(side="left", padx=8)

        # Bank option
        rb_bank = tk.Radiobutton(
            partner_frame, text="BANK / PORTS", variable=self.partner_var, value="BANK",
            bg=DOS_NAVY, fg=DOS_YELLOW, selectcolor="#000033", font=FONT_BODY_BOLD,
            activebackground=DOS_NAVY, activeforeground=DOS_YELLOW,
            command=self._on_partner_changed
        )
        rb_bank.pack(side="left", padx=6)

        # Other players
        for p in self.game.players:
            if p.player_id != self.active_player.player_id:
                rb = tk.Radiobutton(
                    partner_frame, text=f"{p.name} ({p.total_resources})", variable=self.partner_var, value=str(p.player_id),
                    bg=DOS_NAVY, fg=p.color_info["text"], selectcolor="#000033", font=FONT_BODY_BOLD,
                    activebackground=DOS_NAVY, activeforeground=p.color_info["text"],
                    command=self._on_partner_changed
                )
                rb.pack(side="left", padx=4)

        # Trade Columns Frame
        cols_frame = tk.Frame(self, bg=DOS_NAVY)
        cols_frame.pack(fill="both", expand=True, padx=16, pady=8)

        # Column 1: YOU OFFER
        col_offer = tk.Frame(cols_frame, bg="#0C1420", bd=2, relief="groove")
        col_offer.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(
            col_offer, text="═╡ YOU OFFER ╞═",
            bg="#0C1420", fg=DOS_GREEN, font=FONT_SUBTITLE
        ).pack(pady=4)

        for res in RESOURCES:
            self._create_resource_counter(col_offer, res, self.offer_vars[res], is_offer=True)

        # Column 2: YOU REQUEST
        col_req = tk.Frame(cols_frame, bg="#0C1420", bd=2, relief="groove")
        col_req.pack(side="right", fill="both", expand=True, padx=4)

        tk.Label(
            col_req, text="═╡ YOU REQUEST ╞═",
            bg="#0C1420", fg=DOS_YELLOW, font=FONT_SUBTITLE
        ).pack(pady=4)

        for res in RESOURCES:
            self._create_resource_counter(col_req, res, self.request_vars[res], is_offer=False)

        # Info Box (Ratio / Status)
        self.info_lbl = tk.Label(
            self, text="Select resources to exchange.",
            bg=DOS_NAVY, fg=DOS_CYAN, font=FONT_SMALL
        )
        self.info_lbl.pack(pady=4)

        # Bottom Buttons
        btn_box = tk.Frame(self, bg=DOS_NAVY)
        btn_box.pack(fill="x", padx=16, pady=(4, 10))

        DOSButton(btn_box, text="EXECUTE TRADE", command=self.on_execute_trade, bg="#005500", width=18).pack(side="left", padx=10)
        DOSButton(btn_box, text="CANCEL", command=self.destroy, bg="#551111", width=14).pack(side="right", padx=10)

        self._on_partner_changed()

    def _create_resource_counter(self, parent: tk.Frame, resource: str, var: tk.IntVar, is_offer: bool):
        row = tk.Frame(parent, bg="#0C1420")
        row.pack(fill="x", padx=6, pady=3)

        res_name = RESOURCE_NAMES[resource]

        lbl_title = tk.Label(
            row, text=f"{res_name:7s}",
            bg="#0C1420", fg=HEX_COLORS[resource], font=FONT_SMALL, width=8, anchor="w"
        )
        lbl_title.pack(side="left")

        lbl_hint = tk.Label(
            row, text="", bg="#0C1420", fg=DOS_GREY, font=FONT_TINY, width=9, anchor="w"
        )
        lbl_hint.pack(side="left")
        if is_offer:
            self.offer_hint_labels[resource] = lbl_hint
        else:
            self.req_hint_labels[resource] = lbl_hint

        def _dec():
            val = var.get()
            if val > 0:
                var.set(val - 1)
                self._update_info()

        def _inc():
            val = var.get()
            my_amt = self.active_player.resources.get(resource, 0)
            if is_offer and val >= my_amt:
                return  # Cannot offer more than held
            var.set(val + 1)
            self._update_info()

        tk.Button(
            row, text="-", command=_dec, bg=DOS_NAVY, fg=DOS_WHITE,
            font=FONT_TINY, width=2, bd=1
        ).pack(side="left", padx=2)

        tk.Label(
            row, textvariable=var, bg="#000000", fg=DOS_WHITE,
            font=FONT_BODY_BOLD, width=3, bd=1, relief="sunken"
        ).pack(side="left", padx=2)

        tk.Button(
            row, text="+", command=_inc, bg=DOS_NAVY, fg=DOS_WHITE,
            font=FONT_TINY, width=2, bd=1
        ).pack(side="left", padx=2)

    def _on_partner_changed(self):
        target = self.partner_var.get()
        # Update hints for both sides
        for r in RESOURCES:
            my_amt = self.active_player.resources.get(r, 0)
            self.offer_hint_labels[r].configure(text=f"(You:{my_amt:2d})")

            if target == "BANK":
                b_amt = self.game.bank.get(r, 0)
                self.req_hint_labels[r].configure(text=f"(Bnk:{b_amt:2d})")
            else:
                p_id = int(target)
                other_p = self.game.players[p_id]
                o_amt = other_p.resources.get(r, 0)
                self.req_hint_labels[r].configure(text=f"({other_p.name[:3]}:{o_amt:2d})")

        if target == "BANK":
            rates = self.game.get_player_unlocked_rates(self.active_player.player_id)
            rates_str = " | ".join(f"{r[:3].upper()}: {rate}:1" for r, (rate, _) in rates.items())
            self.info_lbl.configure(
                text=f"YOUR UNLOCKED BANK / PORT RATES:\n[{rates_str}]\nSelect 1 resource to offer and 1 resource to receive.",
                fg=DOS_CYAN
            )
        else:
            partner_p = self.game.players[int(target)]
            self.info_lbl.configure(
                text=f"Proposing player-to-player trade with {partner_p.name} ({partner_p.total_resources} cards).",
                fg=DOS_CYAN
            )
        self._update_info()

    def _update_info(self):
        target = self.partner_var.get()
        # Keep hint labels updated
        for r in RESOURCES:
            my_amt = self.active_player.resources.get(r, 0)
            self.offer_hint_labels[r].configure(text=f"(You:{my_amt:2d})")
            if target == "BANK":
                b_amt = self.game.bank.get(r, 0)
                self.req_hint_labels[r].configure(text=f"(Bnk:{b_amt:2d})")

        if target == "BANK":
            offer_items = [(r, v.get()) for r, v in self.offer_vars.items() if v.get() > 0]
            req_items = [(r, v.get()) for r, v in self.request_vars.items() if v.get() > 0]

            if len(offer_items) == 1 and len(req_items) == 1:
                off_res, off_amt = offer_items[0]
                req_res, req_amt = req_items[0]
                ratio, port_desc = self.game.get_best_bank_ratio(self.active_player.player_id, off_res)
                bank_avail = self.game.bank.get(req_res, 0)

                required_give = ratio * req_amt
                if off_amt == required_give:
                    if bank_avail >= req_amt:
                        self.info_lbl.configure(
                            text=f"VALID TRADE! Give {off_amt} {RESOURCE_NAMES[off_res]} ({port_desc}) -> Receive {req_amt} {RESOURCE_NAMES[req_res]} (Bank has {bank_avail})",
                            fg=DOS_GREEN
                        )
                    else:
                        self.info_lbl.configure(
                            text=f"BANK SHORTAGE: Bank has only {bank_avail} {RESOURCE_NAMES[req_res]} available (requested {req_amt})!",
                            fg=DOS_RED
                        )
                else:
                    self.info_lbl.configure(
                        text=f"Rate is {ratio}:1 ({port_desc}). Offer {required_give} {RESOURCE_NAMES[off_res]} for {req_amt} {RESOURCE_NAMES[req_res]} (Currently offering {off_amt}).",
                        fg=DOS_YELLOW
                    )
            elif len(offer_items) > 1 or len(req_items) > 1:
                self.info_lbl.configure(
                    text="Bank / Port trade requires offering exactly ONE resource type and receiving ONE resource type.",
                    fg=DOS_YELLOW
                )
            else:
                rates = self.game.get_player_unlocked_rates(self.active_player.player_id)
                rates_str = " | ".join(f"{r[:3].upper()}: {rate}:1" for r, (rate, _) in rates.items())
                self.info_lbl.configure(
                    text=f"YOUR UNLOCKED BANK / PORT RATES:\n[{rates_str}]\nSelect 1 resource to offer and 1 resource to receive.",
                    fg=DOS_CYAN
                )
        pass

    def on_execute_trade(self):
        target = self.partner_var.get()
        offer = {r: v.get() for r, v in self.offer_vars.items() if v.get() > 0}
        request = {r: v.get() for r, v in self.request_vars.items() if v.get() > 0}

        if sum(offer.values()) == 0 or sum(request.values()) == 0:
            messagebox.showwarning("Trade", "You must offer at least 1 resource and request at least 1 resource.")
            return

        if target == "BANK":
            if len(offer) != 1 or len(request) != 1:
                messagebox.showwarning("Bank Trade", "Bank trade requires offering exactly ONE resource type and requesting ONE resource type.")
                return
            give_res, give_amt = list(offer.items())[0]
            get_res, get_amt = list(request.items())[0]

            ratio, port_desc = self.game.get_best_bank_ratio(self.active_player.player_id, give_res)
            required_give = ratio * get_amt
            if give_amt != required_give:
                messagebox.showwarning("Bank Trade", f"Rate for {RESOURCE_NAMES[give_res]} is {ratio}:1 ({port_desc})!\nYou must offer exactly {required_give} {RESOURCE_NAMES[give_res]} to receive {get_amt} {RESOURCE_NAMES[get_res]}.")
                return

            if self.game.bank.get(get_res, 0) < get_amt:
                messagebox.showwarning("Bank Shortage", f"The Bank only has {self.game.bank.get(get_res, 0)} {RESOURCE_NAMES[get_res]} in stock!")
                return

            ok, msg = self.game.execute_bank_trade(
                self.active_player.player_id, give_res, give_amt, get_res
            )
            if ok:
                messagebox.showinfo("Bank Trade", msg)
                self.callback()
                self.destroy()
            else:
                messagebox.showwarning("Bank Trade", msg)

        else:
            partner_id = int(target)
            partner = self.game.players[partner_id]

            # Validate partner has cards
            if not partner.can_afford(request):
                messagebox.showwarning("Trade", f"{partner.name} does not hold all the requested cards!")
                return

            # Pass-and-play Confirmation Prompt for the Trade Partner
            off_str = ", ".join(f"{cnt} {RESOURCE_NAMES[r]}" for r, cnt in offer.items())
            req_str = ", ".join(f"{cnt} {RESOURCE_NAMES[r]}" for r, cnt in request.items())

            prompt_msg = (
                f"TRADE PROPOSAL FOR {partner.name}:\n\n"
                f"{self.active_player.name} offers you:\n   * {off_str}\n\n"
                f"{self.active_player.name} requests from you:\n   * {req_str}\n\n"
                f"Player {partner.name}, do you ACCEPT this trade?"
            )
            accepted = messagebox.askyesno(f"TRADE PROPOSAL FOR {partner.name}", prompt_msg)

            if accepted:
                ok, msg = self.game.execute_trade(self.active_player.player_id, partner_id, offer, request)
                if ok:
                    messagebox.showinfo("Trade Executed", msg)
                    self.callback()
                    self.destroy()
                else:
                    messagebox.showwarning("Trade Error", msg)
            else:
                self.game.log(f"{partner.name} declined trade offer from {self.active_player.name}.")
                messagebox.showinfo("Trade Declined", f"{partner.name} rejected the trade offer.")
                self.callback()


# =============================================================================
# SAVE / LOAD DIALOG
# =============================================================================

class SaveLoadDialog(tk.Toplevel):
    def __init__(self, master, db: CatanDatabase, game: CatanGame, mode: str, on_load_cb: Callable):
        super().__init__(master)
        self.db = db
        self.game = game
        self.mode = mode  # "SAVE" or "LOAD"
        self.on_load_cb = on_load_cb

        self.title(f"SQL DATABASE - {mode} GAME")
        self.geometry("560x420")
        self.configure(bg=DOS_NAVY)
        self.transient(master)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        title_text = "═╡ SAVE GAME TO SQL DATABASE ╞═" if self.mode == "SAVE" else "═╡ LOAD GAME FROM SQL DATABASE ╞═"
        tk.Label(self, text=title_text, bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_SUBTITLE).pack(pady=8)

        if self.mode == "SAVE":
            input_frame = tk.Frame(self, bg=DOS_NAVY)
            input_frame.pack(fill="x", padx=20, pady=4)
            tk.Label(input_frame, text="SAVE NAME:", bg=DOS_NAVY, fg=DOS_WHITE, font=FONT_BODY_BOLD).pack(side="left", padx=4)
            self.name_entry = tk.Entry(input_frame, bg="#000000", fg=DOS_WHITE, insertbackground=DOS_WHITE, font=FONT_BODY, width=30)
            self.name_entry.pack(side="left", padx=4)
            self.name_entry.insert(0, f"Campaign (Turn {self.game.turn_number})")

        # Saved games listbox
        list_frame = tk.Frame(self, bg=DOS_NAVY)
        list_frame.pack(fill="both", expand=True, padx=20, pady=6)

        self.listbox = tk.Listbox(
            list_frame, bg="#050810", fg=DOS_CYAN, selectbackground=DOS_CYAN,
            selectforeground="#000000", font=FONT_SMALL, bd=2, relief="sunken"
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(list_frame, command=self.listbox.yview, bg=DOS_NAVY)
        sb.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)

        self.saved_slots = self.db.list_saved_games()
        for s in self.saved_slots:
            p_name = PLAYER_NAMES[s["current_player_idx"]]
            item_text = f"ID #{s['game_id']:2d} | {s['name']:20s} | Turn {s['turn_number']:2d} ({p_name}) | {s['updated_at']}"
            self.listbox.insert("end", item_text)

        # Action Buttons
        btn_box = tk.Frame(self, bg=DOS_NAVY)
        btn_box.pack(fill="x", padx=20, pady=10)

        if self.mode == "SAVE":
            DOSButton(btn_box, text="SAVE NEW SLOT", command=self.on_save, bg="#005500").pack(side="left", padx=6)
        else:
            DOSButton(btn_box, text="LOAD SELECTED", command=self.on_load, bg="#005500").pack(side="left", padx=6)
            DOSButton(btn_box, text="DELETE SLOT", command=self.on_delete, bg="#770000").pack(side="left", padx=6)

        DOSButton(btn_box, text="CANCEL", command=self.destroy, bg="#551111").pack(side="right", padx=6)

    def on_save(self):
        name = self.name_entry.get().strip() or "Untitled Save"
        self.db.save_game(self.game, slot_name=name)
        messagebox.showinfo("Saved", f"Game saved successfully to SQLite database as '{name}'.")
        self.destroy()

    def on_load(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Load Game", "Please select a saved game slot from the list.")
            return
        slot = self.saved_slots[sel[0]]
        loaded = self.db.load_game(slot["game_id"])
        if loaded:
            self.on_load_cb(loaded)
            self.destroy()
        else:
            messagebox.showerror("Load Game", "Failed to load saved game from database.")

    def on_delete(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        slot = self.saved_slots[sel[0]]
        if messagebox.askyesno("Delete", f"Delete saved game '{slot['name']}'?"):
            self.db.delete_saved_game(slot["game_id"])
            self.saved_slots = self.db.list_saved_games()
            self.listbox.delete(0, "end")
            for s in self.saved_slots:
                p_name = PLAYER_NAMES[s["current_player_idx"]]
                self.listbox.insert("end", f"ID #{s['game_id']:2d} | {s['name']:20s} | Turn {s['turn_number']:2d} ({p_name}) | {s['updated_at']}")


# =============================================================================
# RULES & HELP DIALOG
# =============================================================================

class RulesHelpDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("HOW TO PLAY CATAN [DOS-BOX]")
        self.geometry("700x560")
        self.configure(bg=DOS_NAVY)
        self.transient(master)

        tk.Label(
            self, text="═╡ RULES & GUIDE : SETTLERS OF CATAN ╞═",
            bg=DOS_NAVY, fg=DOS_YELLOW, font=FONT_TITLE
        ).pack(pady=8)

        text_frame = tk.Frame(self, bg="#000000", bd=2, relief="sunken")
        text_frame.pack(fill="both", expand=True, padx=16, pady=4)

        t = tk.Text(text_frame, bg="#050810", fg=DOS_WHITE, font=FONT_SMALL, wrap="word", padx=8, pady=8)
        t.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(text_frame, command=t.yview, bg=DOS_NAVY)
        sb.pack(side="right", fill="y")
        t.configure(yscrollcommand=sb.set)

        rules_content = """
================================================================================
                    THE SETTLERS OF CATAN (DOS-BOX EDITION)
================================================================================

1. OBJECTIVE:
   Be the first player to accumulate 10 Victory Points (VP)!
   - Settlement: 1 Victory Point
   - City:       2 Victory Points
   - Longest Road (5+ segments): 2 Victory Points
   - Largest Army (3+ Knights):  2 Victory Points
   - Victory Point Dev Cards:    1 Victory Point each

2. HEXAGON COLOR CODING:
   - RED:         Brick (Hill)
   - LIGHT GREEN: Sheep (Pasture)
   - DARK GREEN:  Wood (Forest)
   - YELLOW:      Wheat (Field)
   - GREY:        Ore (Mountain)
   - KHAKI:       Robber's Hexagon (Desert)

3. NUMBER TOKENS & PROBABILITY:
   - Printed in WHITE font at the center of each tile.
   - Dots below each number represent occurrence probability out of 36:
     * 6 and 8:  5 dots (•••••) - Highest probability!
     * 5 and 9:  4 dots (••••)
     * 4 and 10: 3 dots (•••)
     * 3 and 11: 2 dots (••)
     * 2 and 12: 1 dot  (•)     - Lowest probability
   - When 2d6 is rolled, all adjacent buildings receive resources unless the
     hex has the Robber.

4. RESOURCE BANK (95 CARDS TOTAL):
   - Bank holds 95 resource cards: 19 Wood, 19 Brick, 19 Sheep, 19 Wheat, 19 Ore.
   - Resource Bank UI element displays real-time inventory counts.
   - Cards are produced from the bank, and spent/discarded cards return to the bank.

5. BUILDING COSTS:
   - ROAD:       1 Wood + 1 Brick
   - SETTLEMENT: 1 Wood + 1 Brick + 1 Sheep + 1 Wheat
   - CITY:       2 Wheat + 3 Ore (Upgrades an existing settlement)
   - DEV CARD:   1 Sheep + 1 Wheat + 1 Ore

6. DISTANCE RULE:
   - A settlement or city cannot be built within 1 road segment (1 intersection)
     of ANY other settlement or city!

7. TRADING SYSTEM (ACTIVE PLAYER INITIATION ONLY):
   - Trading initiation is available ONLY to the person whose turn is currently
     being played!
   - BANK TRADING (4:1): Trade 4 of any identical resource for 1 card from Bank.
   - GENERIC PORTS (3:1): Build on a 3:1 coastal harbor to trade 3 identical cards
     of ANY resource for 1 card from the Bank.
   - SPECIFIC PORTS (2:1): Build on a 2:1 coastal harbor to trade 2 cards of that
     matching resource (Wood, Brick, Sheep, Wheat, Ore) for 1 card from Bank!
   - PLAYER-TO-PLAYER: Active player proposes trades to any opponent with
     pass-and-play interactive confirmation.

8. THE ROBBER & 7:
   - Rolling a 7 activates the Robber.
   - Any player holding more than 7 cards must discard half (rounded down) to Bank.
   - The active player relocates the Robber to any tile, blocking production.
   - Active player steals 1 random resource card from an opponent on that tile.

9. LOCAL PASS-AND-PLAY:
   - 4 House Colors: RED, BLUE, WHITE, ORANGE.
   - Each piece features a crisp WHITE outline!
   - Controls pass sequentially from player to player.

10. SQL DATABASE PERSISTENCE:
   - All game state, player inventories, Bank cards, and logs are automatically
     backed up to an SQLite database ('catan_game.db') on every action!
   - Resume right where you left off upon reopening the app.

KEYBOARD SHORTCUTS:
   [R] Roll Dice      [B] Build Road     [S] Build Settlement
   [C] Build City     [T] Trade          [E] End Turn
   [F1] Rules Help    [F2] Save Game     [Esc] Cancel Action
================================================================================
"""
        t.insert("1.0", rules_content)
        t.configure(state="disabled")

        DOSButton(self, text="CLOSE", command=self.destroy, bg=DOS_NAVY, width=12).pack(pady=8)
