import pygame
import constants as C

pygame.init()
screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
pygame.display.set_caption("Star Wars Quest")
clock  = pygame.time.Clock()
FONT   = pygame.font.SysFont("consolas", 18)
BIG    = pygame.font.SysFont("consolas", 28)

TIME_SCALE = 0.75 * 1.00 + 0.25 * C.TIME_SLOW   # 75% fast, 25% slow (~0.86)

def fade_to_black():
    fade = pygame.Surface((C.WIDTH, C.HEIGHT))
    fade.fill((0, 0, 0))
    for a in range(0, 255, 12):
        fade.set_alpha(a)
        screen.blit(fade, (0, 0))
        pygame.display.flip()
        pygame.time.delay(12)
