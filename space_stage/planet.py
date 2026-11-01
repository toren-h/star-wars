"""Planet rendering and the off-screen direction arrow."""
import pygame, math
import constants as C

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
