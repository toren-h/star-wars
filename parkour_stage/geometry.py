"""Pure geometry/collision helpers used throughout the parkour stage."""
import pygame, math, random
from collections import deque
import constants as C

# ---- Helpers ----
SCOPE_RANGE_TILES = {'sniper': 500, 'raygun': 10, 'penetrator': 20}  # max Z-scope distance per gun

def rect_for_tile(r, c):
    return pygame.Rect(c * C.TILE, r * C.TILE, C.TILE, C.TILE)

def bfs_tile_path(sr, sc, gr, gc, ROWS, COLS, get_tile):
    """Shortest walkable tile path (BFS, 4-directional) from (sr,sc) to
    (gr,gc), treating 'X' as blocked. Returns a list of (r,c) tiles
    including both ends, or None if no path exists."""
    if not (0 <= sr < ROWS and 0 <= sc < COLS and 0 <= gr < ROWS and 0 <= gc < COLS):
        return None
    if get_tile(gr, gc) == 'X':
        return None
    start = (sr, sc)
    goal = (gr, gc)
    came_from = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        r, c = cur
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (r + dr, c + dc)
            nr, nc = nxt
            if (0 <= nr < ROWS and 0 <= nc < COLS and nxt not in came_from
                    and get_tile(nr, nc) != 'X'):
                came_from[nxt] = cur
                q.append(nxt)
    if goal not in came_from:
        return None
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = came_from[node]
    path.reverse()
    return path

def normalize_and_floor(level_rows):
    max_cols = max(len(row) for row in level_rows)
    lvl = [row.ljust(max_cols, ".") for row in level_rows]
    lvl[-1] = "X" * max_cols
    return lvl, len(lvl), max_cols

def scan_entities(grid, ROWS, COLS):
    start = None; goal = None; turrets = []; siths = []
    for r in range(ROWS):
        for c in range(COLS):
            ch = grid[r][c]
            if ch == 'P' and start is None: start = (c * C.TILE, r * C.TILE)
            elif ch == 'G' and goal  is None: goal  = (c * C.TILE, r * C.TILE)
            elif ch == '^': turrets.append((r, c))
            elif ch == 'S': siths.append((r, c))
    if start is None: start = (C.TILE, C.TILE)
    if goal  is None: goal  = ((COLS - 2) * C.TILE, (ROWS - 3) * C.TILE)
    return start, goal, turrets, siths

def tiles_at(rect, ROWS, COLS, get_tile):
    tiles  = []
    left   = max(0,      rect.left   // C.TILE)
    right  = min(COLS-1, rect.right  // C.TILE)
    top    = max(0,      rect.top    // C.TILE)
    bottom = min(ROWS-1, rect.bottom // C.TILE)
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            tiles.append((r, c, get_tile(r, c)))
    return tiles

def point_seg_dist_sq(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return (px - x1) ** 2 + (py - y1) ** 2
    t  = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t  = max(0, min(1, t))
    nx, ny = x1 + t * dx, y1 + t * dy
    return (px - nx) ** 2 + (py - ny) ** 2

def seg_intersect(p1, p2, q1, q2):
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) < (B[1] - A[1]) * (C[0] - A[0])
    return (ccw(p1, q1, q2) != ccw(p2, q1, q2)) and (ccw(p1, p2, q1) != ccw(p1, p2, q2))

def seg_intersect_point(p1, p2, q1, q2):
    dx1, dy1 = p2[0]-p1[0], p2[1]-p1[1]
    dx2, dy2 = q2[0]-q1[0], q2[1]-q1[1]
    denom = dx1*dy2 - dy1*dx2
    if abs(denom) < 1e-10:
        return None
    t = ((q1[0]-p1[0])*dy2 - (q1[1]-p1[1])*dx2) / denom
    s = ((q1[0]-p1[0])*dy1 - (q1[1]-p1[1])*dx1) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0:
        return (p1[0] + t*dx1, p1[1] + t*dy1)
    return None

def _saber_clip_at_zone(p1, p2, zone_p1, zone_p2, thresh_sq):
    """Return the first point on p1→p2 that is within sqrt(thresh_sq) of segment
    zone_p1→zone_p2, or None.

    Fast path: exact geometric centreline intersection.
    Fallback: binary-search for where the saber tip first enters the thick zone.
    Guard: if the saber origin is already inside the zone we return None (degenerate).
    """
    zx1, zy1, zx2, zy2 = zone_p1[0], zone_p1[1], zone_p2[0], zone_p2[1]

    # Fast path — exact centreline crossing
    pt = seg_intersect_point(p1, p2, zone_p1, zone_p2)
    if pt is not None:
        return pt

    # If the tip is not inside the zone, the saber never enters it
    if point_seg_dist_sq(p2[0], p2[1], zx1, zy1, zx2, zy2) > thresh_sq:
        return None

    # Guard: if the origin is already inside the zone we cannot clip meaningfully
    if point_seg_dist_sq(p1[0], p1[1], zx1, zy1, zx2, zy2) <= thresh_sq:
        return None

    # Binary-search for the entry point (first t where dist² ≤ thresh_sq)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    lo, hi = 0.0, 1.0
    for _ in range(20):          # 20 iterations → ~1e-6 precision
        mid = (lo + hi) * 0.5
        px, py = p1[0] + mid * dx, p1[1] + mid * dy
        if point_seg_dist_sq(px, py, zx1, zy1, zx2, zy2) <= thresh_sq:
            hi = mid
        else:
            lo = mid
    return (p1[0] + hi * dx, p1[1] + hi * dy)

def seg_intersects_rect(p1, p2, rect):
    if rect.collidepoint(p1) or rect.collidepoint(p2):
        return True
    x1, y1 = rect.topleft;  x2, y2 = rect.topright
    x3, y3 = rect.bottomright; x4, y4 = rect.bottomleft
    return (seg_intersect(p1, p2, (x1, y1), (x2, y2)) or
            seg_intersect(p1, p2, (x2, y2), (x3, y3)) or
            seg_intersect(p1, p2, (x3, y3), (x4, y4)) or
            seg_intersect(p1, p2, (x4, y4), (x1, y1)))

# ---- Lightning ----
def _make_lightning(p1, p2, segments=10, jitter=14):
    pts = [p1]
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = max(1, math.hypot(dx, dy))
    px, py = -dy / length, dx / length
    for i in range(1, segments):
        t = i / segments
        mx = p1[0] + dx * t + px * random.uniform(-jitter, jitter)
        my = p1[1] + dy * t + py * random.uniform(-jitter, jitter)
        pts.append((mx, my))
    pts.append(p2)
    return pts
