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
        ux, uy = dx / d, dy / d
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


# ---- Stage ----
def space_stage():
    """Returns 'landed_destroyer', 'planet_touch', or 'space_dead'."""
    xwing       = XWing()
    bullets     = []; enemy_bolts = []; ties = []
    last_spawn  = pygame.time.get_ticks()
    destroyer   = None
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
                if e.key == pygame.K_c:     display.toggle_slow()
                if e.key == pygame.K_SPACE: xwing.shoot(bullets)

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
        for t in ties:        t.world_scroll(sx, sy)
        for b in bullets:     b.world_scroll(sx, sy)
        for eb in enemy_bolts: eb.world_scroll(sx, sy)
        if destroyer:          destroyer.world_scroll(sx, sy)
        if planet_active:      planet_x += sx; planet_y += sy

        now = pygame.time.get_ticks()
        eff_spawn = int(C.TIE_SPAWN_MS / max(ts, 1e-3))
        if STATE == "combat" and (now - last_spawn >= eff_spawn) and (destroyer is None or len(ties) < 12):
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
        for b  in bullets:     b.update()
        for eb in enemy_bolts: eb.update()
        if destroyer: destroyer.update()

        for b in bullets:
            if not b.alive or not b.friendly: continue
            r = pygame.Rect(int(b.x - 3), int(b.y - 3), 6, 6)
            for t in ties:
                if t.alive and r.colliderect(t.rect()):
                    t.alive = False; b.alive = False; xwing.kills += 1; break

        xr = xwing.rect()
        for t in ties:
            if t.alive and xr.colliderect(t.rect()):
                display.fade_to_black()
                return "space_dead"

        ties        = [t for t in ties        if t.alive]
        bullets     = [b for b in bullets     if b.alive]
        enemy_bolts = [e for e in enemy_bolts if e.alive]

        if destroyer is None and xwing.kills >= C.KILLS_TO_SPAWN_DESTROYER:
            side = random.choice(["top", "bottom", "left", "right"])
            if   side == "top":    sx0, sy0 = random.randint(140, C.WIDTH - 140), -400;          v = (0,    0.6)
            elif side == "bottom": sx0, sy0 = random.randint(140, C.WIDTH - 140), C.HEIGHT + 400; v = (0,   -0.6)
            elif side == "left":   sx0, sy0 = -400, random.randint(160, C.HEIGHT - 160);          v = (0.6,  0)
            else:                  sx0, sy0 = C.WIDTH + 400, random.randint(160, C.HEIGHT - 160); v = (-0.6, 0)
            destroyer = StarDestroyer(sx0, sy0, v)

        if STATE == "combat":
            for eb in enemy_bolts:
                if xr.collidepoint(int(eb.x), int(eb.y)):
                    eb.alive = False; xwing.take_hit()

        if destroyer:
            tri = destroyer.triangle_pts()
            cx, cy = C.WIDTH / 2, C.HEIGHT / 2
            in_tri    = point_in_triangle(cx, cy, *tri)
            hx, hy, hw, hh = destroyer.hangar_rect()
            in_hangar = (hx <= cx <= hx + hw and hy <= cy <= hy + hh)
            if STATE == "combat" and in_tri and not in_hangar:
                display.fade_to_black(); return "space_dead"
            if STATE == "combat" and in_hangar:
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
        for t  in ties:        t.draw(display.screen)
        for eb in enemy_bolts: eb.draw(display.screen)
        for b  in bullets:     b.draw(display.screen)
        if destroyer: destroyer.draw(display.screen)
        xwing.draw(display.screen)

        hud = ("Turn ←/→  Thrust ↑  Shoot SPACE  Slow-Mo C  (Find Star Destroyer to land)"
               if STATE == "combat"
               else "Systems failing... small control (←/→ rotate, ↑ thrust). Falling to planet...")
        display.screen.blit(display.FONT.render(hud, True, C.WHITE),
                            (C.WIDTH // 2 - 260, C.HEIGHT - 30))
        display.screen.blit(display.FONT.render(
            f"Kills: {xwing.kills}/{C.KILLS_TO_SPAWN_DESTROYER}   Hits: {xwing.hits}/{C.SHUTDOWN_HITS}",
            True, C.WHITE), (10, 10))
        pygame.display.flip()
