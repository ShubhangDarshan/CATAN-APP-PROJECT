"""
catan_board.py - Graph topology, geometry, and board generation for Catan DOS-Box Edition.
"""

import math
import random
from typing import Dict, List, Tuple, Optional, Set
from catan_constants import (
    BRICK, SHEEP, WOOD, WHEAT, ORE, DESERT,
    HEX_COLORS, PROBABILITY_DOTS
)

class HexTile:
    def __init__(self, hex_id: int, row: int, col: int, center_x: float, center_y: float,
                 resource: str, number_token: Optional[int] = None):
        self.hex_id = hex_id
        self.row = row
        self.col = col
        self.center_x = center_x
        self.center_y = center_y
        self.resource = resource
        self.number_token = number_token
        self.has_robber = (resource == DESERT)
        self.vertex_ids: List[int] = []
        self.edge_ids: List[int] = []

    @property
    def color(self) -> str:
        return HEX_COLORS.get(self.resource, "#888888")

    @property
    def probability_dots(self) -> int:
        if self.number_token:
            return PROBABILITY_DOTS.get(self.number_token, 0)
        return 0


class Vertex:
    def __init__(self, vertex_id: int, x: float, y: float):
        self.vertex_id = vertex_id
        self.x = x
        self.y = y
        self.adjacent_vertices: List[int] = []
        self.adjacent_edges: List[int] = []
        self.adjacent_hexes: List[int] = []
        self.port_type: Optional[str] = None  # None, "3:1", "wood", "brick", "sheep", "wheat", "ore"


class Edge:
    def __init__(self, edge_id: int, v1: int, v2: int):
        self.edge_id = edge_id
        self.v1 = min(v1, v2)
        self.v2 = max(v1, v2)
        self.adjacent_hexes: List[int] = []
        self.is_port: bool = False
        self.port_type: Optional[str] = None


class CatanBoard:
    """
    Standard 19-hex Catan board with 54 vertices and 72 edges.
    Calculates precise hex coordinates, shared vertices, edges, and resource distributions.
    """
    def __init__(self, radius: float = 52.0, randomize: bool = True, seed: Optional[int] = None):
        self.radius = radius
        self.hexes: Dict[int, HexTile] = {}
        self.vertices: Dict[int, Vertex] = {}
        self.edges: Dict[int, Edge] = {}
        self.edge_by_vertices: Dict[Tuple[int, int], int] = {}
        self.robber_hex_id: int = 0
        self.seed = seed
        self._build_board(randomize=randomize, seed=seed)

    def _build_board(self, randomize: bool = True, seed: Optional[int] = None):
        rng = random.Random(seed)

        # Standard Catan resource pool (19 tiles)
        resources_pool = (
            [WOOD] * 4 +
            [SHEEP] * 4 +
            [WHEAT] * 4 +
            [BRICK] * 3 +
            [ORE] * 3 +
            [DESERT] * 1
        )

        # Standard Catan number tokens (18 tokens)
        numbers_pool = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

        if randomize:
            rng.shuffle(resources_pool)
            # Ensure desert gets no number, and 6 and 8 are reasonably separated
            numbers_assigned = self._assign_balanced_numbers(resources_pool, numbers_pool, rng)
        else:
            # Classic fixed layout
            resources_pool = [
                WOOD, SHEEP, WHEAT,
                BRICK, ORE, BRICK, SHEEP,
                DESERT, WOOD, WHEAT, WOOD, ORE,
                BRICK, SHEEP, WHEAT, SHEEP,
                WHEAT, WOOD, ORE
            ]
            numbers_assigned = [
                11, 12, 9,
                4, 6, 5, 10,
                None, 3, 11, 4, 8,
                8, 10, 9, 3,
                5, 2, 6
            ]

        # Geometry setup
        W = math.sqrt(3) * self.radius
        row_counts = [3, 4, 5, 4, 3]

        hex_id = 0
        vertex_coord_map: Dict[Tuple[float, float], int] = {}

        # 1. Create Hexes and Vertices
        for r, count in enumerate(row_counts):
            cy = r * 1.5 * self.radius
            for c in range(count):
                cx = (c - count / 2.0 + 0.5) * W
                res = resources_pool[hex_id]
                num = numbers_assigned[hex_id]

                hex_tile = HexTile(
                    hex_id=hex_id,
                    row=r,
                    col=c,
                    center_x=cx,
                    center_y=cy,
                    resource=res,
                    number_token=num
                )
                if res == DESERT:
                    hex_tile.has_robber = True
                    self.robber_hex_id = hex_id

                self.hexes[hex_id] = hex_tile

                # Hex vertices (pointy-topped)
                hex_vids = []
                for k in range(6):
                    angle = math.radians(30 + 60 * k)
                    vx = round(cx + self.radius * math.cos(angle), 1)
                    vy = round(cy + self.radius * math.sin(angle), 1)
                    v_key = (vx, vy)

                    if v_key not in vertex_coord_map:
                        vid = len(self.vertices)
                        vertex_coord_map[v_key] = vid
                        v_obj = Vertex(vid, vx, vy)
                        self.vertices[vid] = v_obj
                    else:
                        vid = vertex_coord_map[v_key]

                    hex_vids.append(vid)
                    self.vertices[vid].adjacent_hexes.append(hex_id)

                hex_tile.vertex_ids = hex_vids
                hex_id += 1

        # 2. Create Edges
        edge_id = 0
        for hid, htile in self.hexes.items():
            verts = htile.vertex_ids
            for i in range(6):
                v1 = verts[i]
                v2 = verts[(i + 1) % 6]
                edge_key = (min(v1, v2), max(v1, v2))

                if edge_key not in self.edge_by_vertices:
                    eid = edge_id
                    edge_id += 1
                    self.edge_by_vertices[edge_key] = eid
                    e_obj = Edge(eid, v1, v2)
                    self.edges[eid] = e_obj

                    # Link adjacency
                    self.vertices[v1].adjacent_vertices.append(v2)
                    self.vertices[v2].adjacent_vertices.append(v1)
                    self.vertices[v1].adjacent_edges.append(eid)
                    self.vertices[v2].adjacent_edges.append(eid)
                else:
                    eid = self.edge_by_vertices[edge_key]

                if hid not in self.edges[eid].adjacent_hexes:
                    self.edges[eid].adjacent_hexes.append(hid)
                if eid not in htile.edge_ids:
                    htile.edge_ids.append(eid)

        # 3. Setup Coastal Ports
        self._setup_ports()

    def _assign_balanced_numbers(self, resources: List[str], numbers: List[int], rng: random.Random) -> List[Optional[int]]:
        """
        Assigns number tokens ensuring Desert gets None and 6 and 8 are not placed on adjacent hexes.
        """
        # Hex adjacency graph for adjacency checks
        hex_adj = self._get_hex_adjacency_map()

        for _ in range(500):
            shuffled_nums = list(numbers)
            rng.shuffle(shuffled_nums)

            assignment: List[Optional[int]] = []
            num_idx = 0
            for r in resources:
                if r == DESERT:
                    assignment.append(None)
                else:
                    assignment.append(shuffled_nums[num_idx])
                    num_idx += 1

            # Validate that no two 6 or 8 numbers are adjacent
            valid = True
            for h1 in range(19):
                n1 = assignment[h1]
                if n1 in (6, 8):
                    for h2 in hex_adj.get(h1, []):
                        n2 = assignment[h2]
                        if n2 in (6, 8):
                            valid = False
                            break
                if not valid:
                    break

            if valid:
                return assignment

        # Fallback if loop finishes without strict pass
        return assignment

    @staticmethod
    def _get_hex_adjacency_map() -> Dict[int, List[int]]:
        # Hex indices in 3-4-5-4-3 layout:
        # Row 0: 0, 1, 2
        # Row 1: 3, 4, 5, 6
        # Row 2: 7, 8, 9, 10, 11
        # Row 3: 12, 13, 14, 15
        # Row 4: 16, 17, 18
        adj: Dict[int, List[int]] = {i: [] for i in range(19)}
        connections = [
            # Row 0 to Row 0 & 1
            (0, 1), (1, 2),
            (0, 3), (0, 4), (1, 4), (1, 5), (2, 5), (2, 6),
            # Row 1 to Row 1 & 2
            (3, 4), (4, 5), (5, 6),
            (3, 7), (3, 8), (4, 8), (4, 9), (5, 9), (5, 10), (6, 10), (6, 11),
            # Row 2 to Row 2 & 3
            (7, 8), (8, 9), (9, 10), (10, 11),
            (7, 12), (8, 12), (8, 13), (9, 13), (9, 14), (10, 14), (10, 15), (11, 15),
            # Row 3 to Row 3 & 4
            (12, 13), (13, 14), (14, 15),
            (12, 16), (13, 16), (13, 17), (14, 17), (14, 18), (15, 18),
            # Row 4 to Row 4
            (16, 17), (17, 18)
        ]
        for a, b in connections:
            adj[a].append(b)
            adj[b].append(a)
        return adj

    def _setup_ports(self):
        """
        Assigns 9 standard coastal ports around the circular perimeter:
        4 generic (3:1) and 5 resource-specific (2:1: wood, brick, sheep, wheat, ore).
        Ensures each port occupies 2 distinct vertices with no overlap.
        """
        coastal_eids = [eid for eid, edge in self.edges.items() if len(edge.adjacent_hexes) == 1]

        # Trace circular perimeter of coastal edges
        v_to_coastal: Dict[int, List[int]] = {}
        for eid in coastal_eids:
            e = self.edges[eid]
            v_to_coastal.setdefault(e.v1, []).append(eid)
            v_to_coastal.setdefault(e.v2, []).append(eid)

        start_v = min(v_to_coastal.keys())
        curr_v = start_v
        visited_e: Set[int] = set()
        loop_e: List[int] = []

        while len(loop_e) < len(coastal_eids):
            nxt_e = None
            for eid in v_to_coastal.get(curr_v, []):
                if eid not in visited_e:
                    nxt_e = eid
                    break
            if nxt_e is None:
                break
            visited_e.add(nxt_e)
            loop_e.append(nxt_e)
            e = self.edges[nxt_e]
            curr_v = e.v2 if e.v1 == curr_v else e.v1

        # Spacing: 9 ports with 2-3 blank edges between each
        port_indices = [0, 3, 6, 10, 13, 17, 20, 23, 27]
        port_types = ["3:1", BRICK, "3:1", WOOD, SHEEP, "3:1", WHEAT, ORE, "3:1"]

        for p_idx, ptype in zip(port_indices, port_types):
            if p_idx < len(loop_e):
                eid = loop_e[p_idx]
                edge = self.edges[eid]
                edge.is_port = True
                edge.port_type = ptype
                self.vertices[edge.v1].port_type = ptype
                self.vertices[edge.v2].port_type = ptype

    def get_hex_vertices(self, hex_id: int) -> List[Tuple[float, float]]:
        htile = self.hexes[hex_id]
        return [(self.vertices[vid].x, self.vertices[vid].y) for vid in htile.vertex_ids]

    def get_edge_endpoints(self, edge_id: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        edge = self.edges[edge_id]
        v1 = self.vertices[edge.v1]
        v2 = self.vertices[edge.v2]
        return ((v1.x, v1.y), (v2.x, v2.y))

    def get_hex_at_point(self, x: float, y: float, tolerance: float = 38.0) -> Optional[int]:
        closest_id = None
        min_dist = float("inf")
        for hid, htile in self.hexes.items():
            dist = math.hypot(htile.center_x - x, htile.center_y - y)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_id = hid
        return closest_id

    def get_vertex_at_point(self, x: float, y: float, tolerance: float = 14.0) -> Optional[int]:
        closest_id = None
        min_dist = float("inf")
        for vid, v in self.vertices.items():
            dist = math.hypot(v.x - x, v.y - y)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_id = vid
        return closest_id

    def get_edge_at_point(self, x: float, y: float, tolerance: float = 10.0) -> Optional[int]:
        closest_id = None
        min_dist = float("inf")
        for eid, edge in self.edges.items():
            v1 = self.vertices[edge.v1]
            v2 = self.vertices[edge.v2]
            # Distance from point to line segment
            dist = self._point_to_segment_dist(x, y, v1.x, v1.y, v2.x, v2.y)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_id = eid
        return closest_id

    @staticmethod
    def _point_to_segment_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)
