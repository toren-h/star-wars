"""Game entities for the space stage: the X-Wing, bullets/torpedoes,
TIE fighters and the (Super) Star Destroyer."""
import pygame, math, random
import constants as C
import display

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
        if keys[pygame.K_DOWN]:
            self.vx *= C.BRAKE_DRAG ** ts
            self.vy *= C.BRAKE_DRAG ** ts
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
