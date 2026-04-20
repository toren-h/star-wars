# star_wars_quest.py

import pygame, sys, math, random

pygame.init()
WIDTH, HEIGHT = 960, 600
TILE = 40

# -------------------- Shared timing --------------------
TIME_SCALE = 1.00
TIME_SLOW  = 0.45

# Colors
WHITE=(240,240,240); BLACK=(10,10,12); GREY=(65,68,73)
BLUE =(80,135,255);  RED=(230,70,70);  YELLOW=(250,220,80)
CYAN =(120,220,255); GREEN=(40,180,120)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Star Wars Quest")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("consolas", 18)
BIG  = pygame.font.SysFont("consolas", 28)

def toggle_slow():
    global TIME_SCALE
    TIME_SCALE = TIME_SLOW if abs(TIME_SCALE-1.00) < 1e-6 else 1.00

# ============================================================
#                         SPACE STAGE
# ============================================================
SPACE_SHIP_W=46; SPACE_SHIP_H=24
ROT_SPEED=0.06; THRUST=0.45; SPACE_DRAG=0.988; SPACE_MAXSPEED=6.0
LASER_SPEED=14.0; LASER_CD_MS=180
TIE_SPAWN_MS=1000; TIE_MIN_SPEED=2.0; TIE_MAX_SPEED=3.2; TIE_LASER_SPEED=7.0; TIE_SHOOT_CD_MS=900
STAR_COUNT=160; KILLS_TO_SPAWN_DESTROYER=1
SHUTDOWN_HITS=10

# Falling & planet
FALL_THRUST=0.12; FALL_ROT=0.03
PLANET_RADIUS=240
PLANET_PULL=0.00045     # accel toward planet center (per ms)
PLANET_EDGE_OFFSET=1600 # initial offset below view when fall starts
ATMOSPHERE_PAD=20       # touching distance threshold

class XWing:
    def __init__(self):
        self.vx=self.vy=0.0; self.ang=0.0
        self.last_shot=-9999; self.flash_until=0
        self.kills=0; self.hits=0
        self.shutdown=False; self.shutdown_since=0
    def rect(self):
        return pygame.Rect(WIDTH//2-SPACE_SHIP_W//2, HEIGHT//2-SPACE_SHIP_H//2, SPACE_SHIP_W, SPACE_SHIP_H)
    def update_controls(self, keys):
        if self.shutdown: return
        if keys[pygame.K_LEFT]:  self.ang -= ROT_SPEED*TIME_SCALE
        if keys[pygame.K_RIGHT]: self.ang += ROT_SPEED*TIME_SCALE
        if keys[pygame.K_UP]:
            fx,fy=math.cos(self.ang), math.sin(self.ang)
            self.vx += fx*THRUST*TIME_SCALE; self.vy += fy*THRUST*TIME_SCALE
        self.vx *= (SPACE_DRAG**TIME_SCALE); self.vy *= (SPACE_DRAG**TIME_SCALE)
        sp=math.hypot(self.vx,self.vy)
        if sp>SPACE_MAXSPEED:
            k=SPACE_MAXSPEED/sp; self.vx*=k; self.vy*=k
    def falling_controls(self, keys):
        if keys[pygame.K_LEFT]:  self.ang -= FALL_ROT*TIME_SCALE
        if keys[pygame.K_RIGHT]: self.ang += FALL_ROT*TIME_SCALE
        if keys[pygame.K_UP]:
            fx,fy=math.cos(self.ang), math.sin(self.ang)
            self.vx += fx*FALL_THRUST*TIME_SCALE; self.vy += fy*FALL_THRUST*TIME_SCALE
        self.vx *= (SPACE_DRAG**TIME_SCALE); self.vy *= (SPACE_DRAG**TIME_SCALE)
    def shoot(self, bullets):
        if self.shutdown: return
        now=pygame.time.get_ticks(); eff=int(LASER_CD_MS/max(TIME_SCALE,1e-3))
        if now-self.last_shot<eff: return
        self.last_shot=now
        fx,fy=math.cos(self.ang), math.sin(self.ang)
        ux,uy=-math.sin(self.ang), math.cos(self.ang)
        cx,cy=WIDTH/2,HEIGHT/2
        tip1=(cx+fx*20+ux*6, cy+fy*20+uy*6)
        tip2=(cx+fx*20-ux*6, cy+fy*20-uy*6)
        bullets.append(SpaceBullet(*tip1, fx*LASER_SPEED, fy*LASER_SPEED, True))
        bullets.append(SpaceBullet(*tip2, fx*LASER_SPEED, fy*LASER_SPEED, True))
    def take_hit(self):
        self.hits+=1; self.flash_until=pygame.time.get_ticks()+140
        if self.hits>=SHUTDOWN_HITS and not self.shutdown:
            self.shutdown=True; self.shutdown_since=pygame.time.get_ticks()
            self.vx*=0.4; self.vy+=0.8
    def draw(self,surf):
        fx,fy=math.cos(self.ang), math.sin(self.ang)
        ux,uy=-math.sin(self.ang), math.cos(self.ang)
        cx,cy=WIDTH/2,HEIGHT/2
        nose=(int(cx+fx*SPACE_SHIP_W*0.5), int(cy+fy*SPACE_SHIP_W*0.5))
        lt=(int(cx-fx*SPACE_SHIP_W*0.5+ux*SPACE_SHIP_H*0.5), int(cy-fy*SPACE_SHIP_W*0.5+uy*SPACE_SHIP_H*0.5))
        rt=(int(cx-fx*SPACE_SHIP_W*0.5-ux*SPACE_SHIP_H*0.5), int(cy-fy*SPACE_SHIP_W*0.5-uy*SPACE_SHIP_H*0.5))
        pygame.draw.polygon(surf,(180,180,200),[lt,nose,rt])
        pygame.draw.line(surf,(200,200,220),(int(cx-fx*14+ux*8),int(cy-fy*14+uy*8)),(int(cx+fx*22+ux*8),int(cy+fy*22+uy*8)),3)
        pygame.draw.line(surf,(200,200,220),(int(cx-fx*14-ux*8),int(cy-fy*14-uy*8)),(int(cx+fx*22-ux*8),int(cy+fy*22-uy*8)),3)
        if pygame.time.get_ticks()<self.flash_until:
            pygame.draw.circle(surf,(255,120,120),(cx,cy),16,2)

class SpaceBullet:
    def __init__(self,x,y,vx,vy,friendly=False):
        self.x=float(x); self.y=float(y); self.vx=float(vx); self.vy=float(vy)
        self.friendly=friendly; self.alive=True; self.r=3
    def world_scroll(self,sx,sy): self.x+=sx; self.y+=sy
    def update(self):
        if not self.alive: return
        self.x+=self.vx*TIME_SCALE; self.y+=self.vy*TIME_SCALE
        if self.x<-80 or self.x>WIDTH+80 or self.y<-80 or self.y>HEIGHT+80: self.alive=False
    def draw(self,surf): pygame.draw.circle(surf, YELLOW if self.friendly else RED,(int(self.x),int(self.y)),self.r)

class TIE:
    def __init__(self,x,y,vx,vy):
        self.x=float(x); self.y=float(y); self.vx=float(vx); self.vy=float(vy)
        self.w=32; self.h=24; self.alive=True; self.last_shot=-9999
    def rect(self): return pygame.Rect(int(self.x-self.w/2),int(self.y-self.h/2),self.w,self.h)
    def world_scroll(self,sx,sy): self.x+=sx; self.y+=sy
    def update(self):
        if not self.alive: return
        self.x+=self.vx*TIME_SCALE; self.y+=self.vy*TIME_SCALE
        if self.x<-140 or self.x>WIDTH+140 or self.y<-140 or self.y>HEIGHT+140: self.alive=False
    def maybe_shoot(self, enemy_bolts):
        now=pygame.time.get_ticks(); eff=int(TIE_SHOOT_CD_MS/max(TIME_SCALE,1e-3))
        if now-self.last_shot<eff: return
        self.last_shot=now
        cx,cy=WIDTH/2,HEIGHT/2; dx,dy=cx-self.x, cy-self.y; d=max(1.0, math.hypot(dx,dy))
        ux,uy=dx/d,dy/d
        enemy_bolts.append(SpaceBullet(self.x,self.y,ux*TIE_LASER_SPEED,uy*TIE_LASER_SPEED,False))
    def draw(self,surf):
        r=self.rect()
        pygame.draw.rect(surf,(150,150,170),r,border_radius=4)
        pygame.draw.rect(surf,(40,40,60),(r.x+6,r.y+6,r.w-12,r.h-12),border_radius=3)
        pygame.draw.rect(surf,(90,90,110),(r.x-10,r.y+3,10,r.h-6))
        pygame.draw.rect(surf,(90,90,110),(r.right,r.y+3,10,r.h-6))

class StarDestroyer:
    def __init__(self,x,y,vxy):
        self.x=float(x); self.y=float(y); self.vx,self.vy=vxy
        self.top_len=320; self.base_half=240; self.hangar_w=160; self.hangar_h=48
    def world_scroll(self,sx,sy): self.x+=sx; self.y+=sy
    def update(self): self.x+=self.vx*TIME_SCALE; self.y+=self.vy*TIME_SCALE
    def triangle_pts(self):
        return [(self.x, self.y-self.top_len),
                (self.x-self.base_half,self.y+self.base_half),
                (self.x+self.base_half,self.y+self.base_half)]
    def hangar_rect(self): return (self.x-self.hangar_w/2, self.y+self.base_half-self.hangar_h/2, self.hangar_w, self.hangar_h)
    def draw(self,surf):
        pts=[(int(px),int(py)) for px,py in self.triangle_pts()]
        pygame.draw.polygon(surf,(120,120,135),pts); pygame.draw.polygon(surf,WHITE,pts,3)
        hx,hy,hw,hh=self.hangar_rect(); pygame.draw.rect(surf,GREEN,(int(hx),int(hy),int(hw),int(hh)),3)

def point_in_triangle(px,py,A,B,C):
    (x1,y1),(x2,y2),(x3,y3)=A,B,C
    det=(y2-y3)*(x1-x3)+(x3-x2)*(y1-y3)
    if det==0: return False
    l1=((y2-y3)*(px-x3)+(x3-x2)*(py-y3))/det
    l2=((y3-y1)*(px-x3)+(x1-x3)*(py-y3))/det
    l3=1-l1-l2
    return 0<=l1<=1 and 0<=l2<=1 and 0<=l3<=1

# stars
stars=[]
def init_stars():
    global stars; stars=[]
    for _ in range(STAR_COUNT):
        x=random.randint(0,WIDTH); y=random.randint(0,HEIGHT); par=random.uniform(0.3,1.0)
        stars.append([x,y,par])
def scroll_stars(sx,sy):
    for s in stars:
        s[0]+=sx*s[2]*0.5; s[1]+=sy*s[2]*0.5
        if s[0]<-2: s[0]+=WIDTH+4
        if s[0]>WIDTH+2: s[0]-=WIDTH+4
        if s[1]<-2: s[1]+=HEIGHT+4
        if s[1]>HEIGHT+2: s[1]-=HEIGHT+4
def draw_stars(surf):
    for x,y,par in stars:
        size=1 if par<0.6 else 2
        pygame.draw.rect(surf,(200,200,220),(int(x),int(y),size,size))

def draw_planet(surf,px,py):
    center=(int(px),int(py))
    for r,col in [(PLANET_RADIUS+20,(20,30,60)),(PLANET_RADIUS,(25,70,130)),(PLANET_RADIUS-20,(30,110,170))]:
        pygame.draw.circle(surf,col,center,r)
    pygame.draw.circle(surf,(220,240,255),center,PLANET_RADIUS,2)

def draw_planet_arrow(surf,px,py):
    if 0<=px<=WIDTH and 0<=py<=HEIGHT: return
    cx,cy=WIDTH/2,HEIGHT/2; dx,dy=px-cx,py-cy; ang=math.atan2(dy,dx)
    margin=20; cos,sin=math.cos(ang),math.sin(ang); t=1e9
    if cos>0: t=min(t,(WIDTH-margin-cx)/cos)
    if cos<0: t=min(t,(margin-cx)/cos)
    if sin>0: t=min(t,(HEIGHT-margin-cy)/sin)
    if sin<0: t=min(t,(margin-cy)/sin)
    ax,ay=cx+cos*t, cy+sin*t
    wing=12; tip=(int(ax),int(ay))
    left=(int(ax-cos*22-sin*wing), int(ay-sin*22+cos*wing))
    right=(int(ax-cos*22+sin*wing), int(ay-sin*22-cos*wing))
    pygame.draw.polygon(surf,(240,230,110),[tip,left,right])

def fade_to_black():
    fade=pygame.Surface((WIDTH,HEIGHT)); fade.fill((0,0,0))
    for a in range(0,255,12):
        fade.set_alpha(a); screen.blit(fade,(0,0)); pygame.display.flip(); pygame.time.delay(12)

def space_stage():
    """Returns:
       - 'landed_destroyer' when entering hangar (OLD map)
       - 'planet_touch' when actually touching planet (NEW map)
       - 'space_dead' when crashing into Destroyer hull or TIE collision
    """
    xwing=XWing(); bullets=[]; enemy_bolts=[]; ties=[]; last_spawn=pygame.time.get_ticks()
    destroyer=None; init_stars()

    # planet position activates during fall
    planet_active=False; planet_x,planet_y=WIDTH/2, HEIGHT/2+PLANET_EDGE_OFFSET
    STATE="combat"

    while True:
        dt=clock.tick(60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            elif e.type==pygame.KEYDOWN:
                if e.key==pygame.K_c: toggle_slow()
                if e.key==pygame.K_SPACE: xwing.shoot(bullets)

        keys=pygame.key.get_pressed()
        if STATE=="combat":
            xwing.update_controls(keys)
        else:
            xwing.falling_controls(keys)
            # gravitational pull toward visible planet center
            cx,cy=WIDTH/2,HEIGHT/2; dx,dy=planet_x-cx, planet_y-cy
            dist=max(1.0, math.hypot(dx,dy)); ux,uy=dx/dist, dy/dist
            xwing.vx += ux * (PLANET_PULL*dt)
            xwing.vy += uy * (PLANET_PULL*dt)

        # keep ship centered by scrolling world
        sx=-xwing.vx*TIME_SCALE; sy=-xwing.vy*TIME_SCALE
        scroll_stars(sx,sy)
        for t in ties: t.world_scroll(sx,sy)
        for b in bullets: b.world_scroll(sx,sy)
        for eb in enemy_bolts: eb.world_scroll(sx,sy)
        if destroyer: destroyer.world_scroll(sx,sy)
        if planet_active: planet_x+=sx; planet_y+=sy

        # spawn TIEs
        now=pygame.time.get_ticks(); eff_spawn=int(TIE_SPAWN_MS/max(TIME_SCALE,1e-3))
        if STATE=="combat" and (now-last_spawn>=eff_spawn) and (destroyer is None or len(ties)<12):
            last_spawn=now; side=random.choice(["top","bottom","left","right"])
            if side=="top": x,y=random.randint(-30,WIDTH+30), -40
            elif side=="bottom": x,y=random.randint(-30,WIDTH+30), HEIGHT+40
            elif side=="left": x,y=-40, random.randint(-30,HEIGHT+30)
            else: x,y=WIDTH+40, random.randint(-30,HEIGHT+30)
            dx,dy=WIDTH/2-x, HEIGHT/2-y; d=max(1.0, math.hypot(dx,dy))
            sp=random.uniform(TIE_MIN_SPEED, TIE_MAX_SPEED)
            ties.append(TIE(x,y,dx/d*sp,dy/d*sp))

        # updates
        for t in ties:
            t.update()
            if STATE=="combat": t.maybe_shoot(enemy_bolts)
        for b in bullets: b.update()
        for eb in enemy_bolts: eb.update()
        if destroyer: destroyer.update()

        # player lasers vs TIEs (kill TIE)
        for b in bullets:
            if not b.alive or not b.friendly: continue
            r=pygame.Rect(int(b.x-3),int(b.y-3),6,6)
            for t in ties:
                if t.alive and r.colliderect(t.rect()):
                    t.alive=False; b.alive=False; xwing.kills+=1; break

        # -------- NEW: ship collision with TIE = death --------
        xr = xwing.rect()
        for t in ties:
            if t.alive and xr.colliderect(t.rect()):
                fade_to_black()
                return "space_dead"

        # prune
        ties=[t for t in ties if t.alive]; bullets=[b for b in bullets if b.alive]; enemy_bolts=[e for e in enemy_bolts if e.alive]

        # spawn Star Destroyer after enough kills
        if destroyer is None and xwing.kills>=KILLS_TO_SPAWN_DESTROYER:
            side=random.choice(["top","bottom","left","right"])
            if side=="top": sx0,sy0=random.randint(140,WIDTH-140), -400; v=(0,0.6)
            elif side=="bottom": sx0,sy0=random.randint(140,WIDTH-140), HEIGHT+400; v=(0,-0.6)
            elif side=="left": sx0,sy0=-400, random.randint(160,HEIGHT-160); v=(0.6,0)
            else: sx0,sy0=WIDTH+400, random.randint(160,HEIGHT-160); v=(-0.6,0)
            destroyer=StarDestroyer(sx0,sy0,v)

        # enemy hits player (only in combat)
        if STATE=="combat":
            for eb in enemy_bolts:
                if xr.collidepoint(int(eb.x),int(eb.y)):
                    eb.alive=False; xwing.take_hit()

        # destroyer interactions
        if destroyer:
            tri=destroyer.triangle_pts(); cx,cy=WIDTH/2,HEIGHT/2
            in_tri=point_in_triangle(cx,cy,*tri)
            hx,hy,hw,hh=destroyer.hangar_rect()
            in_hangar=(hx<=cx<=hx+hw and hy<=cy<=hy+hh)
            if STATE=="combat" and in_tri and not in_hangar:
                fade_to_black(); return "space_dead"       # crash into hull -> restart space
            if STATE=="combat" and in_hangar:
                fade_to_black(); return "landed_destroyer" # hangar landing -> OLD map

        # enter falling mode once shutdown
        if STATE=="combat" and xwing.shutdown:
            STATE="falling"
            planet_active=True
            planet_x,planet_y=WIDTH/2, HEIGHT/2+PLANET_EDGE_OFFSET

        # falling ends ONLY when touching planet (no timer)
        if STATE=="falling":
            cx,cy=WIDTH/2,HEIGHT/2
            dist=math.hypot(planet_x-cx, planet_y-cy)
            if dist <= PLANET_RADIUS + ATMOSPHERE_PAD:
                fade_to_black()
                return "planet_touch"  # touchdown -> NEW map

        # draw
        screen.fill((5,7,15))
        draw_stars(screen)
        if planet_active:
            draw_planet(screen,planet_x,planet_y); draw_planet_arrow(screen,planet_x,planet_y)
        for t in ties: t.draw(screen)
        for eb in enemy_bolts: eb.draw(screen)
        for b in bullets: b.draw(screen)
        if destroyer: destroyer.draw(screen)
        xwing.draw(screen)
        hud = ("Turn ←/→  Thrust ↑  Shoot SPACE  Slow-Mo C  (Find Star Destroyer to land)" 
               if STATE=="combat" else "Systems failing... small control (←/→ rotate, ↑ thrust). Falling to planet...")
        screen.blit(FONT.render(hud,True,WHITE),(WIDTH//2-260, HEIGHT-30))
        screen.blit(FONT.render(f"Kills: {xwing.kills}/{KILLS_TO_SPAWN_DESTROYER}   Hits: {xwing.hits}/{SHUTDOWN_HITS}",True,WHITE),(10,10))
        pygame.display.flip()

# ============================================================
#                        PARKOUR STAGE
# ============================================================
GRAVITY=0.55; FRICTION=0.85; MAX_XSPEED=6.2; JUMP_SPEED=10.3; CAM_LERP=0.08; BOLT_SPEED=7.2
FIRE_RADIUS_TILES=10; BASE_TURRET_COOLDOWN_MS=500; TURRET_FALL_KILL_TILES=4
SABER_LEN=74; SABER_THICKNESS=8
FORCE_RADIUS_TILES=10; FORCE_RADIUS_PX=FORCE_RADIUS_TILES*TILE; FORCE_BLOCKED_TILES=set(['X','B','G'])
FORCE_TURRET_STEPS=3; FORCE_BOLT_IMPULSE=6.0

# ------------ OLD MAP (landing via Destroyer hangar) ------------
OLD_LEVEL = [
"........................^...............................................................",
".......................XXX............................................................",
".....................XXX.X..............^...............................S...BBBBBBBBBB",
"......................^X.X...^.........XXXX................^...XXXXXXXXXXXXXXXXXXXXXX..",
".............^.......XXX.XXXXXX.............X.............XXX....X....................",
".............X....X..XXX.....^.^X...........X.......^.....X.X....X....................",
".............X...XX....B.....XXXXX.....XXX...X.....XXXX....X.X....XXXX................",
".............XXXXX...............X....X..X...X.....X..X....X.XX^.....X................",
"..........XXX....XXXX...........XX....X..X...X.....X...XXXX.XXXXXX..X................",
".....XXXXX......................X.....X..X...X.....X...............X.X................",
"..XXXX..........^...............X..P..X..X...X.....X..B......X.XXXXX.X................",
"XX............XXXXXXX...........X.....XXXX...X..^..X.........XBBBBXX.X................",
"X.............X.....X...........X..............XXXX...^......XXXXXX.X................",
"X.............X.....XXXXX.......X.....................XXXXX...X......X................",
"X.............X.........X.......X....................XX...X...X..G...X................",
"XXXX.......XXXX.........XXX.....X..........B.........X....X...X...^..X................",
"....XXXXXXX.............X.......X.....^.....XX.......X....XXXXXX..XXXX................",
".....................B..X.......X.....X..............X.^^^..........X.................",
"........................^X...XXXX.....XX.............XXXXXX.........X.................",
"........................XXXX......................................XXX.................",
"...........^.....B.......B............^............^.................X.................",
"....................................................................XXXXXXX...........",
]

# ------------ NEW MAP (touching the planet after fall) ------------
NEW_LEVEL = [
"........................................................................................",
".........................XXXXXXX........................................................",
".......................XX.......XX......................................................",
"......................X..^.B.^.B..X.....................................................",
".....................X...XXXXXXX..XX..................XXXX.............................",
"....................X..XX.......XX..X................XX....XX...........................",
"..............XXXXXXX.....XX.XX..X..X...............XXX.......X..........................",
"............XX.....X...X..X...X..X..X.............XX.........XX.........................",
"...........X..P....X...X..X...X..X..XXXX.......XXXX...........X.........................",
"..........X........X...X..X.B.X..X......X.....X...............X.........................",
"..........X..XXXX..XX..X..XXXXX.........X.....X....XXXXXX.....X.........................",
"..........X..X..X......X.......XXXXX....X.....X....X..BBX.....X.........................",
"..........X..X..B...X..X......XXXXXX.B^.XXXXX.X....X..BBX.....XXXX......................",
"..........X.....X...X..X.....X.....XXXX.....X.X....X..XX........X......................",
"..........X..X..XXXX...X....X...^..^XX.....X.X....X...........X.........................",
"..........X..X.........X...X....XXXXX......X.XXXXXXXX.........X.........................",
"..........X..XXXX......X..X...........^....X.X.............G..X.........................",
"..........X.......XX...X..X..^.......XXXX..X.X...........XXXXX..........................",
"..........XXXXXX..X....X..XXXXXXXXXXXXXXx..X............X...............................",
"..................X....XXXX...XXXXXXXX.....X..XXXX......X...............................",
"..................X..B...^...^XXXXXXXX.^....^.^.XXXX...X...............................",
".................XXXXXXXXXBXXXXXXXXXXXX...XXXXXX....XXXXXX.............................",
"..........................XXX..........XXXXX............................................",
"........................................................................................"
]

# ------------ helpers ------------
def rect_for_tile(r,c): return pygame.Rect(c*TILE, r*TILE, TILE, TILE)

def normalize_and_floor(level_rows):
    max_cols = max(len(row) for row in level_rows)
    lvl = [row.ljust(max_cols, ".") for row in level_rows]
    lvl[-1] = "X"*max_cols
    return lvl, len(lvl), max_cols

def scan_entities(grid, ROWS, COLS):
    start=None; goal=None; turrets=[]; siths=[]
    for r in range(ROWS):
        for c in range(COLS):
            ch=grid[r][c]
            if ch=='P' and start is None: start=(c*TILE, r*TILE)
            elif ch=='G' and goal is None: goal=(c*TILE, r*TILE)
            elif ch=='^': turrets.append((r,c))
            elif ch=='S': siths.append((r,c))
    if start is None: start=(TILE,TILE)
    if goal  is None: goal=((COLS-2)*TILE,(ROWS-3)*TILE)
    return start,goal,turrets,siths

def point_seg_dist_sq(px,py,x1,y1,x2,y2):
    dx=x2-x1; dy=y2-y1
    if dx==0 and dy==0: return (px-x1)**2+(py-y1)**2
    t=((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy); t=max(0,min(1,t))
    nx=x1+t*dx; ny=y1+t*dy
    return (px-nx)**2+(py-ny)**2

def seg_intersect(p1,p2,q1,q2):
    def line_intersection_point(p1, p2, p3, p4):
        x1,y1 = p1
        x2,y2 = p2
        x3,y3 = p3
        x4,y4 = p4

        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if denom == 0:
            return None

        px = ((x1*y2 - y1*x2)*(x3-x4) - (x1-x2)*(x3*y4 - y3*x4)) / denom
        py = ((x1*y2 - y1*x2)*(y3-y4) - (y1-y2)*(x3*y4 - y3*x4)) / denom

        return (px, py)
    def ccw(A,B,C): return (C[1]-A[1])*(B[0]-A[0]) < (B[1]-A[1])*(C[0]-A[0])
    return (ccw(p1,q1,q2)!=ccw(p2,q1,q2)) and (ccw(p1,p2,q1)!=ccw(p1,p2,q2))

def seg_intersects_rect(p1,p2,rect):
    if rect.collidepoint(p1) or rect.collidepoint(p2): return True
    x1,y1=rect.topleft; x2,y2=rect.topright; x3,y3=rect.bottomright; x4,y4=rect.bottomleft
    return (seg_intersect(p1,p2,(x1,y1),(x2,y2)) or
            seg_intersect(p1,p2,(x2,y2),(x3,y3)) or
            seg_intersect(p1,p2,(x3,y3),(x4,y4)) or
            seg_intersect(p1,p2,(x4,y4),(x1,y1)))

class SithLord:
    def __init__(self, x, y):
        self.w, self.h = 26, 34
        self.rect = pygame.Rect(x+7, y+6, self.w, self.h)
        self.saber_len = 100
        self.saber_thickness = 12
        self.wiggle_amount = 0.4

    def update(self, player):
        # always face player
        px, py = player.rect.center
        sx, sy = self.rect.center
        dx, dy = px - sx, py - sy
        d = max(1, math.hypot(dx, dy))
        self.ux, self.uy = dx/d, dy/d

        # wiggle effect
        t = pygame.time.get_ticks() * 0.01
        wiggle = math.sin(t) * 0.3

        # rotate direction slightly
        angle = math.atan2(self.uy, self.ux) + wiggle
        self.wx = math.cos(angle)
        self.wy = math.sin(angle)

        # saber endpoints
        self.p1 = (sx, sy)
        self.p2 = (sx + self.wx * self.saber_len,
                   sy + self.wy * self.saber_len)

    def check_hit(self, player):
        # body collision
        if self.rect.colliderect(player.rect):
            return True

        # saber collision (FIXED thickness)
        px, py = player.rect.center
        if point_seg_dist_sq(px, py, *self.p1, *self.p2) < (self.saber_thickness+4)**2:
            return True

        return False

    def draw(self, screen, camx, camy):
        x, y = self.rect.x - camx, self.rect.y - camy

        pygame.draw.rect(screen, RED, (x, y, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (255,150,150), (x+6, y+4, self.w-12, 8), border_radius=3)

        pygame.draw.line(screen, RED,
                         (int(self.p1[0]-camx), int(self.p1[1]-camy)),
                         (int(self.p2[0]-camx), int(self.p2[1]-camy)),
                         self.saber_thickness)
        
    def update(self, player):
        # always face player
        px, py = player.rect.center
        sx, sy = self.rect.center
        dx, dy = px - sx, py - sy
        d = max(1, math.hypot(dx, dy))
        self.ux, self.uy = dx/d, dy/d

        # wiggle effect
        t = pygame.time.get_ticks() * 0.01
        wiggle = math.sin(t) * 0.3

        # rotate direction slightly
        angle = math.atan2(self.uy, self.ux) + wiggle
        self.wx = math.cos(angle)
        self.wy = math.sin(angle)

        # saber endpoints
        self.p1 = (sx, sy)
        self.p2 = (sx + self.wx * self.saber_len,
                   sy + self.wy * self.saber_len)

    def check_hit(self, player):
        # body collision
        if self.rect.colliderect(player.rect):
            return True

        # saber collision
        px, py = player.rect.center
        if point_seg_dist_sq(px, py, *self.p1, *self.p2) < (SABER_THICKNESS+4)**2:
            return True

        return False

    def draw(self, screen, camx, camy):
        x, y = self.rect.x - camx, self.rect.y - camy

        # red body
        pygame.draw.rect(screen, RED, (x, y, self.w, self.h), border_radius=5)

        # helmet stripe
        pygame.draw.rect(screen, (255,150,150), (x+6, y+4, self.w-12, 8), border_radius=3)

        # saber (wiggling)
        pygame.draw.line(screen, RED,
                         (int(self.p1[0]-camx), int(self.p1[1]-camy)),
                         (int(self.p2[0]-camx), int(self.p2[1]-camy)),
                         SABER_THICKNESS)

class Player:
    def __init__(self,x,y):
        self.w,self.h=26,34; self.rect=pygame.Rect(x+7,y+6,self.w,self.h)
        self.vx=self.vy=0.0; self.on_ground=False; self.jumps_left=2
        self.face_dir=1; self.deaths=0; self.time_ms=0
    def update(self,keys,dt, ROWS, COLS, get_tile):
        ax=0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: ax-=1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: ax+=1
        self.vx+=ax*0.8*TIME_SCALE; self.vx*=(FRICTION**TIME_SCALE)
        self.vx=max(-MAX_XSPEED,min(MAX_XSPEED,self.vx))
        if ax!=0: self.face_dir=1 if ax>0 else -1
        self.vy=min(self.vy+GRAVITY*TIME_SCALE,16)
        self.rect.x+=int(round(self.vx*TIME_SCALE))
        for (r,c,ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch=='X':
                t=rect_for_tile(r,c)
                if self.rect.colliderect(t):
                    if self.vx>0: self.rect.right=t.left; self.vx=0
                    elif self.vx<0: self.rect.left=t.right; self.vx=0
        self.rect.y+=int(round(self.vy*TIME_SCALE)); self.on_ground=False
        for (r,c,ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch=='X':
                t=rect_for_tile(r,c)
                if self.rect.colliderect(t):
                    if self.vy>0: self.rect.bottom=t.top; self.vy=0; self.on_ground=True; self.jumps_left=2
                    elif self.vy<0: self.rect.top=t.bottom; self.vy=0
        for (_,_,ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch=='^': request_restart(True)
        self.time_ms+=dt*TIME_SCALE
    def jump(self):
        if self.jumps_left>0: self.vy=-JUMP_SPEED; self.jumps_left-=1



class Turret:
    def __init__(self,r,c):
        self.r=r; self.c=c; self.rect=pygame.Rect(c*TILE+8, r*TILE+8, 24,24)
        self.last_shot=-9999; self.cooldown=BASE_TURRET_COOLDOWN_MS
        self.falling=False; self.vy=0.0; self.fall_start_y=self.rect.y
    def center(self): return (self.rect.centerx,self.rect.centery)
    def player_within_radius(self,player,tiles=FIRE_RADIUS_TILES):
        tcx,tcy=self.center(); pcx,pcy=player.rect.centerx,player.rect.centery
        dx=pcx-tcx; dy=pcy-tcy
        return (dx*dx+dy*dy) <= (tiles*TILE)*(tiles*TILE)
    def start_fall(self, ROWS, COLS, get_tile, set_tile):
        if not self.falling:
            if 0<=self.r<ROWS and 0<=self.c<COLS and get_tile(self.r,self.c)=='^':
                set_tile(self.r,self.c,'.')
            self.falling=True; self.vy=0.0; self.fall_start_y=self.rect.y
            self.r=self.c=-1
    def check_support_and_maybe_fall(self, ROWS, COLS, get_tile):
        if self.falling: return
        below_r = (self.rect.bottom // TILE)
        col = (self.rect.centerx // TILE)
        if below_r >= ROWS or get_tile(below_r, col) == '.':
            self.start_fall(ROWS, COLS, get_tile, lambda r,c,v=None: None)
    def update_fall(self, ROWS, COLS, get_tile, set_tile):
        if not self.falling: return False
        self.vy=min(self.vy+GRAVITY*TIME_SCALE,16); self.rect.y+=int(round(self.vy*TIME_SCALE))
        if (self.rect.y-self.fall_start_y) >= TURRET_FALL_KILL_TILES*TILE: return True
        for (r,c,ch) in tiles_at(self.rect, ROWS, COLS, get_tile):
            if ch=='X':
                t=rect_for_tile(r,c)
                if self.rect.colliderect(t):
                    self.rect.bottom=t.top; self.vy=0.0; self.falling=False
                    self.r=(self.rect.y-8)//TILE; self.c=(self.rect.x-8)//TILE
                    self.r=max(0,min(ROWS-1,int(self.r))); self.c=max(0,min(COLS-1,int(self.c)))
                    if get_tile(self.r,self.c)=='.': set_tile(self.r,self.c,'^')
                    return False
        if self.rect.top > ROWS*TILE: return True
        return False
    def update_and_maybe_shoot(self, player, bolts, ROWS, COLS, get_tile):
        now=pygame.time.get_ticks(); eff=int(self.cooldown/max(TIME_SCALE,1e-3))
        if self.player_within_radius(player) and now-self.last_shot>=eff:
            self.last_shot=now
            cx,cy=self.center(); tx,ty=player.rect.centerx,player.rect.centery
            dx,dy=tx-cx, ty-cy; d=max(1.0, math.hypot(dx,dy)); ux,uy=dx/d, dy/d
            spawn_x=cx+ux*(self.rect.w/2+4); spawn_y=cy+uy*(self.rect.h/2+4)
            bolts.append(Bolt(spawn_x,spawn_y,ux*BOLT_SPEED,uy*BOLT_SPEED))

class Bolt:
    def __init__(self,x,y,vx,vy):
        self.x=float(x); self.y=float(y); self.vx=float(vx); self.vy=float(vy)
        self.r=4; self.alive=True; self.friendly=False
    def rect(self): return pygame.Rect(int(self.x)-self.r,int(self.y)-self.r,self.r*2,self.r*2)
    def update(self, ROWS, COLS, get_tile):
        if not self.alive: return
        self.x+=self.vx*TIME_SCALE; self.y+=self.vy*TIME_SCALE
        if self.x<-10 or self.x>COLS*TILE+10 or self.y<-10 or self.y>ROWS*TILE+10: self.alive=False; return
        r=int(self.y)//TILE; c=int(self.x)//TILE
        if 0<=r<ROWS and 0<=c<COLS and get_tile(r,c) in ('X','B'): self.alive=False

def tiles_at(rect, ROWS, COLS, get_tile):
    tiles=[]; left=max(0, rect.left//TILE); right=min(COLS-1, rect.right//TILE)
    top=max(0, rect.top//TILE); bottom=min(ROWS-1, rect.bottom//TILE)
    for r in range(top, bottom+1):
        for c in range(left, right+1):
            tiles.append((r,c,get_tile(r,c)))
    return tiles

def parkour_stage(which_map="old"):
    base = OLD_LEVEL if which_map=="old" else NEW_LEVEL
    LEVEL, ROWS, COLS = normalize_and_floor(base)
    level_grid = [list(row) for row in LEVEL]

    def get_tile(r,c): 
        if 0<=r<ROWS and 0<=c<COLS: return level_grid[r][c]
        return '.'
    def set_tile(r,c,val):
        if 0<=r<ROWS and 0<=c<COLS: level_grid[r][c]=val

    START_POS, GOAL_POS, spawns, sith_spawns = scan_entities(level_grid, ROWS, COLS)
    sr,sc = START_POS[1]//TILE, START_POS[0]//TILE
    if get_tile(sr,sc)=='P': set_tile(sr,sc,'.')

    turrets=[Turret(r,c) for (r,c) in spawns]
    siths = [SithLord(c*TILE, r*TILE) for (r,c) in sith_spawns]
    sith_lords=[SithLord(c*TILE, r*TILE) for (r,c) in sith_spawns]
    bolts=[]
    player=Player(*START_POS)
    camx=camy=0.0
    win=False
    RESET_REQUESTED=False
    DEATH_PENDING=False

    def request_restart(death=False):
        nonlocal RESET_REQUESTED, DEATH_PENDING
        RESET_REQUESTED=True; DEATH_PENDING=death

    def restart_run():
        nonlocal level_grid, turrets, bolts, player, camx, camy, win, RESET_REQUESTED, DEATH_PENDING, siths
        level_grid=[list(row) for row in LEVEL]
        START, GOAL, sp, sps = scan_entities(level_grid, ROWS, COLS)
        siths = [SithLord(c*TILE, r*TILE) for (r,c) in sps]
        sr,sc=START[1]//TILE, START[0]//TILE
        if get_tile(sr,sc)=='P': set_tile(sr,sc,'.')
        deaths = player.deaths + (1 if DEATH_PENDING else 0)
        player = Player(*START); player.deaths = deaths
        turrets=[Turret(r,c) for (r,c) in sp]; bolts=[]
        camx=camy=0.0; win=False; RESET_REQUESTED=False; DEATH_PENDING=False
        return START, GOAL

    running=True
    while running:
        dt=clock.tick(60)
        if RESET_REQUESTED:
            START_POS, GOAL_POS = restart_run()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            elif e.type==pygame.KEYDOWN:
                if e.key==pygame.K_c: toggle_slow()
                if e.key in (pygame.K_w, pygame.K_UP): player.jump()
                if e.key==pygame.K_x: force_push(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                if e.key==pygame.K_v: force_pull(player, bolts, turrets, ROWS, COLS, get_tile, set_tile)
                if e.key==pygame.K_r:
                    request_restart(False)
                if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()

        keys = pygame.key.get_pressed()
        player.update(keys, dt, ROWS, COLS, get_tile)

        # --- Calculate player saber FIRST ---
        mx, my = pygame.mouse.get_pos()
        mxw, myw = mx + camx, my + camy
        pcx, pcy = player.rect.centerx, player.rect.centery

        dx, dy = mxw - pcx, myw - pcy
        d = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / d, dy / d

        saber_p1 = (pcx, pcy)
        saber_p2 = (pcx + ux * SABER_LEN, pcy + uy * SABER_LEN)

        # --- Sith update loop ---
        for s in siths[:]:
            s.update(player)
            if seg_intersects_rect(saber_p1, saber_p2, s.rect):
                siths.remove(s)
                continue
            if seg_intersect(saber_p1, saber_p2, s.p1, s.p2):
                continue  # sabers clashing: sith blocked
            if s.check_hit(player):
                request_restart(True)
                break

        # --- Every-frame updates (camera, turrets, bolts) ---
        for t in turrets[:]: t.check_support_and_maybe_fall(ROWS, COLS, get_tile)
        for t in turrets[:]:
            if t.update_fall(ROWS, COLS, get_tile, set_tile): turrets.remove(t)
        for t in turrets[:]: t.update_and_maybe_shoot(player, bolts, ROWS, COLS, get_tile)
        for b in bolts:
            if b.alive: b.update(ROWS, COLS, get_tile)

        camx, camy = center_camera_on_player(camx, camy, player, ROWS, COLS)

        mx,my=pygame.mouse.get_pos(); mxw,myw=mx+camx, my+camy
        pcx,pcy=player.rect.centerx, player.rect.centery
        dx,dy=mxw-pcx,myw-pcy; d=max(1.0, math.hypot(dx,dy)); ux,uy=dx/d, dy/d
        saber_p1=(pcx,pcy); saber_p2=(pcx+ux*SABER_LEN, pcy+uy*SABER_LEN)

        lmb,_,rmb=pygame.mouse.get_pressed(3); thresh_sq=(SABER_THICKNESS/2+4)**2
        for b in bolts:
            if not b.alive: continue
            if point_seg_dist_sq(b.x,b.y,*saber_p1,*saber_p2)<=thresh_sq:
                if rmb: b.alive=False
                else: b.vx*=-1; b.vy*=-1; b.friendly=True
                continue
            if not b.friendly and b.rect().colliderect(player.rect):
                b.alive=False; request_restart(True)

        for b in bolts:
            if not b.alive or not b.friendly: continue
            for t in turrets[:]:
                if t.rect.colliderect(b.rect()):
                    if (not t.falling) and 0<=t.r<ROWS and 0<=t.c<COLS and get_tile(t.r,t.c)=='^':
                        set_tile(t.r,t.c,'.')
                    turrets.remove(t); b.alive=False; break

        minx=int(max(0,(min(saber_p1[0],saber_p2[0])-SABER_THICKNESS)//TILE))
        maxx=int(min(COLS-1,(max(saber_p1[0],saber_p2[0])+SABER_THICKNESS)//TILE))
        miny=int(max(0,(min(saber_p1[1],saber_p2[1])-SABER_THICKNESS)//TILE))
        maxy=int(min(ROWS-1,(max(saber_p1[1],saber_p2[1])+SABER_THICKNESS)//TILE))
        for r in range(miny,maxy+1):
            for c in range(minx,maxx+1):
                if get_tile(r,c)=='B' and seg_intersects_rect(saber_p1,saber_p2,rect_for_tile(r,c)):
                    set_tile(r,c,'.')

        bolts=[b for b in bolts if b.alive]

        for (r,c,ch) in tiles_at(player.rect, ROWS, COLS, get_tile):
            if ch=='G': win=True; break

        # ----- Draw -----
        screen.fill(BLACK)
        draw_level(level_grid, ROWS, COLS, camx, camy)
        draw_falling_turrets(turrets, camx, camy)
        draw_bolts(bolts, camx, camy)
        draw_player(player, camx, camy, saber_p1, saber_p2)
        for s in siths:
            s.draw(screen, camx, camy)
        t=player.time_ms/1000.0
        screen.blit(FONT.render(f"Deaths: {player.deaths}",True,WHITE),(10,10))
        screen.blit(FONT.render(f"Time: {t:05.2f}s   Speed x{TIME_SCALE:.2f} (C toggles)",True,WHITE),(10,30))
        screen.blit(FONT.render("Move A/D or L/R  Jump W/Up  Saber:mouse LMB reflect/RMB destroy  Push X  Pull V  R restart",True,(250,220,80)),(10,HEIGHT-28))
        if win:
            msg=BIG.render("You cleared the stronghold!",True,WHITE)
            sub=FONT.render("Press R to try again.",True,WHITE)
            screen.blit(msg,(WIDTH//2-msg.get_width()//2,70)); screen.blit(sub,(WIDTH//2-sub.get_width()//2,110))
        pygame.display.flip()

# ---- Drawing helpers for parkour ----
def draw_level(level_grid, ROWS, COLS, camx, camy):
    c0=max(0,int(camx//TILE)-2); c1=min(COLS, int((camx+WIDTH)//TILE)+3)
    r0=max(0,int(camy//TILE)-2); r1=min(ROWS, int((camy+HEIGHT)//TILE)+3)
    for r in range(r0,r1):
        for c in range(c0,c1):
            ch=level_grid[r][c]; x,y=c*TILE-camx, r*TILE-camy
            if ch=='X':
                pygame.draw.rect(screen,GREY,(x,y,TILE,TILE))
                pygame.draw.rect(screen,(40,43,47),(x,y,TILE,TILE),2)
            elif ch=='^':
                pts=[(x,y+TILE-2),(x+TILE//2,y+4),(x+TILE-1,y+TILE-2)]
                pygame.draw.polygon(screen,RED,pts); pygame.draw.polygon(screen,BLACK,pts,2)
            elif ch=='B':
                pygame.draw.rect(screen,(170,30,30),(x+6,y+6,TILE-12,TILE-12),border_radius=8)
                pygame.draw.rect(screen,(255,120,120),(x+10,y+10,TILE-20,TILE-20),2,border_radius=6)
            elif ch=='G':
                pygame.draw.rect(screen,(20,120,70),(x,y,TILE,TILE))
                pygame.draw.rect(screen,(40,180,110),(x+6,y+6,TILE-12,TILE-12),2,border_radius=8)

def draw_falling_turrets(turrets, camx, camy):
    for t in turrets:
        if not t.falling: continue
        cx,cy=t.rect.centerx-camx, t.rect.centery-camy; half=TILE//2-2
        pts=[(cx-half,cy+half),(cx,cy-half),(cx+half,cy+half)]
        pygame.draw.polygon(screen,RED,pts); pygame.draw.polygon(screen,BLACK,pts,2)

def draw_bolts(bolts, camx, camy):
    for b in bolts:
        if not b.alive: continue
        color = YELLOW if b.friendly else RED
        pygame.draw.circle(screen, color, (int(b.x-camx), int(b.y-camy)), b.r)

def draw_player(p, camx, camy, p1, p2):
    x,y=p.rect.x-camx, p.rect.y-camy
    pygame.draw.rect(screen,BLUE,(x,y,p.w,p.h),border_radius=5)
    pygame.draw.rect(screen,(230,230,255),(x+6,y+4,p.w-12,8),border_radius=3)
    pygame.draw.line(screen,CYAN,(int(p1[0]-camx),int(p1[1]-camy)),(int(p2[0]-camx),int(p2[1]-camy)),SABER_THICKNESS)
    pygame.draw.circle(screen,CYAN,(int(p.rect.centerx-camx),int(p.rect.centery-camy)),3)

def center_camera_on_player(camx,camy,p, ROWS, COLS):
    tx=p.rect.centerx-WIDTH/2; ty=p.rect.centery-HEIGHT/2
    camx+=(tx-camx)*0.08; camy+=(ty-camy)*0.08
    camx=max(0,min(COLS*TILE-WIDTH,camx)); camy=max(0,min(ROWS*TILE-HEIGHT,camy))
    return camx,camy

# ---- Force powers (horizontal line) ----
FORCE_TURRET_STEPS=3; FORCE_BOLT_IMPULSE=6.0
FORCE_RADIUS_TILES=10; FORCE_RADIUS_PX=FORCE_RADIUS_TILES*TILE; FORCE_BLOCKED_TILES=set(['X','B','G'])
def within_force_line(px,py,x,y): return (abs(y-py)<=TILE) and (abs(x-px)<=FORCE_RADIUS_PX)

def slide_turret_horiz_by_tiles(t,step_c,steps, ROWS, COLS, get_tile, set_tile):
    if step_c==0 or t.falling: return
    for _ in range(steps):
        nr=t.r; nc=t.c+step_c
        if not (0<=nr<ROWS and 0<=nc<COLS): t.start_fall(ROWS, COLS, get_tile, set_tile); break
        ch=get_tile(nr,nc)
        if ch in FORCE_BLOCKED_TILES or ch=='^': break
        set_tile(t.r,t.c,'.'); set_tile(nr,nc,'^')
        t.r,t.c=nr,nc; t.rect.topleft=(t.c*TILE+8, t.r*TILE+8)
        below=t.r+1
        if below>=ROWS or get_tile(below,t.c)=='.':
            t.start_fall(ROWS, COLS, get_tile, set_tile); break

def force_push(player, bolts, turrets, ROWS, COLS, get_tile, set_tile):
    px,py=player.rect.centerx,player.rect.centery
    for b in bolts:
        if b.alive and within_force_line(px,py,b.x,b.y):
            direction=1 if b.x>px else -1
            b.vx=direction*max(abs(b.vx),FORCE_BOLT_IMPULSE); b.friendly=True
    for t in turrets:
        cx,cy=t.center()
        if within_force_line(px,py,cx,cy):
            slide_turret_horiz_by_tiles(t, 1 if cx>px else -1, FORCE_TURRET_STEPS, ROWS, COLS, get_tile, set_tile)

def force_pull(player, bolts, turrets, ROWS, COLS, get_tile, set_tile):
    px,py=player.rect.centerx,player.rect.centery
    for b in bolts:
        if b.alive and within_force_line(px,py,b.x,b.y):
            direction=-1 if b.x>px else 1
            b.vx=direction*max(abs(b.vx),FORCE_BOLT_IMPULSE); b.friendly=True
    for t in turrets:
        cx,cy=t.center()
        if within_force_line(px,py,cx,cy):
            slide_turret_horiz_by_tiles(t, -1 if cx>px else 1, FORCE_TURRET_STEPS, ROWS, COLS, get_tile, set_tile)

# ============================================================
#                           MAIN
# ============================================================
if __name__=="__main__":
    while True:
        result = space_stage()
        if result == "space_dead":
            # crashed into Destroyer hull or collided with a TIE -> restart space
            continue
        elif result == "landed_destroyer":
            # Entered hangar: go to OLD map
            parkour_stage("old")
        elif result == "planet_touch":
            # Actually touched planet while falling: go to NEW map
            parkour_stage("new")
        pygame.quit(); sys.exit()