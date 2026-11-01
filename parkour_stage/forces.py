"""Jedi force-push / force-pull mechanics."""
import constants as C

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

def force_push(player, bolts, turrets, siths, ROWS, COLS, get_tile, set_tile):
    px, py = player.rect.centerx, player.rect.centery
    for b in bolts:
        if b.alive and _within_force_line(px, py, b.x, b.y):
            d = 1 if b.x > px else -1
            b.vx = d * max(abs(b.vx), C.FORCE_BOLT_IMPULSE); b.friendly = True
    for t in turrets:
        cx, cy = t.center()
        if _within_force_line(px, py, cx, cy) and not t.falling:
            if 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                set_tile(t.r, t.c, '.')
            t.push_vx = (1 if cx > px else -1) * C.FORCE_TURRET_STEPS * C.TILE / 12.0
    for s in siths:
        cx, cy = s.rect.centerx, s.rect.centery
        if _within_force_line(px, py, cx, cy):
            s.push_vx = (1 if cx > px else -1) * 14.0

def force_pull(player, bolts, turrets, siths, ROWS, COLS, get_tile, set_tile):
    px, py = player.rect.centerx, player.rect.centery
    for b in bolts:
        if b.alive and _within_force_line(px, py, b.x, b.y):
            d = -1 if b.x > px else 1
            b.vx = d * max(abs(b.vx), C.FORCE_BOLT_IMPULSE); b.friendly = True
    for t in turrets:
        cx, cy = t.center()
        if _within_force_line(px, py, cx, cy) and not t.falling:
            if 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                set_tile(t.r, t.c, '.')
            t.push_vx = (-1 if cx > px else 1) * C.FORCE_TURRET_STEPS * C.TILE / 12.0
    for s in siths:
        cx, cy = s.rect.centerx, s.rect.centery
        if _within_force_line(px, py, cx, cy):
            s.push_vx = (-1 if cx > px else 1) * 14.0
