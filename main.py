import sys
import pygame
import display
from space_stage import space_stage
from parkour_stage import parkour_stage

if __name__ == "__main__":
    while True:
        result = space_stage()
        if result == "space_dead":
            continue
        elif result == "landed_destroyer":
            parkour_stage("old")
        elif result == "planet_touch":
            parkour_stage("new")
        pygame.quit()
        sys.exit()
