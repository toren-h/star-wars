import pygame, sys, math, random
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
    MAX_HP          = 3
    APPROACH_SPEED  = 1.8
    STRIKE_RANGE_PX = 90
    WINDUP_MS       = 600
    STRIKE_MS       = 300
    RECOVER_MS      = 700
    STAGGER_MS      = 500
    HIT_IFRAMES_MS  = 400

    def __init__(self, x, y):
        self.w, self.h = 26, 34
        self.rect = pygame.Rect(x + 7, y + 6, self.w, self.h)
        self.hp = self.MAX_HP
        self.state = 'approach'
        self.state_start = pygame.time.get_ticks()
        self.face_dir = 1
        self.flash_until = 0
        self.invincible_until = 0
        self.p1 = (float(self.rect.centerx), float(self.rect.centery))
        self.p2 = self.p1

    def take_hit(self):
        now = pygame.time.get_ticks()
        if now < self.invincible_until:
            return False
        self.hp -= 1
        self.flash_until = now + 200
        self.invincible_until = now + self.HIT_IFRAMES_MS
        self.state = 'stagger'
        self.state_start = now
        return self.hp <= 0

    def stagger(self):
        now = pygame.time.get_ticks()
        self.state = 'stagger'
        self.state_start = now
        self.flash_until = now + 150

    def update(self, player):
        now = pygame.time.get_ticks()
        ts  = display.TIME_SCALE
        sx, sy = float(self.rect.centerx), float(self.rect.centery)
        px     = float(player.rect.centerx)
        dx     = px - sx
        dist   = abs(dx)
        self.face_dir = 1 if dx >= 0 else -1
        elapsed = now - self.state_start

        if self.state == 'approach':
            if dist > self.STRIKE_RANGE_PX:
                move = min(self.APPROACH_SPEED * ts, dist - self.STRIKE_RANGE_PX)
                self.rect.x += int(self.face_dir * max(1, move))
            else:
                self.state = 'windup'; self.state_start = now
        elif self.state == 'windup':
            if elapsed >= int(self.WINDUP_MS / max(ts, 0.1)):
                self.state = 'strike'; self.state_start = now
        elif self.state == 'strike':
            if elapsed >= int(self.STRIKE_MS / max(ts, 0.1)):
                self.state = 'recover'; self.state_start = now
        elif self.state == 'recover':
            if elapsed >= int(self.RECOVER_MS / max(ts, 0.1)):
                self.state = 'approach'; self.state_start = now
        elif self.state == 'stagger':
            if elapsed >= int(self.STAGGER_MS / max(ts, 0.1)):
                self.state = 'approach'; self.state_start = now

        sx, sy = float(self.rect.centerx), float(self.rect.centery)
        t = now * 0.001
        if self.state == 'windup':
            angle = math.atan2(-0.8, -self.face_dir)
        elif self.state == 'strike':
            progress  = min((now - self.state_start) / max(self.STRIKE_MS, 1), 1.0)
            start_a   = math.atan2(-0.8, -self.face_dir)
            end_a     = math.atan2(0.3,   self.face_dir)
            angle     = start_a + (end_a - start_a) * progress
        elif self.state == 'stagger':
            angle = math.atan2(1.0, -self.face_dir)
        else:
            angle = math.atan2(-0.2, self.face_dir) + math.sin(t * 2) * 0.25
        self.p1 = (sx, sy)
        self.p2 = (sx + math.cos(angle) * C.SABER_LEN, sy + math.sin(angle) * C.SABER_LEN)

    def check_hit_on_player(self, player):
        if self.state != 'strike':
            return False
        if self.rect.colliderect(player.rect):
            return True
        px, py = player.rect.center
        return point_seg_dist_sq(px, py, *self.p1, *self.p2) < (C.SABER_THICKNESS + 4) ** 2

    def draw(self, screen, camx, camy):
        now  = pygame.time.get_ticks()
        x, y = self.rect.x - camx, self.rect.y - camy
        body_col  = (255, 255, 255) if now < self.flash_until else C.RED
        pygame.draw.rect(screen, body_col, (x, y, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (255, 150, 150), (x + 6, y + 4, self.w - 12, 8), border_radius=3)
        saber_col = (255, 100, 100) if self.state == 'windup' else C.RED
        pygame.draw.line(screen, saber_col,
                         (int(self.p1[0] - camx), int(self.p1[1] - camy)),
                         (int(self.p2[0] - camx), int(self.p2[1] - camy)),
                         C.SABER_THICKNESS)
        bar_w = max(0, int(self.w * self.hp / self.MAX_HP))
        bar_x, bar_y = int(x), int(y) - 8
        pygame.draw.rect(screen, (80, 0, 0),    (bar_x, bar_y, self.w, 5))
        pygame.draw.rect(screen, (220, 50, 50), (bar_x, bar_y, bar_w, 5))


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


class Grenade:
    SPEED      = 10.0
    FUSE_MS    = 2500
    EXP_RADIUS = 100  # 2.5 tiles

    def __init__(self, x, y, vx, vy):
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.alive = True
        self.born  = pygame.time.get_ticks()

    def rect(self):
        return pygame.Rect(int(self.x) - 4, int(self.y) - 4, 8, 8)

    BOUNCE_DAMP  = 0.65   # fraction of speed kept after each bounce
    ROLL_FRICTION = 0.015  # vx lost per frame while rolling on ground
    ROLL_STOP    = 0.3    # vx below this snaps to zero

    def _solid(self, x, y, ROWS, COLS, get_tile):
        r = pygame.Rect(int(x) - 4, int(y) - 4, 8, 8)
        return any(ch == 'X' for (_, _, ch) in tiles_at(r, ROWS, COLS, get_tile))

    def update(self, ROWS, COLS, get_tile):
        if not self.alive: return False
        ts = display.TIME_SCALE
        self.vy = min(self.vy + C.GRAVITY * ts, 16)

        nx = self.x + self.vx * ts
        ny = self.y + self.vy * ts

        hit_x = self._solid(nx, self.y, ROWS, COLS, get_tile)
        hit_y = self._solid(self.x, ny, ROWS, COLS, get_tile)

        if hit_x:
            self.vx = -self.vx * self.BOUNCE_DAMP
            self.vy *= self.BOUNCE_DAMP
            nx = self.x
        if hit_y:
            self.vy = -self.vy * self.BOUNCE_DAMP
            self.vx *= self.BOUNCE_DAMP
            ny = self.y

        # rolling: if resting on ground, bleed off horizontal speed with friction
        on_ground = self._solid(self.x, ny + 1, ROWS, COLS, get_tile)
        if on_ground and abs(self.vy) < 1.5:
            self.vy = 0
            friction = self.ROLL_FRICTION * ts
            if abs(self.vx) <= self.ROLL_STOP:
                self.vx = 0
            elif self.vx > 0:
                self.vx = max(0.0, self.vx - friction)
            else:
                self.vx = min(0.0, self.vx + friction)

        self.x, self.y = nx, ny

        if pygame.time.get_ticks() - self.born >= self.FUSE_MS:
            self.alive = False; return True
        return False

    def draw(self, camx, camy):
        t = (pygame.time.get_ticks() - self.born) / self.FUSE_MS
        color = (255, int(200 - 150 * t), 50) if t < 0.7 else (255, 50, 50)
        pygame.draw.circle(display.screen, color,
                           (int(self.x - camx), int(self.y - camy)), 5)


class LavaFlow:
    TICK_MS = 1000  # ms between each drop+expand cycle
    EXPAND  = 1     # new columns added each side per tick

    def __init__(self, r, c):
        self.source_r     = r
        self.source_c     = c
        self.tiles        = {(r, c)}   # source tile visible immediately
        self.alive        = True
        self.col_frontier = {c: r}     # col -> current frontier row
        self.last_tick    = pygame.time.get_ticks()  # first tick after TICK_MS

    def update(self, ROWS, COLS, get_tile, set_tile, turrets, siths, grenades, bolts):
        if not self.alive: return

        if get_tile(self.source_r, self.source_c) in ('X', 'B'):
            self.tiles.clear()
            self.alive = False
            return

        now = pygame.time.get_ticks()
        if now - self.last_tick >= self.TICK_MS:
            self.last_tick = now

            # drop every active column by 1 independently
            dropped = set()
            new_frontier = {}
            for col, fr in self.col_frontier.items():
                next_fr = fr + 1
                if next_fr < ROWS and get_tile(next_fr, col) != 'X':
                    new_frontier[col] = next_fr
                    self.tiles.add((next_fr, col))
                    dropped.add(col)
                else:
                    new_frontier[col] = fr  # blocked — stays in place
            self.col_frontier = new_frontier

            # only expand from an outer edge if that edge column actually dropped
            if self.col_frontier:
                left_col  = min(self.col_frontier)
                right_col = max(self.col_frontier)
                for edge_col, step in ((left_col, -1), (right_col, 1)):
                    if edge_col not in dropped:
                        continue  # this edge hit the floor/block — no expansion
                    fr = self.col_frontier[edge_col]
                    for i in range(1, self.EXPAND + 1):
                        nc = edge_col + step * i
                        if not (0 <= nc < COLS) or get_tile(fr, nc) == 'X':
                            break  # wall or map edge — stop expanding this direction
                        if nc not in self.col_frontier:
                            self.col_frontier[nc] = fr
                            self.tiles.add((fr, nc))

        # destroy everything except blocks under lava tiles
        for (r, c) in list(self.tiles):
            ch = get_tile(r, c)
            if ch in ('X', '.'):
                continue
            if ch == '^':
                for t in turrets[:]:
                    if t.r == r and t.c == c:
                        turrets.remove(t)
            set_tile(r, c, '.')

        # destroy sith lords standing in lava
        for s in siths[:]:
            sr = s.rect.centery // C.TILE
            sc = s.rect.centerx // C.TILE
            if (sr, sc) in self.tiles:
                siths.remove(s)

        # destroy grenades (circles) and bolts (circles) caught in lava
        for g in grenades[:]:
            if (int(g.y) // C.TILE, int(g.x) // C.TILE) in self.tiles:
                grenades.remove(g)
        for b in bolts[:]:
            if (int(b.y) // C.TILE, int(b.x) // C.TILE) in self.tiles:
                b.alive = False

    def player_touching(self, player):
        pr0 = player.rect.top    // C.TILE
        pr1 = player.rect.bottom // C.TILE
        pc0 = player.rect.left   // C.TILE
        pc1 = player.rect.right  // C.TILE
        return any(pr0 <= r <= pr1 and pc0 <= c <= pc1 for (r, c) in self.tiles)

    def draw(self, camx, camy):
        ts = C.TILE
        for (r, c) in self.tiles:
            x = c * ts - int(camx)
            y = r * ts - int(camy)
            pygame.draw.rect(display.screen, (220, 55, 0),   (x, y, ts, ts))
            pygame.draw.rect(display.screen, (255, 180, 20), (x + 3, y + 3, ts - 6, 8), border_radius=3)


class Bolt:
    def __init__(self, x, y, vx, vy):
        self.x  = float(x); self.y  = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.r  = 4; self.alive = True; self.friendly = False
        self.prev_x = self.x; self.prev_y = self.y

    def rect(self):
        return pygame.Rect(int(self.x) - self.r, int(self.y) - self.r, self.r * 2, self.r * 2)

    def update(self, ROWS, COLS, get_tile):
        if not self.alive: return
        ts = display.TIME_SCALE
        self.prev_x = self.x; self.prev_y = self.y
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

def draw_player(p, camx, camy, p1, p2, saber_color=C.CYAN, flash=False):
    x, y = p.rect.x - camx, p.rect.y - camy
    body_col = (255, 255, 255) if flash else C.BLUE
    pygame.draw.rect(display.screen,  body_col,       (x, y, p.w, p.h), border_radius=5)
    pygame.draw.rect(display.screen,  (230, 230, 255), (x + 6, y + 4, p.w - 12, 8), border_radius=3)
    pygame.draw.line(display.screen,  saber_color,
                     (int(p1[0] - camx), int(p1[1] - camy)),
                     (int(p2[0] - camx), int(p2[1] - camy)), C.SABER_THICKNESS)
    pygame.draw.circle(display.screen, saber_color,
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
    saber_len       = float(C.SABER_LEN)
    saber_target    = float(C.SABER_LEN)
    saber_color     = C.CYAN
    saber_switching = False
    lightnings      = []  # list of (world_points, expire_ms)
    grenades             = []
    lava_flows           = []
    explosions           = []  # list of (wx, wy, start_ms, sparks)
    crumbling_effects    = []  # list of (wx, wy, start_ms, pieces)
    grenade_charge_start = None
    last_lightning_t     = 0
    float_accum          = 0.0
    nuke_state           = None  # None | ('fuse', start_ms, x, y) | ('blast', start_ms, sparks)
    player_hp            = 3
    player_flash_until   = 0
    red_seq              = []   # tracks progress through R-E-D combo
    _request_restart_flag[0] = False
    _death_pending_flag[0]   = False

    def restart_run():
        nonlocal level_grid, turrets, bolts, player, camx, camy, win, siths, saber_len, saber_target, saber_color, saber_switching, lightnings, grenades, lava_flows, explosions, crumbling_effects, grenade_charge_start, last_lightning_t, float_accum, nuke_state, player_hp, player_flash_until
        level_grid = [list(row) for row in LEVEL]
        START, GOAL, sp, sps = scan_entities(level_grid, ROWS, COLS)
        siths = [SithLord(c * C.TILE, r * C.TILE) for (r, c) in sps]
        sr2, sc2 = START[1] // C.TILE, START[0] // C.TILE
        if get_tile(sr2, sc2) == 'P': set_tile(sr2, sc2, '.')
        deaths = player.deaths + (1 if _death_pending_flag[0] else 0)
        player = Player(*START); player.deaths = deaths
        turrets = [Turret(r, c) for (r, c) in sp]; bolts = []
        camx = camy = 0.0; win = False
        saber_len = saber_target = float(C.SABER_LEN); saber_color = C.CYAN; saber_switching = False
        lightnings = []; grenades = []; lava_flows = []; explosions = []; crumbling_effects = []; grenade_charge_start = None; last_lightning_t = 0; float_accum = 0.0; nuke_state = None
        player_hp = 3; player_flash_until = 0; red_seq.clear()
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
                if e.key == pygame.K_e:
                    saber_target = 0.0 if saber_target > 0 else float(C.SABER_LEN)
                if e.key == pygame.K_x:   force_push(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                if e.key == pygame.K_v:   force_pull(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                # R-E-D sequence activates color switch
                _RED_KEYS = [pygame.K_r, pygame.K_e, pygame.K_d]
                _RED_TIMEOUT = 10000
                if e.key == pygame.K_r:
                    red_seq.clear()
                    red_seq.append((pygame.K_r, pygame.time.get_ticks()))
                elif e.key == pygame.K_e and red_seq and red_seq[-1][0] == pygame.K_r:
                    if pygame.time.get_ticks() - red_seq[0][1] <= _RED_TIMEOUT:
                        red_seq.append((pygame.K_e, pygame.time.get_ticks()))
                elif e.key == pygame.K_d and len(red_seq) == 2 and red_seq[-1][0] == pygame.K_e:
                    if pygame.time.get_ticks() - red_seq[0][1] <= _RED_TIMEOUT:
                        saber_switching = True
                        saber_target = 0.0
                    red_seq.clear()
                if e.key == pygame.K_z and nuke_state is None and saber_color == C.RED:
                    nuke_state = ('phone', pygame.time.get_ticks(), float(player.rect.centerx))
                if e.key == pygame.K_g and saber_color == C.RED:
                    grenade_charge_start = pygame.time.get_ticks()
                if e.key == pygame.K_o and saber_color == C.RED:
                    mx, my = pygame.mouse.get_pos()
                    lava_flows.append(LavaFlow(int(my + camy) // C.TILE,
                                               int(mx + camx) // C.TILE))
                if e.key == pygame.K_BACKSPACE:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = False
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            elif e.type == pygame.KEYUP:
                if e.key == pygame.K_g and grenade_charge_start is not None:
                    hold_ms = pygame.time.get_ticks() - grenade_charge_start
                    # scale speed: min 4, max ~20 (≈10 blocks horizontal range)
                    speed = 4.0 + 16.0 * min(hold_ms / 1500.0, 1.0)
                    mx, my = pygame.mouse.get_pos()
                    tx, ty = mx + camx, my + camy
                    pcx, pcy = float(player.rect.centerx), float(player.rect.centery)
                    dx, dy = tx - pcx, ty - pcy
                    d = max(1.0, math.hypot(dx, dy))
                    grenades.append(Grenade(pcx, pcy, dx / d * speed, dy / d * speed))
                    grenade_charge_start = None

        keys = pygame.key.get_pressed()
        ts   = display.TIME_SCALE
        floating_now = keys[pygame.K_f] and saber_color == C.RED
        if not floating_now:
            float_accum = 0.0
        else:
            # pre-cancel gravity so player.update() produces zero net downward movement
            player.vy = -C.GRAVITY * ts
        player.update(keys, dt, ROWS, COLS, get_tile)

        if floating_now:
            float_accum += dt * ts * (C.TILE * 1.5 / 1000.0)
            rise = int(float_accum)
            float_accum -= rise
            player.rect.y -= rise
            for (r, c, ch) in tiles_at(player.rect, ROWS, COLS, get_tile):
                if ch == 'X':
                    t = rect_for_tile(r, c)
                    if player.rect.colliderect(t):
                        player.rect.top = t.bottom
                        float_accum = 0.0
                        break
            player.vy = 0
            pcx = float(player.rect.centerx)
            feet_y = float(player.rect.bottom)
            col = player.rect.centerx // C.TILE
            ground_y = float(ROWS * C.TILE)
            for r in range(player.rect.bottom // C.TILE, ROWS):
                if get_tile(r, col) == 'X':
                    ground_y = float(r * C.TILE); break
            lp1 = (pcx, feet_y)
            lp2 = (pcx, ground_y)
            lightnings.append((_make_lightning(lp1, lp2, segments=6, jitter=8),
                               pygame.time.get_ticks() + int(80 / max(ts, 0.1))))
            for s in siths[:]:
                if seg_intersects_rect(lp1, lp2, s.rect):
                    siths.remove(s)
            for t in turrets[:]:
                if seg_intersects_rect(lp1, lp2, t.rect):
                    if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                        set_tile(t.r, t.c, '.')
                    turrets.remove(t)

        now_t = pygame.time.get_ticks()
        if keys[pygame.K_t] and saber_color == C.RED and now_t - last_lightning_t >= int(80 / max(ts, 0.1)):
            last_lightning_t = now_t
            mx, my = pygame.mouse.get_pos()
            lp1 = (float(player.rect.centerx), float(player.rect.centery))
            lp2 = (mx + camx, my + camy)
            lightnings.append((_make_lightning(lp1, lp2), now_t + int(120 / max(ts, 0.1))))
            for s in siths[:]:
                if seg_intersects_rect(lp1, lp2, s.rect):
                    siths.remove(s)
            for t in turrets[:]:
                if seg_intersects_rect(lp1, lp2, t.rect):
                    if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                        set_tile(t.r, t.c, '.')
                    turrets.remove(t)

        if saber_color == C.RED:
            mx, my = pygame.mouse.get_pos()
            tc = int(mx + camx) // C.TILE
            tr = int(my + camy) // C.TILE
            if keys[pygame.K_q] and get_tile(tr, tc) == '.':
                set_tile(tr, tc, 'X')
            if keys[pygame.K_l] and get_tile(tr, tc) == 'X':
                set_tile(tr, tc, '.')
                for t in turrets:
                    if not t.falling and t.r == tr - 1 and t.c == tc:
                        t.start_fall(ROWS, COLS, get_tile, set_tile)

        step = 2.5 * display.TIME_SCALE
        if saber_len < saber_target:
            saber_len = min(saber_len + step, saber_target)
        elif saber_len > saber_target:
            saber_len = max(saber_len - step, saber_target)
        if saber_switching and saber_len == 0.0:
            saber_color = C.RED if saber_color == C.CYAN else C.CYAN
            saber_target = float(C.SABER_LEN)
            saber_switching = False

        mx, my   = pygame.mouse.get_pos()
        mxw, myw = mx + camx, my + camy
        pcx, pcy = player.rect.centerx, player.rect.centery
        dx, dy   = mxw - pcx, myw - pcy
        d        = max(1.0, math.hypot(dx, dy))
        ux, uy   = dx / d, dy / d
        saber_p1 = (pcx, pcy)
        saber_p2 = (pcx + ux * saber_len, pcy + uy * saber_len)

        for s in siths[:]:
            s.update(player)
            sabers_clash        = seg_intersect(saber_p1, saber_p2, s.p1, s.p2)
            player_hits_body    = seg_intersects_rect(saber_p1, saber_p2, s.rect)

            if sabers_clash and s.state in ('windup', 'strike'):
                s.stagger()
            elif player_hits_body:
                if s.take_hit():
                    siths.remove(s); continue

            if s in siths and s.check_hit_on_player(player):
                player_hp -= 1
                player_flash_until = pygame.time.get_ticks() + 350
                s.state = 'recover'; s.state_start = pygame.time.get_ticks()
                player.vx = s.face_dir * 4.0
                if player_hp <= 0:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = True

        for t in turrets[:]:
            if seg_intersects_rect(saber_p1, saber_p2, t.rect):
                if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                    set_tile(t.r, t.c, '.')
                turrets.remove(t)
        for t in turrets[:]: t.check_support_and_maybe_fall(ROWS, COLS, get_tile)
        for t in turrets[:]:
            if t.update_fall(ROWS, COLS, get_tile, set_tile): turrets.remove(t)
        for t in turrets[:]: t.update_and_maybe_shoot(player, bolts, ROWS, COLS, get_tile)
        for b in bolts:
            if b.alive: b.update(ROWS, COLS, get_tile)

        def do_explode(gx, gy):
            sparks = []
            for _ in range(20):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(2.0, 7.0)
                sparks.append((math.cos(angle) * speed, math.sin(angle) * speed,
                               random.choice([(255,220,80),(255,140,0),(255,60,0),(255,255,180)])))
            explosions.append((gx, gy, pygame.time.get_ticks(), sparks))
            r = Grenade.EXP_RADIUS
            for row in range(ROWS):
                for col in range(COLS):
                    tx = col * C.TILE + C.TILE // 2
                    ty = row * C.TILE + C.TILE // 2
                    if math.hypot(tx - gx, ty - gy) <= r and get_tile(row, col) in ('B', 'X'):
                        set_tile(row, col, '.')
                        pieces = []
                        for _ in range(6):
                            a = random.uniform(0, 2 * math.pi)
                            sp = random.uniform(1.5, 4.0)
                            pieces.append((math.cos(a)*sp, math.sin(a)*sp, random.randint(4,10)))
                        crumbling_effects.append((float(tx), float(ty), pygame.time.get_ticks(), pieces))
            for s in siths[:]:
                if math.hypot(s.rect.centerx - gx, s.rect.centery - gy) <= r:
                    siths.remove(s)
            for t in turrets[:]:
                if math.hypot(t.rect.centerx - gx, t.rect.centery - gy) <= r:
                    if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                        set_tile(t.r, t.c, '.')
                    turrets.remove(t)
            if math.hypot(player.rect.centerx - gx, player.rect.centery - gy) <= r:
                _request_restart_flag[0] = True; _death_pending_flag[0] = True

        for g in grenades[:]:
            detonated = g.update(ROWS, COLS, get_tile)
            if not detonated:
                for s in siths:
                    if g.rect().colliderect(s.rect):
                        detonated = True; break
            if not detonated:
                for t in turrets:
                    if g.rect().colliderect(t.rect):
                        detonated = True; break
            if detonated:
                do_explode(g.x, g.y)
                grenades.remove(g)

        for lf in lava_flows:
            lf.update(ROWS, COLS, get_tile, set_tile, turrets, siths, grenades, bolts)
            if lf.alive and lf.player_touching(player):
                _request_restart_flag[0] = True; _death_pending_flag[0] = True
        lava_flows = [lf for lf in lava_flows if lf.alive]

        explosions        = [e for e in explosions        if pygame.time.get_ticks() - e[2] < 700]
        crumbling_effects = [e for e in crumbling_effects if pygame.time.get_ticks() - e[2] < 450]

        def _trigger_nuke_blast(nx, ny):
            for row in range(ROWS):
                for col in range(COLS):
                    if get_tile(row, col) in ('X', 'B', '^'):
                        set_tile(row, col, '.')
                        if random.random() < 0.3:
                            tx = col * C.TILE + C.TILE // 2
                            ty = row * C.TILE + C.TILE // 2
                            pieces = [(math.cos(a := random.uniform(0,2*math.pi))*random.uniform(2,6),
                                       math.sin(a)*random.uniform(2,6),
                                       random.randint(4,10)) for _ in range(5)]
                            crumbling_effects.append((float(tx), float(ty), pygame.time.get_ticks(), pieces))
            siths.clear()
            turrets.clear()
            bolts.clear()
            grenades.clear()
            lava_flows.clear()
            crumbling_effects.clear()
            explosions.clear()
            sparks = []
            for _ in range(60):
                a  = random.uniform(0, 2*math.pi)
                sp = random.uniform(3.0, 18.0)
                sparks.append((math.cos(a)*sp, math.sin(a)*sp,
                               random.choice([(255,220,80),(255,140,0),(255,60,0),(255,255,180),(255,255,255)])))
            return ('blast', pygame.time.get_ticks(), nx, ny, sparks)

        if nuke_state is not None:
            if nuke_state[0] == 'phone':
                _, phone_start, spawn_x = nuke_state
                if pygame.time.get_ticks() - phone_start >= 10000:
                    nuke_state = ('falling', spawn_x, -80.0, 0.0)
            elif nuke_state[0] == 'falling':
                _, nx, ny, vy = nuke_state
                vy  = min(vy + C.GRAVITY * display.TIME_SCALE * 2.5, 24.0)
                ny += vy * display.TIME_SCALE
                nuke_rect = pygame.Rect(int(nx)-20, int(ny)-20, 40, 40)
                hit = ny >= ROWS * C.TILE
                for (_, _, ch) in tiles_at(nuke_rect, ROWS, COLS, get_tile):
                    if ch == 'X': hit = True; break
                if hit:
                    nuke_state = _trigger_nuke_blast(nx, ny)
                else:
                    nuke_state = ('falling', nx, ny, vy)
            elif nuke_state[0] == 'blast':
                _, blast_start, nx, ny, _ = nuke_state
                if pygame.time.get_ticks() - blast_start >= 2000:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = True
                    nuke_state = None

        camx, camy = center_camera_on_player(camx, camy, player, ROWS, COLS)

        lmb, _, rmb = pygame.mouse.get_pressed(3)
        thresh_sq   = (C.SABER_THICKNESS / 2 + 4) ** 2
        for b in bolts:
            if not b.alive: continue
            hit = (point_seg_dist_sq(b.x, b.y, *saber_p1, *saber_p2) <= thresh_sq or
                   seg_intersect((b.prev_x, b.prev_y), (b.x, b.y), saber_p1, saber_p2))
            if hit:
                if rmb:
                    b.alive = False
                else:
                    tip_dist_sq = (b.x - saber_p2[0])**2 + (b.y - saber_p2[1])**2
                    if tip_dist_sq <= thresh_sq:
                        b.vx *= -1; b.vy *= -1
                    else:
                        # reflect bolt off the lightsaber blade surface
                        sx = saber_p2[0] - saber_p1[0]; sy = saber_p2[1] - saber_p1[1]
                        sd = (sx*sx + sy*sy) ** 0.5
                        if sd > 0:
                            sx /= sd; sy /= sd
                            nx, ny = -sy, sx
                            dot = b.vx * nx + b.vy * ny
                            b.vx -= 2 * dot * nx; b.vy -= 2 * dot * ny
                    b.friendly = True
                    # push bolt clear of the detection zone so it can't re-collide next frame
                    bspeed = (b.vx**2 + b.vy**2) ** 0.5
                    if bspeed > 0:
                        clear = thresh_sq ** 0.5 + b.r + 2
                        b.x += b.vx / bspeed * clear
                        b.y += b.vy / bspeed * clear
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
        draw_player(player, camx, camy, saber_p1, saber_p2, saber_color,
                    flash=pygame.time.get_ticks() < player_flash_until)
        for s in siths: s.draw(display.screen, camx, camy)
        for lf in lava_flows: lf.draw(camx, camy)
        for g in grenades: g.draw(camx, camy)
        if grenade_charge_start is not None:
            charge = min((pygame.time.get_ticks() - grenade_charge_start) / 1500.0, 1.0)
            bx = int(player.rect.centerx - camx) - 20
            by = int(player.rect.top - camy) - 12
            pygame.draw.rect(display.screen, (80, 80, 80),   (bx, by, 40, 6))
            pygame.draw.rect(display.screen, (255, 140, 0),  (bx, by, int(40 * charge), 6))
        for ex, ey, start, sparks in explosions:
            age  = pygame.time.get_ticks() - start
            t    = age / 700.0          # 0→1 over lifetime
            fade = max(0, 1.0 - t)
            sx, sy = int(ex - camx), int(ey - camy)

            # central flash (bright white → yellow, shrinks fast)
            flash_r = int(Grenade.EXP_RADIUS * 0.5 * max(0, 1 - age / 120))
            if flash_r > 0:
                pygame.draw.circle(display.screen, (255, 255, 220), (sx, sy), flash_r)

            # slow outer ring (orange → red, expands to full radius)
            r1 = int(Grenade.EXP_RADIUS * min(t * 1.4, 1.0))
            if r1 > 0:
                c1 = (255, int(120 * fade), 0)
                pygame.draw.circle(display.screen, c1, (sx, sy), r1, 3)

            # fast inner ring (yellow, expands to 60% radius quickly)
            r2 = int(Grenade.EXP_RADIUS * 0.6 * min(t * 2.5, 1.0))
            if r2 > 0:
                c2 = (255, int(220 * fade), int(80 * fade))
                pygame.draw.circle(display.screen, c2, (sx, sy), r2, 2)

            # spark particles
            age_s = age / 60.0  # convert ms→ approx frames at ~60fps scaled
            for vx, vy, color in sparks:
                px = int(ex + vx * age_s - camx)
                py = int(ey + vy * age_s + 0.3 * age_s * age_s - camy)
                size = max(1, int(4 * fade))
                fc   = (int(color[0] * fade), int(color[1] * fade), int(color[2] * fade))
                pygame.draw.circle(display.screen, fc, (px, py), size)

        for bx, by, start, pieces in crumbling_effects:
            age  = pygame.time.get_ticks() - start
            t    = age / 450.0
            fade = max(0.0, 1.0 - t)
            age_s = age / 60.0
            for vx, vy, size in pieces:
                px = int(bx + vx * age_s - camx)
                py = int(by + vy * age_s + 0.25 * age_s * age_s - camy)
                s  = max(1, int(size * fade))
                g  = int(68 * fade)
                pygame.draw.rect(display.screen, (g+10, g+10, g+15), (px - s//2, py - s//2, s, s))

        if nuke_state is not None:
            if nuke_state[0] == 'phone':
                _, phone_start, _ = nuke_state
                remaining = max(0, 10 - (pygame.time.get_ticks() - phone_start) / 1000.0)
                # small phone in player's left hand
                hx = int(player.rect.left  - 12 - camx)
                hy = int(player.rect.centery + 2 - camy)
                pw, ph = 12, 20
                pygame.draw.rect(display.screen, (30, 30, 35),    (hx, hy, pw, ph), border_radius=3)
                pygame.draw.rect(display.screen, (160, 160, 190), (hx, hy, pw, ph), 1, border_radius=3)
                pygame.draw.rect(display.screen, (10, 20, 80),    (hx+2, hy+3, pw-4, ph-8), border_radius=1)
                # pulsing red dot (call indicator)
                pulse_r = 2 + int(abs(math.sin(pygame.time.get_ticks() * 0.01)))
                pygame.draw.circle(display.screen, (255, 60, 60), (hx + pw//2, hy + ph - 4), pulse_r)
                # countdown above player
                cd_surf = display.FONT.render(f"{remaining:.1f}s", True, (255, 200, 80))
                display.screen.blit(cd_surf, (int(player.rect.centerx - camx) - cd_surf.get_width()//2,
                                              int(player.rect.top - camy) - 22))
            elif nuke_state[0] == 'falling':
                _, nx, ny, vy = nuke_state
                pulse  = abs(math.sin(pygame.time.get_ticks() * 0.012)) * 0.3 + 0.7
                radius = int(28 * pulse)
                sx, sy = int(nx - camx), int(ny - camy)
                pygame.draw.circle(display.screen, (200, 80, 0),   (sx, sy), radius)
                pygame.draw.circle(display.screen, (255, 200, 50), (sx, sy), radius, 3)
                # speed lines above to show it's falling
                for i in range(1, 5):
                    ly = sy - radius - i * 10
                    pygame.draw.line(display.screen, (255, 150, int(50*pulse)),
                                     (sx - 6, ly), (sx + 6, ly), max(1, 3 - i))
            elif nuke_state[0] == 'blast':
                _, blast_start, nx, ny, sparks = nuke_state
                age  = pygame.time.get_ticks() - blast_start
                t    = age / 2000.0
                fade = max(0.0, 1.0 - t)
                sx, sy = int(nx - camx), int(ny - camy)
                # multiple huge expanding rings
                for ring_t, ring_col in [(t*1.2, (255,220,80)), (t*0.8, (255,100,0)), (t*0.5, (255,255,200))]:
                    r = int(min(ring_t, 1.0) * max(C.WIDTH, C.HEIGHT) * 1.5)
                    if r > 0:
                        c = (int(ring_col[0]*fade), int(ring_col[1]*fade), int(ring_col[2]*fade))
                        pygame.draw.circle(display.screen, c, (sx, sy), r, max(1, int(8*fade)))
                # central flash
                flash = int(120 * max(0, 1 - age/300))
                if flash > 0:
                    pygame.draw.circle(display.screen, (255,255,240), (sx, sy), flash)
                # sparks
                age_s = age / 60.0
                for vx, vy, color in sparks:
                    px = int(nx + vx * age_s - camx)
                    py = int(ny + vy * age_s + 0.2 * age_s * age_s - camy)
                    sz = max(1, int(6 * fade))
                    fc = (int(color[0]*fade), int(color[1]*fade), int(color[2]*fade))
                    pygame.draw.circle(display.screen, fc, (px, py), sz)

        now = pygame.time.get_ticks()
        lightnings = [l for l in lightnings if l[1] > now]
        for pts, expire in lightnings:
            for i in range(len(pts) - 1):
                p1s = (int(pts[i][0]   - camx), int(pts[i][1]   - camy))
                p2s = (int(pts[i+1][0] - camx), int(pts[i+1][1] - camy))
                pygame.draw.line(display.screen, (180, 180, 255), p1s, p2s, 3)
                pygame.draw.line(display.screen, (255, 255, 255), p1s, p2s, 1)

        t = player.time_ms / 1000.0
        display.screen.blit(display.FONT.render(f"Deaths: {player.deaths}", True, C.WHITE), (10, 10))
        display.screen.blit(display.FONT.render(
            f"Time: {t:05.2f}s   Speed x{display.TIME_SCALE:.2f} (C toggles)", True, C.WHITE), (10, 30))
        # Player HP pips
        for i in range(3):
            col = (220, 50, 50) if i < player_hp else (60, 20, 20)
            pygame.draw.rect(display.screen, col, (10 + i * 18, 52, 14, 14), border_radius=3)
        display.screen.blit(display.FONT.render(
            "Move A/D or L/R  Jump W/Up  Saber: mouse  Push X  Pull V  Backspace restart",
            True, C.YELLOW), (10, C.HEIGHT - 28))
        if win:
            msg = display.BIG.render("You cleared the stronghold!", True, C.WHITE)
            sub = display.FONT.render("Press R to try again.", True, C.WHITE)
            display.screen.blit(msg, (C.WIDTH // 2 - msg.get_width() // 2, 70))
            display.screen.blit(sub, (C.WIDTH // 2 - sub.get_width() // 2, 110))
        pygame.display.flip()
