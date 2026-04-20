import pygame, sys, math
import constants as C
import display

# ---- Level maps ----
OLD_LEVEL = [
"........................^...............................................................",
".......................XXX............................................................",
".....................XXX.X..............^...............................S...BBBBBBBBBB",
"......................^X.X...^.........XXXX................^...XXXXXXXXXXXXXXXXXXXXXX..",
".............^.......XXX.XXXXXX.............X.............XXX....X....................",
".............X....X..XXX.....^.^X...........X.......^.....X.X....X....................",
".............X...XX....B.....XXXXX.....XXX...X.....XXXX....X.X....XXXX................",
".............XXXXX...............X....X..X...X.....X..X....X.XX^.....X................",
"..........XXX....XXXX...........XX....X..X...X.....X...XXXX.XXXXXX..X................",
".....XXXXX......................X.....X..X...X.....X...............X.X................",
"..XXXX..........^...............X..P..X..X...X.....X..B......X.XXXXX.X................",
"XX............XXXXXXX...........X.....XXXX...X..^..X.........XBBBBXX.X................",
"X.............X.....X...........X..............XXXX...^......XXXXXX.X................",
"X.............X.....XXXXX.......X.....................XXXXX...X......X................",
"X.............X.........X.......X....................XX...X...X..G...X................",
"XXXX.......XXXX.........XXX.....X..........B.........X....X...X...^..X................",
"....XXXXXXX.............X.......X.....^.....XX.......X....XXXXXX..XXXX................",
".....................B..X.......X.....X..............X.^^^..........X.................",
"........................^X...XXXX.....XX.............XXXXXX.........X.................",
"........................XXXX......................................XXX.................",
"...........^.....B.......B............^............^.................X.................",
"....................................................................XXXXXXX...........",
]

NEW_LEVEL = [
"........................................................................................",
".........................XXXXXXX........................................................",
".......................XX.......XX......................................................",
"......................X..^.B.^.B..X.....................................................",
".....................X...XXXXXXX..XX..................XXXX.............................",
"....................X..XX.......XX..X................XX....XX...........................",
"..............XXXXXXX.....XX.XX..X..X...............XXX.......X..........................",
"............XX.....X...X..X...X..X..X.............XX.........XX.........................",
"...........X..P....X...X..X...X..X..XXXX.......XXXX...........X.........................",
"..........X........X...X..X.B.X..X......X.....X...............X.........................",
"..........X..XXXX..XX..X..XXXXX.........X.....X....XXXXXX.....X.........................",
"..........X..X..X......X.......XXXXX....X.....X....X..BBX.....X.........................",
"..........X..X..B...X..X......XXXXXX.B^.XXXXX.X....X..BBX.....XXXX......................",
"..........X.....X...X..X.....X.....XXXX.....X.X....X..XX........X......................",
"..........X..X..XXXX...X....X...^..^XX.....X.X....X...........X.........................",
"..........X..X.........X...X....XXXXX......X.XXXXXXXX.........X.........................",
"..........X..XXXX......X..X...........^....X.X.............G..X.........................",
"..........X.......XX...X..X..^.......XXXX..X.X...........XXXXX..........................",
"..........XXXXXX..X....X..XXXXXXXXXXXXXXx..X............X...............................",
"..................X....XXXX...XXXXXXXX.....X..XXXX......X...............................",
"..................X..B...^...^XXXXXXXX.^....^.^.XXXX...X...............................",
".................XXXXXXXXXBXXXXXXXXXXXX...XXXXXX....XXXXXX.............................",
"..........................XXX..........XXXXX............................................",
"........................................................................................"
]

# ---- Helpers ----
def rect_for_tile(r, c):
    return pygame.Rect(c * C.TILE, r * C.TILE, C.TILE, C.TILE)

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

def seg_intersects_rect(p1, p2, rect):
    if rect.collidepoint(p1) or rect.collidepoint(p2):
        return True
    x1, y1 = rect.topleft;  x2, y2 = rect.topright
    x3, y3 = rect.bottomright; x4, y4 = rect.bottomleft
    return (seg_intersect(p1, p2, (x1, y1), (x2, y2)) or
            seg_intersect(p1, p2, (x2, y2), (x3, y3)) or
            seg_intersect(p1, p2, (x3, y3), (x4, y4)) or
            seg_intersect(p1, p2, (x4, y4), (x1, y1)))

# ---- Force powers ----
def _within_force_line(px, py, x, y):
    return abs(y - py) <= C.TILE and abs(x - px) <= C.FORCE_RADIUS_PX

def _slide_turret_horiz(t, step_c, steps, ROWS, COLS, get_tile, set_tile):
    if step_c == 0 or t.falling:
        return
    for _ in range(steps):
        nr, nc = t.r, t.c + step_c
        if not (0 <= nr < ROWS and 0 <= nc < COLS):
            t.start_fall(ROWS, COLS, get_tile, set_tile); break
        ch = get_tile(nr, nc)
        if ch in C.FORCE_BLOCKED_TILES or ch == '^': break
        set_tile(t.r, t.c, '.'); set_tile(nr, nc, '^')
        t.r, t.c = nr, nc
        t.rect.topleft = (t.c * C.TILE + 8, t.r * C.TILE + 8)
        below = t.r + 1
        if below >= ROWS or get_tile(below, t.c) == '.':
            t.start_fall(ROWS, COLS, get_tile, set_tile); break

def force_push(player, bolts, turrets, ROWS, COLS, get_tile, set_tile):
    px, py = player.rect.centerx, player.rect.centery
    for b in bolts:
        if b.alive and _within_force_line(px, py, b.x, b.y):
            d = 1 if b.x > px else -1
            b.vx = d * max(abs(b.vx), C.FORCE_BOLT_IMPULSE); b.friendly = True
    for t in turrets:
        cx, cy = t.center()
        if _within_force_line(px, py, cx, cy):
            _slide_turret_horiz(t, 1 if cx > px else -1,
                                C.FORCE_TURRET_STEPS, ROWS, COLS, get_tile, set_tile)

def force_pull(player, bolts, turrets, ROWS, COLS, get_tile, set_tile):
    px, py = player.rect.centerx, player.rect.centery
    for b in bolts:
        if b.alive and _within_force_line(px, py, b.x, b.y):
            d = -1 if b.x > px else 1
            b.vx = d * max(abs(b.vx), C.FORCE_BOLT_IMPULSE); b.friendly = True
    for t in turrets:
        cx, cy = t.center()
        if _within_force_line(px, py, cx, cy):
            _slide_turret_horiz(t, -1 if cx > px else 1,
                                C.FORCE_TURRET_STEPS, ROWS, COLS, get_tile, set_tile)

# ---- Entities ----
class SithLord:
    def __init__(self, x, y):
        self.w, self.h = 26, 34
        self.rect      = pygame.Rect(x + 7, y + 6, self.w, self.h)

    def update(self, player):
        px, py = player.rect.center
        sx, sy = self.rect.center
        dx, dy = px - sx, py - sy
        d      = max(1, math.hypot(dx, dy))
        self.ux, self.uy = dx / d, dy / d
        t      = pygame.time.get_ticks() * 0.01
        angle  = math.atan2(self.uy, self.ux) + math.sin(t) * 0.3
        self.wx, self.wy = math.cos(angle), math.sin(angle)
        self.p1 = (sx, sy)
        self.p2 = (sx + self.wx * C.SABER_LEN, sy + self.wy * C.SABER_LEN)

    def check_hit(self, player):
        if self.rect.colliderect(player.rect):
            return True
        px, py = player.rect.center
        return point_seg_dist_sq(px, py, *self.p1, *self.p2) < (C.SABER_THICKNESS + 4) ** 2

    def draw(self, screen, camx, camy):
        x, y = self.rect.x - camx, self.rect.y - camy
        pygame.draw.rect(screen, C.RED, (x, y, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (255, 150, 150), (x + 6, y + 4, self.w - 12, 8), border_radius=3)
        pygame.draw.line(screen, C.RED,
                         (int(self.p1[0] - camx), int(self.p1[1] - camy)),
                         (int(self.p2[0] - camx), int(self.p2[1] - camy)),
                         C.SABER_THICKNESS)


class Player:
    def __init__(self, x, y):
        self.w, self.h = 26, 34
        self.rect      = pygame.Rect(x + 7, y + 6, self.w, self.h)
        self.vx = self.vy = 0.0
        self.on_ground  = False; self.jumps_left = 2
        self.face_dir   = 1;     self.deaths = 0; self.time_ms = 0

    def update(self, keys, dt, ROWS, COLS, get_tile):
        ts = display.TIME_SCALE
        ax = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  ax -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: ax += 1
        self.vx += ax * 0.8 * ts
        self.vx *= C.FRICTION ** ts
        self.vx  = max(-C.MAX_XSPEED, min(C.MAX_XSPEED, self.vx))
        if ax != 0: self.face_dir = 1 if ax > 0 else -1
        self.vy  = min(self.vy + C.GRAVITY * ts, 16)
        self.rect.x += int(round(self.vx * ts))
        for (r, c, ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch == 'X':
                t = rect_for_tile(r, c)
                if self.rect.colliderect(t):
                    if self.vx > 0: self.rect.right = t.left;  self.vx = 0
                    elif self.vx < 0: self.rect.left = t.right; self.vx = 0
        self.rect.y += int(round(self.vy * ts)); self.on_ground = False
        for (r, c, ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch == 'X':
                t = rect_for_tile(r, c)
                if self.rect.colliderect(t):
                    if self.vy > 0:
                        self.rect.bottom = t.top; self.vy = 0
                        self.on_ground = True; self.jumps_left = 2
                    elif self.vy < 0:
                        self.rect.top = t.bottom; self.vy = 0
        for (_, _, ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch == '^': _request_restart_flag[0] = True; _death_pending_flag[0] = True
        self.time_ms += dt * ts

    def jump(self):
        if self.jumps_left > 0:
            self.vy = -C.JUMP_SPEED; self.jumps_left -= 1


class Turret:
    def __init__(self, r, c):
        self.r, self.c  = r, c
        self.rect       = pygame.Rect(c * C.TILE + 8, r * C.TILE + 8, 24, 24)
        self.last_shot  = -9999; self.cooldown = C.BASE_TURRET_COOLDOWN_MS
        self.falling    = False; self.vy = 0.0; self.fall_start_y = self.rect.y

    def center(self):
        return (self.rect.centerx, self.rect.centery)

    def player_within_radius(self, player, tiles=C.FIRE_RADIUS_TILES):
        tcx, tcy = self.center()
        dx = player.rect.centerx - tcx; dy = player.rect.centery - tcy
        return (dx * dx + dy * dy) <= (tiles * C.TILE) ** 2

    def start_fall(self, ROWS, COLS, get_tile, set_tile):
        if not self.falling:
            if 0 <= self.r < ROWS and 0 <= self.c < COLS and get_tile(self.r, self.c) == '^':
                set_tile(self.r, self.c, '.')
            self.falling = True; self.vy = 0.0; self.fall_start_y = self.rect.y
            self.r = self.c = -1

    def check_support_and_maybe_fall(self, ROWS, COLS, get_tile):
        if self.falling: return
        below = self.rect.bottom // C.TILE
        col   = self.rect.centerx // C.TILE
        if below >= ROWS or get_tile(below, col) == '.':
            self.start_fall(ROWS, COLS, get_tile, lambda r, c, v=None: None)

    def update_fall(self, ROWS, COLS, get_tile, set_tile):
        if not self.falling: return False
        ts = display.TIME_SCALE
        self.vy = min(self.vy + C.GRAVITY * ts, 16)
        self.rect.y += int(round(self.vy * ts))
        if (self.rect.y - self.fall_start_y) >= C.TURRET_FALL_KILL_TILES * C.TILE:
            return True
        for (r, c, ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch == 'X':
                t = rect_for_tile(r, c)
                if self.rect.colliderect(t):
                    self.rect.bottom = t.top; self.vy = 0.0; self.falling = False
                    self.r = max(0, min(ROWS - 1, (self.rect.y - 8) // C.TILE))
                    self.c = max(0, min(COLS - 1, (self.rect.x - 8) // C.TILE))
                    if get_tile(self.r, self.c) == '.': set_tile(self.r, self.c, '^')
                    return False
        return self.rect.top > ROWS * C.TILE

    def update_and_maybe_shoot(self, player, bolts, ROWS, COLS, get_tile):
        now = pygame.time.get_ticks()
        eff = int(self.cooldown / max(display.TIME_SCALE, 1e-3))
        if self.player_within_radius(player) and now - self.last_shot >= eff:
            self.last_shot = now
            cx, cy = self.center()
            tx, ty = player.rect.centerx, player.rect.centery
            dx, dy = tx - cx, ty - cy
            d      = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / d, dy / d
            spawn_x = cx + ux * (self.rect.w / 2 + 4)
            spawn_y = cy + uy * (self.rect.h / 2 + 4)
            bolts.append(Bolt(spawn_x, spawn_y, ux * C.BOLT_SPEED, uy * C.BOLT_SPEED))


class Bolt:
    def __init__(self, x, y, vx, vy):
        self.x  = float(x); self.y  = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.r  = 4; self.alive = True; self.friendly = False

    def rect(self):
        return pygame.Rect(int(self.x) - self.r, int(self.y) - self.r, self.r * 2, self.r * 2)

    def update(self, ROWS, COLS, get_tile):
        if not self.alive: return
        ts = display.TIME_SCALE
        self.x += self.vx * ts; self.y += self.vy * ts
        if (self.x < -10 or self.x > COLS * C.TILE + 10 or
                self.y < -10 or self.y > ROWS * C.TILE + 10):
            self.alive = False; return
        r, c = int(self.y) // C.TILE, int(self.x) // C.TILE
        if 0 <= r < ROWS and 0 <= c < COLS and get_tile(r, c) in ('X', 'B'):
            self.alive = False


# ---- Draw helpers ----
def draw_level(level_grid, ROWS, COLS, camx, camy):
    c0 = max(0,    int(camx // C.TILE) - 2);   c1 = min(COLS, int((camx + C.WIDTH)  // C.TILE) + 3)
    r0 = max(0,    int(camy // C.TILE) - 2);   r1 = min(ROWS, int((camy + C.HEIGHT) // C.TILE) + 3)
    for r in range(r0, r1):
        for c in range(c0, c1):
            ch = level_grid[r][c]; x, y = c * C.TILE - camx, r * C.TILE - camy
            if ch == 'X':
                pygame.draw.rect(display.screen, C.GREY, (x, y, C.TILE, C.TILE))
                pygame.draw.rect(display.screen, (40, 43, 47), (x, y, C.TILE, C.TILE), 2)
            elif ch == '^':
                pts = [(x, y + C.TILE - 2), (x + C.TILE // 2, y + 4), (x + C.TILE - 1, y + C.TILE - 2)]
                pygame.draw.polygon(display.screen, C.RED, pts)
                pygame.draw.polygon(display.screen, C.BLACK, pts, 2)
            elif ch == 'B':
                pygame.draw.rect(display.screen, (170, 30, 30),   (x + 6,  y + 6,  C.TILE - 12, C.TILE - 12), border_radius=8)
                pygame.draw.rect(display.screen, (255, 120, 120), (x + 10, y + 10, C.TILE - 20, C.TILE - 20), 2, border_radius=6)
            elif ch == 'G':
                pygame.draw.rect(display.screen, (20,  120, 70),  (x, y, C.TILE, C.TILE))
                pygame.draw.rect(display.screen, (40,  180, 110), (x + 6, y + 6, C.TILE - 12, C.TILE - 12), 2, border_radius=8)

def draw_falling_turrets(turrets, camx, camy):
    for t in turrets:
        if not t.falling: continue
        cx, cy = t.rect.centerx - camx, t.rect.centery - camy
        half   = C.TILE // 2 - 2
        pts    = [(cx - half, cy + half), (cx, cy - half), (cx + half, cy + half)]
        pygame.draw.polygon(display.screen, C.RED,   pts)
        pygame.draw.polygon(display.screen, C.BLACK, pts, 2)

def draw_bolts(bolts, camx, camy):
    for b in bolts:
        if not b.alive: continue
        color = C.YELLOW if b.friendly else C.RED
        pygame.draw.circle(display.screen, color, (int(b.x - camx), int(b.y - camy)), b.r)

def draw_player(p, camx, camy, p1, p2):
    x, y = p.rect.x - camx, p.rect.y - camy
    pygame.draw.rect(display.screen,  C.BLUE,         (x, y, p.w, p.h), border_radius=5)
    pygame.draw.rect(display.screen,  (230, 230, 255), (x + 6, y + 4, p.w - 12, 8), border_radius=3)
    pygame.draw.line(display.screen,  C.CYAN,
                     (int(p1[0] - camx), int(p1[1] - camy)),
                     (int(p2[0] - camx), int(p2[1] - camy)), C.SABER_THICKNESS)
    pygame.draw.circle(display.screen, C.CYAN,
                       (int(p.rect.centerx - camx), int(p.rect.centery - camy)), 3)

def center_camera_on_player(camx, camy, p, ROWS, COLS):
    tx = p.rect.centerx - C.WIDTH  / 2
    ty = p.rect.centery - C.HEIGHT / 2
    camx += (tx - camx) * 0.08; camy += (ty - camy) * 0.08
    camx = max(0, min(COLS * C.TILE - C.WIDTH,  camx))
    camy = max(0, min(ROWS * C.TILE - C.HEIGHT, camy))
    return camx, camy


# ---- Restart flags (shared between Player.update and parkour_stage) ----
_request_restart_flag = [False]
_death_pending_flag   = [False]


# ---- Stage ----
def parkour_stage(which_map="old"):
    base             = OLD_LEVEL if which_map == "old" else NEW_LEVEL
    LEVEL, ROWS, COLS = normalize_and_floor(base)
    level_grid       = [list(row) for row in LEVEL]

    def get_tile(r, c):
        return level_grid[r][c] if 0 <= r < ROWS and 0 <= c < COLS else '.'
    def set_tile(r, c, val):
        if 0 <= r < ROWS and 0 <= c < COLS: level_grid[r][c] = val

    START_POS, GOAL_POS, spawns, sith_spawns = scan_entities(level_grid, ROWS, COLS)
    sr, sc = START_POS[1] // C.TILE, START_POS[0] // C.TILE
    if get_tile(sr, sc) == 'P': set_tile(sr, sc, '.')

    turrets = [Turret(r, c) for (r, c) in spawns]
    siths   = [SithLord(c * C.TILE, r * C.TILE) for (r, c) in sith_spawns]
    bolts   = []
    player  = Player(*START_POS)
    camx = camy = 0.0
    win  = False
    _request_restart_flag[0] = False
    _death_pending_flag[0]   = False

    def restart_run():
        nonlocal level_grid, turrets, bolts, player, camx, camy, win, siths
        level_grid = [list(row) for row in LEVEL]
        START, GOAL, sp, sps = scan_entities(level_grid, ROWS, COLS)
        siths = [SithLord(c * C.TILE, r * C.TILE) for (r, c) in sps]
        sr2, sc2 = START[1] // C.TILE, START[0] // C.TILE
        if get_tile(sr2, sc2) == 'P': set_tile(sr2, sc2, '.')
        deaths = player.deaths + (1 if _death_pending_flag[0] else 0)
        player = Player(*START); player.deaths = deaths
        turrets = [Turret(r, c) for (r, c) in sp]; bolts = []
        camx = camy = 0.0; win = False
        _request_restart_flag[0] = False; _death_pending_flag[0] = False
        return START, GOAL

    while True:
        dt = display.clock.tick(60)

        if _request_restart_flag[0]:
            START_POS, GOAL_POS = restart_run()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_c:   display.toggle_slow()
                if e.key in (pygame.K_w, pygame.K_UP): player.jump()
                if e.key == pygame.K_x:   force_push(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                if e.key == pygame.K_v:   force_pull(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                if e.key == pygame.K_r:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = False
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

        keys = pygame.key.get_pressed()
        player.update(keys, dt, ROWS, COLS, get_tile)

        mx, my   = pygame.mouse.get_pos()
        mxw, myw = mx + camx, my + camy
        pcx, pcy = player.rect.centerx, player.rect.centery
        dx, dy   = mxw - pcx, myw - pcy
        d        = max(1.0, math.hypot(dx, dy))
        ux, uy   = dx / d, dy / d
        saber_p1 = (pcx, pcy)
        saber_p2 = (pcx + ux * C.SABER_LEN, pcy + uy * C.SABER_LEN)

        for s in siths[:]:
            s.update(player)
            if seg_intersects_rect(saber_p1, saber_p2, s.rect):
                siths.remove(s); continue
            if seg_intersect(saber_p1, saber_p2, s.p1, s.p2):
                continue
            if s.check_hit(player):
                _request_restart_flag[0] = True; _death_pending_flag[0] = True; break

        for t in turrets[:]: t.check_support_and_maybe_fall(ROWS, COLS, get_tile)
        for t in turrets[:]:
            if t.update_fall(ROWS, COLS, get_tile, set_tile): turrets.remove(t)
        for t in turrets[:]: t.update_and_maybe_shoot(player, bolts, ROWS, COLS, get_tile)
        for b in bolts:
            if b.alive: b.update(ROWS, COLS, get_tile)

        camx, camy = center_camera_on_player(camx, camy, player, ROWS, COLS)

        lmb, _, rmb = pygame.mouse.get_pressed(3)
        thresh_sq   = (C.SABER_THICKNESS / 2 + 4) ** 2
        for b in bolts:
            if not b.alive: continue
            if point_seg_dist_sq(b.x, b.y, *saber_p1, *saber_p2) <= thresh_sq:
                if rmb: b.alive = False
                else:   b.vx *= -1; b.vy *= -1; b.friendly = True
                continue
            if not b.friendly and b.rect().colliderect(player.rect):
                b.alive = False; _request_restart_flag[0] = True; _death_pending_flag[0] = True

        for b in bolts:
            if not b.alive or not b.friendly: continue
            for t in turrets[:]:
                if t.rect.colliderect(b.rect()):
                    if (not t.falling) and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                        set_tile(t.r, t.c, '.')
                    turrets.remove(t); b.alive = False; break

        minx = int(max(0,      (min(saber_p1[0], saber_p2[0]) - C.SABER_THICKNESS) // C.TILE))
        maxx = int(min(COLS-1, (max(saber_p1[0], saber_p2[0]) + C.SABER_THICKNESS) // C.TILE))
        miny = int(max(0,      (min(saber_p1[1], saber_p2[1]) - C.SABER_THICKNESS) // C.TILE))
        maxy = int(min(ROWS-1, (max(saber_p1[1], saber_p2[1]) + C.SABER_THICKNESS) // C.TILE))
        for r in range(miny, maxy + 1):
            for c in range(minx, maxx + 1):
                if get_tile(r, c) == 'B' and seg_intersects_rect(saber_p1, saber_p2, rect_for_tile(r, c)):
                    set_tile(r, c, '.')

        bolts = [b for b in bolts if b.alive]

        for (_, _, ch) in tiles_at(player.rect, ROWS, COLS, get_tile):
            if ch == 'G': win = True; break

        display.screen.fill(C.BLACK)
        draw_level(level_grid, ROWS, COLS, camx, camy)
        draw_falling_turrets(turrets, camx, camy)
        draw_bolts(bolts, camx, camy)
        draw_player(player, camx, camy, saber_p1, saber_p2)
        for s in siths: s.draw(display.screen, camx, camy)

        t = player.time_ms / 1000.0
        display.screen.blit(display.FONT.render(f"Deaths: {player.deaths}", True, C.WHITE), (10, 10))
        display.screen.blit(display.FONT.render(
            f"Time: {t:05.2f}s   Speed x{display.TIME_SCALE:.2f} (C toggles)", True, C.WHITE), (10, 30))
        display.screen.blit(display.FONT.render(
            "Move A/D or L/R  Jump W/Up  Saber:mouse LMB reflect/RMB destroy  Push X  Pull V  R restart",
            True, C.YELLOW), (10, C.HEIGHT - 28))
        if win:
            msg = display.BIG.render("You cleared the stronghold!", True, C.WHITE)
            sub = display.FONT.render("Press R to try again.", True, C.WHITE)
            display.screen.blit(msg, (C.WIDTH // 2 - msg.get_width() // 2, 70))
            display.screen.blit(sub, (C.WIDTH // 2 - sub.get_width() // 2, 110))
        pygame.display.flip()
