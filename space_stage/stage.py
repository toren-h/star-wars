"""Main space stage game loop."""
import pygame, sys, math, random
import constants as C
import display

from .stars import init_stars, scroll_stars, draw_stars
from .planet import draw_planet, draw_planet_arrow, point_in_triangle
from .entities import (
    XWing, SpaceBullet, Torpedo, TIE, StarDestroyer, SSDTurret, SuperStarDestroyer,
)

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

        hud = (f"Turn ←/→  Thrust ↑  Shoot SPACE  Torpedo T [{torpedo_count}]  (fly into green hangar to land)"
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
