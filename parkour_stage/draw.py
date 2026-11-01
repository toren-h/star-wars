"""Drawing helpers for the parkour stage (level, entities, player)."""
import pygame, math
import constants as C
import display

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
                pygame.draw.circle(display.screen, (255, 215, 60), (x + C.TILE // 2, y + C.TILE // 2), C.TILE // 2 - 6)
                pygame.draw.circle(display.screen, (200, 160, 20), (x + C.TILE // 2, y + C.TILE // 2), C.TILE // 2 - 6, 2)
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
        if b.wide:
            # Wide taser beam: 2-tile-tall glowing bar
            bsx = int(b.x - camx)
            bsy = int(b.y - camy)
            speed = max(1.0, math.hypot(b.vx, b.vy))
            norm_x, norm_y = b.vx / speed, b.vy / speed
            pygame.draw.line(display.screen, (80, 255, 180),
                             (bsx - int(norm_y * C.TILE), bsy + int(norm_x * C.TILE)),
                             (bsx + int(norm_y * C.TILE), bsy - int(norm_x * C.TILE)), 6)
            pygame.draw.line(display.screen, (200, 255, 240),
                             (bsx - int(norm_y * C.TILE), bsy + int(norm_x * C.TILE)),
                             (bsx + int(norm_y * C.TILE), bsy - int(norm_x * C.TILE)), 2)
        else:
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
