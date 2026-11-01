"""Game entities for the parkour stage: Sith Lords, the player, turrets,
grenades, lava, bolts and gun pickups."""
import pygame, math, random
import constants as C
import display
from .geometry import rect_for_tile, tiles_at, point_seg_dist_sq
from .state import _request_restart_flag, _death_pending_flag

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
        self.push_vx = 0.0
        self.push_sub = 0.0
        self.stun_until = 0

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

    def _has_ground_ahead(self, step, ROWS, COLS, get_tile):
        # Check tile directly below the leading edge after stepping
        check_x = self.rect.right if step > 0 else self.rect.left - 1
        check_y = self.rect.bottom + 1
        c = check_x // C.TILE
        r = check_y // C.TILE
        if r < 0 or r >= ROWS or c < 0 or c >= COLS:
            return False
        return get_tile(r, c) == 'X'

    def update(self, player, ROWS=None, COLS=None, get_tile=None):
        now = pygame.time.get_ticks()
        if now < self.stun_until:
            return
        ts  = display.TIME_SCALE
        sx, sy = float(self.rect.centerx), float(self.rect.centery)
        px     = float(player.rect.centerx)
        dx     = px - sx
        dist   = abs(dx)
        self.face_dir = 1 if dx >= 0 else -1
        elapsed = now - self.state_start

        if self.state == 'approach':
            if dist > self.STRIKE_RANGE_PX:
                move = int(self.face_dir * max(1, min(self.APPROACH_SPEED * ts, dist - self.STRIKE_RANGE_PX)))
                if get_tile is None or self._has_ground_ahead(move, ROWS, COLS, get_tile):
                    self.rect.x += move
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
        stunned = now < self.stun_until
        if stunned:
            body_col = (80, 80, 180)
        else:
            body_col = (255, 255, 255) if now < self.flash_until else C.RED
        pygame.draw.rect(screen, body_col, (x, y, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (255, 150, 150) if not stunned else (120, 120, 220),
                         (x + 6, y + 4, self.w - 12, 8), border_radius=3)
        if stunned:
            zs = display.FONT.render("ZZZ", True, (180, 220, 255))
            screen.blit(zs, (int(x) + self.w // 2 - zs.get_width() // 2, int(y) - 18))
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
    def __init__(self, x, y, max_jumps=2, max_health=None):
        self.w, self.h = 26, 34
        self.rect      = pygame.Rect(x + 7, y + 6, self.w, self.h)
        self.vx = self.vy = 0.0
        self.on_ground  = False; self.max_jumps = max_jumps; self.jumps_left = max_jumps
        self.face_dir   = 1;     self.deaths = 0; self.time_ms = 0
        self.max_health = max_health  # None = no health pool (bullets/falls stay instant-death)
        self.health     = max_health if max_health is not None else 0

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
                        self.on_ground = True; self.jumps_left = self.max_jumps
                    elif self.vy < 0:
                        self.rect.top = t.bottom; self.vy = 0
        if self.rect.bottom > ROWS * C.TILE:
            self.rect.bottom = ROWS * C.TILE
            self.vy = 0; self.on_ground = True; self.jumps_left = self.max_jumps
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
        self.push_vx    = 0.0
        self.push_sub   = 0.0
        self.stun_until = 0
        self.mg_hits    = 0

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
        if now < self.stun_until:
            return
        eff = int(self.cooldown / max(display.TIME_SCALE, 1e-3))
        if self.player_within_radius(player) and now - self.last_shot >= eff:
            self.last_shot = now
            cx, cy = self.center()
            tx, ty = player.rect.centerx, player.rect.centery
            dx, dy = tx - cx, ty - cy
            angle  = math.atan2(dy, dx)
            if random.random() < 0.5:  # 50% chance to miss
                angle += random.choice([-1, 1]) * random.uniform(math.radians(10), math.radians(30))
            ux, uy = math.cos(angle), math.sin(angle)
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
        self.roll_angle = 0.0

    def rect(self):
        return pygame.Rect(int(self.x) - 4, int(self.y) - 4, 8, 8)

    BOUNCE_DAMP  = 0.65   # fraction of speed kept after each bounce
    ROLL_FRICTION = 0.015  # vx lost per frame while rolling on ground
    ROLL_STOP    = 0.3    # vx below this snaps to zero
    AIR_DRAG     = 0.012  # fraction of vx bled per frame while airborne

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
        else:
            self.vx *= max(0.0, 1.0 - self.AIR_DRAG * ts)

        self.x, self.y = nx, ny
        if self.y + 4 >= ROWS * C.TILE:
            self.y = float(ROWS * C.TILE - 4)
            self.vy = -abs(self.vy) * self.BOUNCE_DAMP
            self.vx *= self.BOUNCE_DAMP
        self.roll_angle += self.vx * ts * 0.12

        if pygame.time.get_ticks() - self.born >= self.FUSE_MS:
            self.alive = False; return True
        return False

    def draw(self, camx, camy):
        t = (pygame.time.get_ticks() - self.born) / self.FUSE_MS
        color = (255, int(200 - 150 * t), 50) if t < 0.7 else (255, 50, 50)
        sx, sy = int(self.x - camx), int(self.y - camy)
        pygame.draw.circle(display.screen, color, (sx, sy), 5)
        dot_x = sx + int(math.cos(self.roll_angle) * 3)
        dot_y = sy + int(math.sin(self.roll_angle) * 3)
        pygame.draw.circle(display.screen, (30, 30, 30), (dot_x, dot_y), 2)


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
        self.enemy_penetrating = False  # passes through enemies without stopping
        self.tasing           = False  # stuns instead of kills
        self.mg_bolt          = False  # machine-gun bolt; turrets need 3 hits
        self.one_shot         = False  # kills any enemy in one hit
        self.wide             = False  # taser wide-beam: 2-tile-tall hitbox
        self.hit_ids          = set()  # enemy ids already hit

    def rect(self):
        if self.wide:
            return pygame.Rect(int(self.x) - self.r, int(self.y) - C.TILE,
                               self.r * 2, C.TILE * 2)
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
        if 0 <= r < ROWS and 0 <= c < COLS and get_tile(r, c) == 'X':
            self.alive = False


class GunPickup:
    W, H = 22, 10

    def __init__(self, cx, bottom_y):
        self.rect = pygame.Rect(cx - self.W // 2, bottom_y - self.H, self.W, self.H)
        self.vy = 0.0

    def update(self, ROWS, COLS, get_tile):
        ts = display.TIME_SCALE
        self.vy = min(self.vy + C.GRAVITY * ts, 16)
        self.rect.y += int(round(self.vy * ts))
        for (r, c, ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch == 'X':
                t = rect_for_tile(r, c)
                if self.rect.colliderect(t) and self.vy >= 0:
                    self.rect.bottom = t.top
                    self.vy = 0.0
                    return

    def draw(self, screen, camx, camy):
        x, y = self.rect.x - int(camx), self.rect.y - int(camy)
        pygame.draw.rect(screen, (10, 10, 12),   (x, y, self.W, self.H))
        pygame.draw.rect(screen, (90, 90, 100),  (x, y, self.W, self.H), 1)
        pygame.draw.rect(screen, (50, 50, 60),   (x + self.W - 6, y + 2, 6, self.H - 4))



