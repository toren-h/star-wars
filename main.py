import pygame, sys
import display
import constants as C
from space_stage import space_stage
from parkour_stage import parkour_stage, home_screen

if __name__ == "__main__":
    bg_color, fog_color, trooper_gun = C.GREEN, (0, 0, 0), 'dual'
    bg_color, fog_color, trooper_gun = home_screen(bg_color, fog_color, trooper_gun)
    while True:
        result = space_stage()
        if result == "space_dead":
            continue
        elif result == "landed_destroyer":
            parkour_stage("old", bg_color=bg_color, fog_color=fog_color, trooper_gun=trooper_gun)
        elif result == "planet_touch":
            parkour_stage("new", bg_color=bg_color, fog_color=fog_color, trooper_gun=trooper_gun)
        pygame.quit()
        sys.exit()
