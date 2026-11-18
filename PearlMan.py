import os
import sys
import math
import random
from collections import deque
import pygame

# Initialize Pygame. Audio is optional so a missing audio device does not crash the game.
pygame.init()
AUDIO_AVAILABLE = True
try:
    pygame.mixer.init()
    pygame.mixer.set_num_channels(16)
except pygame.error as e:
    AUDIO_AVAILABLE = False
    print(f"WARNING: Audio is unavailable ({e}). The game will run without sound.")

# Flexible Asset Finder: checks script folder and parent folder case-insensitively
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
BUNDLE_DIR = getattr(sys, "_MEIPASS", SCRIPT_DIR)        # where bundled files are unpacked
EXE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))  # folder the .exe sits in


def get_asset_path(filename):
    search_dirs = [BUNDLE_DIR, EXE_DIR, SCRIPT_DIR, PARENT_DIR]
    base_target, _ = os.path.splitext(filename)

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for file_name in os.listdir(directory):
                file_base, _ = os.path.splitext(file_name)
                if file_base.lower() == base_target.lower() or file_name.lower() == filename.lower():
                    return os.path.join(directory, file_name)
        except Exception:
            pass

    return os.path.join(PARENT_DIR, filename)


# Game Constants
TILE_SIZE = 24
ROWS = 31
COLS = 28
HUD_HEIGHT = 60
WIDTH = COLS * TILE_SIZE
HEIGHT = ROWS * TILE_SIZE + HUD_HEIGHT
FPS = 60

# Ghost speed progression (tweak these to change difficulty)
GHOST_BASE_SPEED = 2.0
GHOST_LEVEL_SPEEDUP = 0.08         # extra speed multiplier gained per level beaten
GHOST_WITHIN_LEVEL_SPEEDUP = 0.12  # extra multiplier gained as pellets get eaten in a level
GHOST_MAX_SPEED_MULT = 1.5         # hard cap on the multiplier
GHOST_SPURT_THRESHOLD = 1.05       # at/above this multiplier the "spurt" sound is used
GHOST_RESPAWN_PAUSE = 45           # frames an eaten ghost waits before moving again

# Colors
BLACK = (0, 0, 0)
WALL_BLUE = (25, 25, 220)
GATE_YELLOW = (255, 215, 0)
WHITE = (255, 255, 255)
GRAY = (120, 120, 120)
VULNERABLE_TINT = (80, 120, 255)

# Maze Layout
MAZE_LAYOUT = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.##### ## #####.######",
    "     #.##### ## #####.#     ",
    "     #.##          ##.#     ",
    "     #.## ###--### ##.#     ",
    "######.## #      # ##.######",
    "      .   #      #   .      ",
    "######.## #      # ##.######",
    "     #.## ######## ##.#     ",
    "     #.##          ##.#     ",
    "     #.## ######## ##.#     ",
    "######.## ######## ##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#.####.#####.##.#####.####.#",
    "#o..##.......  .......##..o#",
    "###.##.##.########.##.##.###",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################"
]

# -------------------------------------------------------------------
# DISPLAY / GRAPHICS SETTINGS
# The game renders internally at its original resolution. Only the
# finished frame is scaled to the actual window or monitor resolution.
# -------------------------------------------------------------------
screen = pygame.Surface((WIDTH, HEIGHT))
display_surface = None
fullscreen = False
stretch_mode = False  # False = preserve aspect ratio; True = stretch to fill.


def set_display_mode():
    global display_surface, fullscreen

    if fullscreen:
        display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        display_surface = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

    pygame.display.set_caption("Pearl Man")


def get_viewport():
    display_w, display_h = display_surface.get_size()

    if stretch_mode:
        return pygame.Rect(0, 0, display_w, display_h)

    scale = min(display_w / WIDTH, display_h / HEIGHT)
    scaled_w = max(1, int(WIDTH * scale))
    scaled_h = max(1, int(HEIGHT * scale))
    x = (display_w - scaled_w) // 2
    y = (display_h - scaled_h) // 2

    return pygame.Rect(x, y, scaled_w, scaled_h)


def present_frame():
    display_surface.fill(BLACK)
    viewport = get_viewport()

    scaled_image = pygame.transform.smoothscale(
        screen, (viewport.width, viewport.height)
    )
    display_surface.blit(scaled_image, viewport.topleft)
    pygame.display.flip()


def screen_to_game(pos):
    """Convert mouse coordinates from the window to internal game coordinates."""
    viewport = get_viewport()
    x, y = pos

    if not viewport.collidepoint(x, y):
        return -10000, -10000

    game_x = (x - viewport.x) * WIDTH / viewport.width
    game_y = (y - viewport.y) * HEIGHT / viewport.height
    return int(game_x), int(game_y)


set_display_mode()
clock = pygame.time.Clock()
font_large = pygame.font.SysFont("arial", 36, bold=True)
font_medium = pygame.font.SysFont("arial", 24, bold=True)
font_small = pygame.font.SysFont("arial", 18, bold=True)


# --- ASSET LOADING ---
def load_image(name, size, fallback_color, is_circle=False):
    path = get_asset_path(name)
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except Exception as e:
        print(f"WARNING: Could not load image '{name}' ({e}). Using fallback.")
        surf = pygame.Surface(size, pygame.SRCALPHA)
        if is_circle:
            pygame.draw.circle(
                surf, fallback_color,
                (size[0] // 2, size[1] // 2), size[0] // 2
            )
        else:
            surf.fill(fallback_color)
        return surf


def load_sound(name):
    path = get_asset_path(name)
    try:
        if not AUDIO_AVAILABLE:
            return None
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"WARNING: Could not load audio '{name}' ({e}).")
        return None


# Load Images
poop_img = load_image("Poop.png", (12, 12), (139, 69, 19), is_circle=True)
poop_power_img = load_image("Poop.png", (22, 22), (139, 69, 19), is_circle=True)
tom_open_img = load_image(
    "TomMouthOpen.png", (TILE_SIZE + 4, TILE_SIZE + 4),
    (255, 255, 0), is_circle=True
)
tom_closed_img = load_image(
    "TomMouthClosed.png", (TILE_SIZE + 4, TILE_SIZE + 4),
    (220, 220, 0), is_circle=True
)
police_img = load_image(
    "Police.png", (TILE_SIZE + 4, TILE_SIZE + 4), (255, 50, 50)
)

police_vulnerable_img = police_img.copy()
police_vulnerable_img.fill(
    VULNERABLE_TINT, special_flags=pygame.BLEND_RGB_MULT
)

# Load Sounds
snd_start_game = load_sound("StartGame.mp3")
snd_start_narrator = load_sound("StartGameNarrator.mp3")
snd_end_game = load_sound("EndGame.mp3")
snd_end_narrator = load_sound("EndGameNarrator.mp3")
snd_eat_poo = load_sound("EatPoo.mp3")
snd_ghost_powerup = load_sound("GhostSoundWhenPowerUp.mp3")
snd_ghost_normal = load_sound("GhostMove.mp3")
snd_ghost_spurt = load_sound("GhostSpurtMove.mp3")

# Audio Channels
ch_start_main = pygame.mixer.Channel(0) if AUDIO_AVAILABLE else None
ch_start_narr = pygame.mixer.Channel(1) if AUDIO_AVAILABLE else None
ch_end_main = pygame.mixer.Channel(2) if AUDIO_AVAILABLE else None
ch_end_narr = pygame.mixer.Channel(3) if AUDIO_AVAILABLE else None
ch_eat = pygame.mixer.Channel(4) if AUDIO_AVAILABLE else None
ch_powerup_loop = pygame.mixer.Channel(5) if AUDIO_AVAILABLE else None
ch_ghost_normal = pygame.mixer.Channel(6) if AUDIO_AVAILABLE else None
ch_ghost_spurt = pygame.mixer.Channel(7) if AUDIO_AVAILABLE else None


def stop_all_custom_sounds():
    for channel in (
        ch_start_main, ch_start_narr, ch_end_main, ch_end_narr,
        ch_eat, ch_powerup_loop, ch_ghost_normal, ch_ghost_spurt
    ):
        if channel is not None:
            channel.stop()


def set_loop(channel, sound, should_play):
    """Keep a looping sound playing while should_play is True, silent otherwise."""
    if channel is None or sound is None:
        return

    if should_play:
        if not channel.get_busy():
            channel.play(sound, loops=-1)
    elif channel.get_busy():
        channel.stop()


# --- PROCEDURAL MAZE DRAWING ---
def is_wall(r, c):
    if 0 <= r < ROWS and 0 <= c < COLS:
        return MAZE_LAYOUT[r][c] == '#'
    return False


def draw_maze(surface):
    surface.fill(BLACK)
    outer_pad = 3
    inner_pad = 7

    for r in range(ROWS):
        for c in range(COLS):
            tile = MAZE_LAYOUT[r][c]
            x = c * TILE_SIZE
            y = r * TILE_SIZE + HUD_HEIGHT

            if tile == '#':
                top = is_wall(r - 1, c)
                bottom = is_wall(r + 1, c)
                left = is_wall(r, c - 1)
                right = is_wall(r, c + 1)

                if not top:
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x, y + outer_pad), (x + TILE_SIZE, y + outer_pad), 2
                    )
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x, y + inner_pad), (x + TILE_SIZE, y + inner_pad), 2
                    )
                if not bottom:
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x, y + TILE_SIZE - outer_pad),
                        (x + TILE_SIZE, y + TILE_SIZE - outer_pad), 2
                    )
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x, y + TILE_SIZE - inner_pad),
                        (x + TILE_SIZE, y + TILE_SIZE - inner_pad), 2
                    )
                if not left:
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x + outer_pad, y), (x + outer_pad, y + TILE_SIZE), 2
                    )
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x + inner_pad, y), (x + inner_pad, y + TILE_SIZE), 2
                    )
                if not right:
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x + TILE_SIZE - outer_pad, y),
                        (x + TILE_SIZE - outer_pad, y + TILE_SIZE), 2
                    )
                    pygame.draw.line(
                        surface, WALL_BLUE,
                        (x + TILE_SIZE - inner_pad, y),
                        (x + TILE_SIZE - inner_pad, y + TILE_SIZE), 2
                    )

            elif tile == '-':
                pygame.draw.line(
                    surface, GATE_YELLOW,
                    (x, y + TILE_SIZE // 2),
                    (x + TILE_SIZE, y + TILE_SIZE // 2), 4
                )


maze_background = pygame.Surface((WIDTH, HEIGHT))
draw_maze(maze_background)


# --- ENTITIES ---
class Player:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = 14 * TILE_SIZE + TILE_SIZE // 2
        self.y = 23 * TILE_SIZE + TILE_SIZE // 2
        self.dir = (0, 0)
        self.next_dir = (0, 0)
        self.speed = 2.0
        self.anim_timer = 0
        self.mouth_open = True
        self.facing_angle = 0

    def get_grid_pos(self):
        return int(self.y // TILE_SIZE), int(self.x // TILE_SIZE)

    def can_move(self, dx, dy):
        test_x = self.x + dx * (TILE_SIZE // 2)
        test_y = self.y + dy * (TILE_SIZE // 2)
        col = int(test_x // TILE_SIZE)
        row = int(test_y // TILE_SIZE)

        if col < 0 or col >= COLS:
            return row == 14

        if 0 <= row < ROWS:
            tile = MAZE_LAYOUT[row][col]
            return tile not in ('#', '-')
        return False

    def update(self):
        r, c = self.get_grid_pos()
        center_x = c * TILE_SIZE + TILE_SIZE // 2
        center_y = r * TILE_SIZE + TILE_SIZE // 2

        if self.next_dir != (0, 0):
            if (
                self.next_dir[0] == -self.dir[0]
                and self.next_dir[1] == -self.dir[1]
            ):
                self.dir = self.next_dir
                self.next_dir = (0, 0)
            elif (
                abs(self.x - center_x) <= self.speed
                and abs(self.y - center_y) <= self.speed
            ):
                if self.can_move(*self.next_dir):
                    self.x = center_x
                    self.y = center_y
                    self.dir = self.next_dir
                    self.next_dir = (0, 0)

        if self.dir != (0, 0):
            if self.can_move(*self.dir):
                self.x += self.dir[0] * self.speed
                self.y += self.dir[1] * self.speed

                if self.dir == (1, 0):
                    self.facing_angle = 0
                elif self.dir == (-1, 0):
                    self.facing_angle = 180
                elif self.dir == (0, -1):
                    self.facing_angle = 90
                elif self.dir == (0, 1):
                    self.facing_angle = -90

                self.anim_timer += 1
                if self.anim_timer >= 8:
                    self.mouth_open = not self.mouth_open
                    self.anim_timer = 0
            else:
                self.x = center_x
                self.y = center_y

        if self.x < 0:
            self.x = WIDTH - 1
        elif self.x >= WIDTH:
            self.x = 0

    def draw(self, surface):
        img = tom_open_img if self.mouth_open else tom_closed_img
        if self.facing_angle == 180:
            rotated = pygame.transform.flip(img, True, False)
        else:
            rotated = pygame.transform.rotate(img, self.facing_angle)

        rect = rotated.get_rect(
            center=(int(self.x), int(self.y) + HUD_HEIGHT)
        )
        surface.blit(rotated, rect)


class PoliceGhost:
    def __init__(self, spawn_col, ghost_id):
        self.spawn_col = spawn_col
        self.ghost_id = ghost_id
        self.reset()

    def reset(self):
        self.x = float(self.spawn_col * TILE_SIZE + TILE_SIZE // 2)
        self.y = float(1 * TILE_SIZE + TILE_SIZE // 2)

        r, c = int(self.y // TILE_SIZE), int(self.x // TILE_SIZE)
        valid = []

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nr, nc = r + dy, c + dx
            if (
                0 <= nr < ROWS and 0 <= nc < COLS
                and MAZE_LAYOUT[nr][nc] != '#'
            ):
                valid.append((dx, dy))

        self.dir = random.choice(valid) if valid else (1, 0)
        self.speed = GHOST_BASE_SPEED
        self.frightened = False
        self.moving = False   # True only on frames where the ghost actually travelled
        self.pause = 0        # frames left to stand still (after being eaten)

    def get_grid_pos(self):
        col = int(round((self.x - TILE_SIZE / 2) / TILE_SIZE))
        row = int(round((self.y - TILE_SIZE / 2) / TILE_SIZE))
        return row, col

    @staticmethod
    def tile_open(r, c):
        if r == 14 and (c < 0 or c >= COLS):
            return True
        if 0 <= r < ROWS and 0 <= c < COLS:
            return MAZE_LAYOUT[r][c] != '#'
        return False

    def valid_dirs(self, r, c):
        dirs = []
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            if self.tile_open(r + dy, c + dx):
                dirs.append((dx, dy))
        return dirs

    def chase_direction(self, start, target):
        """Return the first step on a shortest walkable route to the player."""
        queue = deque([(start, None)])
        visited = {start}
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]

        while queue:
            (r, c), first_step = queue.popleft()

            if (r, c) == target and first_step is not None:
                return first_step

            for dx, dy in directions:
                nr, nc = r + dy, c + dx

                if nr == 14 and nc < 0:
                    nc = COLS - 1
                elif nr == 14 and nc >= COLS:
                    nc = 0
                elif not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue

                if MAZE_LAYOUT[nr][nc] == '#':
                    continue

                nxt = (nr, nc)
                if nxt in visited:
                    continue

                visited.add(nxt)
                step = (dx, dy) if first_step is None else first_step
                queue.append((nxt, step))

        return None

    def update(self, player):
        """Move the ghost. Works with any speed: it stops exactly on every tile
        center to make turn decisions, then carries any leftover distance on."""
        self.moving = False

        if self.pause > 0:
            self.pause -= 1
            return

        remaining = self.speed * (0.75 if self.frightened else 1.0)
        guard = 0

        while remaining > 1e-6 and guard < 6:
            guard += 1

            # Snap to a tile center if we are essentially on one.
            snap_x = round((self.x - TILE_SIZE / 2) / TILE_SIZE) * TILE_SIZE + TILE_SIZE / 2
            snap_y = round((self.y - TILE_SIZE / 2) / TILE_SIZE) * TILE_SIZE + TILE_SIZE / 2
            if abs(self.x - snap_x) < 1e-4:
                self.x = float(snap_x)
            if abs(self.y - snap_y) < 1e-4:
                self.y = float(snap_y)

            r, c = self.get_grid_pos()
            center_x = c * TILE_SIZE + TILE_SIZE / 2
            center_y = r * TILE_SIZE + TILE_SIZE / 2
            at_center = (
                abs(self.x - center_x) < 1e-6
                and abs(self.y - center_y) < 1e-6
            )

            if at_center:
                choices = self.valid_dirs(r, c)

                if self.frightened:
                    if choices:
                        self.dir = random.choice(choices)
                else:
                    target = player.get_grid_pos()
                    best_step = self.chase_direction((r, c), target)

                    if best_step in choices:
                        self.dir = best_step
                    elif choices:
                        self.dir = random.choice(choices)

                # Blocked (dead end / wall): stand still instead of moving.
                if not self.tile_open(r + self.dir[1], c + self.dir[0]):
                    self.dir = (0, 0)

            if self.dir == (0, 0):
                break

            # Distance to the next tile center along the current direction.
            if at_center:
                dist = float(TILE_SIZE)
            elif self.dir[0] != 0:
                offset = (self.x - TILE_SIZE / 2) % TILE_SIZE
                dist = (TILE_SIZE - offset) if self.dir[0] > 0 else offset
            else:
                offset = (self.y - TILE_SIZE / 2) % TILE_SIZE
                dist = (TILE_SIZE - offset) if self.dir[1] > 0 else offset

            step = min(remaining, dist)
            self.x += self.dir[0] * step
            self.y += self.dir[1] * step
            remaining -= step
            self.moving = True

            # Tunnel wrap, keeping the ghost aligned to tile centers.
            if self.x <= -TILE_SIZE / 2 + 1e-6:
                self.x += WIDTH
            elif self.x >= WIDTH + TILE_SIZE / 2 - 1e-6:
                self.x -= WIDTH

    def draw(self, surface, fright_timer):
        img = police_img

        if self.frightened:
            if fright_timer < 120 and (fright_timer // 10) % 2 == 0:
                img = police_img
            else:
                img = police_vulnerable_img

        rect = img.get_rect(
            center=(int(self.x), int(self.y) + HUD_HEIGHT)
        )
        surface.blit(img, rect)


# --- GAME MANAGER ---
class PacmanGame:
    def __init__(self):
        self.state = "START"
        self.score = 0
        self.high_score = 0
        self.level = 1
        self.fright_timer = 0

        self.start_narrator_due = None
        self.end_narrator_due = None
        self.narrator_finished = False
        self.narrator_unlock_time = None

        self.end_narrator_finished = False
        self.end_narrator_unlock_time = None

        self.play_btn_rect = None

        self.graphics_menu_open = False
        self.graphics_buttons = {}

        self.player = Player()
        top_spawn_cols = [1, 6, 12, 15, 26]
        self.ghosts = [
            PoliceGhost(col, i) for i, col in enumerate(top_spawn_cols)
        ]

        self.pellets = set()
        self.power_pellets = set()
        self.total_pellets = 1
        self.populate_pellets()

        self.trigger_start_audio()

    def populate_pellets(self):
        self.pellets.clear()
        self.power_pellets.clear()

        for r in range(ROWS):
            for c in range(COLS):
                if MAZE_LAYOUT[r][c] == '.':
                    self.pellets.add((r, c))
                elif MAZE_LAYOUT[r][c] == 'o':
                    self.power_pellets.add((r, c))

        self.total_pellets = max(1, len(self.pellets) + len(self.power_pellets))

    def ghost_speed_mult(self):
        """Ghosts speed up a little each level and gradually within a level."""
        eaten = self.total_pellets - (len(self.pellets) + len(self.power_pellets))
        progress = max(0.0, min(1.0, eaten / self.total_pellets))
        mult = (
            1.0
            + GHOST_LEVEL_SPEEDUP * (self.level - 1)
            + GHOST_WITHIN_LEVEL_SPEEDUP * progress
        )
        return min(mult, GHOST_MAX_SPEED_MULT)

    def trigger_start_audio(self):
        stop_all_custom_sounds()
        self.end_narrator_due = None
        self.narrator_unlock_time = None
        self.narrator_finished = False

        if snd_start_game and ch_start_main:
            ch_start_main.play(snd_start_game)

        self.start_narrator_due = pygame.time.get_ticks() + 4500

    def trigger_end_audio(self):
        stop_all_custom_sounds()
        self.start_narrator_due = None
        self.narrator_unlock_time = None
        self.narrator_finished = True

        self.end_narrator_finished = False
        self.end_narrator_unlock_time = None

        if snd_end_game and ch_end_main:
            ch_end_main.play(snd_end_game)

        self.end_narrator_due = pygame.time.get_ticks() + 2000

    def start_new_game(self):
        if self.state == "START" and not self.narrator_finished:
            return
        if self.state == "GAME_OVER" and not self.end_narrator_finished:
            return

        advancing = self.state == "WIN"

        stop_all_custom_sounds()
        self.start_narrator_due = None
        self.end_narrator_due = None
        self.narrator_unlock_time = None
        self.narrator_finished = True
        self.end_narrator_finished = True

        if advancing:
            # Beat the level: keep the score, go up a level (ghosts get faster).
            self.level += 1
        else:
            self.level = 1
            self.score = 0
        self.fright_timer = 0

        self.populate_pellets()
        self.reset_positions()
        self.state = "PLAYING"

    def reset_positions(self):
        self.player.reset()
        for ghost in self.ghosts:
            ghost.reset()
            ghost.frightened = self.fright_timer > 0

    def update_audio_timers(self):
        now = pygame.time.get_ticks()

        if self.start_narrator_due is not None and now >= self.start_narrator_due:
            self.start_narrator_due = None
            if snd_start_narrator and ch_start_narr:
                ch_start_narr.play(snd_start_narrator)
                self.narrator_unlock_time = (
                    now + int(snd_start_narrator.get_length() * 1000)
                )
            else:
                self.narrator_finished = True

        if self.state == "START" and not self.narrator_finished:
            if (
                self.narrator_unlock_time is not None
                and now >= self.narrator_unlock_time
            ):
                self.narrator_finished = True
            elif (
                self.start_narrator_due is None
                and ch_start_narr and not ch_start_narr.get_busy()
            ):
                self.narrator_finished = True

        if self.end_narrator_due is not None and now >= self.end_narrator_due:
            self.end_narrator_due = None
            if snd_end_narrator and ch_end_narr:
                ch_end_narr.play(snd_end_narrator)
                self.end_narrator_unlock_time = (
                    now + int(snd_end_narrator.get_length() * 1000)
                )
            else:
                self.end_narrator_finished = True

        if self.state == "GAME_OVER" and not self.end_narrator_finished:
            if (
                self.end_narrator_unlock_time is not None
                and now >= self.end_narrator_unlock_time
            ):
                self.end_narrator_finished = True
            elif (
                self.end_narrator_due is None
                and ch_end_narr and not ch_end_narr.get_busy()
                and ch_end_main and not ch_end_main.get_busy()
            ):
                self.end_narrator_finished = True

    def update_movement_audio(self):
        """Start/stop the looping gameplay sounds based on what is happening now.

        - Power-up active: the power-up loop plays (replaces the normal ghost loops).
        - Otherwise, while any ghost is actively travelling: the normal loop plays,
          or the spurt loop once the ghosts have sped up.
        - Nothing loops when the game is not being played (menus, game over, win,
          settings open), or when every ghost is standing still.
        """
        playing = self.state == "PLAYING" and not self.graphics_menu_open
        powered = playing and self.fright_timer > 0
        moving = playing and any(g.moving for g in self.ghosts)
        sped_up = self.ghost_speed_mult() >= GHOST_SPURT_THRESHOLD

        set_loop(ch_powerup_loop, snd_ghost_powerup, powered)
        set_loop(
            ch_ghost_normal, snd_ghost_normal,
            moving and not powered and not sped_up
        )
        set_loop(
            ch_ghost_spurt, snd_ghost_spurt,
            moving and not powered and sped_up
        )

    def update(self):
        self.update_audio_timers()

        if self.state != "PLAYING" or self.graphics_menu_open:
            self.update_movement_audio()
            return

        self.player.update()

        pr, pc = self.player.get_grid_pos()

        if (pr, pc) in self.pellets:
            self.pellets.remove((pr, pc))
            self.score += 10
        elif (pr, pc) in self.power_pellets:
            self.power_pellets.remove((pr, pc))
            self.score += 50
            self.fright_timer = 420
            for ghost in self.ghosts:
                ghost.frightened = True

            if snd_eat_poo and ch_eat:
                ch_eat.play(snd_eat_poo)

        if self.score > self.high_score:
            self.high_score = self.score

        if self.fright_timer > 0:
            self.fright_timer -= 1
            if self.fright_timer == 0:
                for ghost in self.ghosts:
                    ghost.frightened = False

        if not self.pellets and not self.power_pellets:
            self.state = "WIN"
            self.update_movement_audio()
            return

        speed = GHOST_BASE_SPEED * self.ghost_speed_mult()

        for ghost in self.ghosts:
            ghost.speed = speed
            ghost.update(self.player)
            dist = math.hypot(
                self.player.x - ghost.x,
                self.player.y - ghost.y
            )

            if dist < TILE_SIZE * 0.75:
                if ghost.frightened:
                    self.score += 200
                    ghost.reset()
                    ghost.frightened = self.fright_timer > 0
                    ghost.pause = GHOST_RESPAWN_PAUSE
                else:
                    self.state = "GAME_OVER"
                    self.trigger_end_audio()
                    break

        self.update_movement_audio()

    def draw_hud(self):
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, HUD_HEIGHT))

        score_surf = font_medium.render(
            f"SCORE: {self.score}", True, WHITE
        )
        high_surf = font_medium.render(
            f"HIGH: {self.high_score}", True, GATE_YELLOW
        )
        level_surf = font_small.render(
            f"LEVEL {self.level}", True, WHITE
        )

        screen.blit(score_surf, (20, 16))
        screen.blit(
            high_surf,
            (WIDTH // 2 - high_surf.get_width() // 2, 10)
        )
        screen.blit(
            level_surf,
            (WIDTH // 2 - level_surf.get_width() // 2, 36)
        )

        mode_surf = font_small.render(
            "ONE-HIT ARCADE MODE", True, WHITE
        )
        screen.blit(mode_surf, (WIDTH - 190, 20))

    def handle_graphics_click(self, pos):
        """Handle clicks on the graphics settings buttons."""
        global stretch_mode, fullscreen

        if "close" not in self.graphics_buttons:
            return

        if self.graphics_buttons["close"].collidepoint(pos):
            self.graphics_menu_open = False

        elif self.graphics_buttons["normal"].collidepoint(pos):
            stretch_mode = False

        elif self.graphics_buttons["stretched"].collidepoint(pos):
            stretch_mode = True

        elif self.graphics_buttons["fullscreen"].collidepoint(pos):
            fullscreen = not fullscreen
            set_display_mode()

    def draw_graphics_settings(self):
        """Draw the graphics settings overlay."""
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        panel = pygame.Rect(
            WIDTH // 2 - 220,
            HEIGHT // 2 - 210,
            440,
            420
        )

        pygame.draw.rect(
            screen, (20, 20, 35), panel, border_radius=15
        )
        pygame.draw.rect(
            screen, WALL_BLUE, panel, 4, border_radius=15
        )

        title = font_large.render(
            "GRAPHICS SETTINGS", True, GATE_YELLOW
        )
        screen.blit(
            title,
            (panel.centerx - title.get_width() // 2, panel.y + 25)
        )

        mode_text = "STRETCHED" if stretch_mode else "NORMAL"
        mode_label = font_medium.render(
            f"Graphics Mode: {mode_text}", True, WHITE
        )
        screen.blit(
            mode_label,
            (panel.centerx - mode_label.get_width() // 2, panel.y + 100)
        )

        button_width = 300
        button_height = 48
        button_x = panel.centerx - button_width // 2

        normal_btn = pygame.Rect(
            button_x, panel.y + 145, button_width, button_height
        )
        stretched_btn = pygame.Rect(
            button_x, panel.y + 205, button_width, button_height
        )
        fullscreen_btn = pygame.Rect(
            button_x, panel.y + 265, button_width, button_height
        )
        close_btn = pygame.Rect(
            button_x, panel.y + 345, button_width, button_height
        )

        self.graphics_buttons = {
            "normal": normal_btn,
            "stretched": stretched_btn,
            "fullscreen": fullscreen_btn,
            "close": close_btn
        }

        def draw_button(rect, label_text, selected=False):
            color = WALL_BLUE if selected else (55, 55, 75)
            border = GATE_YELLOW if selected else WHITE

            pygame.draw.rect(
                screen, color, rect, border_radius=8
            )
            pygame.draw.rect(
                screen, border, rect, 2, border_radius=8
            )

            label = font_small.render(label_text, True, WHITE)
            screen.blit(
                label,
                (
                    rect.centerx - label.get_width() // 2,
                    rect.centery - label.get_height() // 2
                )
            )

        draw_button(
            normal_btn, "NORMAL ASPECT RATIO", not stretch_mode
        )
        draw_button(
            stretched_btn, "STRETCHED TO FULL SCREEN", stretch_mode
        )
        draw_button(
            fullscreen_btn,
            "EXIT FULLSCREEN" if fullscreen else "ENABLE FULLSCREEN"
        )
        draw_button(close_btn, "CLOSE SETTINGS")

        instruction = font_small.render(
            "F2: Settings     F11: Fullscreen     ESC: Close",
            True, GRAY
        )
        screen.blit(
            instruction,
            (
                WIDTH // 2 - instruction.get_width() // 2,
                panel.bottom - 35
            )
        )

    def draw(self):
        screen.blit(maze_background, (0, 0))
        self.draw_hud()

        # Draw regular pellets
        for r, c in self.pellets:
            cx = c * TILE_SIZE + TILE_SIZE // 2
            cy = r * TILE_SIZE + TILE_SIZE // 2 + HUD_HEIGHT
            rect = poop_img.get_rect(center=(cx, cy))
            screen.blit(poop_img, rect)

        # Draw blinking power pellets
        if (pygame.time.get_ticks() // 200) % 2 == 0:
            for r, c in self.power_pellets:
                cx = c * TILE_SIZE + TILE_SIZE // 2
                cy = r * TILE_SIZE + TILE_SIZE // 2 + HUD_HEIGHT
                rect = poop_power_img.get_rect(center=(cx, cy))
                screen.blit(poop_power_img, rect)

        self.player.draw(screen)

        for ghost in self.ghosts:
            ghost.draw(screen, self.fright_timer)

        # START, GAME_OVER, and WIN overlays
        if self.state in ("START", "GAME_OVER", "WIN"):
            overlay = pygame.Surface(
                (WIDTH, HEIGHT), pygame.SRCALPHA
            )
            overlay.fill((0, 0, 0, 175))
            screen.blit(overlay, (0, 0))

            if self.state == "START":
                title = font_large.render(
                    "PEARL MAN", True, GATE_YELLOW
                )
                sub = font_small.render("", True, WHITE)
                btn_text = "PLAY"
                can_press = self.narrator_finished

            elif self.state == "GAME_OVER":
                title = font_large.render(
                    "BUSTED BY POLICE!", True, (255, 60, 60)
                )
                sub = font_small.render(
                    f"Final Score: {self.score}", True, WHITE
                )
                btn_text = "PLAY AGAIN"
                can_press = self.end_narrator_finished

            else:
                title = font_large.render(
                    "YOU CLEARED THE MAP!", True, (80, 255, 120)
                )
                sub = font_small.render(
                    f"Score: {self.score}   -   Next up: Level {self.level + 1}",
                    True, WHITE
                )
                btn_text = "NEXT LEVEL"
                can_press = True

            screen.blit(
                title,
                (
                    WIDTH // 2 - title.get_width() // 2,
                    HEIGHT // 2 - 80
                )
            )
            screen.blit(
                sub,
                (
                    WIDTH // 2 - sub.get_width() // 2,
                    HEIGHT // 2 - 30
                )
            )

            self.play_btn_rect = pygame.Rect(
                WIDTH // 2 - 100,
                HEIGHT // 2 + 10,
                200,
                50
            )

            btn_color = WALL_BLUE if can_press else GRAY
            border_color = GATE_YELLOW if can_press else GRAY

            pygame.draw.rect(
                screen, btn_color, self.play_btn_rect,
                border_radius=10
            )
            pygame.draw.rect(
                screen, border_color, self.play_btn_rect,
                3, border_radius=10
            )

            btn_surf = font_medium.render(
                btn_text, True,
                WHITE if can_press else (180, 180, 180)
            )
            screen.blit(
                btn_surf,
                (
                    self.play_btn_rect.centerx - btn_surf.get_width() // 2,
                    self.play_btn_rect.centery - btn_surf.get_height() // 2
                )
            )
        else:
            self.play_btn_rect = None

        # Draw settings last so it appears above every other screen element.
        if self.graphics_menu_open:
            self.draw_graphics_settings()

        present_frame()


def main():
    global display_surface, fullscreen

    game = PacmanGame()
    running = True

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                if not fullscreen:
                    display_surface = pygame.display.set_mode(
                        event.size, pygame.RESIZABLE
                    )

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = screen_to_game(event.pos)

                if game.graphics_menu_open:
                    game.handle_graphics_click(mouse_pos)

                elif (
                    game.play_btn_rect
                    and game.play_btn_rect.collidepoint(mouse_pos)
                ):
                    if (
                        game.state == "START"
                        and game.narrator_finished
                    ):
                        game.start_new_game()

                    elif (
                        game.state == "GAME_OVER"
                        and game.end_narrator_finished
                    ):
                        game.start_new_game()

                    elif game.state == "WIN":
                        game.start_new_game()

            elif event.type == pygame.KEYDOWN:
                # F11 toggles fullscreen from any game state.
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    set_display_mode()

                # F2 opens or closes the graphics settings.
                elif event.key == pygame.K_F2:
                    game.graphics_menu_open = not game.graphics_menu_open

                # ESC closes the settings menu.
                elif event.key == pygame.K_ESCAPE:
                    game.graphics_menu_open = False

                # Ignore gameplay keys while the settings menu is open.
                elif game.graphics_menu_open:
                    pass

                elif (
                    game.state == "WIN"
                    and event.key in (pygame.K_RETURN, pygame.K_SPACE)
                ):
                    game.start_new_game()

                elif (
                    game.state == "GAME_OVER"
                    and event.key in (pygame.K_RETURN, pygame.K_SPACE)
                ):
                    if game.end_narrator_finished:
                        game.start_new_game()

                elif (
                    game.state == "START"
                    and event.key in (pygame.K_RETURN, pygame.K_SPACE)
                ):
                    if game.narrator_finished:
                        game.start_new_game()

                elif game.state == "PLAYING":
                    if event.key in (pygame.K_w, pygame.K_UP):
                        game.player.next_dir = (0, -1)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        game.player.next_dir = (0, 1)
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        game.player.next_dir = (-1, 0)
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        game.player.next_dir = (1, 0)

        game.update()
        game.draw()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()