"""
catan_constants.py - Constants, Palette, Rules, and Configuration for Catan DOS-Box Edition.
"""

# -----------------------------------------------------------------------------
# RESOURCE TYPES
# -----------------------------------------------------------------------------
BRICK = "brick"
SHEEP = "sheep"
WOOD = "wood"
WHEAT = "wheat"
ORE = "ore"
DESERT = "desert"

RESOURCES = [WOOD, BRICK, SHEEP, WHEAT, ORE]

RESOURCE_NAMES = {
    BRICK: "Brick",
    SHEEP: "Sheep",
    WOOD: "Wood",
    WHEAT: "Wheat",
    ORE: "Ore",
    DESERT: "Desert",
}

# -----------------------------------------------------------------------------
# HEXAGON COLORS (Strict user specifications)
# RED: Brick
# LIGHT GREEN: Sheep
# DARK GREEN: Wood
# YELLOW: Wheat
# GREY: Ore
# KHAKI: Robber's hexagon (Desert)
# -----------------------------------------------------------------------------
HEX_COLORS = {
    BRICK: "#C0392B",       # RED: Brick
    SHEEP: "#2ECC71",       # LIGHT GREEN: Sheep
    WOOD: "#145A32",        # DARK GREEN: Wood
    WHEAT: "#F1C40F",       # YELLOW: Wheat
    ORE: "#7F8C8D",         # GREY: Ore
    DESERT: "#D2B48C",      # KHAKI: Robber's hexagon
}

# -----------------------------------------------------------------------------
# PLAYER HOUSE COLORS (Strict user specifications)
# RED, BLUE, WHITE, ORANGE
# Each road, house, or city must also have a white outline!
# -----------------------------------------------------------------------------
PLAYER_COLORS = {
    "RED": {
        "fill": "#E74C3C",
        "outline": "#FFFFFF",
        "text": "#FF6B6B",
        "name": "RED",
    },
    "BLUE": {
        "fill": "#2980B9",
        "outline": "#FFFFFF",
        "text": "#5DADE2",
        "name": "BLUE",
    },
    "WHITE": {
        "fill": "#E0E6ED",     # Crisp light tone so white outline is clearly distinguished
        "outline": "#FFFFFF",
        "text": "#FFFFFF",
        "name": "WHITE",
    },
    "ORANGE": {
        "fill": "#E67E22",
        "outline": "#FFFFFF",
        "text": "#F39C12",
        "name": "ORANGE",
    },
}

PLAYER_NAMES = ["RED", "BLUE", "WHITE", "ORANGE"]

# -----------------------------------------------------------------------------
# PROBABILITY DOTS MAPPING
# Numbers printed with white font, along with dots below numbers representing
# probability of that number occurring (6 and 8 highest, 2 and 12 lowest).
# -----------------------------------------------------------------------------
PROBABILITY_DOTS = {
    2: 1,   # 1/36
    3: 2,   # 2/36
    4: 3,   # 3/36
    5: 4,   # 4/36
    6: 5,   # 5/36 (highest)
    8: 5,   # 5/36 (highest)
    9: 4,   # 4/36
    10: 3,  # 3/36
    11: 2,  # 2/36
    12: 1,  # 1/36 (lowest)
}

# -----------------------------------------------------------------------------
# BUILDING COSTS & VP
# -----------------------------------------------------------------------------
COST_ROAD = {WOOD: 1, BRICK: 1}
COST_SETTLEMENT = {WOOD: 1, BRICK: 1, SHEEP: 1, WHEAT: 1}
COST_CITY = {WHEAT: 2, ORE: 3}
COST_DEV_CARD = {SHEEP: 1, WHEAT: 1, ORE: 1}

BUILDING_COSTS = {
    "road": COST_ROAD,
    "settlement": COST_SETTLEMENT,
    "city": COST_CITY,
    "dev_card": COST_DEV_CARD,
}

WINNING_VICTORY_POINTS = 10

# -----------------------------------------------------------------------------
# RESOURCE BANK (Official Catan Rules: 95 cards total, 19 of each type)
# -----------------------------------------------------------------------------
BANK_INITIAL_PER_RESOURCE = 19
BANK_INITIAL_TOTAL = 95  # 19 * 5 = 95 cards

# -----------------------------------------------------------------------------
# DEVELOPMENT CARDS
# -----------------------------------------------------------------------------
CARD_KNIGHT = "Knight"
CARD_VICTORY_POINT = "Victory Point"
CARD_ROAD_BUILDING = "Road Building"
CARD_YEAR_OF_PLENTY = "Year of Plenty"
CARD_MONOPOLY = "Monopoly"

DEV_CARD_DECK = (
    [CARD_KNIGHT] * 14 +
    [CARD_VICTORY_POINT] * 5 +
    [CARD_ROAD_BUILDING] * 2 +
    [CARD_YEAR_OF_PLENTY] * 2 +
    [CARD_MONOPOLY] * 2
)

# -----------------------------------------------------------------------------
# RETRO DOS-BOX THEME & PALETTE
# -----------------------------------------------------------------------------
DOS_BG_DARK = "#0A0E1A"        # Deep retro terminal space
DOS_BG_PANEL = "#111827"       # Panel background
DOS_BG_BOARD = "#001428"       # Sea / Ocean dark blue
DOS_NAVY = "#000084"           # Norton Commander classic blue
DOS_CYAN = "#00E5FF"           # DOS high-intensity cyan
DOS_YELLOW = "#FFFF55"         # DOS bright yellow
DOS_GREEN = "#55FF55"          # DOS bright green
DOS_RED = "#FF5555"            # DOS bright red
DOS_WHITE = "#FFFFFF"          # DOS pure white
DOS_GREY = "#9E9E9E"           # DOS grey
DOS_DARK_GREY = "#374151"      # Border line dark grey
DOS_ACCENT = "#55FFFF"

DOS_FONT_FAMILY = "Consolas"
FONT_TITLE = (DOS_FONT_FAMILY, 14, "bold")
FONT_SUBTITLE = (DOS_FONT_FAMILY, 11, "bold")
FONT_BODY = (DOS_FONT_FAMILY, 10, "normal")
FONT_BODY_BOLD = (DOS_FONT_FAMILY, 10, "bold")
FONT_SMALL = (DOS_FONT_FAMILY, 9, "normal")
FONT_TINY = (DOS_FONT_FAMILY, 8, "normal")
FONT_DICE = (DOS_FONT_FAMILY, 12, "bold")
FONT_HEX_NUM = (DOS_FONT_FAMILY, 13, "bold")
FONT_HEX_DOTS = (DOS_FONT_FAMILY, 11, "bold")
