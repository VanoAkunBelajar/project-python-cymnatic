"""
ECHO LOOP  -  time-loop arena shooter (pygame)

Every 8 seconds time loops. Each finished loop becomes an ECHO: a ghost that
replays exactly what you did (movement + every shot) and fights beside you.
Up to 5 echoes stack at once, so plan your runs: a loop where you strafe and
shoot a lane becomes a turret-ghost covering that lane forever.

  - Red/orange enemies chase the NEAREST body - echoes act as decoys.
    Touching an echo shatters it for the rest of the loop (it returns next loop).
  - Purple LEECHES hunt echoes and devour them PERMANENTLY. Kill them first.
  - Yellow shooters keep distance and fire at you.

Controls:
  WASD / Arrows  move
  Mouse          aim
  Left click     shoot (hold)
  Space / Shift  dash (invulnerable while dashing)
  P / Esc        pause

Run:  python echo_loop.py   (needs: pip install pygame)
"""

import math
import os
import random
import sys

import pygame

V = pygame.math.Vector2

# ---------------------------------------------------------------- config ---
W, H = 960, 640
FPS = 60
LOOP_SECONDS = 8
LOOP_FRAMES = LOOP_SECONDS * FPS
MAX_ECHOES = 5
TOP = 56
ARENA = pygame.Rect(16, TOP + 8, W - 32, H - TOP - 24)

PLAYER_R = 11
ECHO_R = 11
PLAYER_SPEED = 3.6
DASH_SPEED = 11.0
DASH_FRAMES = 9
DASH_COOLDOWN = 55
FIRE_COOLDOWN = 8
BULLET_SPEED = 10.0
MAX_HP = 5
START_HP = 3
INVULN_FRAMES = 90
COMBO_WINDOW = 100
MAX_PICKUPS = 3
MAX_ENEMIES = 60

BG = (9, 9, 18)
GRID = (20, 20, 38)
WALL = (70, 70, 130)
WHITE = (235, 235, 245)
DIM = (120, 120, 150)
BAR_BG = (14, 14, 28)
PLAYER_C = (130, 245, 255)
ECHO_C = (90, 150, 255)
FRIEND_BULLET = (210, 250, 255)
ECHO_BULLET = (120, 165, 255)
ENEMY_BULLET = (255, 210, 90)
HEART_C = (255, 90, 130)
REC_C = (255, 60, 70)

ENEMY_TYPES = {
    "chaser":   dict(r=12, hp=2,  speed=2.0,  color=(255, 80, 80),   value=10),
    "mini":     dict(r=7,  hp=1,  speed=2.9,  color=(255, 150, 120), value=5),
    "splitter": dict(r=17, hp=5,  speed=1.5,  color=(80, 230, 140),  value=25),
    "shooter":  dict(r=13, hp=3,  speed=1.8,  color=(255, 205, 70),  value=30),
    "leech":    dict(r=11, hp=3,  speed=2.4,  color=(200, 90, 255),  value=35),
    "brute":    dict(r=24, hp=14, speed=1.05, color=(255, 130, 40),  value=60),
}

HIGHSCORE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "echo_loop_highscore.txt")


# --------------------------------------------------------------- helpers ---
def clamp_to_arena(pos, r):
    pos.x = max(ARENA.left + r, min(ARENA.right - r, pos.x))
    pos.y = max(ARENA.top + r, min(ARENA.bottom - r, pos.y))


def heart_points(cx, cy, size):
    pts = []
    k = size / 17.0
    for i in range(24):
        t = i / 24 * math.tau
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * k, cy - y * k))
    return pts


def draw_heart(surf, cx, cy, size, color, filled=True):
    pygame.draw.polygon(surf, color, heart_points(cx, cy, size), 0 if filled else 2)


def regular_poly(cx, cy, r, n, rot=0.0):
    return [(cx + math.cos(rot + i / n * math.tau) * r,
             cy + math.sin(rot + i / n * math.tau) * r) for i in range(n)]


# ---------------------------------------------------------------- entities ---
class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "color", "size", "drag")

    def __init__(self, pos, vel, life, color, size, drag=0.9):
        self.pos = V(pos)
        self.vel = V(vel)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.drag = drag

    def update(self):
        self.pos += self.vel
        self.vel *= self.drag
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        r = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), r)


class Bullet:
    __slots__ = ("pos", "vel", "color", "friendly", "r", "life", "dead")

    def __init__(self, pos, vel, color, friendly, r=4, life=90):
        self.pos = V(pos)
        self.vel = V(vel)
        self.color = color
        self.friendly = friendly
        self.r = r
        self.life = life
        self.dead = False

    def update(self):
        self.pos += self.vel
        self.life -= 1
        if self.life <= 0 or not ARENA.collidepoint(self.pos.x, self.pos.y):
            self.dead = True

    def draw(self, surf):
        p = (int(self.pos.x), int(self.pos.y))
        tail = self.pos - self.vel * 1.3
        pygame.draw.line(surf, self.color, p, (int(tail.x), int(tail.y)), 2)
        pygame.draw.circle(surf, self.color, p, self.r)


class Echo:
    def __init__(self, frames, number):
        self.frames = frames          # list of (x, y, angle, fired)
        self.number = number
        self.alive = True             # False = shattered for this loop
        self.gone = False             # True = devoured forever
        self.pos = V(frames[0][0], frames[0][1])
        self.angle = frames[0][2]


class Enemy:
    def __init__(self, kind, pos, speed_mult):
        d = ENEMY_TYPES[kind]
        self.kind = kind
        self.pos = V(pos)
        self.r = d["r"]
        self.hp = d["hp"]
        self.max_hp = d["hp"]
        self.speed = d["speed"] * speed_mult * random.uniform(0.9, 1.1)
        self.color = d["color"]
        self.value = d["value"]
        self.flash = 0
        self.fire_timer = random.randint(70, 130)
        self.strafe = random.choice((-1, 1))
        self.wobble = random.uniform(0, math.tau)
        self.knock = V()
        self.facing = 0.0


# ------------------------------------------------------------------- game ---
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ECHO LOOP")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((W, H))
        self.glow = pygame.Surface((W, H), pygame.SRCALPHA)
        self.font_huge = pygame.font.SysFont("consolas", 72, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 44, bold=True)
        self.font_med = pygame.font.SysFont("consolas", 24, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 17)
        self.bg = self.make_background()
        self.highscore = self.load_highscore()
        self.state = "menu"
        self.state_t = 0
        self.menu_dots = [[random.uniform(0, W), random.uniform(0, H),
                           random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6)]
                          for _ in range(40)]
        pygame.mouse.set_visible(False)
        self.reset()

    # ---------------------------------------------------------- persistence
    def load_highscore(self):
        try:
            with open(HIGHSCORE_FILE, "r", encoding="utf-8") as fh:
                return max(0, int(fh.read().strip() or 0))
        except (OSError, ValueError):
            return 0

    def save_highscore(self):
        try:
            with open(HIGHSCORE_FILE, "w", encoding="utf-8") as fh:
                fh.write(str(self.highscore))
        except OSError:
            pass

    # ---------------------------------------------------------------- setup
    def make_background(self):
        surf = pygame.Surface((W, H))
        surf.fill(BG)
        for x in range(ARENA.left, ARENA.right, 40):
            pygame.draw.line(surf, GRID, (x, ARENA.top), (x, ARENA.bottom))
        for y in range(ARENA.top, ARENA.bottom, 40):
            pygame.draw.line(surf, GRID, (ARENA.left, y), (ARENA.right, y))
        pygame.draw.rect(surf, WALL, ARENA, 2)
        return surf

    def reset(self):
        self.player_pos = V(ARENA.center)
        self.hp = START_HP
        self.inv = 0
        self.dash_timer = 0
        self.dash_cd = 0
        self.dash_dir = V(1, 0)
        self.fire_cd = 0
        self.aim = 0.0
        self.move = V()
        self.record = []
        self.loop_frame = 0
        self.loop_count = 1
        self.echo_serial = 0
        self.echoes = []
        self.enemies = []
        self.pending_enemies = []
        self.bullets = []
        self.particles = []
        self.popups = []       # [pos, text, color, life]
        self.rings = []        # [pos, radius, color]
        self.warnings = []     # [pos, kind, timer]
        self.pickups = []      # [pos, life]
        self.score = 0
        self.combo = 0
        self.combo_timer = 0
        self.mult = 1
        self.total_frames = 0
        self.spawn_timer = 80
        self.shake = 0.0
        self.banner = None     # [text, color, life]
        self.kills = 0
        self.echoes_lost = 0
        self.new_best = False
        self.set_banner("LOOP 1", PLAYER_C)

    def set_state(self, s):
        self.state = s
        self.state_t = 0

    def set_banner(self, text, color, life=80):
        self.banner = [text, color, life]

    # --------------------------------------------------------------- events
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.quit()

        if self.state == "play" and ev.type == pygame.WINDOWFOCUSLOST:
            self.set_state("pause")
            return

        if self.state == "menu":
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.reset()
                    self.set_state("play")
                elif ev.key == pygame.K_ESCAPE:
                    self.quit()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.state_t > 15:
                self.reset()
                self.set_state("play")

        elif self.state == "play":
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.set_state("pause")
                elif ev.key in (pygame.K_SPACE, pygame.K_LSHIFT, pygame.K_RSHIFT):
                    self.try_dash()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                self.try_dash()

        elif self.state == "pause":
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.set_state("play")
                elif ev.key == pygame.K_q:
                    self.set_state("menu")

        elif self.state == "over":
            if ev.type == pygame.KEYDOWN and self.state_t > 40:
                if ev.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.reset()
                    self.set_state("play")
                elif ev.key == pygame.K_ESCAPE:
                    self.set_state("menu")

    def try_dash(self):
        if self.dash_cd > 0 or self.dash_timer > 0:
            return
        if self.move.length_squared() > 0:
            self.dash_dir = V(self.move)
        else:
            self.dash_dir = V(math.cos(self.aim), math.sin(self.aim))
        self.dash_timer = DASH_FRAMES
        self.dash_cd = DASH_COOLDOWN
        for _ in range(10):
            self.particles.append(Particle(self.player_pos, V(random.uniform(-2, 2), random.uniform(-2, 2)),
                                           18, PLAYER_C, 4))

    # --------------------------------------------------------------- update
    def update(self):
        self.total_frames += 1
        f = self.loop_frame

        self.update_player()
        self.update_echoes(f)
        self.update_spawning()
        self.update_enemies()

        for b in self.bullets:
            b.update()
        self.collide()

        if self.pending_enemies:
            self.enemies.extend(self.pending_enemies)
            self.pending_enemies = []
        self.enemies = [e for e in self.enemies if e.hp > 0]
        self.bullets = [b for b in self.bullets if not b.dead]

        self.update_pickups()
        self.update_fx()

        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer == 0:
                self.combo = 0
                self.mult = 1

        if self.state != "play":      # died this frame
            return

        self.loop_frame += 1
        if self.loop_frame >= LOOP_FRAMES:
            self.end_loop()

    def update_player(self):
        keys = pygame.key.get_pressed()
        move = V(0, 0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1
        if move.length_squared() > 0:
            move = move.normalize()
        self.move = move

        if self.dash_timer > 0:
            self.player_pos += self.dash_dir * DASH_SPEED
            self.dash_timer -= 1
            self.particles.append(Particle(self.player_pos, V(), 14, ECHO_C, PLAYER_R - 2, 1.0))
        else:
            self.player_pos += move * PLAYER_SPEED
        clamp_to_arena(self.player_pos, PLAYER_R)

        if self.dash_cd > 0:
            self.dash_cd -= 1
        if self.inv > 0:
            self.inv -= 1
        if self.fire_cd > 0:
            self.fire_cd -= 1

        mx, my = pygame.mouse.get_pos()
        dx, dy = mx - self.player_pos.x, my - self.player_pos.y
        if dx * dx + dy * dy > 4:
            self.aim = math.atan2(dy, dx)

        fired = False
        if pygame.mouse.get_pressed()[0] and self.fire_cd == 0:
            self.fire_cd = FIRE_COOLDOWN
            self.shoot(self.player_pos, self.aim, FRIEND_BULLET)
            fired = True
        self.record.append((self.player_pos.x, self.player_pos.y, self.aim, fired))

    def shoot(self, pos, angle, color):
        d = V(math.cos(angle), math.sin(angle))
        self.bullets.append(Bullet(pos + d * (PLAYER_R + 4), d * BULLET_SPEED, color, True))

    def update_echoes(self, f):
        for e in self.echoes:
            if e.gone or f >= len(e.frames):
                continue
            x, y, a, fired = e.frames[f]
            e.pos.update(x, y)
            e.angle = a
            if e.alive and fired:
                self.shoot(e.pos, a, ECHO_BULLET)

    def live_echoes(self):
        return [e for e in self.echoes if e.alive and not e.gone]

    def nearest(self, pos, candidates):
        best, best_d = None, float("inf")
        for c in candidates:
            d = (c - pos).length_squared()
            if d < best_d:
                best, best_d = c, d
        return best

    def update_spawning(self):
        t = self.total_frames / FPS
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn_timer = int(max(16, 72 - t * 0.75))
            n = 1
            if t > 50 and random.random() < 0.35:
                n += 1
            if t > 110 and random.random() < 0.35:
                n += 1
            for _ in range(n):
                self.queue_spawn(self.pick_kind(t))

        for w in self.warnings:
            w[2] -= 1
            if w[2] <= 0:
                speed_mult = 1 + min(t / 200.0, 0.5)
                self.pending_enemies.append(Enemy(w[1], w[0], speed_mult))
        self.warnings = [w for w in self.warnings if w[2] > 0]

    def pick_kind(self, t):
        table = [("chaser", 10)]
        if t > 18:
            table.append(("splitter", 4))
        if t > 32:
            table.append(("shooter", 3))
        if self.loop_count >= 3 and self.echoes:
            table.append(("leech", 3))
        if t > 60:
            table.append(("brute", 2))
        total = sum(w for _, w in table)
        roll = random.uniform(0, total)
        for kind, w in table:
            roll -= w
            if roll <= 0:
                return kind
        return "chaser"

    def queue_spawn(self, kind):
        if len(self.enemies) + len(self.pending_enemies) + len(self.warnings) >= MAX_ENEMIES:
            return
        pos = None
        for _ in range(25):
            side = random.randint(0, 3)
            m = 30
            if side == 0:
                p = V(random.uniform(ARENA.left + m, ARENA.right - m), ARENA.top + m)
            elif side == 1:
                p = V(random.uniform(ARENA.left + m, ARENA.right - m), ARENA.bottom - m)
            elif side == 2:
                p = V(ARENA.left + m, random.uniform(ARENA.top + m, ARENA.bottom - m))
            else:
                p = V(ARENA.right - m, random.uniform(ARENA.top + m, ARENA.bottom - m))
            if (p - self.player_pos).length() > 190:
                pos = p
                break
        if pos is None:   # fallback: far corner from player
            pos = V(ARENA.left + 30 if self.player_pos.x > ARENA.centerx else ARENA.right - 30,
                    ARENA.top + 30 if self.player_pos.y > ARENA.centery else ARENA.bottom - 30)
        self.warnings.append([pos, kind, 50])

    def update_enemies(self):
        live = self.live_echoes()
        bodies = [self.player_pos] + [e.pos for e in live]
        echo_bodies = [e.pos for e in live]

        for e in self.enemies:
            if e.flash > 0:
                e.flash -= 1
            e.wobble += 0.12

            if e.kind == "leech":
                target = self.nearest(e.pos, echo_bodies) or self.player_pos
            elif e.kind == "shooter":
                target = self.player_pos
            else:
                target = self.nearest(e.pos, bodies)

            to = target - e.pos
            dist = to.length()
            d = to / dist if dist > 0.001 else V(0, 0)

            if e.kind == "shooter":
                if dist > 290:
                    vel = d * e.speed
                elif dist < 200:
                    vel = -d * e.speed
                else:
                    vel = V(-d.y, d.x) * e.strafe * e.speed * 0.8
                e.fire_timer -= 1
                if e.fire_timer <= 0:
                    e.fire_timer = random.randint(95, 135)
                    self.bullets.append(Bullet(e.pos + d * (e.r + 5), d * 4.3, ENEMY_BULLET, False, r=5, life=220))
            else:
                vel = d * e.speed
                if e.kind in ("chaser", "mini"):
                    vel += V(-d.y, d.x) * math.sin(e.wobble) * 0.7

            if vel.length_squared() > 0:
                e.facing = math.atan2(vel.y, vel.x)
            e.pos += vel + e.knock
            e.knock *= 0.8
            before = V(e.pos)
            clamp_to_arena(e.pos, e.r)
            if e.kind == "shooter" and before != e.pos:
                e.strafe *= -1

        # soft separation so enemies don't stack into one blob
        en = self.enemies
        for i in range(len(en)):
            a = en[i]
            for j in range(i + 1, len(en)):
                b = en[j]
                dx = b.pos.x - a.pos.x
                dy = b.pos.y - a.pos.y
                md = a.r + b.r
                d2 = dx * dx + dy * dy
                if 0.0001 < d2 < md * md:
                    dd = math.sqrt(d2)
                    push = (md - dd) / (2 * dd)
                    a.pos.x -= dx * push
                    a.pos.y -= dy * push
                    b.pos.x += dx * push
                    b.pos.y += dy * push

    # ------------------------------------------------------------ collision
    def can_hurt(self):
        return self.state == "play" and self.inv == 0 and self.dash_timer == 0

    def collide(self):
        # friendly bullets -> enemies
        for b in self.bullets:
            if b.dead or not b.friendly:
                continue
            for e in self.enemies:
                if e.hp <= 0:
                    continue
                rr = e.r + b.r
                if (e.pos - b.pos).length_squared() < rr * rr:
                    b.dead = True
                    e.hp -= 1
                    e.flash = 5
                    if e.kind != "brute" and b.vel.length_squared() > 0:
                        e.knock += b.vel.normalize() * 1.6
                    for _ in range(3):
                        self.particles.append(Particle(b.pos, -b.vel * 0.2 + V(random.uniform(-2, 2), random.uniform(-2, 2)),
                                                       10, b.color, 3))
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    break

        # enemy bullets -> player / echoes
        for b in self.bullets:
            if b.dead or b.friendly:
                continue
            rr = PLAYER_R + b.r - 2
            if (self.player_pos - b.pos).length_squared() < rr * rr and self.can_hurt():
                b.dead = True
                self.hurt()
                continue
            for ec in self.live_echoes():
                rr = ECHO_R + b.r
                if (ec.pos - b.pos).length_squared() < rr * rr:
                    b.dead = True
                    self.shatter(ec)
                    break

        # enemy bodies -> player / echoes
        for e in self.enemies:
            if e.hp <= 0:
                continue
            rr = e.r + PLAYER_R - 2
            off = self.player_pos - e.pos
            if off.length_squared() < rr * rr and self.can_hurt():
                self.hurt()
                if off.length_squared() > 0:
                    e.knock -= off.normalize() * 7
            for ec in self.live_echoes():
                rr = e.r + ECHO_R
                if (ec.pos - e.pos).length_squared() < rr * rr:
                    if e.kind == "leech":
                        self.devour(ec, e)
                    else:
                        self.shatter(ec)
                        e.hp -= 2
                        e.flash = 5
                        if e.hp <= 0:
                            self.kill_enemy(e)
                            break

    def hurt(self):
        self.hp -= 1
        self.inv = INVULN_FRAMES
        self.shake = max(self.shake, 14)
        self.combo = 0
        self.combo_timer = 0
        self.mult = 1
        for _ in range(26):
            a = random.uniform(0, math.tau)
            s = random.uniform(1, 6)
            self.particles.append(Particle(self.player_pos, V(math.cos(a) * s, math.sin(a) * s), 30, HEART_C, 4))
        if self.hp <= 0:
            self.game_over()

    def shatter(self, ec):
        ec.alive = False
        for _ in range(14):
            a = random.uniform(0, math.tau)
            s = random.uniform(1, 4)
            self.particles.append(Particle(ec.pos, V(math.cos(a) * s, math.sin(a) * s), 24, ECHO_C, 3))
        self.popups.append([V(ec.pos), "shattered", DIM, 45])

    def devour(self, ec, leech):
        ec.gone = True
        self.echoes_lost += 1
        leech.hp += 2
        leech.max_hp += 2
        leech.r = min(leech.r + 3, 22)
        leech.flash = 8
        self.shake = max(self.shake, 8)
        for _ in range(30):
            a = random.uniform(0, math.tau)
            s = random.uniform(1, 5)
            self.particles.append(Particle(ec.pos, V(math.cos(a) * s, math.sin(a) * s), 35, (200, 90, 255), 4))
        self.set_banner("ECHO %d DEVOURED" % ec.number, (200, 90, 255), 70)

    def kill_enemy(self, e):
        self.kills += 1
        self.combo += 1
        self.combo_timer = COMBO_WINDOW
        self.mult = min(8, 1 + self.combo // 5)
        gained = e.value * self.mult
        self.score += gained
        self.popups.append([V(e.pos), "+%d" % gained, e.color, 40])
        big = e.kind in ("brute", "splitter")
        for _ in range(26 if big else 14):
            a = random.uniform(0, math.tau)
            s = random.uniform(1, 6 if big else 4)
            self.particles.append(Particle(e.pos, V(math.cos(a) * s, math.sin(a) * s), 28, e.color, 4 if big else 3))
        self.shake = max(self.shake, 9 if e.kind == "brute" else 3)

        t = self.total_frames / FPS
        speed_mult = 1 + min(t / 200.0, 0.5)
        if e.kind == "splitter":
            for s in (-1, 1):
                self.pending_enemies.append(Enemy("mini", e.pos + V(s * 10, -s * 6), speed_mult))
        elif e.kind == "brute":
            for i in range(4):
                a = i / 4 * math.tau
                self.pending_enemies.append(Enemy("mini", e.pos + V(math.cos(a), math.sin(a)) * 14, speed_mult))

        chance = 0.3 if e.kind == "brute" else 0.045
        if random.random() < chance and len(self.pickups) < MAX_PICKUPS:
            self.pickups.append([V(e.pos), 540])

    def update_pickups(self):
        for p in self.pickups:
            p[1] -= 1
            rr = PLAYER_R + 11
            if (p[0] - self.player_pos).length_squared() < rr * rr:
                p[1] = 0
                if self.hp < MAX_HP:
                    self.hp += 1
                    self.popups.append([V(p[0]), "+1 HP", HEART_C, 50])
                else:
                    self.score += 150
                    self.popups.append([V(p[0]), "+150", HEART_C, 50])
        self.pickups = [p for p in self.pickups if p[1] > 0]

    def update_fx(self):
        self.particles = [p for p in self.particles if p.update()]
        if len(self.particles) > 900:
            self.particles = self.particles[-900:]
        for p in self.popups:
            p[0].y -= 0.6
            p[3] -= 1
        self.popups = [p for p in self.popups if p[3] > 0]
        for r in self.rings:
            r[1] += 14
        self.rings = [r for r in self.rings if r[1] < 900]
        self.shake *= 0.85
        if self.shake < 0.3:
            self.shake = 0
        if self.banner:
            self.banner[2] -= 1
            if self.banner[2] <= 0:
                self.banner = None

    def end_loop(self):
        self.echoes = [e for e in self.echoes if not e.gone]
        for e in self.echoes:
            e.alive = True
            if e.frames:
                start = V(e.frames[0][0], e.frames[0][1])
                for _ in range(8):
                    self.particles.append(Particle(start, V(random.uniform(-2, 2), random.uniform(-2, 2)),
                                                   20, ECHO_C, 3))
        self.echo_serial += 1
        if len(self.record) == LOOP_FRAMES:
            self.echoes.append(Echo(self.record, self.echo_serial))
        if len(self.echoes) > MAX_ECHOES:
            self.echoes.pop(0)
        self.record = []
        self.loop_frame = 0
        self.loop_count += 1
        bonus = 25 * self.loop_count
        self.score += bonus
        self.rings.append([V(self.player_pos), 10, ECHO_C])
        self.set_banner("LOOP %d" % self.loop_count, PLAYER_C)

        # rhythm wave at every loop start
        wave = min(self.loop_count - 1, 7)
        for _ in range(wave):
            self.queue_spawn(self.pick_kind(self.total_frames / FPS))

    def game_over(self):
        if self.score > self.highscore:
            self.highscore = self.score
            self.new_best = True
            self.save_highscore()
        self.shake = 20
        self.set_state("over")

    # ----------------------------------------------------------------- draw
    def draw(self):
        self.state_t += 1
        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_world()
            self.draw_hud()
            if self.state == "pause":
                self.draw_pause()
            elif self.state == "over":
                self.draw_over()
        self.draw_crosshair()
        pygame.display.flip()

    def text(self, surf, s, font, color, center=None, topleft=None, topright=None, alpha=255):
        img = font.render(s, True, color)
        if alpha < 255:
            img.set_alpha(alpha)
        r = img.get_rect()
        if center:
            r.center = center
        elif topleft:
            r.topleft = topleft
        elif topright:
            r.topright = topright
        surf.blit(img, r)
        return r

    def draw_world(self):
        c = self.canvas
        g = self.glow
        c.blit(self.bg, (0, 0))
        g.fill((0, 0, 0, 0))
        tick = self.total_frames

        # spawn warnings
        for pos, kind, timer in self.warnings:
            col = ENEMY_TYPES[kind]["color"]
            s = 6 + (50 - timer) * 0.25
            if (timer // 5) % 2 == 0:
                x, y = int(pos.x), int(pos.y)
                pygame.draw.line(c, col, (x - s, y - s), (x + s, y + s), 2)
                pygame.draw.line(c, col, (x - s, y + s), (x + s, y - s), 2)

        # pickups
        for pos, life in self.pickups:
            if life > 120 or (life // 6) % 2 == 0:
                bob = math.sin(tick * 0.1) * 2
                draw_heart(c, pos.x, pos.y + bob, 10, HEART_C)

        # echoes: future path preview + ghost body
        f = self.loop_frame
        for e in self.echoes:
            if e.gone:
                continue
            if e.alive:
                for k in range(6, 60, 6):
                    idx = f + k
                    if idx < len(e.frames):
                        fx, fy = e.frames[idx][0], e.frames[idx][1]
                        pygame.draw.circle(g, (90, 150, 255, max(10, 90 - k)), (int(fx), int(fy)), 2)
                p = (int(e.pos.x), int(e.pos.y))
                pygame.draw.circle(g, (90, 150, 255, 110), p, ECHO_R)
                pygame.draw.circle(g, (150, 200, 255, 200), p, ECHO_R, 2)
                tip = e.pos + V(math.cos(e.angle), math.sin(e.angle)) * (ECHO_R + 7)
                pygame.draw.line(g, (150, 200, 255, 200), p, (int(tip.x), int(tip.y)), 3)
                self.text(g, str(e.number), self.font_small, (200, 220, 255), center=(p[0], p[1] - 22))
            else:
                p = (int(e.pos.x), int(e.pos.y))
                for k in range(8):
                    a = k / 8 * math.tau + tick * 0.03
                    pygame.draw.circle(g, (90, 150, 255, 60),
                                       (int(p[0] + math.cos(a) * ECHO_R), int(p[1] + math.sin(a) * ECHO_R)), 2)

        # bullets
        for b in self.bullets:
            b.draw(c)

        # enemies
        for e in self.enemies:
            self.draw_enemy(c, e)

        # player
        if self.state != "over":
            visible = self.inv == 0 or (self.inv // 4) % 2 == 0
            if visible:
                p = (int(self.player_pos.x), int(self.player_pos.y))
                pygame.draw.circle(g, (130, 245, 255, 50), p, PLAYER_R + 8)
                pygame.draw.circle(c, PLAYER_C, p, PLAYER_R)
                pygame.draw.circle(c, WHITE, p, PLAYER_R - 5)
                tip = self.player_pos + V(math.cos(self.aim), math.sin(self.aim)) * (PLAYER_R + 8)
                pygame.draw.line(c, WHITE, p, (int(tip.x), int(tip.y)), 3)
                if self.dash_cd == 0:
                    pygame.draw.circle(c, (130, 245, 255), p, PLAYER_R + 4, 1)

        for p in self.particles:
            p.draw(c)

        for pos, radius, col in self.rings:
            a = max(0, 160 - int(radius / 5))
            pygame.draw.circle(g, (col[0], col[1], col[2], a), (int(pos.x), int(pos.y)), int(radius), 3)

        c.blit(g, (0, 0))

        for pos, s, col, life in self.popups:
            self.text(c, s, self.font_small, col, center=(int(pos.x), int(pos.y)), alpha=min(255, life * 8))

        if self.banner:
            s, col, life = self.banner
            self.text(c, s, self.font_big, col, center=(W // 2, H // 2 - 40), alpha=min(255, life * 6))

        ox = oy = 0
        if self.shake > 0:
            ox = random.uniform(-self.shake, self.shake)
            oy = random.uniform(-self.shake, self.shake)
        self.screen.fill(BG)
        self.screen.blit(c, (int(ox), int(oy)))

    def draw_enemy(self, surf, e):
        col = WHITE if e.flash > 0 else e.color
        x, y = e.pos.x, e.pos.y
        p = (int(x), int(y))
        if e.kind in ("chaser", "mini"):
            pygame.draw.circle(surf, col, p, e.r)
            pygame.draw.circle(surf, BG, p, max(2, e.r // 3))
        elif e.kind == "splitter":
            pygame.draw.circle(surf, col, p, e.r)
            pygame.draw.circle(surf, BG, p, e.r - 5)
            off = math.sin(e.wobble) * 4
            pygame.draw.circle(surf, col, (int(x - 5 - off), int(y)), 4)
            pygame.draw.circle(surf, col, (int(x + 5 + off), int(y)), 4)
        elif e.kind == "shooter":
            charging = e.fire_timer < 22
            pts = regular_poly(x, y, e.r + (3 if charging else 0), 4, e.wobble * 0.5)
            pygame.draw.polygon(surf, WHITE if charging and (e.fire_timer // 3) % 2 == 0 else col, pts)
            pygame.draw.circle(surf, BG, p, 4)
        elif e.kind == "leech":
            a = e.facing
            pts = [(x + math.cos(a) * (e.r + 5), y + math.sin(a) * (e.r + 5)),
                   (x + math.cos(a + 2.4) * e.r, y + math.sin(a + 2.4) * e.r),
                   (x + math.cos(a + math.pi) * (e.r * 0.4), y + math.sin(a + math.pi) * (e.r * 0.4)),
                   (x + math.cos(a - 2.4) * e.r, y + math.sin(a - 2.4) * e.r)]
            pygame.draw.polygon(surf, col, pts)
        elif e.kind == "brute":
            pygame.draw.polygon(surf, col, regular_poly(x, y, e.r, 8, e.wobble * 0.1))
            pygame.draw.polygon(surf, BG, regular_poly(x, y, e.r - 7, 8, e.wobble * 0.1))
        if e.max_hp >= 5 and e.hp < e.max_hp:
            w = e.r * 2
            frac = max(0, e.hp) / e.max_hp
            pygame.draw.rect(surf, (50, 50, 70), (x - w / 2, y - e.r - 9, w, 4))
            pygame.draw.rect(surf, e.color, (x - w / 2, y - e.r - 9, w * frac, 4))

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, BAR_BG, (0, 0, W, TOP))
        pygame.draw.line(s, WALL, (0, TOP), (W, TOP), 1)

        # score + multiplier
        self.text(s, "SCORE %d" % self.score, self.font_med, WHITE, topleft=(16, 6))
        mcol = (255, 220, 90) if self.mult > 1 else DIM
        self.text(s, "x%d" % self.mult, self.font_med, mcol, topleft=(16, 30))
        if self.combo_timer > 0:
            pygame.draw.rect(s, mcol, (60, 40, int(90 * self.combo_timer / COMBO_WINDOW), 5))

        # hearts
        for i in range(MAX_HP):
            draw_heart(s, 240 + i * 26, 20, 10, HEART_C if i < self.hp else (60, 40, 55), filled=True)
        # dash
        self.text(s, "DASH", self.font_small, DIM, topleft=(228, 33))
        frac = 1 - self.dash_cd / DASH_COOLDOWN
        pygame.draw.rect(s, (40, 40, 60), (274, 39, 90, 6))
        pygame.draw.rect(s, PLAYER_C if self.dash_cd == 0 else ECHO_C, (274, 39, int(90 * frac), 6))

        # loop timer
        cx = W // 2 + 60
        remaining = LOOP_FRAMES - self.loop_frame
        warn = remaining < 90
        col = REC_C if warn and (self.total_frames // 6) % 2 == 0 else PLAYER_C
        self.text(s, "LOOP %d" % self.loop_count, self.font_med, col, center=(cx, 16))
        if (self.total_frames // 30) % 2 == 0:
            pygame.draw.circle(s, REC_C, (cx - 62, 16), 5)
        bw = 240
        pygame.draw.rect(s, (40, 40, 60), (cx - bw // 2, 34, bw, 8))
        pygame.draw.rect(s, col, (cx - bw // 2, 34, int(bw * self.loop_frame / LOOP_FRAMES), 8))
        self.text(s, "%.1fs" % (remaining / FPS), self.font_small, DIM, topleft=(cx + bw // 2 + 8, 30))

        # echo slots
        self.text(s, "ECHOES", self.font_small, DIM, topright=(W - 16, 4))
        for i in range(MAX_ECHOES):
            x = W - 24 - i * 22
            if i < len(self.echoes):
                e = self.echoes[-1 - i]
                if e.gone:
                    colr = (70, 40, 90)
                elif e.alive:
                    colr = ECHO_C
                else:
                    colr = (45, 60, 100)
                pygame.draw.circle(s, colr, (x, 36), 8)
            else:
                pygame.draw.circle(s, (45, 45, 70), (x, 36), 8, 1)

    def dim_overlay(self, alpha=170):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((5, 5, 12, alpha))
        self.screen.blit(ov, (0, 0))

    def draw_pause(self):
        self.dim_overlay()
        self.text(self.screen, "PAUSED", self.font_big, WHITE, center=(W // 2, H // 2 - 30))
        self.text(self.screen, "P / ESC  resume      Q  main menu", self.font_small, DIM, center=(W // 2, H // 2 + 20))

    def draw_over(self):
        self.dim_overlay(min(190, self.state_t * 6))
        s = self.screen
        cy = H // 2 - 110
        self.glitch_title("TIME COLLAPSED", self.font_big, (W // 2, cy))
        self.text(s, "SCORE  %d" % self.score, self.font_med, WHITE, center=(W // 2, cy + 70))
        best_col = (255, 220, 90) if self.new_best else DIM
        self.text(s, ("NEW BEST!  %d" if self.new_best else "BEST  %d") % self.highscore,
                  self.font_med, best_col, center=(W // 2, cy + 102))
        stats = "loops survived %d   |   kills %d   |   echoes devoured %d" % (
            self.loop_count - 1, self.kills, self.echoes_lost)
        self.text(s, stats, self.font_small, DIM, center=(W // 2, cy + 145))
        if self.state_t > 40:
            self.text(s, "[R / ENTER] retry        [ESC] menu", self.font_small, WHITE, center=(W // 2, cy + 200))

    def glitch_title(self, s, font, center):
        t = self.state_t
        for i, col in enumerate(((60, 90, 200), (90, 150, 255), (130, 200, 255))):
            k = 3 - i
            ox = math.sin(t * 0.05 + i) * 4 * k
            self.text(self.screen, s, font, col, center=(center[0] + ox - 4 * k, center[1] + 2 * k), alpha=90)
        self.text(self.screen, s, font, WHITE, center=center)

    def draw_menu(self):
        s = self.screen
        s.fill(BG)
        s.blit(self.bg, (0, 0))
        for d in self.menu_dots:
            d[0] = (d[0] + d[2]) % W
            d[1] = (d[1] + d[3]) % H
            pygame.draw.circle(s, (40, 60, 120), (int(d[0]), int(d[1])), 2)
        self.glitch_title("ECHO LOOP", self.font_huge, (W // 2, 130))
        self.text(s, "time loops every %d seconds. your past self fights with you." % LOOP_SECONDS,
                  self.font_small, PLAYER_C, center=(W // 2, 190))

        lines = [
            ("WASD / Arrows", "move"),
            ("Mouse + Left click", "aim & shoot (hold)"),
            ("Space / Shift / Right click", "dash - invulnerable"),
            ("P / Esc", "pause"),
        ]
        y = 245
        for k, v in lines:
            self.text(s, k, self.font_small, WHITE, topright=(W // 2 - 10, y))
            self.text(s, v, self.font_small, DIM, topleft=(W // 2 + 10, y))
            y += 26

        tips = [
            ((90, 150, 255), "ECHO  replays your last loops exactly. max %d. plan your routes." % MAX_ECHOES),
            ((255, 80, 80), "RED   chases nearest body. echoes = decoys (they shatter, return next loop)."),
            ((200, 90, 255), "PURPLE LEECH  eats echoes FOREVER. kill it first."),
            ((255, 205, 70), "YELLOW  keeps distance and shoots.  GREEN splits.  ORANGE is tanky."),
        ]
        y = 375
        for col, t in tips:
            pygame.draw.circle(s, col, (110, y + 9), 6)
            self.text(s, t, self.font_small, (200, 200, 215), topleft=(126, y))
            y += 28

        self.text(s, "BEST %d" % self.highscore, self.font_med, (255, 220, 90), center=(W // 2, 520))
        if (self.state_t // 30) % 2 == 0:
            self.text(s, "[ ENTER ]  or  CLICK  to start", self.font_med, WHITE, center=(W // 2, 570))

    def draw_crosshair(self):
        mx, my = pygame.mouse.get_pos()
        col = PLAYER_C
        pygame.draw.circle(self.screen, col, (mx, my), 8, 1)
        pygame.draw.line(self.screen, col, (mx - 13, my), (mx - 4, my))
        pygame.draw.line(self.screen, col, (mx + 4, my), (mx + 13, my))
        pygame.draw.line(self.screen, col, (mx, my - 13), (mx, my - 4))
        pygame.draw.line(self.screen, col, (mx, my + 4), (mx, my + 13))

    # ----------------------------------------------------------------- loop
    def quit(self):
        pygame.quit()
        sys.exit(0)

    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle_event(ev)
            if self.state == "play":
                self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
