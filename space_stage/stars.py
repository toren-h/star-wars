"""Scrolling background starfield for the space stage."""
import pygame, random
import constants as C

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
