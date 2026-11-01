"""Main parkour stage game loop."""
import pygame, sys, math, random
import constants as C
import display

from .levels import OLD_LEVEL, NEW_LEVEL
from .geometry import (
    rect_for_tile, bfs_tile_path, normalize_and_floor, scan_entities, tiles_at,
    point_seg_dist_sq, seg_intersect, seg_intersect_point, _saber_clip_at_zone,
    seg_intersects_rect, _make_lightning, SCOPE_RANGE_TILES,
    raycast_wall_distance, has_line_of_sight,
)
from .forces import _within_force_line, _slide_turret_horiz, force_push, force_pull
from .state import _request_restart_flag, _death_pending_flag
from .entities import SithLord, Player, Turret, Grenade, LavaFlow, Bolt, GunPickup
from .draw import (
    draw_level, draw_falling_turrets, draw_bolts, draw_player, center_camera_on_player,
)
from .screens import color_picker, character_select, shop_screen, hub_screen, GUN_NAMES

# ---- Stage ----
def parkour_stage(which_map="old", bg_color=None, fog_color=None, trooper_gun='dual'):
    character        = character_select()
    # Trooper's gun is chosen once on the home screen and can't be changed
    # mid-level; Mandalorian always carries a plain, no-frills blaster.
    gun_type         = (trooper_gun if character == 'trooper' else
                         'blaster' if character == 'mandalorian' else None)
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
    _max_jumps  = 1 if character in ('trooper', 'mandalorian') else 2
    _max_health = (C.MANDALORIAN_MAX_HEALTH if character == 'mandalorian' else
                   C.MAX_HEALTH if character == 'trooper' else None)
    player  = Player(*START_POS, max_jumps=_max_jumps, max_health=_max_health)
    _fall_peak_y    = float(player.rect.y)  # tracks the highest point reached since last landing
    _was_on_ground  = player.on_ground
    camx = camy = 0.0
    saber_len       = float(C.SABER_LEN)
    saber_target    = float(C.SABER_LEN)
    saber_active    = True
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
    jetpack_float_accum  = 0.0
    nuke_state           = None  # None | ('fuse', start_ms, x, y) | ('blast', start_ms, sparks)
    player_hp            = 3
    player_flash_until   = 0
    red_seq              = []   # tracks progress through R-E-D combo
    gun_count           = 0
    active_weapon       = 'saber'
    last_gun_shot       = 0
    gun_pickups         = []
    GUN_COOLDOWN        = 500
    def _cooldown_for(gt):
        # 'dual' is intentionally very fast (rapid bang-bang-bang, every 4th
        # shot followed by a brief rest); 'sniper' fires its two-shot volley
        # with no gap between the two bolts, then rests before the next one;
        # 'shotgun' is a slower pump between 5-pellet blasts.
        return {'dual': 140, 'shotgun': 700, 'blaster': 350, 'dualblaster': 380,
                'sniper': 900, 'raygun': 500, 'penetrator': 650}.get(gt, GUN_COOLDOWN)
    grenade_count       = 3
    force_spark         = 100.0
    FORCE_SPARK_MAX     = 100.0
    FORCE_SPARK_COST    = 10.0   # drained per tick
    FORCE_SPARK_REGEN   = 15.0   # per second while not held
    FORCE_TICK_MS       = 150    # ms between each 1-tile push/pull
    force_tick_acc      = 0.0
    JETPACK_FUEL_MAX = 300.0
    FLAME_DRAIN      = 55.0   # fuel per second while firing
    FLAME_SPAWN      = 6      # particles per frame while firing
    GRAPPLE_SPEED    = 14.0
    GRAPPLE_PULL     = 0.7
    jetpack_fuel     = JETPACK_FUEL_MAX
    grapple          = None  # None or {'x','y','vx','vy','attached'}
    flame_particles  = []   # list of {'x','y','vx','vy','life','max_life','col'}
    bg_color         = bg_color if bg_color is not None else C.GREEN
    fog_color        = fog_color if fog_color is not None else (0, 0, 0)
    taser_mode       = False
    coins            = 0      # persists across in-stage deaths/restarts
    _l_coin_acc      = 0.0    # fractional-second accumulator for the L-key coin cheat
    whistling_birds  = []     # list of {'x','y','vx','vy','target','life'}
    _last_birds_t    = -999999  # cooldown timestamp for Whistling Birds
    # 'kind' is 'manual' (self-destruct, A/D steered, pilot view) or
    # 'homing' (auto-aims, but only while it has line of sight on a target)
    # — only one rocket (of either kind) is ever in flight at a time.
    rockets          = []     # list of {'x','y','vx','vy','kind','born'}
    _last_rocket_t   = -999999  # cooldown timestamp for Rocket Rounds
    # Everything here must survive an in-stage death/restart (Player and most
    # locals get recreated/reset by restart_run, so this dict is the one
    # source of truth shop_screen/hub_screen mutate in place).
    progress = {
        'sword_bought':     False,
        'bonus_hits':       0,
        'bonus_max_health': 0,
        'jetpack_bought':   False,
        'barrier_bought':   False,
        'bird_ammo':          0,
        'rocket_ammo_manual': 0,   # self-destruct, A/D-steered rocket
        'rocket_ammo_homing': 0,   # auto-aims, but only with line of sight
        # Trooper picked this one gun on the home screen and is stuck with
        # it for the whole level — no shop purchases, no switching.
        'owned_guns':       [gun_type] if gun_type else [],
        'gun_count':        1 if character in ('trooper', 'mandalorian') else 0,
    }
    _gun_cooldown      = _cooldown_for(gun_type)
    # Double gun fires fast, but every 4th shot is followed by a brief,
    # silent rest (no HUD countdown) before the next one.
    _dual_burst_count  = 0
    _dual_rest_until   = 0
    sniper_scoping   = False  # True when Z held with sniper rifle
    _scope_dist      = 0.0   # how far along the laser the scope has drifted (px)
    if character in ('trooper', 'mandalorian'):
        gun_count     = 1
        active_weapon = 'gun'
        saber_len     = 0.0
        saber_target  = 0.0
    if character == 'trooper':
        grenade_count = 5
    _request_restart_flag[0] = False
    _death_pending_flag[0]   = False

    def restart_run():
        nonlocal level_grid, turrets, bolts, player, camx, camy, siths, saber_len, saber_target, saber_active, saber_color, saber_switching, lightnings, grenades, lava_flows, explosions, crumbling_effects, grenade_charge_start, last_lightning_t, float_accum, jetpack_float_accum, nuke_state, player_hp, player_flash_until, gun_count, active_weapon, last_gun_shot, gun_pickups, grenade_count, force_spark, force_tick_acc, jetpack_fuel, grapple, flame_particles, taser_mode, _dual_burst_count, _dual_rest_until, sniper_scoping, _scope_dist, _fall_peak_y, _was_on_ground, whistling_birds, _last_birds_t, rockets, _last_rocket_t
        level_grid = [list(row) for row in LEVEL]
        START, GOAL, sp, sps = scan_entities(level_grid, ROWS, COLS)
        siths = [SithLord(c * C.TILE, r * C.TILE) for (r, c) in sps]
        sr2, sc2 = START[1] // C.TILE, START[0] // C.TILE
        if get_tile(sr2, sc2) == 'P': set_tile(sr2, sc2, '.')
        deaths = player.deaths + (1 if _death_pending_flag[0] else 0)
        _restart_max_health = (_max_health + progress['bonus_max_health']) if _max_health is not None else None
        player = Player(*START, max_jumps=_max_jumps, max_health=_restart_max_health); player.deaths = deaths
        _fall_peak_y = float(player.rect.y); _was_on_ground = player.on_ground
        turrets = [Turret(r, c) for (r, c) in sp]; bolts = []
        camx = camy = 0.0
        saber_len = saber_target = float(C.SABER_LEN); saber_active = True
        saber_color = C.CYAN  # never start a life already in red/Sith mode, even if it was bought
        saber_switching = False
        lightnings = []; grenades = []; lava_flows = []; explosions = []; crumbling_effects = []; grenade_charge_start = None; last_lightning_t = 0; float_accum = 0.0; jetpack_float_accum = 0.0; nuke_state = None
        player_hp = 3 + progress['bonus_hits']; player_flash_until = 0; red_seq.clear()
        gun_count = 0; active_weapon = 'saber'; last_gun_shot = 0; gun_pickups = []; grenade_count = 3; force_spark = FORCE_SPARK_MAX; force_tick_acc = 0.0
        jetpack_fuel = JETPACK_FUEL_MAX; grapple = None; flame_particles = []; whistling_birds = []; _last_birds_t = -999999
        rockets = []; _last_rocket_t = -999999
        taser_mode = False; _dual_burst_count = 0; _dual_rest_until = 0
        sniper_scoping = False; _scope_dist = 0.0
        if character in ('trooper', 'mandalorian'):
            gun_count = 1; active_weapon = 'gun'; saber_len = 0.0; saber_target = 0.0
        if progress['owned_guns']:
            gun_count = max(gun_count, progress['gun_count'])  # keep shop-bought guns usable via [3]
        if character == 'trooper':
            grenade_count = 5
        _request_restart_flag[0] = False; _death_pending_flag[0] = False
        return START, GOAL

    while True:
        dt = display.clock.tick(60)

        if _request_restart_flag[0]:
            START_POS, GOAL_POS = restart_run()

        _prev_sith_n = len(siths)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_w, pygame.K_UP): player.jump()
                if e.key == pygame.K_e and character == 'jedi':
                    saber_active = not saber_active
                if e.key == pygame.K_x and character == 'jedi':
                    force_push(player, bolts, turrets, siths, ROWS, COLS, get_tile, set_tile)
                if e.key == pygame.K_v and character == 'jedi':
                    force_pull(player, bolts, turrets, siths, ROWS, COLS, get_tile, set_tile)
                # R-E-D sequence activates color switch (Jedi only)
                if character == 'jedi':
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
                if e.key == pygame.K_i:
                    mx, my = pygame.mouse.get_pos()
                    lava_flows.append(LavaFlow(int(my + camy) // C.TILE,
                                               int(mx + camx) // C.TILE))
                    coins += 100  # cheat: free coins + jump straight to the home screen
                    coins, gun_type, saber_color, player_hp = hub_screen(
                        coins, character, gun_type, saber_color, player, player_hp, progress)
                    _gun_cooldown = _cooldown_for(gun_type)
                    START_POS, GOAL_POS = restart_run()
                if e.key == pygame.K_k:
                    siths.clear()  # cheat: instantly clear all Sith Lords
                if e.key == pygame.K_m:
                    coins += 1000000  # cheat: a million coins
                if e.key == pygame.K_q and character == 'mandalorian':
                    if grapple is not None:
                        grapple = None
                    else:
                        mx, my = pygame.mouse.get_pos()
                        _pcx, _pcy = float(player.rect.centerx), float(player.rect.centery)
                        _tx, _ty = float(mx) + camx, float(my) + camy
                        _dx, _dy = _tx - _pcx, _ty - _pcy
                        _d = max(1.0, math.hypot(_dx, _dy))
                        grapple = {'x': _pcx, 'y': _pcy,
                                   'vx': _dx / _d * GRAPPLE_SPEED,
                                   'vy': _dy / _d * GRAPPLE_SPEED,
                                   'attached': False}
                if e.key == pygame.K_p:
                    for gp in gun_pickups[:]:
                        if gp.rect.colliderect(player.rect):
                            gun_count += 1
                            gun_pickups.remove(gp)
                            break
                    for g in grenades[:]:
                        pickup_rect = pygame.Rect(int(g.x) - 16, int(g.y) - 16, 32, 32)
                        if pickup_rect.colliderect(player.rect):
                            grenades.remove(g)
                            grenade_count += 1
                            if active_weapon != 'grenade':
                                active_weapon = 'grenade'
                            break
                if e.key == pygame.K_1 and character == 'jedi':
                    active_weapon = 'saber'
                    grenade_charge_start = None
                if e.key == pygame.K_2 and grenade_count > 0:
                    active_weapon = 'grenade'
                    grenade_charge_start = None; grapple = None
                if e.key == pygame.K_3 and gun_count >= 1:
                    if active_weapon == 'gun' and len(progress['owned_guns']) > 1:
                        _gi = progress['owned_guns'].index(gun_type) if gun_type in progress['owned_guns'] else -1
                        gun_type = progress['owned_guns'][(_gi + 1) % len(progress['owned_guns'])]
                        _gun_cooldown = _cooldown_for(gun_type)
                    active_weapon = 'gun'
                    grenade_charge_start = None; grapple = None
                if e.key == pygame.K_4 and character == 'trooper':
                    active_weapon = 'grapple'
                    grenade_charge_start = None
                if (e.key == pygame.K_b and character == 'mandalorian' and progress['bird_ammo'] > 0
                        and pygame.time.get_ticks() - _last_birds_t >= C.BIRDS_COOLDOWN_MS):
                    _bpcx, _bpcy = float(player.rect.centerx), float(player.rect.centery)
                    _targets = list(turrets) + list(siths)
                    if _targets:
                        # auto-aim: home in on whichever enemy is currently nearest
                        _btarget = min(_targets, key=lambda en: math.hypot(
                            en.rect.centerx - _bpcx, en.rect.centery - _bpcy))
                        _last_birds_t = pygame.time.get_ticks()
                        progress['bird_ammo'] -= 1
                        _bsr, _bsc = int(_bpcy) // C.TILE, int(_bpcx) // C.TILE
                        _bgr, _bgc = _btarget.rect.centery // C.TILE, _btarget.rect.centerx // C.TILE
                        _btiles = bfs_tile_path(_bsr, _bsc, _bgr, _bgc, ROWS, COLS, get_tile)
                        _bpath = [(c * C.TILE + C.TILE // 2, r * C.TILE + C.TILE // 2)
                                  for (r, c) in _btiles] if _btiles else []
                        _bang = math.atan2(_btarget.rect.centery - _bpcy, _btarget.rect.centerx - _bpcx)
                        whistling_birds.append({
                            'x': _bpcx, 'y': _bpcy,
                            'vx': math.cos(_bang) * 3.0, 'vy': math.sin(_bang) * 3.0,
                            'target': _btarget, 'life': C.BIRDS_LIFE_FRAMES,
                            'path': _bpath, 'path_idx': 0,
                        })
                # N = self-destruct rocket: manually steered with A/D the whole
                # flight, freezes the character (normal third-person view —
                # you're watching it fly, not seeing through it), and it
                # self-destructs after 20s in the air if it hits nothing.
                if (e.key == pygame.K_n and character == 'mandalorian' and progress['rocket_ammo_manual'] > 0
                        and not rockets
                        and pygame.time.get_ticks() - _last_rocket_t >= C.ROCKET_COOLDOWN_MS):
                    _last_rocket_t = pygame.time.get_ticks()
                    progress['rocket_ammo_manual'] -= 1
                    _rpcx, _rpcy = float(player.rect.centerx), float(player.rect.centery)
                    _rang = 0.0 if player.face_dir > 0 else math.pi
                    rockets.append({
                        'x': _rpcx, 'y': _rpcy, 'kind': 'manual',
                        'vx': math.cos(_rang) * C.ROCKET_SPEED, 'vy': math.sin(_rang) * C.ROCKET_SPEED,
                        'born': pygame.time.get_ticks(),
                    })
                # H = homing rocket: auto-aims at the nearest enemy, but only
                # while it has a clear line of sight to it (otherwise it just
                # flies straight until it does, or expires). Freezes the
                # character and the camera rides with the rocket — you see
                # out of it while it's in flight.
                if (e.key == pygame.K_h and character == 'mandalorian' and progress['rocket_ammo_homing'] > 0
                        and not rockets
                        and pygame.time.get_ticks() - _last_rocket_t >= C.ROCKET_COOLDOWN_MS):
                    _last_rocket_t = pygame.time.get_ticks()
                    progress['rocket_ammo_homing'] -= 1
                    _rpcx, _rpcy = float(player.rect.centerx), float(player.rect.centery)
                    _rtargets = list(turrets) + list(siths)
                    if _rtargets:
                        _rt = min(_rtargets, key=lambda en: math.hypot(
                            en.rect.centerx - _rpcx, en.rect.centery - _rpcy))
                        _rang = math.atan2(_rt.rect.centery - _rpcy, _rt.rect.centerx - _rpcx)
                    else:
                        _rang = 0.0 if player.face_dir > 0 else math.pi
                    rockets.append({
                        'x': _rpcx, 'y': _rpcy, 'kind': 'homing',
                        'vx': math.cos(_rang) * C.ROCKET_SPEED, 'vy': math.sin(_rang) * C.ROCKET_SPEED,
                        'life': C.ROCKET_LIFE_FRAMES,
                    })
                if e.key == pygame.K_s and character == 'trooper' and gun_type in ('dualblaster', 'raygun', 'penetrator'):
                    taser_mode = not taser_mode
                if e.key == pygame.K_z and gun_type in SCOPE_RANGE_TILES:
                    sniper_scoping = True
                if e.key == pygame.K_BACKSPACE:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = False
                if e.key == pygame.K_ESCAPE:
                    bg_color, fog_color, _quit = color_picker(bg_color, fog_color)
                    if _quit: pygame.quit(); sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and active_weapon == 'grapple' and character == 'trooper':
                    if grapple is not None:
                        grapple = None
                    else:
                        mx, my = pygame.mouse.get_pos()
                        _pcx, _pcy = float(player.rect.centerx), float(player.rect.centery)
                        _tx, _ty = float(mx) + camx, float(my) + camy
                        _dx, _dy = _tx - _pcx, _ty - _pcy
                        _d = max(1.0, math.hypot(_dx, _dy))
                        grapple = {'x': _pcx, 'y': _pcy,
                                   'vx': _dx / _d * GRAPPLE_SPEED,
                                   'vy': _dy / _d * GRAPPLE_SPEED,
                                   'attached': False}
                if e.button == 1 and active_weapon == 'grenade' and grenade_count > 0 and grenade_charge_start is None:
                    grenade_charge_start = pygame.time.get_ticks()
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1 and active_weapon == 'grenade' and grenade_charge_start is not None:
                    hold_ms = pygame.time.get_ticks() - grenade_charge_start
                    speed = 4.0 + 16.0 * min(hold_ms / 1500.0, 1.0)
                    mx, my = pygame.mouse.get_pos()
                    tx, ty = mx + camx, my + camy
                    pcx, pcy = float(player.rect.centerx), float(player.rect.centery)
                    dx, dy = tx - pcx, ty - pcy
                    d = max(1.0, math.hypot(dx, dy))
                    grenades.append(Grenade(pcx, pcy, dx / d * speed, dy / d * speed))
                    grenade_charge_start = None
                    grenade_count -= 1
                    if grenade_count <= 0:
                        active_weapon = 'saber' if character == 'jedi' else 'gun'
            elif e.type == pygame.KEYUP:
                if e.key == pygame.K_z:
                    sniper_scoping = False
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
        # While any rocket is in flight, the character doesn't move at all —
        # for the self-destruct one you're busy steering it with A/D anyway,
        # and for the homing one the camera itself is off watching it fly.
        _piloting_rocket = bool(rockets)
        # Flamethrower and jetpack are two separate things now: Mandalorian
        # always has the flamethrower (Space) for free; the purchasable
        # jetpack (E) is real, unlimited vertical flight, for whoever buys
        # it (not Jedi — E is already their R-E-D saber-unlock key).
        _has_flamethrower = character == 'mandalorian'
        _has_jetpack = progress['jetpack_bought'] and character != 'jedi'
        _pushing = keys[pygame.K_x] and force_spark > 0 and character == 'jedi'
        _pulling = keys[pygame.K_v] and force_spark > 0 and character == 'jedi'
        _force_held = _pushing or _pulling
        if _force_held:
            force_spark = max(0.0, force_spark - 30.0 * dt / 1000.0)
            force_tick_acc += dt
            while force_tick_acc >= FORCE_TICK_MS and force_spark > 0:
                force_tick_acc -= FORCE_TICK_MS
                _fpx, _fpy = player.rect.centerx, player.rect.centery
                for s in siths:
                    if _within_force_line(_fpx, _fpy, s.rect.centerx, s.rect.centery):
                        _d = (1 if s.rect.centerx > _fpx else -1) if _pushing else (-1 if s.rect.centerx > _fpx else 1)
                        s.rect.x += _d * C.TILE
                for t in turrets:
                    if not t.falling and _within_force_line(_fpx, _fpy, t.rect.centerx, t.rect.centery):
                        _d = (1 if t.rect.centerx > _fpx else -1) if _pushing else (-1 if t.rect.centerx > _fpx else 1)
                        _slide_turret_horiz(t, _d, 1, ROWS, COLS, get_tile, set_tile)
                for b in bolts:
                    if b.alive and _within_force_line(_fpx, _fpy, b.x, b.y):
                        _d = (1 if b.x > _fpx else -1) if _pushing else (-1 if b.x > _fpx else 1)
                        b.vx = _d * max(abs(b.vx), C.FORCE_BOLT_IMPULSE); b.friendly = True
        else:
            force_tick_acc = 0.0
            force_spark = min(FORCE_SPARK_MAX, force_spark + FORCE_SPARK_REGEN * dt / 1000.0)
        floating_now = keys[pygame.K_f] and saber_color == C.RED and character == 'jedi'
        if not floating_now:
            float_accum = 0.0
        else:
            # pre-cancel gravity so player.update() produces zero net downward movement
            player.vy = -C.GRAVITY * ts
        # Jetpack (E): real vertical flight, unlimited — no fuel cost at all.
        jetpack_flying = _has_jetpack and keys[pygame.K_e]
        if not jetpack_flying:
            jetpack_float_accum = 0.0
        else:
            player.vy = -C.GRAVITY * ts  # pre-cancel gravity, same trick as the Jedi float
        if _has_flamethrower and keys[pygame.K_SPACE] and jetpack_fuel > 0:
            jetpack_fuel = max(0.0, jetpack_fuel - FLAME_DRAIN * dt / 1000.0)
            _fmx, _fmy = pygame.mouse.get_pos()
            _fpcx = float(player.rect.centerx); _fpcy = float(player.rect.centery)
            _fdx = (_fmx + camx) - _fpcx; _fdy = (_fmy + camy) - _fpcy
            _fd = max(1.0, math.hypot(_fdx, _fdy))
            _base_ang = math.atan2(_fdy, _fdx)
            for _ in range(FLAME_SPAWN):
                _ang = _base_ang + random.uniform(-0.32, 0.32)
                _spd = 9.0 * random.uniform(0.7, 1.3) * ts
                _col = random.choice([(255,70,0),(255,140,0),(255,200,40),(255,40,0),(255,100,10)])
                flame_particles.append({'x': _fpcx, 'y': _fpcy,
                                        'vx': math.cos(_ang)*_spd, 'vy': math.sin(_ang)*_spd,
                                        'life': 22, 'max_life': 22, 'col': _col})
        if not _piloting_rocket:
            player.update(keys, dt, ROWS, COLS, get_tile)

        if player.max_health is not None:
            if player.on_ground:
                if not _was_on_ground:
                    _fall_tiles = (player.rect.y - _fall_peak_y) / C.TILE
                    if _fall_tiles > C.FALL_SAFE_TILES:
                        player.health = max(0, player.health - int(C.FALL_DAMAGE_PER_TILE * (_fall_tiles - C.FALL_SAFE_TILES)))
                        player_flash_until = pygame.time.get_ticks() + 350
                _fall_peak_y = float(player.rect.y)
            else:
                _fall_peak_y = min(_fall_peak_y, float(player.rect.y))
            _was_on_ground = player.on_ground
            if player.health <= 0:
                _request_restart_flag[0] = True; _death_pending_flag[0] = True

        if jetpack_flying:
            jetpack_float_accum += dt * ts * (C.TILE * 1.5 / 1000.0)
            rise = int(jetpack_float_accum)
            jetpack_float_accum -= rise
            player.rect.y -= rise
            for (r, c, ch) in tiles_at(player.rect, ROWS, COLS, get_tile):
                if ch == 'X':
                    t = rect_for_tile(r, c)
                    if player.rect.colliderect(t):
                        player.rect.top = t.bottom
                        jetpack_float_accum = 0.0
                        break
            player.vy = 0

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
                    gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                    turrets.remove(t)

        if character in ('trooper', 'mandalorian') and grapple is not None:
            if not grapple['attached']:
                grapple['x'] += grapple['vx'] * ts
                grapple['y'] += grapple['vy'] * ts
                if (grapple['x'] < -C.TILE or grapple['x'] > COLS * C.TILE + C.TILE or
                        grapple['y'] < -C.TILE or grapple['y'] > ROWS * C.TILE + C.TILE):
                    grapple = None
                else:
                    _gr = int(grapple['y']) // C.TILE
                    _gc = int(grapple['x']) // C.TILE
                    if 0 <= _gr < ROWS and 0 <= _gc < COLS and get_tile(_gr, _gc) == 'X':
                        grapple['attached'] = True
            if grapple is not None and grapple['attached']:
                _gx, _gy = grapple['x'], grapple['y']
                _pcx, _pcy = float(player.rect.centerx), float(player.rect.centery)
                _dx, _dy = _gx - _pcx, _gy - _pcy
                _dist = math.hypot(_dx, _dy)
                if _dist < C.TILE * 0.6:
                    grapple = None
                else:
                    _pull = GRAPPLE_PULL * ts
                    player.vx += _dx / _dist * _pull
                    player.vy += _dy / _dist * _pull
                    player.vx = max(-C.MAX_XSPEED * 2.5, min(C.MAX_XSPEED * 2.5, player.vx))
                    player.vy = max(-22.0, min(22.0, player.vy))

        if flame_particles:
            new_flames = []
            for _fp in flame_particles:
                _fp['x'] += _fp['vx']
                _fp['y'] += _fp['vy']
                _fp['vy'] += C.GRAVITY * 0.18 * ts
                _fp['life'] -= 1
                if _fp['life'] <= 0:
                    continue
                _fr = int(_fp['y']) // C.TILE; _fc = int(_fp['x']) // C.TILE
                if 0 <= _fr < ROWS and 0 <= _fc < COLS and get_tile(_fr, _fc) == 'X':
                    continue
                _fpr = pygame.Rect(int(_fp['x'])-3, int(_fp['y'])-3, 6, 6)
                _fhit = False
                for s in siths[:]:
                    if s.rect.colliderect(_fpr):
                        if s.take_hit(): siths.remove(s)
                        _fhit = True; break
                if not _fhit:
                    for t in turrets[:]:
                        if t.rect.colliderect(_fpr):
                            if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                                set_tile(t.r, t.c, '.')
                            gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                            turrets.remove(t); _fhit = True; break
                if not _fhit:
                    new_flames.append(_fp)
            flame_particles = new_flames

        if whistling_birds:
            new_birds = []
            for bd in whistling_birds:
                bd['life'] -= 1
                _target = bd['target']
                _target_alive = _target is not None and (_target in turrets or _target in siths)
                # Auto-aims straight at the target whenever it currently has
                # a clear line of sight to it; otherwise it keeps following
                # the path it worked out at launch (so it still finds its
                # way around corners instead of just flying dumbly straight).
                _bird_los = _target_alive and has_line_of_sight(
                    bd['x'], bd['y'], _target.rect.centerx, _target.rect.centery, ROWS, COLS, get_tile)
                if _bird_los:
                    _aim_x, _aim_y = _target.rect.centerx, _target.rect.centery
                else:
                    _path = bd['path']; _pidx = bd['path_idx']
                    _aim_x = _aim_y = None
                    while _pidx < len(_path):
                        _wx, _wy = _path[_pidx]
                        if math.hypot(_wx - bd['x'], _wy - bd['y']) <= C.TILE * 0.6:
                            _pidx += 1
                            continue
                        _aim_x, _aim_y = _wx, _wy
                        break
                    bd['path_idx'] = _pidx
                    if _aim_x is None and _target_alive:
                        _aim_x, _aim_y = _target.rect.centerx, _target.rect.centery
                if _aim_x is not None:
                    _dx = _aim_x - bd['x']; _dy = _aim_y - bd['y']
                    _dd = max(1.0, math.hypot(_dx, _dy))
                    _ux, _uy = _dx / _dd, _dy / _dd
                    bd['vx'] += (_ux * C.BIRDS_SPEED - bd['vx']) * C.BIRDS_TURN_RATE
                    bd['vy'] += (_uy * C.BIRDS_SPEED - bd['vy']) * C.BIRDS_TURN_RATE
                bd['x'] += bd['vx'] * ts; bd['y'] += bd['vy'] * ts
                if bd['life'] <= 0:
                    continue
                _bzr, _bzc = int(bd['y']) // C.TILE, int(bd['x']) // C.TILE
                if 0 <= _bzr < ROWS and 0 <= _bzc < COLS and get_tile(_bzr, _bzc) == 'X':
                    continue  # darts cannot pass through walls
                _brd = pygame.Rect(int(bd['x']) - 3, int(bd['y']) - 3, 6, 6)
                _bhit = False
                if _target_alive and _target.rect.colliderect(_brd):
                    if _target in siths:
                        siths.remove(_target)
                    elif _target in turrets:
                        t = _target
                        if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                            set_tile(t.r, t.c, '.')
                        gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                        turrets.remove(t)
                    _bhit = True
                if not _bhit:
                    new_birds.append(bd)
            whistling_birds = new_birds

        now_t = pygame.time.get_ticks()
        if keys[pygame.K_t] and saber_color == C.RED and character == 'jedi' and now_t - last_lightning_t >= int(80 / max(ts, 0.1)):
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
                    gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                    turrets.remove(t)

        if saber_color == C.RED and character == 'jedi':
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
        if keys[pygame.K_l]:
            _l_coin_acc += 100.0 * dt / 1000.0  # cheat: +100 coins/sec while held, any time
            _l_gain = int(_l_coin_acc)
            if _l_gain:
                coins += _l_gain
                _l_coin_acc -= _l_gain

        if character != 'jedi' or active_weapon in ('gun', 'grenade'):
            saber_target = 0.0
        elif not saber_switching:
            shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            if saber_active:
                saber_target = float(C.SABER_LEN) * (1.6 if shift_held else 1.0)
            else:
                saber_target = 0.0
        step = 2.5 * display.TIME_SCALE
        if saber_len < saber_target:
            saber_len = min(saber_len + step, saber_target)
        elif saber_len > saber_target:
            saber_len = max(saber_len - step, saber_target)
        if saber_switching and saber_len == 0.0:
            saber_color = C.RED if saber_color == C.CYAN else C.CYAN
            saber_switching = False

        mx, my   = pygame.mouse.get_pos()
        mxw, myw = mx + camx, my + camy
        pcx, pcy = player.rect.centerx, player.rect.centery
        dx, dy   = mxw - pcx, myw - pcy
        d        = max(1.0, math.hypot(dx, dy))
        ux, uy   = dx / d, dy / d
        saber_p1 = (pcx, pcy)
        saber_p2 = (pcx + ux * saber_len, pcy + uy * saber_len)

        for s in siths:
            s.update(player, ROWS, COLS, get_tile)

        # Two 8-px-thick sabers visually overlap when their centrelines are within
        # SABER_THICKNESS px of each other (4 px half-thickness each side).
        _ZONE_SQ = C.SABER_THICKNESS ** 2   # = 64

        # Save the unclipped player saber — we MUST use this (not the clipped version)
        # when checking the Sith's saber, otherwise the endpoint lies exactly on the
        # zone boundary (s ≈ 1.0) and floating-point causes seg_intersect_point to
        # return None, leaving the Sith's saber unclipped.
        saber_p2_orig = saber_p2

        # Find where the player's saber first enters each Sith's saber zone.
        sith_clash_pts = {}
        for s in siths:
            pt = _saber_clip_at_zone(saber_p1, saber_p2, s.p1, s.p2, _ZONE_SQ)
            if pt is not None:
                sith_clash_pts[id(s)] = pt

        sith_clashes = {id(s): id(s) in sith_clash_pts for s in siths}

        # Clip player's saber at the nearest clash point.
        closest_pt = None
        closest_dsq = float('inf')
        for s in siths:
            pt = sith_clash_pts.get(id(s))
            if pt is not None:
                dsq = (pt[0]-saber_p1[0])**2 + (pt[1]-saber_p1[1])**2
                if dsq < closest_dsq:
                    closest_dsq = dsq
                    closest_pt = pt
        if closest_pt is not None:
            saber_p2 = closest_pt

        # Clip each Sith's saber against the ORIGINAL (un-clipped) player saber.
        # Using saber_p2_orig means the Sith saber crosses the player saber in the
        # interior (t < 1), so seg_intersect_point never hits the s=1.0 edge case.
        for s in siths:
            pt = _saber_clip_at_zone(s.p1, s.p2, saber_p1, saber_p2_orig, _ZONE_SQ)
            if pt is not None:
                s.p2 = pt

        for s in siths[:]:
            sabers_clash        = sith_clashes[id(s)]
            player_hits_body    = seg_intersects_rect(saber_p1, saber_p2, s.rect)

            if sabers_clash and s.state in ('windup', 'strike'):
                s.stagger()
            elif player_hits_body:
                if s.take_hit():
                    siths.remove(s); continue

            if s in siths and not sabers_clash and s.check_hit_on_player(player):
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
                gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                turrets.remove(t)
        for t in turrets[:]: t.check_support_and_maybe_fall(ROWS, COLS, get_tile)
        for t in turrets[:]:
            if t.update_fall(ROWS, COLS, get_tile, set_tile): turrets.remove(t)
        for t in turrets[:]: t.update_and_maybe_shoot(player, bolts, ROWS, COLS, get_tile)
        for b in bolts:
            if b.alive: b.update(ROWS, COLS, get_tile)

        def do_explode(gx, gy, radius=Grenade.EXP_RADIUS):
            sparks = []
            spark_count = 20 + int(20 * (radius / Grenade.EXP_RADIUS - 1))
            for _ in range(spark_count):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(2.0, 7.0)
                sparks.append((math.cos(angle) * speed, math.sin(angle) * speed,
                               random.choice([(255,220,80),(255,140,0),(255,60,0),(255,255,180)])))
            explosions.append((gx, gy, pygame.time.get_ticks(), sparks, radius))
            for row in range(ROWS):
                for col in range(COLS):
                    tx = col * C.TILE + C.TILE // 2
                    ty = row * C.TILE + C.TILE // 2
                    if math.hypot(tx - gx, ty - gy) <= radius and get_tile(row, col) in ('B', 'X'):
                        set_tile(row, col, '.')
                        pieces = []
                        for _ in range(6):
                            a = random.uniform(0, 2 * math.pi)
                            sp = random.uniform(1.5, 4.0)
                            pieces.append((math.cos(a)*sp, math.sin(a)*sp, random.randint(4,10)))
                        crumbling_effects.append((float(tx), float(ty), pygame.time.get_ticks(), pieces))
            for s in siths[:]:
                if math.hypot(s.rect.centerx - gx, s.rect.centery - gy) <= radius:
                    siths.remove(s)
            for t in turrets[:]:
                if math.hypot(t.rect.centerx - gx, t.rect.centery - gy) <= radius:
                    if not t.falling and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                        set_tile(t.r, t.c, '.')
                    gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                    turrets.remove(t)
            if math.hypot(player.rect.centerx - gx, player.rect.centery - gy) <= radius:
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

        if rockets:
            new_rockets = []
            for rk in rockets:
                _rk_expired = False
                if rk['kind'] == 'manual':
                    # Self-destruct rocket: A/D steer it (mandatory — it never
                    # auto-aims), and it blows itself up after 20s in the air.
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        _rang = math.atan2(rk['vy'], rk['vx']) - C.ROCKET_MANUAL_TURN
                        _rspd = math.hypot(rk['vx'], rk['vy']) or C.ROCKET_SPEED
                        rk['vx'], rk['vy'] = math.cos(_rang) * _rspd, math.sin(_rang) * _rspd
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        _rang = math.atan2(rk['vy'], rk['vx']) + C.ROCKET_MANUAL_TURN
                        _rspd = math.hypot(rk['vx'], rk['vy']) or C.ROCKET_SPEED
                        rk['vx'], rk['vy'] = math.cos(_rang) * _rspd, math.sin(_rang) * _rspd
                    if pygame.time.get_ticks() - rk['born'] >= 20000:
                        _rk_expired = True
                else:
                    # Homing rocket: auto-aims at the nearest enemy, but only
                    # while it has a clear line of sight to it — otherwise it
                    # just keeps flying straight until it does.
                    rk['life'] -= 1
                    _rtargets = list(turrets) + list(siths)
                    if _rtargets:
                        _rt = min(_rtargets, key=lambda en: math.hypot(
                            en.rect.centerx - rk['x'], en.rect.centery - rk['y']))
                        if has_line_of_sight(rk['x'], rk['y'], _rt.rect.centerx, _rt.rect.centery, ROWS, COLS, get_tile):
                            _rdx = _rt.rect.centerx - rk['x']; _rdy = _rt.rect.centery - rk['y']
                            _rdd = max(1.0, math.hypot(_rdx, _rdy))
                            _rux, _ruy = _rdx / _rdd, _rdy / _rdd
                            rk['vx'] += (_rux * C.ROCKET_SPEED - rk['vx']) * C.ROCKET_TURN_RATE
                            rk['vy'] += (_ruy * C.ROCKET_SPEED - rk['vy']) * C.ROCKET_TURN_RATE
                    _rk_expired = rk['life'] <= 0
                rk['x'] += rk['vx'] * ts; rk['y'] += rk['vy'] * ts
                _rzr, _rzc = int(rk['y']) // C.TILE, int(rk['x']) // C.TILE
                _rhit_wall = 0 <= _rzr < ROWS and 0 <= _rzc < COLS and get_tile(_rzr, _rzc) == 'X'
                _rrect = pygame.Rect(int(rk['x']) - 4, int(rk['y']) - 4, 8, 8)
                _rhit_enemy = (any(t.rect.colliderect(_rrect) for t in turrets)
                               or any(s.rect.colliderect(_rrect) for s in siths))
                if _rhit_wall or _rhit_enemy or _rk_expired:
                    do_explode(rk['x'], rk['y'], radius=C.ROCKET_EXP_RADIUS)
                else:
                    new_rockets.append(rk)
            rockets = new_rockets

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

        # The homing rocket sends back its own view — the camera rides with
        # it while it's in flight. (The self-destruct one stays third-person;
        # you're steering it with A/D, not watching through it.) Re-checked
        # fresh here rather than trusting an earlier flag, since the
        # rocket-update block above can explode and remove it this same frame.
        _pilot_rk = next((rk for rk in rockets if rk['kind'] == 'homing'), None)
        if _pilot_rk is not None:
            camx = max(0, min(COLS * C.TILE - C.WIDTH,  _pilot_rk['x'] - C.WIDTH  / 2))
            camy = max(0, min(ROWS * C.TILE - C.HEIGHT, _pilot_rk['y'] - C.HEIGHT / 2))
        else:
            camx, camy = center_camera_on_player(camx, camy, player, ROWS, COLS)

        # Sniper scope: zooms forward along the aim line while Z is held,
        # but a wall blocks it — once the sight line hits one, it simply
        # stops advancing there (it doesn't creep through or snap back).
        if _scope_dist > 0 or (sniper_scoping and gun_type in SCOPE_RANGE_TILES):
            _smx, _smy = pygame.mouse.get_pos()
            _spx, _spy = float(player.rect.centerx), float(player.rect.centery)
            _sdx, _sdy = (_smx + camx) - _spx, (_smy + camy) - _spy
            _sd = max(1.0, math.hypot(_sdx, _sdy))
            _sux, _suy = _sdx / _sd, _sdy / _sd
        if sniper_scoping and gun_type in SCOPE_RANGE_TILES:
            _SCOPE_MAX  = float(C.TILE * SCOPE_RANGE_TILES[gun_type])
            _wall_limit = raycast_wall_distance(_spx, _spy, _sux, _suy, _SCOPE_MAX, ROWS, COLS, get_tile)
            _scope_dist = min(_scope_dist + dt * 0.22, _wall_limit)
        else:
            _scope_dist = max(0.0, _scope_dist - dt * 0.35)
        if _scope_dist > 0 and gun_type in SCOPE_RANGE_TILES:
            _stx = _spx + _sux * _scope_dist - C.WIDTH  / 2
            _sty = _spy + _suy * _scope_dist - C.HEIGHT / 2
            camx += (_stx - camx) * 0.10
            camy += (_sty - camy) * 0.10
            camx = max(0, min(COLS * C.TILE - C.WIDTH,  camx))
            camy = max(0, min(ROWS * C.TILE - C.HEIGHT, camy))

        for gp in gun_pickups:
            gp.update(ROWS, COLS, get_tile)

        lmb, _, rmb = pygame.mouse.get_pressed(3)

        # Helper: get aim direction toward mouse (world coords)
        def _aim_dir():
            _mx, _my = pygame.mouse.get_pos()
            _pcx, _pcy = float(player.rect.centerx), float(player.rect.centery)
            _dx, _dy = (_mx + camx) - _pcx, (_my + camy) - _pcy
            _d = max(1.0, math.hypot(_dx, _dy))
            return _pcx, _pcy, _dx / _d, _dy / _d

        def _make_bolt(px, py, ux, uy, ox=0.0, oy=0.0, max_range_tiles=None):
            gb = Bolt(px + ox, py + oy, ux * C.BOLT_SPEED, uy * C.BOLT_SPEED, max_range_tiles=max_range_tiles)
            gb.friendly = True
            if gun_type == 'dual':
                gb.one_shot = True
            elif gun_type == 'shotgun':
                gb.multi_hit = True  # takes 3 pellet hits to down a turret
            elif gun_type == 'dualblaster':
                if taser_mode: gb.tasing = True
            elif gun_type == 'sniper':
                gb.enemy_penetrating = True
            elif gun_type == 'raygun':
                gb.enemy_penetrating = True
                if taser_mode:
                    gb.tasing = True
                    gb.wide = True
            elif gun_type == 'penetrator':
                gb.enemy_penetrating = True
                if taser_mode: gb.tasing = True
            return gb

        if active_weapon == 'gun':
            _now_g = pygame.time.get_ticks()
            if gun_type == 'dual':
                # Fires fast (bang-bang-bang); every 4th shot is followed by
                # a brief 0.5s rest before the next one — no HUD countdown
                # is shown for this rest.
                if lmb and _now_g >= _dual_rest_until and _now_g - last_gun_shot >= _gun_cooldown:
                    last_gun_shot = _now_g
                    _px, _py, _ux, _uy = _aim_dir()
                    bolts.append(_make_bolt(_px, _py, _ux, _uy, max_range_tiles=15))
                    _dual_burst_count += 1
                    if _dual_burst_count >= 4:
                        _dual_burst_count = 0
                        _dual_rest_until  = _now_g + 500
            elif lmb and _now_g - last_gun_shot >= _gun_cooldown:
                last_gun_shot = _now_g
                _px, _py, _ux, _uy = _aim_dir()
                if gun_type == 'dualblaster':
                    # fire two bolts side-by-side, offset perpendicularly
                    _perp_x, _perp_y = -_uy * 5, _ux * 5
                    bolts.append(_make_bolt(_px, _py, _ux, _uy,  _perp_x,  _perp_y))
                    bolts.append(_make_bolt(_px, _py, _ux, _uy, -_perp_x, -_perp_y))
                elif gun_type == 'sniper':
                    # Both shots of the volley fire together — no gap
                    # between them — then the full cooldown rests before
                    # the next volley.
                    _perp_x, _perp_y = -_uy * 3, _ux * 3
                    bolts.append(_make_bolt(_px, _py, _ux, _uy,  _perp_x,  _perp_y))
                    bolts.append(_make_bolt(_px, _py, _ux, _uy, -_perp_x, -_perp_y))
                elif gun_type == 'shotgun':
                    # 5-pellet close-range spread; each pellet fizzles out
                    # after 10 tiles instead of flying the length of the level.
                    for _ang in (-16, -8, 0, 8, 16):
                        _rad = math.radians(_ang)
                        _rux = _ux * math.cos(_rad) - _uy * math.sin(_rad)
                        _ruy = _ux * math.sin(_rad) + _uy * math.cos(_rad)
                        bolts.append(_make_bolt(_px, _py, _rux, _ruy, max_range_tiles=10))
                else:
                    bolts.append(_make_bolt(_px, _py, _ux, _uy))
        thresh_sq   = (C.SABER_THICKNESS / 2 + 4) ** 2
        _barrier_pos = None
        if progress['barrier_bought'] and keys[pygame.K_c]:
            _bmx, _bmy = pygame.mouse.get_pos()
            _bpcx, _bpcy = float(player.rect.centerx), float(player.rect.centery)
            _bdx, _bdy = (_bmx + camx) - _bpcx, (_bmy + camy) - _bpcy
            _bd = max(1.0, math.hypot(_bdx, _bdy))
            _bux, _buy = _bdx / _bd, _bdy / _bd
            _barrier_pos = (_bpcx + _bux * C.BARRIER_OFFSET, _bpcy + _buy * C.BARRIER_OFFSET)
        for b in bolts:
            if not b.alive: continue
            if b.friendly: continue  # gun shots and reflected bolts skip saber interaction
            if _barrier_pos is not None and math.hypot(b.x - _barrier_pos[0], b.y - _barrier_pos[1]) <= C.BARRIER_RADIUS + b.r:
                b.alive = False
                continue
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
                b.alive = False
                if player.max_health is not None:
                    player.health = max(0, player.health - C.BULLET_DAMAGE)
                    player_flash_until = pygame.time.get_ticks() + 350
                    if player.health <= 0:
                        _request_restart_flag[0] = True; _death_pending_flag[0] = True
                else:
                    _request_restart_flag[0] = True; _death_pending_flag[0] = True

        _now_col = pygame.time.get_ticks()
        for b in bolts:
            if not b.alive or not b.friendly: continue
            for t in turrets[:]:
                if id(t) in b.hit_ids: continue
                if t.rect.colliderect(b.rect()):
                    if b.tasing:
                        t.stun_until = _now_col + 30000
                        b.hit_ids.add(id(t))
                        if not b.enemy_penetrating: b.alive = False
                    elif b.multi_hit:
                        t.hit_count += 1
                        b.hit_ids.add(id(t))
                        if not b.enemy_penetrating: b.alive = False
                        if t.hit_count >= 3:
                            if (not t.falling) and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                                set_tile(t.r, t.c, '.')
                            gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                            turrets.remove(t)
                    else:
                        if (not t.falling) and 0 <= t.r < ROWS and 0 <= t.c < COLS and get_tile(t.r, t.c) == '^':
                            set_tile(t.r, t.c, '.')
                        gun_pickups.append(GunPickup(t.rect.centerx, t.rect.bottom))
                        b.hit_ids.add(id(t))
                        turrets.remove(t)
                        if not b.enemy_penetrating: b.alive = False
                    if not b.alive: break
            if not b.alive: continue
            for s in siths[:]:
                if id(s) in b.hit_ids: continue
                if s.rect.colliderect(b.rect()):
                    if b.tasing:
                        s.stun_until = _now_col + 30000
                        b.hit_ids.add(id(s))
                        if not b.enemy_penetrating: b.alive = False
                    else:
                        b.hit_ids.add(id(s))
                        if b.one_shot:
                            siths.remove(s)
                        elif s.take_hit():
                            siths.remove(s)
                        if not b.enemy_penetrating: b.alive = False
                    if not b.alive: break

        minx = int(max(0,      (min(saber_p1[0], saber_p2[0]) - C.SABER_THICKNESS) // C.TILE))
        maxx = int(min(COLS-1, (max(saber_p1[0], saber_p2[0]) + C.SABER_THICKNESS) // C.TILE))
        miny = int(max(0,      (min(saber_p1[1], saber_p2[1]) - C.SABER_THICKNESS) // C.TILE))
        maxy = int(min(ROWS-1, (max(saber_p1[1], saber_p2[1]) + C.SABER_THICKNESS) // C.TILE))
        for r in range(miny, maxy + 1):
            for c in range(minx, maxx + 1):
                if get_tile(r, c) == 'B' and seg_intersects_rect(saber_p1, saber_p2, rect_for_tile(r, c)):
                    set_tile(r, c, '.')

        bolts = [b for b in bolts if b.alive]

        _sith_killed_now = max(0, _prev_sith_n - len(siths))
        if _sith_killed_now:
            coins += _sith_killed_now * C.SITH_KILL_COINS

        for (r, c, ch) in tiles_at(player.rect, ROWS, COLS, get_tile):
            if ch == 'B':
                set_tile(r, c, '.')
                coins += C.COIN_PICKUP_VALUE
            elif ch == 'G' and not siths:
                coins, gun_type, saber_color, player_hp = hub_screen(
                    coins, character, gun_type, saber_color, player, player_hp, progress)
                _gun_cooldown = _cooldown_for(gun_type)
                START_POS, GOAL_POS = restart_run()
                break

        display.screen.fill(bg_color)
        draw_level(level_grid, ROWS, COLS, camx, camy)
        draw_falling_turrets(turrets, camx, camy)
        draw_bolts(bolts, camx, camy)
        draw_player(player, camx, camy, saber_p1,
                    saber_p1 if (character != 'jedi' or active_weapon in ('gun', 'grenade')) else saber_p2,
                    saber_color, flash=pygame.time.get_ticks() < player_flash_until)
        if _barrier_pos is not None:
            _bsx, _bsy = int(_barrier_pos[0] - camx), int(_barrier_pos[1] - camy)
            pygame.draw.circle(display.screen, (80, 180, 255), (_bsx, _bsy), C.BARRIER_RADIUS)
            pygame.draw.circle(display.screen, (200, 235, 255), (_bsx, _bsy), C.BARRIER_RADIUS, 2)
        if character in ('trooper', 'mandalorian') and grapple is not None:
            _pcx_g = int(player.rect.centerx - camx)
            _pcy_g = int(player.rect.centery - camy)
            _grx_s = int(grapple['x'] - camx)
            _gry_s = int(grapple['y'] - camy)
            pygame.draw.line(display.screen, (190, 170, 110), (_pcx_g, _pcy_g), (_grx_s, _gry_s), 2)
            _hook_col = (255, 220, 80) if grapple['attached'] else (210, 190, 130)
            pygame.draw.circle(display.screen, _hook_col, (_grx_s, _gry_s), 4)
        for _fp in flame_particles:
            _fa = _fp['life'] / _fp['max_life']
            _fr2 = max(1, int(5 * _fa))
            _fc2 = (int(_fp['col'][0]*_fa), int(_fp['col'][1]*_fa), int(_fp['col'][2]*_fa))
            pygame.draw.circle(display.screen, _fc2,
                               (int(_fp['x'] - camx), int(_fp['y'] - camy)), _fr2)
        for bd in whistling_birds:
            _bsx, _bsy = int(bd['x'] - camx), int(bd['y'] - camy)
            _bspd = max(1.0, math.hypot(bd['vx'], bd['vy']))
            pygame.draw.line(display.screen, (200, 200, 210),
                              (int(_bsx - bd['vx'] / _bspd * 10), int(_bsy - bd['vy'] / _bspd * 10)),
                              (_bsx, _bsy), 2)
            pygame.draw.circle(display.screen, (240, 240, 245), (_bsx, _bsy), 3)
        for rk in rockets:
            _rsx, _rsy = int(rk['x'] - camx), int(rk['y'] - camy)
            _rspd2 = max(1.0, math.hypot(rk['vx'], rk['vy']))
            _rnx, _rny = rk['vx'] / _rspd2, rk['vy'] / _rspd2
            pygame.draw.line(display.screen, (255, 140, 30),
                              (int(_rsx - _rnx * 16), int(_rsy - _rny * 16)), (_rsx, _rsy), 4)
            pygame.draw.circle(display.screen, (255, 60, 20), (_rsx, _rsy), 5)
        if active_weapon == 'grenade' and grenade_count > 0:
            hx = int(player.rect.centerx - camx) + player.face_dir * 14
            hy = int(player.rect.centery  - camy) + 6
            if grenade_charge_start is not None:
                charge = min((pygame.time.get_ticks() - grenade_charge_start) / 1500.0, 1.0)
                gcol = (255, int(200 - 150 * charge), 50) if charge < 0.7 else (255, 50, 50)
            else:
                gcol = (255, 200, 50)
            pygame.draw.circle(display.screen, gcol, (hx, hy), 6)
        if active_weapon == 'gun':
            mx, my = pygame.mouse.get_pos()
            pcx_d = player.rect.centerx - camx
            pcy_d = player.rect.centery - camy
            dx, dy = mx - pcx_d, my - pcy_d
            d = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / d, dy / d
            pygame.draw.line(display.screen, (10, 10, 12),
                             (int(pcx_d), int(pcy_d)),
                             (int(pcx_d + ux * 22), int(pcy_d + uy * 22)), 7)
            pygame.draw.line(display.screen, (110, 110, 120),
                             (int(pcx_d), int(pcy_d)),
                             (int(pcx_d + ux * 22), int(pcy_d + uy * 22)), 2)
            # Laser sight for sniper, ray gun, dual blaster, and penetrator
            if gun_type in ('sniper', 'raygun', 'dualblaster', 'penetrator'):
                _lx, _ly = float(player.rect.centerx), float(player.rect.centery)
                _laser_col = (80, 255, 80) if taser_mode else (255, 30, 30)
                _laser_end = None
                _laser_max = C.TILE * 500
                for _ls in range(C.TILE, _laser_max, 4):
                    _lsx = _lx + ux * _ls
                    _lsy = _ly + uy * _ls
                    _ltc = int(_lsx) // C.TILE
                    _ltr = int(_lsy) // C.TILE
                    if (0 <= _ltr < ROWS and 0 <= _ltc < COLS
                            and get_tile(_ltr, _ltc) == 'X'):
                        _laser_end = (int(_lsx - camx), int(_lsy - camy))
                        break
                if _laser_end is None:
                    _laser_end = (int(_lx + ux * _laser_max - camx),
                                  int(_ly + uy * _laser_max - camy))
                pygame.draw.line(display.screen, _laser_col,
                                 (int(pcx_d + ux * 24), int(pcy_d + uy * 24)),
                                 _laser_end, 1)
        for gp in gun_pickups: gp.draw(display.screen, camx, camy)

        for s in siths: s.draw(display.screen, camx, camy)
        for lf in lava_flows: lf.draw(camx, camy)
        for g in grenades: g.draw(camx, camy)
        if grenade_charge_start is not None:
            charge = min((pygame.time.get_ticks() - grenade_charge_start) / 1500.0, 1.0)
            bx = int(player.rect.centerx - camx) - 20
            by = int(player.rect.top - camy) - 12
            pygame.draw.rect(display.screen, (80, 80, 80),   (bx, by, 40, 6))
            pygame.draw.rect(display.screen, (255, 140, 0),  (bx, by, int(40 * charge), 6))
        for ex, ey, start, sparks, exp_r in explosions:
            age  = pygame.time.get_ticks() - start
            t    = age / 700.0          # 0→1 over lifetime
            fade = max(0, 1.0 - t)
            sx, sy = int(ex - camx), int(ey - camy)

            # central flash (bright white → yellow, shrinks fast)
            flash_r = int(exp_r * 0.5 * max(0, 1 - age / 120))
            if flash_r > 0:
                pygame.draw.circle(display.screen, (255, 255, 220), (sx, sy), flash_r)

            # slow outer ring (orange → red, expands to full radius)
            r1 = int(exp_r * min(t * 1.4, 1.0))
            if r1 > 0:
                c1 = (255, int(120 * fade), 0)
                pygame.draw.circle(display.screen, c1, (sx, sy), r1, 3)

            # fast inner ring (yellow, expands to 60% radius quickly)
            r2 = int(exp_r * 0.6 * min(t * 2.5, 1.0))
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

        # Fog of war: in-LoS = fully visible, behind walls = barely visible
        _FOG_ALPHA = 255   # complete blackness outside LoS
        _CK        = (1, 2, 3)  # colorkey — marks the "clear" (visible) region
        _fog = pygame.Surface((C.WIDTH, C.HEIGHT))
        _fog.fill(fog_color if fog_color != (1, 2, 3) else (0, 0, 1))
        _fog.set_colorkey(_CK)
        _pcx_s = int(player.rect.centerx - camx)
        _pcy_s = int(player.rect.centery - camy)
        if sniper_scoping and gun_type in SCOPE_RANGE_TILES:
            # Scope mode: narrow strip 1 tile above/below laser until wall hit or max range
            _scope_range_px = C.TILE * SCOPE_RANGE_TILES[gun_type]
            _smx2, _smy2 = pygame.mouse.get_pos()
            _spx2, _spy2 = float(player.rect.centerx), float(player.rect.centery)
            _sdx2 = (_smx2 + camx) - _spx2; _sdy2 = (_smy2 + camy) - _spy2
            _sd2  = max(1.0, math.hypot(_sdx2, _sdy2))
            _sux2, _suy2 = _sdx2 / _sd2, _sdy2 / _sd2
            # cast ray to find wall (or stop at max scope range)
            _scope_end_x, _scope_end_y = _spx2 + _sux2 * _scope_range_px, _spy2 + _suy2 * _scope_range_px
            for _ss in range(C.TILE, _scope_range_px, 4):
                _rwx = _spx2 + _sux2 * _ss; _rwy = _spy2 + _suy2 * _ss
                _rtc = int(_rwx) // C.TILE; _rtr = int(_rwy) // C.TILE
                if (0 <= _rtr < ROWS and 0 <= _rtc < COLS and get_tile(_rtr, _rtc) == 'X'):
                    _scope_end_x, _scope_end_y = _rwx, _rwy; break
            # perp offset = 1 tile
            _sperpx, _sperpy = -_suy2 * C.TILE, _sux2 * C.TILE
            _strip_pts = [
                (int(_pcx_s + _sperpx), int(_pcy_s + _sperpy)),
                (int(_pcx_s - _sperpx), int(_pcy_s - _sperpy)),
                (int(_scope_end_x - camx - _sperpx), int(_scope_end_y - camy - _sperpy)),
                (int(_scope_end_x - camx + _sperpx), int(_scope_end_y - camy + _sperpy)),
            ]
            pygame.draw.polygon(_fog, _CK, _strip_pts)
        else:
            _NUM_RAYS = 180
            _MAX_DIST = C.TILE * 14
            _STEP     = 5
            _vis_pts  = [(_pcx_s, _pcy_s)]
            for _ri in range(_NUM_RAYS):
                _ang = 2 * math.pi * _ri / _NUM_RAYS
                _cos = math.cos(_ang); _sin = math.sin(_ang)
                _ex  = _pcx_s + _cos * _MAX_DIST
                _ey  = _pcy_s + _sin * _MAX_DIST
                for _s in range(_STEP, _MAX_DIST, _STEP):
                    _wx = _pcx_s + _cos * _s + camx
                    _wy = _pcy_s + _sin * _s + camy
                    _tc = int(_wx) // C.TILE
                    _tr = int(_wy) // C.TILE
                    if _tr < 0 or _tr >= ROWS or _tc < 0 or _tc >= COLS:
                        _ex = _pcx_s + _cos * _s
                        _ey = _pcy_s + _sin * _s
                        break
                    if get_tile(_tr, _tc) == 'X':
                        _ex = _pcx_s + _cos * _s
                        _ey = _pcy_s + _sin * _s
                        break
                _vis_pts.append((int(_ex), int(_ey)))
            _vis_pts.append(_vis_pts[1])  # close the circle back to ray_0 so no sliver at 0°/right
            if len(_vis_pts) >= 3:
                pygame.draw.polygon(_fog, _CK, _vis_pts)   # punch hole = fully visible
        _fog.set_alpha(_FOG_ALPHA)
        display.screen.blit(_fog, (0, 0))

        # Redraw saber/player on top of fog so they always shine through
        draw_player(player, camx, camy, saber_p1,
                    saber_p1 if (character != 'jedi' or active_weapon in ('gun', 'grenade')) else saber_p2,
                    saber_color, flash=pygame.time.get_ticks() < player_flash_until)

        t = player.time_ms / 1000.0
        display.screen.blit(display.FONT.render(f"Deaths: {player.deaths}", True, C.WHITE), (10, 10))
        display.screen.blit(display.FONT.render(f"Time: {t:05.2f}s", True, C.WHITE), (10, 30))
        _coin_lbl = display.FONT.render(f"Coins: {coins}", True, (255, 215, 80))
        display.screen.blit(_coin_lbl, (C.WIDTH - _coin_lbl.get_width() - 10, 10))
        # Player HP pips
        for i in range(3):
            col = (220, 50, 50) if i < player_hp else (60, 20, 20)
            pygame.draw.rect(display.screen, col, (10 + i * 18, 52, 14, 14), border_radius=3)
        # Force spark bar (Jedi only) — centered at top
        if character == 'jedi':
            _fb_w, _fb_h = 200, 20
            _fb_x = C.WIDTH // 2 - _fb_w // 2
            _fb_y = 6
            _fb_fill = int(_fb_w * force_spark / FORCE_SPARK_MAX)
            _fb_col = (80, 140, 255) if force_spark > 0 else (60, 60, 120)
            pygame.draw.rect(display.screen, (20, 20, 60),    (_fb_x, _fb_y, _fb_w, _fb_h), border_radius=5)
            pygame.draw.rect(display.screen, _fb_col,         (_fb_x, _fb_y, _fb_fill, _fb_h), border_radius=5)
            pygame.draw.rect(display.screen, (160, 200, 255), (_fb_x, _fb_y, _fb_w, _fb_h), 1, border_radius=5)
            _val_lbl = display.FONT.render(f"FORCE  {int(force_spark)}", True, (220, 235, 255))
            display.screen.blit(_val_lbl, (C.WIDTH // 2 - _val_lbl.get_width() // 2, _fb_y + _fb_h // 2 - _val_lbl.get_height() // 2))
        # Health bar (trooper/mandalorian only) — centered at top
        if player.max_health is not None:
            _hb_w, _hb_h = 200, 20
            _hb_x = C.WIDTH // 2 - _hb_w // 2
            _hb_y = 6
            _hb_fill = int(_hb_w * player.health / player.max_health)
            _hb_col = (60, 200, 80) if player.health > player.max_health * 0.3 else (220, 50, 50)
            pygame.draw.rect(display.screen, (20, 40, 20),    (_hb_x, _hb_y, _hb_w, _hb_h), border_radius=5)
            pygame.draw.rect(display.screen, _hb_col,         (_hb_x, _hb_y, _hb_fill, _hb_h), border_radius=5)
            pygame.draw.rect(display.screen, (160, 220, 180), (_hb_x, _hb_y, _hb_w, _hb_h), 1, border_radius=5)
            _hval_lbl = display.FONT.render(f"HEALTH  {int(player.health)}", True, (220, 255, 230))
            display.screen.blit(_hval_lbl, (C.WIDTH // 2 - _hval_lbl.get_width() // 2, _hb_y + _hb_h // 2 - _hval_lbl.get_height() // 2))
        # Flamethrower fuel bar (Mandalorian only — the jetpack itself is unlimited)
        if _has_flamethrower:
            _jb_w, _jb_h = 130, 10
            _jb_x, _jb_y = 10, 72
            _jb_fill = int(_jb_w * jetpack_fuel / JETPACK_FUEL_MAX)
            _jb_col = (220, 100, 20) if jetpack_fuel > JETPACK_FUEL_MAX * 0.3 else (220, 50, 50)
            pygame.draw.rect(display.screen, (55, 25, 5),    (_jb_x, _jb_y, _jb_w, _jb_h), border_radius=3)
            pygame.draw.rect(display.screen, _jb_col,        (_jb_x, _jb_y, _jb_fill, _jb_h), border_radius=3)
            pygame.draw.rect(display.screen, (220, 130, 60), (_jb_x, _jb_y, _jb_w, _jb_h), 1, border_radius=3)
            display.screen.blit(display.FONT.render("FUEL", True, (220, 130, 60)), (_jb_x + _jb_w + 4, _jb_y - 2))
        # Weapon slots
        saber_c = C.CYAN  if active_weapon == 'saber'   else (40, 80, 100)
        gren_c  = C.YELLOW if active_weapon == 'grenade' else ((80, 80, 30) if grenade_count == 0 else (140, 120, 40))
        if character == 'jedi':
            display.screen.blit(display.FONT.render("[1] SABER", True, saber_c), (10, 70))
        display.screen.blit(display.FONT.render(f"[2] GRENADE x{grenade_count}", True, gren_c), (110, 70))
        if gun_count >= 1:
            gun_c = C.WHITE if active_weapon == 'gun' else (80, 80, 90)
            _gun_lbl = {'dual': 'DOUBLE', 'shotgun': 'SHOTGUN', 'blaster': 'BLASTER', 'dualblaster': 'DUAL',
                         'sniper': 'SNIPER', 'raygun': 'RAY', 'penetrator': 'PENETR'}.get(gun_type, 'GUN')
            display.screen.blit(display.FONT.render(f"[3] {_gun_lbl}", True, gun_c), (280, 70))
        elif gun_pickups:
            display.screen.blit(display.FONT.render(f"[P] GUN ({gun_count})", True, (160, 160, 80)), (280, 70))
        if character == 'trooper':
            _grp_c = (100, 200, 255) if active_weapon == 'grapple' else (50, 100, 130)
            display.screen.blit(display.FONT.render("[4] GRAPPLE", True, _grp_c), (370, 70))
            if gun_type in ('dualblaster', 'raygun', 'penetrator'):
                _tsz_col = (80, 255, 180) if taser_mode else (60, 80, 70)
                display.screen.blit(display.FONT.render("S=TASER [ON]" if taser_mode else "S=TASER", True, _tsz_col), (490, 70))
            if gun_type in SCOPE_RANGE_TILES and sniper_scoping:
                display.screen.blit(display.FONT.render("[ SCOPE ]", True, (180, 220, 255)), (650, 70))
        if character == 'jedi':
            _hint = "A/D move  W jump  Mouse aim saber  X push  V pull  ESC colours  Backspace restart"
        elif character == 'mandalorian':
            _hint = "A/D move  W jump  Space flamethrower  Q grapple  LMB shoot  ESC colours  Bksp restart"
        elif gun_type == 'sniper':
            _hint = "A/D move  W jump  LMB shoot  Z=scope  4=grapple then click  ESC colours  Bksp restart"
        elif gun_type in ('raygun', 'penetrator'):
            _hint = "A/D move  W jump  LMB shoot  S=taser  Z=scope  4=grapple then click  ESC colours  Bksp restart"
        else:
            _hint = "A/D move  W jump  LMB shoot  S=taser  4=grapple then click  ESC colours  Bksp restart"
        if character == 'trooper' and len(progress['owned_guns']) > 1:
            _hint += "  3=switch gun"
        if _has_jetpack:
            _hint += "  E=jetpack"
        if progress['barrier_bought']:
            _hint += "  C=shield"
        if character == 'mandalorian' and progress['bird_ammo'] > 0:
            _hint += f"  B=bird x{progress['bird_ammo']}"
        if character == 'mandalorian' and progress['rocket_ammo_manual'] > 0:
            _hint += f"  N=self-destruct rocket x{progress['rocket_ammo_manual']}"
        if character == 'mandalorian' and progress['rocket_ammo_homing'] > 0:
            _hint += f"  H=homing rocket x{progress['rocket_ammo_homing']}"
        display.screen.blit(display.FONT.render(_hint, True, C.YELLOW), (10, C.HEIGHT - 28))
        pygame.display.flip()
