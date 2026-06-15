import pygame, sys, math, random
import constants as C
import display

# ---- Stars ----
stars = []

def init_stars():
    global stars
    stars = []
    for _ in range(C.STAR_COUNT):
        x   = random.randint(0, C.WIDTH)
        y   = random.randint(0, C.HEIGHT)
        par = random.uniform(0.3, 1.0)
        stars.append([x, y, par])

def scroll_stars(sx, sy):
    for s in stars:
        s[0] += sx * s[2] * 0.5
        s[1] += sy * s[2] * 0.5
        if s[0] < -2:          s[0] += C.WIDTH + 4
        if s[0] > C.WIDTH + 2: s[0] -= C.WIDTH + 4
        if s[1] < -2:          s[1] += C.HEIGHT + 4
        if s[1] > C.HEIGHT + 2: s[1] -= C.HEIGHT + 4

def draw_stars(surf):
    for x, y, par in stars:
        size = 1 if par < 0.6 else 2
        pygame.draw.rect(surf, (200, 200, 220), (int(x), int(y), size, size))

# ---- Planet ----
def draw_planet(surf, px, py):
    center = (int(px), int(py))
    for r, col in [(C.PLANET_RADIUS + 20, (20, 30, 60)),
                   (C.PLANET_RADIUS,      (25, 70, 130)),
                   (C.PLANET_RADIUS - 20, (30, 110, 170))]:
        pygame.draw.circle(surf, col, center, r)
    pygame.draw.circle(surf, (220, 240, 255), center, C.PLANET_RADIUS, 2)

def draw_planet_arrow(surf, px, py):
    if 0 <= px <= C.WIDTH and 0 <= py <= C.HEIGHT:
        return
    cx, cy = C.WIDTH / 2, C.HEIGHT / 2
    dx, dy = px - cx, py - cy
    ang    = math.atan2(dy, dx)
    margin = 20
    cos, sin = math.cos(ang), math.sin(ang)
    t = 1e9
    if cos > 0: t = min(t, (C.WIDTH  - margin - cx) / cos)
    if cos < 0: t = min(t, (margin   - cx) / cos)
    if sin > 0: t = min(t, (C.HEIGHT - margin - cy) / sin)
    if sin < 0: t = min(t, (margin   - cy) / sin)
    ax, ay = cx + cos * t, cy + sin * t
    wing   = 12
    tip    = (int(ax), int(ay))
    left   = (int(ax - cos * 22 - sin * wing), int(ay - sin * 22 + cos * wing))
    right  = (int(ax - cos * 22 + sin * wing), int(ay - sin * 22 - cos * wing))
    pygame.draw.polygon(surf, (240, 230, 110), [tip, left, right])

# ---- Geometry ----
def point_in_triangle(px, py, A, B, C_pt):
    (x1, y1), (x2, y2), (x3, y3) = A, B, C_pt
    det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if det == 0:
        return False
    l1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / det
    l2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / det
    l3 = 1 - l1 - l2
    return 0 <= l1 <= 1 and 0 <= l2 <= 1 and 0 <= l3 <= 1

# ---- Entities ----
class XWing:
    def __init__(self):
        self.vx = self.vy = 0.0
        self.ang = 0.0
        self.last_shot    = -9999
        self.flash_until  = 0
        self.kills        = 0
        self.hits         = 0
        self.shutdown     = False
        self.shutdown_since = 0

    def rect(self):
        return pygame.Rect(C.WIDTH // 2 - C.SPACE_SHIP_W // 2,
                           C.HEIGHT // 2 - C.SPACE_SHIP_H // 2,
                           C.SPACE_SHIP_W, C.SPACE_SHIP_H)

    def update_controls(self, keys):
        if self.shutdown:
            return
        ts = display.TIME_SCALE
        if keys[pygame.K_LEFT]:  self.ang -= C.ROT_SPEED * ts
        if keys[pygame.K_RIGHT]: self.ang += C.ROT_SPEED * ts
        if keys[pygame.K_UP]:
            fx, fy = math.cos(self.ang), math.sin(self.ang)
            self.vx += fx * C.THRUST * ts
            self.vy += fy * C.THRUST * ts
        self.vx *= C.SPACE_DRAG ** ts
        self.vy *= C.SPACE_DRAG ** ts
        sp = math.hypot(self.vx, self.vy)
        if sp > C.SPACE_MAXSPEED:
            k = C.SPACE_MAXSPEED / sp
            self.vx *= k; self.vy *= k

    def falling_controls(self, keys):
        ts = display.TIME_SCALE
        if keys[pygame.K_LEFT]:  self.ang -= C.FALL_ROT * ts
        if keys[pygame.K_RIGHT]: self.ang += C.FALL_ROT * ts
        if keys[pygame.K_UP]:
            fx, fy = math.cos(self.ang), math.sin(self.ang)
            self.vx += fx * C.FALL_THRUST * ts
            self.vy += fy * C.FALL_THRUST * ts
        self.vx *= C.SPACE_DRAG ** ts
        self.vy *= C.SPACE_DRAG ** ts

    def shoot(self, bullets):
        if self.shutdown:
            return
        now = pygame.time.get_ticks()
        eff = int(C.LASER_CD_MS / max(display.TIME_SCALE, 1e-3))
        if now - self.last_shot < eff:
            return
        self.last_shot = now
        fx, fy = math.cos(self.ang), math.sin(self.ang)
        ux, uy = -math.sin(self.ang), math.cos(self.ang)
        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
        tip1 = (cx + fx * 20 + ux * 6, cy + fy * 20 + uy * 6)
        tip2 = (cx + fx * 20 - ux * 6, cy + fy * 20 - uy * 6)
        bullets.append(SpaceBullet(*tip1, fx * C.LASER_SPEED, fy * C.LASER_SPEED, True))
        bullets.append(SpaceBullet(*tip2, fx * C.LASER_SPEED, fy * C.LASER_SPEED, True))

    def take_hit(self):
        self.hits += 1
        self.flash_until = pygame.time.get_ticks() + 140
        if self.hits >= C.SHUTDOWN_HITS and not self.shutdown:
            self.shutdown = True
            self.shutdown_since = pygame.time.get_ticks()
            self.vx *= 0.4; self.vy += 0.8

    def draw(self, surf):
        fx, fy = math.cos(self.ang), math.sin(self.ang)
        ux, uy = -math.sin(self.ang), math.cos(self.ang)
        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
        nose = (int(cx + fx * C.SPACE_SHIP_W * 0.5), int(cy + fy * C.SPACE_SHIP_W * 0.5))
        lt   = (int(cx - fx * C.SPACE_SHIP_W * 0.5 + ux * C.SPACE_SHIP_H * 0.5),
                int(cy - fy * C.SPACE_SHIP_W * 0.5 + uy * C.SPACE_SHIP_H * 0.5))
        rt   = (int(cx - fx * C.SPACE_SHIP_W * 0.5 - ux * C.SPACE_SHIP_H * 0.5),
                int(cy - fy * C.SPACE_SHIP_W * 0.5 - uy * C.SPACE_SHIP_H * 0.5))
        pygame.draw.polygon(surf, (180, 180, 200), [lt, nose, rt])
        pygame.draw.line(surf, (200, 200, 220),
                         (int(cx - fx * 14 + ux * 8), int(cy - fy * 14 + uy * 8)),
                         (int(cx + fx * 22 + ux * 8), int(cy + fy * 22 + uy * 8)), 3)
        pygame.draw.line(surf, (200, 200, 220),
                         (int(cx - fx * 14 - ux * 8), int(cy - fy * 14 - uy * 8)),
                         (int(cx + fx * 22 - ux * 8), int(cy + fy * 22 - uy * 8)), 3)
        if pygame.time.get_ticks() < self.flash_until:
            pygame.draw.circle(surf, (255, 120, 120), (int(cx), int(cy)), 16, 2)


class SpaceBullet:
    def __init__(self, x, y, vx, vy, friendly=False):
        self.x  = float(x); self.y  = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.friendly = friendly; self.alive = True; self.r = 3

    def world_scroll(self, sx, sy):
        self.x += sx; self.y += sy

    def update(self):
        if not self.alive:
            return
        ts = display.TIME_SCALE
        self.x += self.vx * ts; self.y += self.vy * ts
        if (self.x < -80 or self.x > C.WIDTH + 80 or
                self.y < -80 or self.y > C.HEIGHT + 80):
            self.alive = False

    def draw(self, surf):
        pygame.draw.circle(surf, C.YELLOW if self.friendly else C.RED,
                           (int(self.x), int(self.y)), self.r)


class Torpedo:
    SPEED   = C.SPACE_MAXSPEED
    HIT_R   = 18
    CD_MS   = 1500

    def __init__(self, x, y, target):
        self.x = float(x); self.y = float(y)
        self.vx = 0.0; self.vy = 0.0
        self.target = target   # TIE instance, or (SuperStarDestroyer, SSDTurret)
        self.alive = True

    def _target_pos(self):
        if isinstance(self.target, TIE):
            return self.target.x, self.target.y
        ssd, turret = self.target
        return ssd.x + turret.rel_x, ssd.y + turret.rel_y

    def _target_alive(self):
        if isinstance(self.target, TIE):
            return self.target.alive
        return self.target[1].alive

    def world_scroll(self, sx, sy):
        self.x += sx; self.y += sy

    def update(self):
        if not self.alive:
            return False
        if not self._target_alive():
            self.alive = False
            return False
        tx, ty = self._target_pos()
        dx, dy = tx - self.x, ty - self.y
        dist   = max(1.0, math.hypot(dx, dy))
        ts     = display.TIME_SCALE
        self.vx = dx / dist * self.SPEED
        self.vy = dy / dist * self.SPEED
        self.x += self.vx * ts
        self.y += self.vy * ts
        if (self.x < -150 or self.x > C.WIDTH + 150 or
                self.y < -150 or self.y > C.HEIGHT + 150):
            self.alive = False
            return False
        if math.hypot(self.x - tx, self.y - ty) < self.HIT_R:
            self.alive = False
            if isinstance(self.target, TIE):
                self.target.alive = False
                return True   # caller should increment kills
            else:
                self.target[1].alive = False
        return False

    def draw(self, surf):
        sx, sy = int(self.x), int(self.y)
        pygame.draw.circle(surf, (255, 220, 60), (sx, sy), 5)
        if abs(self.vx) + abs(self.vy) > 0.1:
            pygame.draw.line(surf, (255, 100, 20),
                             (sx, sy),
                             (int(self.x - self.vx * 3), int(self.y - self.vy * 3)), 2)


class TIE:
    def __init__(self, x, y, vx, vy):
        self.x  = float(x); self.y  = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.w  = 32; self.h = 24; self.alive = True; self.last_shot = -9999

    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)

    def world_scroll(self, sx, sy):
        self.x += sx; self.y += sy

    def update(self):
        if not self.alive:
            return
        ts = display.TIME_SCALE
        self.x += self.vx * ts; self.y += self.vy * ts
        if (self.x < -140 or self.x > C.WIDTH + 140 or
                self.y < -140 or self.y > C.HEIGHT + 140):
            self.alive = False

    def maybe_shoot(self, enemy_bolts):
        now = pygame.time.get_ticks()
        eff = int(C.TIE_SHOOT_CD_MS / max(display.TIME_SCALE, 1e-3))
        if now - self.last_shot < eff:
            return
        self.last_shot = now
        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
        dx, dy = cx - self.x, cy - self.y
        d  = max(1.0, math.hypot(dx, dy))
        angle = math.atan2(dy, dx)
        if random.random() >= 0.75:
            angle += random.choice([-1, 1]) * random.uniform(math.radians(20), math.radians(45))
        ux, uy = math.cos(angle), math.sin(angle)
        enemy_bolts.append(SpaceBullet(self.x, self.y,
                                       ux * C.TIE_LASER_SPEED, uy * C.TIE_LASER_SPEED, False))

    def draw(self, surf):
        r = self.rect()
        pygame.draw.rect(surf, (150, 150, 170), r, border_radius=4)
        pygame.draw.rect(surf, (40,  40,  60), (r.x + 6,  r.y + 6,  r.w - 12, r.h - 12), border_radius=3)
        pygame.draw.rect(surf, (90,  90, 110), (r.x - 10, r.y + 3,  10,        r.h - 6))
        pygame.draw.rect(surf, (90,  90, 110), (r.right,  r.y + 3,  10,        r.h - 6))


class StarDestroyer:
    def __init__(self, x, y, vxy):
        self.x  = float(x); self.y = float(y)
        self.vx, self.vy = vxy
        self.top_len    = 320
        self.base_half  = 240
        self.hangar_w   = 160
        self.hangar_h   = 48

    def world_scroll(self, sx, sy):
        self.x += sx; self.y += sy

    def update(self):
        ts = display.TIME_SCALE
        self.x += self.vx * ts; self.y += self.vy * ts

    def triangle_pts(self):
        return [(self.x,                  self.y - self.top_len),
                (self.x - self.base_half, self.y + self.base_half),
                (self.x + self.base_half, self.y + self.base_half)]

    def hangar_rect(self):
        return (self.x - self.hangar_w / 2,
                self.y + self.base_half - self.hangar_h / 2,
                self.hangar_w, self.hangar_h)

    def draw(self, surf):
        pts = [(int(px), int(py)) for px, py in self.triangle_pts()]
        pygame.draw.polygon(surf, (120, 120, 135), pts)
        pygame.draw.polygon(surf, C.WHITE, pts, 3)
        hx, hy, hw, hh = self.hangar_rect()
        pygame.draw.rect(surf, C.GREEN, (int(hx), int(hy), int(hw), int(hh)), 3)


class SSDTurret:
    def __init__(self, rel_x, rel_y):
        self.rel_x = float(rel_x)
        self.rel_y = float(rel_y)
        self.alive = True
        self.last_shot = -9999

    def maybe_shoot(self, ssd, enemy_bolts):
        if not self.alive:
            return
        now = pygame.time.get_ticks()
        if now - self.last_shot < C.SSD_TURRET_COOLDOWN_MS:
            return
        self.last_shot = now
        tx = ssd.x + self.rel_x;  ty = ssd.y + self.rel_y
        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
        dx, dy = cx - tx, cy - ty
        d = max(1.0, math.hypot(dx, dy))
        angle = math.atan2(dy, dx)
        if random.random() >= 0.75:
            angle += random.choice([-1, 1]) * random.uniform(math.radians(20), math.radians(45))
        ux, uy = math.cos(angle), math.sin(angle)
        enemy_bolts.append(SpaceBullet(tx, ty,
                                       ux * C.TIE_LASER_SPEED, uy * C.TIE_LASER_SPEED, False))


class SuperStarDestroyer:
    TOP_LEN   = 560
    BASE_HALF = 420

    HANGAR_W = 180
    HANGAR_H = 50

    def __init__(self, x, y):
        self.x = float(x); self.y = float(y)
        # Turrets placed well inside the triangle hull
        self.turrets = [
            SSDTurret(   0, -350),   # upper centre
            SSDTurret(-120, -100),   # mid left
            SSDTurret( 120, -100),   # mid right
            SSDTurret(-220,  200),   # lower left
            SSDTurret( 220,  200),   # lower right
        ]

    def world_scroll(self, sx, sy):
        self.x += sx; self.y += sy

    def update(self):
        ts = display.TIME_SCALE
        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
        dx, dy = cx - self.x, cy - self.y
        dist = max(1.0, math.hypot(dx, dy))
        self.x += (dx / dist) * C.SSD_SPEED * ts
        self.y += (dy / dist) * C.SSD_SPEED * ts

    def triangle_pts(self):
        tl, bh = self.TOP_LEN, self.BASE_HALF
        return [(self.x,       self.y - tl),
                (self.x - bh,  self.y + bh),
                (self.x + bh,  self.y + bh)]

    def hangar_rect(self):
        hw, hh = self.HANGAR_W, self.HANGAR_H
        return (self.x - hw / 2, self.y + self.BASE_HALF - hh, hw, hh)

    def shoot_all(self, enemy_bolts):
        for t in self.turrets:
            t.maybe_shoot(self, enemy_bolts)

    def check_bullet_hits(self, bullets):
        for b in bullets:
            if not b.alive or not b.friendly:
                continue
            for t in self.turrets:
                if not t.alive:
                    continue
                if math.hypot(b.x - (self.x + t.rel_x), b.y - (self.y + t.rel_y)) < 14:
                    t.alive = False; b.alive = False; break

    def turrets_remaining(self):
        return sum(1 for t in self.turrets if t.alive)

    def draw(self, surf):
        pts = [(int(px), int(py)) for px, py in self.triangle_pts()]
        pygame.draw.polygon(surf, (70, 70, 85), pts)
        pygame.draw.polygon(surf, (155, 155, 180), pts, 4)
        # Bridge tower near tip
        bx = int(self.x); by = int(self.y - self.TOP_LEN + 100)
        pygame.draw.rect(surf, (95, 95, 115), (bx - 28, by, 56, 45))
        pygame.draw.rect(surf, (135, 135, 160), (bx - 28, by, 56, 45), 2)
        # Hangar bay at base — only visible once all turrets are destroyed
        if self.turrets_remaining() == 0:
            hx, hy, hw, hh = self.hangar_rect()
            pygame.draw.rect(surf, C.GREEN, (int(hx), int(hy), int(hw), int(hh)), 3)
        # Turrets (inside the hull)
        for t in self.turrets:
            tx = int(self.x + t.rel_x); ty = int(self.y + t.rel_y)
            if t.alive:
                pygame.draw.circle(surf, (200, 60, 60), (tx, ty), 9)
                pygame.draw.circle(surf, (255, 110, 110), (tx, ty), 9, 2)
            else:
                pygame.draw.circle(surf, (45, 25, 25), (tx, ty), 7)
                pygame.draw.circle(surf, (80, 50, 50), (tx, ty), 7, 1)


# ---- Stage ----
def space_stage():
    """Returns 'landed_destroyer', 'planet_touch', or 'space_dead'."""
    xwing          = XWing()
    bullets        = []; enemy_bolts = []; ties = []; torpedoes = []
    last_spawn     = pygame.time.get_ticks()
    last_torpedo   = -9999
    torpedo_count  = 7
    super_destroyer = None   # spawns after first kill

    init_stars()

    planet_active = False
    planet_x, planet_y = C.WIDTH / 2, C.HEIGHT / 2 + C.PLANET_EDGE_OFFSET
    STATE = "combat"

    while True:
        dt = display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE: xwing.shoot(bullets)
                if e.key == pygame.K_f:     return "landed_destroyer"
                if e.key in (pygame.K_t, pygame.K_v) and not xwing.shutdown:
                    free_shot = (e.key == pygame.K_v)
                    now_t = pygame.time.get_ticks()
                    can_fire = (torpedo_count > 0 or free_shot) and now_t - last_torpedo >= Torpedo.CD_MS
                    if can_fire:
                        cx, cy = C.WIDTH / 2, C.HEIGHT / 2
                        best = None; best_d = float('inf')
                        for _t in ties:
                            if _t.alive:
                                _d = math.hypot(_t.x - cx, _t.y - cy)
                                if _d < best_d: best_d = _d; best = _t
                        if super_destroyer:
                            for _turret in super_destroyer.turrets:
                                if _turret.alive:
                                    _tx = super_destroyer.x + _turret.rel_x
                                    _ty = super_destroyer.y + _turret.rel_y
                                    _d  = math.hypot(_tx - cx, _ty - cy)
                                    if _d < best_d: best_d = _d; best = (super_destroyer, _turret)
                        if best is not None:
                            torpedoes.append(Torpedo(cx, cy, best))
                            last_torpedo = now_t
                            if not free_shot:
                                torpedo_count -= 1

        keys = pygame.key.get_pressed()
        if STATE == "combat":
            xwing.update_controls(keys)
        else:
            xwing.falling_controls(keys)
            cx, cy = C.WIDTH / 2, C.HEIGHT / 2
            dx, dy = planet_x - cx, planet_y - cy
            dist   = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / dist, dy / dist
            xwing.vx += ux * (C.PLANET_PULL * dt)
            xwing.vy += uy * (C.PLANET_PULL * dt)

        ts = display.TIME_SCALE
        sx = -xwing.vx * ts; sy = -xwing.vy * ts
        scroll_stars(sx, sy)
        for t in ties:         t.world_scroll(sx, sy)
        for b in bullets:      b.world_scroll(sx, sy)
        for eb in enemy_bolts: eb.world_scroll(sx, sy)
        for tp in torpedoes:   tp.world_scroll(sx, sy)
        if super_destroyer:    super_destroyer.world_scroll(sx, sy)
        if planet_active:      planet_x += sx; planet_y += sy

        now = pygame.time.get_ticks()
        eff_spawn = int(C.TIE_SPAWN_MS / max(ts, 1e-3))
        if STATE == "combat" and (now - last_spawn >= eff_spawn) and len(ties) < 10:
            last_spawn = now
            side = random.choice(["top", "bottom", "left", "right"])
            if   side == "top":    x, y = random.randint(-30, C.WIDTH + 30), -40
            elif side == "bottom": x, y = random.randint(-30, C.WIDTH + 30), C.HEIGHT + 40
            elif side == "left":   x, y = -40, random.randint(-30, C.HEIGHT + 30)
            else:                  x, y = C.WIDTH + 40, random.randint(-30, C.HEIGHT + 30)
            dx, dy = C.WIDTH / 2 - x, C.HEIGHT / 2 - y
            d  = max(1.0, math.hypot(dx, dy))
            sp = random.uniform(C.TIE_MIN_SPEED, C.TIE_MAX_SPEED)
            ties.append(TIE(x, y, dx / d * sp, dy / d * sp))

        for t in ties:
            t.update()
            if STATE == "combat": t.maybe_shoot(enemy_bolts)
        # Push TIEs out of the SSD hull so they can't pass through
        if super_destroyer:
            ssd_tri = super_destroyer.triangle_pts()
            for t in ties:
                if t.alive and point_in_triangle(t.x, t.y, *ssd_tri):
                    t.vx = -t.vx; t.vy = -t.vy
                    dout = max(1.0, math.hypot(t.x - super_destroyer.x, t.y - super_destroyer.y))
                    t.x += (t.x - super_destroyer.x) / dout * 8
                    t.y += (t.y - super_destroyer.y) / dout * 8
        for b  in bullets:     b.update()
        for eb in enemy_bolts: eb.update()
        for tp in torpedoes:
            if tp.update():  # returns True when it kills a TIE
                xwing.kills += 1
        torpedoes = [tp for tp in torpedoes if tp.alive]
        if super_destroyer and STATE == "combat": super_destroyer.update()
        if super_destroyer and STATE == "combat": super_destroyer.shoot_all(enemy_bolts)

        for b in bullets:
            if not b.alive or not b.friendly: continue
            r = pygame.Rect(int(b.x - 3), int(b.y - 3), 6, 6)
            for t in ties:
                if t.alive and r.colliderect(t.rect()):
                    t.alive = False; b.alive = False; xwing.kills += 1; break
        if super_destroyer: super_destroyer.check_bullet_hits(bullets)

        xr = xwing.rect()
        for t in ties:
            if t.alive and xr.colliderect(t.rect()):
                display.fade_to_black()
                return "space_dead"

        ties        = [t for t in ties        if t.alive]
        bullets     = [b for b in bullets     if b.alive]
        enemy_bolts = [e for e in enemy_bolts if e.alive]

        # Spawn Super Star Destroyer after first kill
        if super_destroyer is None and xwing.kills >= C.KILLS_TO_SPAWN_DESTROYER:
            _side = random.choice(["top", "bottom", "left", "right"])
            if   _side == "top":    _sx0, _sy0 = random.randint(220, C.WIDTH - 220), -750
            elif _side == "bottom": _sx0, _sy0 = random.randint(220, C.WIDTH - 220), C.HEIGHT + 750
            elif _side == "left":   _sx0, _sy0 = -750, random.randint(220, C.HEIGHT - 220)
            else:                   _sx0, _sy0 = C.WIDTH + 750, random.randint(220, C.HEIGHT - 220)
            super_destroyer = SuperStarDestroyer(_sx0, _sy0)

        if STATE == "combat":
            for eb in enemy_bolts:
                if xr.collidepoint(int(eb.x), int(eb.y)):
                    eb.alive = False; xwing.take_hit()

        if STATE == "combat" and super_destroyer:
            ssd_tri = super_destroyer.triangle_pts()
            cx, cy  = C.WIDTH / 2, C.HEIGHT / 2
            in_ssd  = point_in_triangle(cx, cy, *ssd_tri)
            hx, hy, hw, hh = super_destroyer.hangar_rect()
            all_turrets_dead = super_destroyer.turrets_remaining() == 0
            in_hangar = (hx <= cx <= hx + hw and hy <= cy <= hy + hh)
            if in_ssd and not (in_hangar and all_turrets_dead):
                display.fade_to_black(); return "space_dead"
            if in_hangar and all_turrets_dead:
                display.fade_to_black(); return "landed_destroyer"

        if STATE == "combat" and xwing.shutdown:
            STATE = "falling"
            planet_active = True
            planet_x, planet_y = C.WIDTH / 2, C.HEIGHT / 2 + C.PLANET_EDGE_OFFSET

        if STATE == "falling":
            cx, cy = C.WIDTH / 2, C.HEIGHT / 2
            dist = math.hypot(planet_x - cx, planet_y - cy)
            if dist <= C.PLANET_RADIUS + C.ATMOSPHERE_PAD:
                display.fade_to_black()
                return "planet_touch"

        display.screen.fill((5, 7, 15))
        draw_stars(display.screen)
        if planet_active:
            draw_planet(display.screen, planet_x, planet_y)
            draw_planet_arrow(display.screen, planet_x, planet_y)
        if super_destroyer: super_destroyer.draw(display.screen)
        for t  in ties:        t.draw(display.screen)
        for eb in enemy_bolts: eb.draw(display.screen)
        for b  in bullets:     b.draw(display.screen)
        for tp in torpedoes:   tp.draw(display.screen)
        xwing.draw(display.screen)

        hud = (f"Turn ←/→  Thrust ↑  Shoot SPACE  Torpedo T [{torpedo_count}]  Free Torpedo V  (fly into green hangar to land)"
               if STATE == "combat"
               else "Systems failing... small control (←/→ rotate, ↑ thrust). Falling to planet...")
        display.screen.blit(display.FONT.render(hud, True, C.WHITE),
                            (C.WIDTH // 2 - 310, C.HEIGHT - 30))
        ssd_info = (f"   SSD Turrets: {super_destroyer.turrets_remaining()}/5"
                    if super_destroyer else "   SSD: incoming after 1 kill")
        display.screen.blit(display.FONT.render(
            f"Kills: {xwing.kills}   Hits: {xwing.hits}/{C.SHUTDOWN_HITS}{ssd_info}",
            True, C.WHITE), (10, 10))
        pygame.display.flip()
