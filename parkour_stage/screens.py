"""Menu-style screens: colour settings, character select, shop and hub."""
import pygame, sys
import constants as C
import display

# ---- Colour settings picker ----
def color_picker(bg_color, fog_color):
    """Returns (new_bg, new_fog, quit_game)."""
    bg  = list(bg_color)
    fog = list(fog_color)
    items = [
        ("Background  Red",   bg,  0),
        ("Background  Green", bg,  1),
        ("Background  Blue",  bg,  2),
        ("Shadow  Red",       fog, 0),
        ("Shadow  Green",     fog, 1),
        ("Shadow  Blue",      fog, 2),
    ]
    selected = 0
    held_since = {}  # key -> ms when first pressed
    REPEAT_DELAY = 300; REPEAT_RATE = 60
    while True:
        dt = display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return tuple(bg), tuple(fog), True
            elif e.type == pygame.KEYDOWN:
                held_since[e.key] = pygame.time.get_ticks()
                if e.key == pygame.K_ESCAPE:
                    return tuple(bg), tuple(fog), False
                if e.key == pygame.K_q:
                    return tuple(bg), tuple(fog), True
                if e.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % 6
                if e.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % 6
            elif e.type == pygame.KEYUP:
                held_since.pop(e.key, None)
        # Held-key repeat for slider adjustment
        now = pygame.time.get_ticks()
        for key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            if key not in held_since:
                continue
            age = now - held_since[key]
            if age < REPEAT_DELAY:
                continue
            if (age - REPEAT_DELAY) % REPEAT_RATE < dt:
                delta = -5 if key in (pygame.K_LEFT, pygame.K_a) else 5
                _, arr, idx = items[selected]
                arr[idx] = max(0, min(255, arr[idx] + delta))
        display.screen.fill((18, 18, 28))
        title = display.BIG.render("COLOUR SETTINGS", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 36))
        # Preview boxes
        for label, arr, ox, col in (("Background", bg, 180, None), ("Shadow", fog, 560, None)):
            col = tuple(arr) if label == "Background" else tuple(fog)
            arr2 = bg if label == "Background" else fog
            rect = pygame.Rect(ox, 90, 200, 70)
            pygame.draw.rect(display.screen, tuple(arr2), rect, border_radius=8)
            pygame.draw.rect(display.screen, C.WHITE, rect, 1, border_radius=8)
            ls = display.FONT.render(label, True, C.WHITE)
            display.screen.blit(ls, (ox + 100 - ls.get_width() // 2, 170))
        # Sliders
        for i, (lbl, arr, idx) in enumerate(items):
            y = 210 + i * 38
            active = (i == selected)
            c = (255, 220, 80) if active else (200, 200, 220)
            display.screen.blit(display.FONT.render(f"{lbl}:  {arr[idx]:>3}", True, c), (80, y))
            bx, by = 370, y + 2
            fill = int(200 * arr[idx] / 255)
            pygame.draw.rect(display.screen, (50, 50, 60), (bx, by, 200, 14), border_radius=4)
            pygame.draw.rect(display.screen, c, (bx, by, fill, 14), border_radius=4)
            if active:
                pygame.draw.rect(display.screen, (255, 220, 80), (bx, by, 200, 14), 1, border_radius=4)
        h1 = display.FONT.render("W/S or ↑↓ select    A/D or ←→ adjust (hold for fast)", True, (110, 110, 140))
        h2 = display.FONT.render("ESC = back to game    Q = quit", True, (110, 110, 140))
        display.screen.blit(h1, (C.WIDTH // 2 - h1.get_width() // 2, C.HEIGHT - 56))
        display.screen.blit(h2, (C.WIDTH // 2 - h2.get_width() // 2, C.HEIGHT - 34))
        pygame.display.flip()


# ---- Character selection ----
def character_select():
    chars = [
        ('JEDI',         ['Lightsaber & Force', 'powers'],              C.CYAN),
        ('TROOPER',      ['Blaster pistol'],                            (180, 180, 200)),
        ('MANDALORIAN',  ['Blaster + Flamethrower', 'Q = Grapple hook'], (200, 160, 80)),
    ]
    keys_map = ('jedi', 'trooper', 'mandalorian')
    box_w, box_h = 240, 170
    gap = 30
    total_w = 3 * box_w + 2 * gap
    start_x = C.WIDTH  // 2 - total_w // 2
    start_y = C.HEIGHT // 2 - box_h  // 2
    boxes = [pygame.Rect(start_x + i * (box_w + gap), start_y, box_w, box_h)
             for i in range(3)]
    selected = 0
    while True:
        display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % 3
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % 3
                elif e.key == pygame.K_RETURN:
                    return keys_map[selected]
                elif e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        return keys_map[i]
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        selected = i
        display.screen.fill((8, 8, 18))
        title = display.BIG.render("CHOOSE YOUR CLASS", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 80))
        for i, (name, lines, col) in enumerate(chars):
            rect = boxes[i]
            bx, by = rect.x, rect.y
            fill_col   = (25, 25, 45) if i == selected else (15, 15, 30)
            border_col = col           if i == selected else (60, 60, 80)
            border_w   = 3             if i == selected else 1
            pygame.draw.rect(display.screen, fill_col,   rect, border_radius=10)
            pygame.draw.rect(display.screen, border_col, rect, border_w, border_radius=10)
            ns = display.BIG.render(name, True, col)
            display.screen.blit(ns, (bx + box_w // 2 - ns.get_width() // 2, by + 28))
            for j, line in enumerate(lines):
                ls = display.FONT.render(line, True, (180, 180, 210))
                display.screen.blit(ls, (bx + box_w // 2 - ls.get_width() // 2, by + 82 + j * 22))
        hint = display.FONT.render("← → or hover to choose    ENTER or click to confirm", True, (100, 100, 130))
        display.screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, C.HEIGHT - 70))
        pygame.display.flip()


# ---- Shop (hub screen after clearing all Sith Lords) ----
GUN_NAMES = {'dual': 'DOUBLE GUN', 'shotgun': 'SHOTGUN', 'dualblaster': 'DUAL BLASTER',
             'sniper': 'SNIPER RIFLE', 'raygun': 'RAY GUN', 'penetrator': 'PENETRATOR'}

def shop_screen(coins, character, gun_type, saber_color, player, player_hp, progress):
    """Spend coins on a new gun, a red lightsaber unlock (Jedi), a shield, a
    jetpack, a riot shield, or (Mandalorian) Whistling Birds.

    `progress` is a dict mutated in place holding everything that must
    survive an in-stage death/restart: sword_bought, bonus_hits,
    bonus_max_health, jetpack_bought, barrier_bought, bird_ammo,
    rocket_ammo_manual, rocket_ammo_homing, owned_guns (list), gun_count.
    Mutates player.health/max_health in place. Returns (coins, gun_type,
    saber_color, player_hp)."""
    selected = 0
    while True:
        # Trooper and Mandalorian each picked/carry one fixed gun and keep it
        # for the whole level, so the shop doesn't offer any others.
        items = ([('gun', gt, name, C.SHOP_GUN_PRICE)
                  for gt, name in GUN_NAMES.items() if gt not in progress['owned_guns']]
                 if character not in ('trooper', 'mandalorian') else [])
        if character == 'jedi' and not progress['sword_bought']:
            items.append(('sword', None, 'RED LIGHTSABER', C.SHOP_SWORD_PRICE))
        if player.max_health is not None:
            items.append(('shield', None, f'ARMOR PLATING (+{C.SHOP_SHIELD_HEALTH_BONUS} Max HP)', C.SHOP_SHIELD_PRICE))
        else:
            items.append(('shield', None, 'SITH RESIST (+1 Hit)', C.SHOP_SHIELD_PRICE))
        if not progress['jetpack_bought']:
            # Mandalorian's jetpack/flamethrower costs far more than anyone
            # else's plain flight jetpack.
            _jetpack_price = 5000 if character == 'mandalorian' else C.SHOP_JETPACK_PRICE
            items.append(('jetpack', None, 'JETPACK (hold E to fly, unlimited)', _jetpack_price))
        if not progress['barrier_bought']:
            items.append(('barrier', None, 'RIOT SHIELD (hold C)', C.SHOP_BARRIER_PRICE))
        if character == 'mandalorian':
            items.append(('birds', None, f"WHISTLING BIRD (have {progress['bird_ammo']})", C.SHOP_BIRDS_PRICE))
            items.append(('rocket_manual', None,
                          f"ROCKET: SELF-DESTRUCT (have {progress['rocket_ammo_manual']})", C.SHOP_ROCKET_PRICE))
            items.append(('rocket_homing', None,
                          f"ROCKET: HOMING (have {progress['rocket_ammo_homing']})", C.SHOP_ROCKET_PRICE))
        items.append(('leave', None, 'LEAVE SHOP', 0))
        n = len(items)
        selected = max(0, min(selected, n - 1))

        def buy(idx):
            nonlocal coins, gun_type, saber_color, player_hp
            kind, gt, _label, price = items[idx]
            if kind == 'leave':
                return True
            if coins >= price:
                coins -= price
                if kind == 'gun':
                    gun_type = gt
                    if gt not in progress['owned_guns']:
                        progress['owned_guns'].append(gt)
                    progress['gun_count'] = max(progress['gun_count'], 1)
                elif kind == 'sword':
                    saber_color = C.RED
                    progress['sword_bought'] = True
                elif kind == 'shield':
                    if player.max_health is not None:
                        player.max_health += C.SHOP_SHIELD_HEALTH_BONUS
                        player.health     += C.SHOP_SHIELD_HEALTH_BONUS
                        progress['bonus_max_health'] += C.SHOP_SHIELD_HEALTH_BONUS
                    else:
                        player_hp += 1
                        progress['bonus_hits'] += 1
                elif kind == 'jetpack':
                    progress['jetpack_bought'] = True
                elif kind == 'barrier':
                    progress['barrier_bought'] = True
                elif kind == 'birds':
                    progress['bird_ammo'] += 1
                elif kind == 'rocket_manual':
                    progress['rocket_ammo_manual'] += 1
                elif kind == 'rocket_homing':
                    progress['rocket_ammo_homing'] += 1
            return False

        box_w, box_h = 360, 44
        gap = 8
        start_x = C.WIDTH // 2 - box_w // 2
        start_y = 130
        boxes = [pygame.Rect(start_x, start_y + i * (box_h + gap), box_w, box_h) for i in range(n)]

        display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % n
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % n
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if buy(selected):
                        return coins, gun_type, saber_color, player_hp
                elif e.key == pygame.K_ESCAPE:
                    return coins, gun_type, saber_color, player_hp
            elif e.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        if buy(i):
                            return coins, gun_type, saber_color, player_hp
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        selected = i

        display.screen.fill((10, 14, 22))
        title = display.BIG.render("SHOP", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 36))
        coin_lbl = display.FONT.render(f"Coins: {coins}", True, (255, 215, 80))
        display.screen.blit(coin_lbl, (C.WIDTH // 2 - coin_lbl.get_width() // 2, 78))
        for i, (kind, gt, label, price) in enumerate(items):
            rect = boxes[i]
            affordable = price == 0 or coins >= price
            fill_col   = (30, 50, 30) if i == selected else (18, 18, 28)
            border_col = (90, 220, 120) if i == selected else (60, 60, 80)
            text_col   = C.WHITE if affordable else (110, 60, 60)
            pygame.draw.rect(display.screen, fill_col,   rect, border_radius=8)
            pygame.draw.rect(display.screen, border_col, rect, 2, border_radius=8)
            price_txt = f"  ({price}c)" if price > 0 else ""
            lbl = display.FONT.render(label + price_txt, True, text_col)
            display.screen.blit(lbl, (rect.x + 14, rect.y + rect.h // 2 - lbl.get_height() // 2))
        hint = display.FONT.render("W/S or hover select   Enter/click buy   ESC leave", True, (130, 130, 150))
        display.screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, C.HEIGHT - 40))
        pygame.display.flip()


def hub_screen(coins, character, gun_type, saber_color, player, player_hp, progress):
    """Stage-complete hub shown after reaching the goal with all Sith Lords
    dead. PLAY exits back to gameplay (caller restarts the level); SHOP
    opens shop_screen. Returns (coins, gun_type, saber_color, player_hp)
    once PLAY is chosen. See shop_screen for what `progress` holds."""
    selected = 0
    labels = ['PLAY', 'SHOP']
    box_w, box_h = 220, 80
    gap = 30
    total_w = 2 * box_w + gap
    start_x = C.WIDTH  // 2 - total_w // 2
    start_y = C.HEIGHT // 2 - box_h  // 2
    boxes = [pygame.Rect(start_x + i * (box_w + gap), start_y, box_w, box_h) for i in range(2)]
    while True:
        display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % 2
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % 2
                elif e.key == pygame.K_RETURN:
                    if labels[selected] == 'PLAY':
                        return coins, gun_type, saber_color, player_hp
                    coins, gun_type, saber_color, player_hp = shop_screen(
                        coins, character, gun_type, saber_color, player, player_hp, progress)
                elif e.key == pygame.K_ESCAPE:
                    return coins, gun_type, saber_color, player_hp
            elif e.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        if labels[i] == 'PLAY':
                            return coins, gun_type, saber_color, player_hp
                        coins, gun_type, saber_color, player_hp = shop_screen(
                            coins, character, gun_type, saber_color, player, player_hp, progress)
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        selected = i
        display.screen.fill((8, 8, 18))
        title = display.BIG.render("STRONGHOLD CLEARED", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 90))
        coin_lbl = display.FONT.render(f"Coins: {coins}", True, (255, 215, 80))
        display.screen.blit(coin_lbl, (C.WIDTH // 2 - coin_lbl.get_width() // 2, 140))
        for i, label in enumerate(labels):
            rect = boxes[i]
            fill_col   = (25, 45, 25) if i == selected else (15, 15, 30)
            border_col = (90, 220, 120) if i == selected else (60, 60, 80)
            pygame.draw.rect(display.screen, fill_col,   rect, border_radius=10)
            pygame.draw.rect(display.screen, border_col, rect, 3, border_radius=10)
            lbl = display.BIG.render(label, True, C.WHITE)
            display.screen.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))
        hint = display.FONT.render("← → or hover to choose    ENTER or click to confirm", True, (100, 100, 130))
        display.screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, C.HEIGHT - 70))
        pygame.display.flip()




# ---- Trooper gun select (reached from the home screen) ----
TROOPER_GUNS = ['dual', 'shotgun', 'sniper']
_TROOPER_GUN_BLURBS = {
    'dual':       ['Fast single shots', 'Every 4th shot: 0.5s rest'],
    'shotgun':    ['5-pellet close-range spread', 'Takes 3 pellets to drop a turret'],
    'sniper':     ['Zoom scope (hold Z)', 'Two-shot volley, then a long rest'],
}

def gun_select_screen(current_gun):
    """Pick the one gun Trooper will carry for the whole level — this is
    only reachable from the home screen; there's no changing it mid-level.
    Returns the chosen gun key."""
    keys_map = TROOPER_GUNS
    selected = keys_map.index(current_gun) if current_gun in keys_map else 0
    box_w, box_h = 240, 170
    gap = 30
    total_w = 3 * box_w + 2 * gap
    start_x = C.WIDTH  // 2 - total_w // 2
    start_y = C.HEIGHT // 2 - box_h  // 2
    boxes = [pygame.Rect(start_x + i * (box_w + gap), start_y, box_w, box_h) for i in range(3)]
    while True:
        display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % 3
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % 3
                elif e.key == pygame.K_RETURN:
                    return keys_map[selected]
                elif e.key == pygame.K_ESCAPE:
                    return keys_map[selected]
            elif e.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        return keys_map[i]
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        selected = i
        display.screen.fill((8, 8, 18))
        title = display.BIG.render("CHOOSE YOUR GUN", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 80))
        for i, gkey in enumerate(keys_map):
            rect = boxes[i]
            bx, by = rect.x, rect.y
            fill_col   = (25, 25, 45) if i == selected else (15, 15, 30)
            border_col = C.CYAN       if i == selected else (60, 60, 80)
            border_w   = 3            if i == selected else 1
            pygame.draw.rect(display.screen, fill_col,   rect, border_radius=10)
            pygame.draw.rect(display.screen, border_col, rect, border_w, border_radius=10)
            ns = display.FONT.render(GUN_NAMES[gkey], True, C.CYAN if i == selected else C.WHITE)
            display.screen.blit(ns, (bx + box_w // 2 - ns.get_width() // 2, by + 22))
            for j, line in enumerate(_TROOPER_GUN_BLURBS[gkey]):
                ls = display.FONT.render(line, True, (180, 180, 210))
                display.screen.blit(ls, (bx + box_w // 2 - ls.get_width() // 2, by + 86 + j * 22))
        hint = display.FONT.render("← → or hover to choose    ENTER or click to confirm    ESC = keep current", True, (100, 100, 130))
        display.screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, C.HEIGHT - 70))
        pygame.display.flip()


# ---- Home screen (shown at launch: PLAY, pick your gun, or change colours) ----
def home_screen(bg_color, fog_color, trooper_gun='dual'):
    """The title screen shown when the game first launches, in the same
    style as hub_screen. PLAY starts the game (space stage, then whichever
    parkour stage is reached); GUN opens gun_select_screen to choose the
    one gun Trooper will carry for the whole level (can't be changed once
    you're in a level); COLOURS opens the same colour picker used in-level,
    letting the background/shadow colours be set up front.
    Returns (bg_color, fog_color, trooper_gun) once PLAY is chosen."""
    selected = 0
    labels = ['PLAY', 'GUN', 'COLOURS']
    box_w, box_h = 220, 80
    gap = 24
    total_w = 3 * box_w + 2 * gap
    start_x = C.WIDTH  // 2 - total_w // 2
    start_y = C.HEIGHT // 2 - box_h  // 2
    boxes = [pygame.Rect(start_x + i * (box_w + gap), start_y, box_w, box_h) for i in range(3)]
    while True:
        display.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % 3
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % 3
                elif e.key == pygame.K_RETURN:
                    if labels[selected] == 'PLAY':
                        return bg_color, fog_color, trooper_gun
                    elif labels[selected] == 'GUN':
                        trooper_gun = gun_select_screen(trooper_gun)
                    else:
                        bg_color, fog_color, _quit = color_picker(bg_color, fog_color)
                        if _quit: pygame.quit(); sys.exit()
                elif e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        if labels[i] == 'PLAY':
                            return bg_color, fog_color, trooper_gun
                        elif labels[i] == 'GUN':
                            trooper_gun = gun_select_screen(trooper_gun)
                        else:
                            bg_color, fog_color, _quit = color_picker(bg_color, fog_color)
                            if _quit: pygame.quit(); sys.exit()
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(boxes):
                    if rect.collidepoint(e.pos):
                        selected = i
        display.screen.fill((8, 8, 18))
        title = display.BIG.render("STAR WARS QUEST", True, C.WHITE)
        display.screen.blit(title, (C.WIDTH // 2 - title.get_width() // 2, 90))
        swatch = pygame.Rect(C.WIDTH // 2 - 100, 150, 200, 34)
        pygame.draw.rect(display.screen, bg_color, swatch, border_radius=6)
        pygame.draw.rect(display.screen, C.WHITE, swatch, 1, border_radius=6)
        swatch_lbl = display.FONT.render("background colour", True, (180, 180, 210))
        display.screen.blit(swatch_lbl, (C.WIDTH // 2 - swatch_lbl.get_width() // 2, 190))
        gun_lbl = display.FONT.render(f"Trooper gun: {GUN_NAMES[trooper_gun]}", True, (180, 220, 255))
        display.screen.blit(gun_lbl, (C.WIDTH // 2 - gun_lbl.get_width() // 2, 212))
        for i, label in enumerate(labels):
            rect = boxes[i]
            fill_col   = (25, 45, 25) if i == selected else (15, 15, 30)
            border_col = (90, 220, 120) if i == selected else (60, 60, 80)
            pygame.draw.rect(display.screen, fill_col,   rect, border_radius=10)
            pygame.draw.rect(display.screen, border_col, rect, 3, border_radius=10)
            lbl = display.BIG.render(label, True, C.WHITE)
            display.screen.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))
        hint = display.FONT.render("← → or hover to choose    ENTER or click to confirm    ESC quit", True, (100, 100, 130))
        display.screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, C.HEIGHT - 70))
        pygame.display.flip()
