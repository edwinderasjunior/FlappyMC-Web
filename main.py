import io
import sys
import pygame
import os
import random
import math
import asyncio  # 1. Added for web loop compliance
import platform # Added to handle platform detection safely

def resource_path(relative_path):
    """
    Resolves the correct path for bundled assets.
    Uses sys._MEIPASS when running as a PyInstaller exe,
    falls back to the script's directory otherwise.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def play_click(click_sound):
    """Safely plays the button click sound if the asset is loaded."""
    if click_sound:
        click_sound.play()

def draw_background(panorama, window):
    """
    Renders the panoramic fader background animation.
    If the asset fader isn't ready or missing, clears the screen with a clean sky color.
    """
    if panorama and panorama.images:
        panorama.draw(window)
    else:
        window.fill((135, 206, 250))  # Minecraft sky blue fallback color

# ==========================================
# 1. SETTINGS AND CONSTANTS
# ==========================================

SCREEN_W, SCREEN_H = 1280, 720
SCROLL_SPEED = 3
GAME_SPEED = 4
BASE_GAME_SPEED = 4
FADE_SPEED = 4
FPS = 60

IMAGE_FOLDER = resource_path("panoramas")
MUSIC_FOLDER = resource_path("assets")
GRASS_SPEED = 1.0

PLAYER_HEAD_W, PLAYER_HEAD_H = 80, 80
BLOCK_W, BLOCK_H = 120, 800

WHITE, BLACK, GRAY = (255, 255, 255), (0, 0, 0), (50, 50, 50)
RED = (255, 50, 50)

PIPE_OSCILLATION = False
PIPE_OSCILLATE_SPEED = 0.05
PIPE_OSCILLATE_AMOUNT = 1.5
BASE_PIPE_OSCILLATE_SPEED = 0.05
BASE_PIPE_OSCILLATE_AMOUNT = 1.5

# Pre-initialize the mixer with optimized web settings
pygame.mixer.pre_init(44100, -16, 2, 4096)

pygame.init()
pygame.mixer.init()

# ==========================================
# 2. CLASS DEFINITIONS
# ==========================================

class PanoramicFader:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        if os.path.exists(IMAGE_FOLDER):
            image_paths = sorted([
                os.path.join(IMAGE_FOLDER, f)
                for f in os.listdir(IMAGE_FOLDER)
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))
            ])
        else:
            image_paths = []

        self.images = []
        if image_paths:
            for path in image_paths:
                raw = pygame.image.load(path).convert()
                aspect_ratio = raw.get_width() / raw.get_height()
                scaled_w = int(self.screen_h * aspect_ratio)
                img = pygame.transform.smoothscale(raw, (scaled_w, self.screen_h))
                self.images.append(img)
        else:
            fallback = pygame.Surface((self.screen_w, self.screen_h))
            fallback.fill(BLACK)
            self.images.append(fallback)

        self.scroll_limits = [
            -(img.get_width() - self.screen_w - 300)
            for img in self.images
        ]

        self.index = 0
        self.img_x = 0.0
        self.fade_alpha = 0
        self.state = "SLIDE"

        self.fade_surf = pygame.Surface((screen_w, screen_h))
        self.fade_surf.fill((0, 0, 0))
        self.load_image()

    def load_image(self):
        self.img_x = 0.0
        self.scroll_limit = self.scroll_limits[self.index] if self.scroll_limits else 0

    def update(self):
        if not self.scroll_limits:
            return
            
        if self.state == "SLIDE":
            self.img_x -= SCROLL_SPEED
            if self.img_x <= self.scroll_limit:
                self.state = "FADE_OUT"

        elif self.state == "FADE_OUT":
            self.img_x -= (SCROLL_SPEED * 0.8)
            self.fade_alpha += FADE_SPEED
            if self.fade_alpha >= 255:
                self.fade_alpha = 255
                self.index = (self.index + 1) % len(self.images)
                self.load_image()
                self.state = "FADE_IN"

        elif self.state == "FADE_IN":
            self.img_x -= SCROLL_SPEED
            self.fade_alpha -= FADE_SPEED
            if self.fade_alpha <= 0:
                self.fade_alpha = 0
                self.state = "SLIDE"

    def draw(self, surface):
        surface.blit(self.images[self.index], (int(self.img_x), 0))
        if self.fade_alpha > 0:
            self.fade_surf.set_alpha(self.fade_alpha)
            surface.blit(self.fade_surf, (0, 0))


class Player(pygame.Rect):
    def __init__(self, img):
        super().__init__(SCREEN_W // 8, SCREEN_H // 2, PLAYER_HEAD_W, PLAYER_HEAD_H)
        self.original_image = img
        self.image = img
        self.velocity = 0
        self.gravity = 0.5

    def update(self):
        self.velocity += self.gravity
        self.y += self.velocity
        self.top = max(0, self.top)

        rotation_angle = self.velocity * -2
        if rotation_angle > 20: rotation_angle = 20
        if rotation_angle < -40: rotation_angle = -40

        self.image = pygame.transform.rotate(self.original_image, rotation_angle)


class Block(pygame.Rect):
    def __init__(self, x, y, img, mob_img=None):
        super().__init__(x, y, BLOCK_W, BLOCK_H)
        self.image = img
        self.mob_image = mob_img
        self.scored = False
        self.offset = 0.0
        self.angle = random.uniform(0, 6.28)


# ==========================================
# 3. GLOBAL UTILITY FUNCTIONS
# ==========================================

def load_random_music():
    track = f"music{str(random.randint(1, 34)).zfill(2)}.ogg"
    path = os.path.join(MUSIC_FOLDER, track)
    if os.path.exists(path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
        except:
            pass

def is_web():
    """Reliably detect if running in a Pyodide/WASM environment."""
    try:
        import sys
        return sys.platform == "emscripten"
    except:
        pass
    try:
        import platform
        return platform.system() == "Emscripten"
    except:
        pass
    try:
        import js  # type: ignore  # js module only exists in Pyodide/pygbag
        return True
    except ImportError:
        pass
    return False


def quit_to_site():
    """
    On web: redirects the browser to edwinjr.com.
    On desktop: quits pygame and exits.
    """
    if is_web():
        try:
            import js  # type: ignore
            js.window.location.href = "https://edwinjr.com"
        except Exception as e:
            print(f"Redirect failed: {e}")
            pygame.quit()
            sys.exit()
    else:
        pygame.quit()
        sys.exit()


SKIN_FETCH_ERROR = ""  # surfaced on the input screen so failures are visible without a terminal


async def get_minecraft_skin(username):
    """
    Fetches the player's Minecraft skin avatar head using MC-Heads.
    Handles Pygbag/Pyodide (web/WASM) via js.fetch and desktop (requests) separately.
    """
    global SKIN_FETCH_ERROR
    SKIN_FETCH_ERROR = ""
    url = f"https://mc-heads.net/avatar/{username}/{PLAYER_HEAD_W}"

    if is_web():
        try:
            import js  # type: ignore
            try:
                from pyodide.ffi import create_proxy as _real_create_proxy  # type: ignore
            except Exception:
                _real_create_proxy = None
            if callable(_real_create_proxy):
                create_proxy = _real_create_proxy
            else:
                create_proxy = lambda fn: fn  # pygbag may auto-proxy, or no proxy needed
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            fut = loop.create_future()

            # construct Uint8Array on the JS side — pygbag's JsProxy may not expose .new
            _make_u8 = js.eval("(b) => new Uint8Array(b)")

            def _on_buffer(buffer):
                try:
                    u8 = _make_u8(buffer)
                    length = int(u8.length)
                    ba = bytearray(length)
                    for i in range(length):
                        ba[i] = int(u8[i])
                    if not fut.done():
                        fut.set_result(bytes(ba))
                except Exception as ex:
                    if not fut.done():
                        fut.set_exception(ex)

            def _on_response(response):
                try:
                    status = int(response.status)
                    if status != 200:
                        if not fut.done():
                            fut.set_exception(Exception(f"HTTP {status}"))
                        return
                    response.arrayBuffer().then(
                        create_proxy(_on_buffer),
                        create_proxy(lambda e: fut.set_exception(Exception(f"arrayBuffer: {e}")) if not fut.done() else None),
                    )
                except Exception as ex:
                    if not fut.done():
                        fut.set_exception(ex)

            # pygbag/pyodide expose fetch in different places across versions
            fetch_fn = getattr(js, "fetch", None)
            if fetch_fn is None:
                window_obj = getattr(js, "window", None)
                if window_obj is not None:
                    fetch_fn = getattr(window_obj, "fetch", None)
            if fetch_fn is None:
                try:
                    import platform as _plat
                    fetch_fn = _plat.window.fetch
                except Exception:
                    fetch_fn = None
            if fetch_fn is None:
                raise RuntimeError("no js fetch available in this runtime")
            fetch_fn(url).then(
                create_proxy(_on_response),
                create_proxy(lambda e: fut.set_exception(Exception(f"fetch: {e}")) if not fut.done() else None),
            )

            img_bytes = await asyncio.wait_for(fut, timeout=8.0)
            print(f"[Web] Got {len(img_bytes)} bytes for skin")
            if len(img_bytes) < 100:
                raise RuntimeError(f"image data too small ({len(img_bytes)} bytes) — likely CORS-blocked")
            # pygame_ce on pygbag can't read from BytesIO — write to Emscripten FS first
            tmp_path = "/tmp/skin.png"
            with open(tmp_path, "wb") as f:
                f.write(img_bytes)
            surf = pygame.image.load(tmp_path)
            try:
                return surf.convert_alpha()
            except Exception as ce:
                print(f"[Web] convert_alpha failed, using raw surface: {ce}")
                return surf
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            where = f" @ line {tb[-1].lineno}" if tb else ""
            traceback.print_exc()
            SKIN_FETCH_ERROR = f"[Web] {type(e).__name__}{where}: {e}"
            print(SKIN_FETCH_ERROR)
    else:
        try:
            import requests
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(url, timeout=5)
            )
            if response.status_code == 200:
                return pygame.image.load(io.BytesIO(response.content)).convert_alpha()
            else:
                SKIN_FETCH_ERROR = f"[Desktop] Bad status: {response.status_code}"
                print(SKIN_FETCH_ERROR)
        except Exception as e:
            SKIN_FETCH_ERROR = f"[Desktop] Fetch failed: {type(e).__name__}: {e}"
            print(SKIN_FETCH_ERROR)

    # --- Fallback: icon.png ---
    try:
        fallback_path = resource_path("assets/icon.png")
        if os.path.exists(fallback_path):
            print("[Fallback] Using icon.png")
            return pygame.image.load(fallback_path).convert_alpha()
    except Exception as e:
        print(f"[Fallback] icon.png load failed: {e}")

    # --- Last resort: brown square ---
    surf = pygame.Surface((PLAYER_HEAD_W, PLAYER_HEAD_H))
    surf.fill((141, 107, 78))
    return surf


# ==========================================
# 4. MAIN APP EXECUTION LOOP
# ==========================================

# At the very top of main(), add a CORS-safe mixer pre-init guard:
try:
    pygame.mixer.pre_init(22050, -16, 1, 512)  # Lower buffer = less latency on web
except:
    pass

# Replace load_random_music() for web — ogg streaming can hang in WASM:
async def load_random_music_async():
    track = f"music{str(random.randint(1, 34)).zfill(2)}.ogg"
    path = os.path.join(MUSIC_FOLDER, track)
    if os.path.exists(path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"Music load failed (expected on web): {e}")

async def main():
    global GAME_SPEED, PIPE_OSCILLATION, PIPE_OSCILLATE_SPEED, PIPE_OSCILLATE_AMOUNT

    window = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("FlappyMC - Minecraft-themed Flappy Bird")
    clock = pygame.time.Clock()
    
    font = pygame.font.SysFont("Arial", 40, bold=True)
    title_font = pygame.font.SysFont("Arial", 60, bold=True)

    icon_path = resource_path("assets/icon.png")
    font_path = resource_path("assets/Minecraft.ttf")

    if os.path.exists(font_path):
        font = pygame.font.Font(font_path, 40)
        title_font = pygame.font.Font(font_path, 60)

    if os.path.exists(icon_path):
        try:
            icon_img = pygame.image.load(icon_path).convert_alpha()
            pygame.display.set_icon(icon_img)
        except:
            pass

    load_random_music()
    
    try:
        grass = pygame.image.load(resource_path("assets/grass_block.png")).convert_alpha()
        grass = pygame.transform.scale(grass, (SCREEN_W, SCREEN_H))
    except:
        grass = pygame.Surface((SCREEN_W, SCREEN_H))
        grass.fill((0, 50, 0))

    try:
        pipe_img = pygame.image.load(resource_path("assets/topblock.png")).convert_alpha()
        pipe_img = pygame.transform.scale(pipe_img, (BLOCK_W, BLOCK_H))
    except:
        pipe_img = pygame.Surface((BLOCK_W, BLOCK_H))
        pipe_img.fill((0, 200, 0))

    try:
        pipe_bottom_img = pygame.image.load(resource_path("assets/bottomblock.png")).convert_alpha()
        pipe_bottom_img = pygame.transform.scale(pipe_bottom_img, (BLOCK_W, BLOCK_H))
    except:
        pipe_bottom_img = pygame.transform.flip(pipe_img, False, True)

    mob_images = []
    for i in range(1, 16):
        filename = f"animal{i}.png"
        try:
            mob_img = pygame.image.load(resource_path(f"assets/{filename}")).convert_alpha()
            mob_img = pygame.transform.scale(mob_img, (120, 120))
            mob_images.append(mob_img)
        except:
            pass

    try:
        panorama = PanoramicFader(SCREEN_W, SCREEN_H)
    except:
        panorama = None

    try:
        xp_sound = pygame.mixer.Sound(resource_path("assets/xp.ogg"))
        xp_sound.set_volume(0.3)
    except:
        xp_sound = None

    try:
        xp2_sound = pygame.mixer.Sound(resource_path("assets/xp2.ogg"))
        xp2_sound.set_volume(0.3)
    except:
        xp2_sound = None

    try:
        jump_sound = pygame.mixer.Sound(resource_path("assets/jump.ogg"))
        jump_sound.set_volume(1.0)
    except:
        jump_sound = None

    try:
        oof_sound = pygame.mixer.Sound(resource_path("assets/oof.ogg"))
        oof_sound.set_volume(1.0)
    except:
        oof_sound = None

    volume_level = 0.5  
    pygame.mixer.music.set_volume(volume_level)

    try:
        click_sound = pygame.mixer.Sound(resource_path("assets/click.ogg"))
        click_sound.set_volume(volume_level)
    except:
        click_sound = None

    blocks, scroll, user_text = [], 0, ""
    score = 0
    input_active = True
    menu_active = False
    waiting_active = False
    game_active = False
    game_over_active = False
    options_active = False
    music_on = True
    fullscreen_on = False
    player = None

    pipe_timer = 0
    pipe_interval = 1500  

    btn_w, btn_h = 300, 60
    btn_x = SCREEN_W // 2 - btn_w // 2
    play_button = pygame.Rect(btn_x, 300, btn_w, btn_h)
    options_button = pygame.Rect(btn_x, 380, btn_w, btn_h)
    menu_quit_button = pygame.Rect(btn_x, 460, btn_w, btn_h)

    back_button = pygame.Rect(btn_x, 500, btn_w, btn_h)
    checkbox_rect = pygame.Rect(SCREEN_W // 2 + 200, 300, 40, 40)
    fs_checkbox_rect = pygame.Rect(SCREEN_W // 2 + 370, 300, 40, 40)
    
    minus_button = pygame.Rect(SCREEN_W // 2 + 100, 440, 40, 40)
    plus_button = pygame.Rect(SCREEN_W // 2 + 300, 440, 40, 40)

    reset_button = pygame.Rect(btn_x, 320, btn_w, btn_h)        
    change_user_button = pygame.Rect(btn_x, 400, btn_w, btn_h)  
    go_options_button = pygame.Rect(btn_x, 480, btn_w, btn_h)   
    go_menu_button = pygame.Rect(btn_x, 560, btn_w, btn_h)      
    exit_button = pygame.Rect(btn_x, 640, btn_w, btn_h)         

    options_source = "MENU" 
    is_fetching_skin = False 

    while True:
        dt = clock.tick(FPS) 
        events = pygame.event.get()
        mouse_pos = pygame.mouse.get_pos()

        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if input_active and not is_fetching_skin:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if user_text.strip() != "":
                            is_fetching_skin = True
                            skin = await get_minecraft_skin(user_text)
                            if skin is None:
                                skin = pygame.Surface((PLAYER_HEAD_W, PLAYER_HEAD_H))
                                skin.fill((100, 50, 20)) 
                            player = Player(skin)
                            is_fetching_skin = False
                            input_active = False
                            menu_active = True
                    elif event.key == pygame.K_BACKSPACE:
                        user_text = user_text[:-1]
                    elif event.key == pygame.K_SPACE:
                        pass 
                    else:
                        char = event.unicode
                        if char.isalnum() or char == "_":
                            user_text += char

            elif options_active:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if checkbox_rect.collidepoint(event.pos):
                            play_click(click_sound)
                            music_on = not music_on
                            if music_on:
                                pygame.mixer.music.unpause()
                            else:
                                pygame.mixer.music.pause()
                        elif fs_checkbox_rect.collidepoint(event.pos):
                            play_click(click_sound)
                            fullscreen_on = not fullscreen_on
                            if fullscreen_on:
                                window = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
                            else:
                                window = pygame.display.set_mode((SCREEN_W, SCREEN_H))
                        elif back_button.collidepoint(event.pos):
                            play_click(click_sound)
                            options_active = False
                            if options_source == "GAMEOVER":
                                game_over_active = True
                            else:
                                menu_active = True
                        
                        elif minus_button.collidepoint(event.pos):
                            volume_level = max(0.0, volume_level - 0.1)
                            pygame.mixer.music.set_volume(volume_level)
                            play_click(click_sound)  
                            if click_sound: click_sound.set_volume(volume_level)
                            if xp_sound: xp_sound.set_volume(volume_level * 0.3)
                            if xp2_sound: xp2_sound.set_volume(volume_level * 0.3)
                            if jump_sound: jump_sound.set_volume(volume_level)
                            if oof_sound: oof_sound.set_volume(volume_level)

                        elif plus_button.collidepoint(event.pos):
                            volume_level = min(1.0, volume_level + 0.1)
                            pygame.mixer.music.set_volume(volume_level)
                            play_click(click_sound)  
                            if click_sound: click_sound.set_volume(volume_level)
                            if xp_sound: xp_sound.set_volume(volume_level * 0.3)
                            if xp2_sound: xp2_sound.set_volume(volume_level * 0.3)
                            if jump_sound: jump_sound.set_volume(volume_level)
                            if oof_sound: oof_sound.set_volume(volume_level)

            elif menu_active:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if play_button.collidepoint(event.pos):
                            play_click(click_sound)
                            menu_active = False
                            waiting_active = True
                            player.y = SCREEN_H // 2
                            player.velocity = 0
                        elif options_button.collidepoint(event.pos):  
                            play_click(click_sound)
                            menu_active = False
                            options_source = "MENU"
                            options_active = True
                        elif menu_quit_button.collidepoint(event.pos):
                            # ── QUIT from main menu → back to edwinjr.com ──
                            play_click(click_sound)
                            quit_to_site()

            elif game_over_active:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if reset_button.collidepoint(event.pos):
                            play_click(click_sound)
                            blocks = []
                            scroll = 0
                            score = 0
                            GAME_SPEED = BASE_GAME_SPEED
                            PIPE_OSCILLATION = False
                            PIPE_OSCILLATE_SPEED = BASE_PIPE_OSCILLATE_SPEED
                            PIPE_OSCILLATE_AMOUNT = BASE_PIPE_OSCILLATE_AMOUNT
                            player.y = SCREEN_H // 2
                            player.velocity = 0
                            game_over_active = False
                            waiting_active = True

                        elif change_user_button.collidepoint(event.pos):
                            play_click(click_sound)
                            blocks = []
                            scroll = 0
                            score = 0
                            GAME_SPEED = BASE_GAME_SPEED
                            PIPE_OSCILLATION = False
                            PIPE_OSCILLATE_SPEED = BASE_PIPE_OSCILLATE_SPEED
                            PIPE_OSCILLATE_AMOUNT = BASE_PIPE_OSCILLATE_AMOUNT
                            user_text = ""
                            game_over_active = False
                            input_active = True

                        elif go_options_button.collidepoint(event.pos):
                            play_click(click_sound)
                            game_over_active = False
                            options_source = "GAMEOVER"
                            options_active = True

                        elif go_menu_button.collidepoint(event.pos):
                            play_click(click_sound)
                            blocks = []
                            scroll = 0
                            score = 0
                            GAME_SPEED = BASE_GAME_SPEED
                            PIPE_OSCILLATION = False
                            PIPE_OSCILLATE_SPEED = BASE_PIPE_OSCILLATE_SPEED
                            PIPE_OSCILLATE_AMOUNT = BASE_PIPE_OSCILLATE_AMOUNT
                            game_over_active = False
                            menu_active = True

                        elif exit_button.collidepoint(event.pos):
                            # ── QUIT from game over screen → back to edwinjr.com ──
                            play_click(click_sound)
                            quit_to_site()
                    
            elif waiting_active:
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE) or \
                   (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                    waiting_active = False
                    game_active = True
                    player.velocity = -9
                    if jump_sound:
                        jump_sound.play()
                    pipe_timer = 0  

            elif game_active:
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE) or \
                   (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                    player.velocity = -9
                    if jump_sound:
                        jump_sound.play()

        if panorama:
            panorama.update()

        if game_active:
            pipe_timer += dt
            if pipe_timer >= pipe_interval:
                pipe_timer = 0
                gap_y = random.randint(150, SCREEN_H - 400)
                shared_angle = random.uniform(0, 6.28)
                
                top_pipe = Block(SCREEN_W, gap_y - BLOCK_H, pipe_img)
                top_pipe.angle = shared_angle
                
                chosen_mob = random.choice(mob_images) if mob_images else None
                bottom_pipe = Block(SCREEN_W, gap_y + 250, pipe_bottom_img, mob_img=chosen_mob)
                bottom_pipe.angle = shared_angle
                
                blocks.append(top_pipe)
                blocks.append(bottom_pipe)

            scroll += GAME_SPEED
            player.update()

            for b in blocks[:]:
                b.x -= GAME_SPEED
                
                if PIPE_OSCILLATION and b.y < 0:
                    b.angle += PIPE_OSCILLATE_SPEED
                    b.offset = math.sin(b.angle) * PIPE_OSCILLATE_AMOUNT
                    b.y += b.offset
                elif PIPE_OSCILLATION and b.y >= 0:
                    for top in blocks:
                        if top.y < 0 and top.x == b.x:
                            b.y += top.offset
                            break

                if player.colliderect(b):
                    game_active = False
                    game_over_active = True
                    if oof_sound:
                        oof_sound.play()

                if b.right < player.left and not getattr(b, 'scored', False):
                    b.scored = True
                    if b.y < 0: 
                        score += 1
                        if score % 50 == 0:
                            if xp2_sound:
                                xp2_sound.play()
                            GAME_SPEED += 0.1
                            PIPE_OSCILLATE_SPEED += 0.05
                            PIPE_OSCILLATE_AMOUNT += 1.5
                            PIPE_OSCILLATION = True
                        else:
                            if xp_sound:
                                xp_sound.play()

            if player.bottom > SCREEN_H:
                player.bottom = SCREEN_H
                game_active = False
                game_over_active = True
                if oof_sound:
                    oof_sound.play()

        draw_background(panorama, window)

        if input_active:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H))
            overlay.set_alpha(150)
            window.blit(overlay, (0, 0))
            
            prompt_text = "Loading Skin..." if is_fetching_skin else "Enter Minecraft Username:"
            prompt = font.render(prompt_text, True, WHITE)
            window.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, 200))
            
            input_box = pygame.Rect(SCREEN_W // 2 - 250, 300, 500, 55)
            pygame.draw.rect(window, GRAY, input_box)
            text_surf = font.render(user_text, True, WHITE)
            window.blit(text_surf, (input_box.x + 15, input_box.y + 8))

            if SKIN_FETCH_ERROR:
                err_font = pygame.font.SysFont("Arial", 22)
                err_surf = err_font.render(SKIN_FETCH_ERROR[:120], True, RED)
                window.blit(err_surf, (SCREEN_W // 2 - err_surf.get_width() // 2, 380))

        elif menu_active:
            title = title_font.render("FLAPPY MC", True, WHITE)
            window.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 150))
            
            pygame.draw.rect(window, WHITE if play_button.collidepoint(mouse_pos) else GRAY, play_button)
            play_text = font.render("PLAY", True, BLACK if play_button.collidepoint(mouse_pos) else WHITE)
            window.blit(play_text, (play_button.x + 75, play_button.y + 7))
              
            pygame.draw.rect(window, WHITE if options_button.collidepoint(mouse_pos) else GRAY, options_button)
            options_text = font.render("OPTIONS", True, BLACK if options_button.collidepoint(mouse_pos) else WHITE)
            window.blit(options_text, (options_button.x + 45, options_button.y + 7))

            pygame.draw.rect(window, WHITE if menu_quit_button.collidepoint(mouse_pos) else GRAY, menu_quit_button)
            menu_quit_text = font.render("QUIT", True, BLACK if menu_quit_button.collidepoint(mouse_pos) else WHITE)
            window.blit(menu_quit_text, (menu_quit_button.x + 95, menu_quit_button.y + 7))

        elif options_active:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H))
            overlay.set_alpha(150)
            overlay.fill(BLACK)
            window.blit(overlay, (0, 0))

            options_title = title_font.render("OPTIONS", True, WHITE)
            window.blit(options_title, (SCREEN_W // 2 - options_title.get_width() // 2, 150))

            audio_text = font.render("Background Audio", True, WHITE)
            window.blit(audio_text, (SCREEN_W // 2 - 220, 300))
            pygame.draw.rect(window, WHITE, checkbox_rect, 3)
            if music_on:
                pygame.draw.line(window, WHITE, (checkbox_rect.x + 6, checkbox_rect.y + 20), (checkbox_rect.x + 15, checkbox_rect.y + 30), 3)
                pygame.draw.line(window, WHITE, (checkbox_rect.x + 15, checkbox_rect.y + 30), (checkbox_rect.x + 34, checkbox_rect.y + 8), 3)

            fs_text = font.render("Fullscreen", True, WHITE)
            window.blit(fs_text, (SCREEN_W // 2 - 220, 370))
            pygame.draw.rect(window, WHITE, fs_checkbox_rect, 3)
            if fullscreen_on:
                pygame.draw.line(window, WHITE, (fs_checkbox_rect.x + 6, fs_checkbox_rect.y + 20), (fs_checkbox_rect.x + 15, fs_checkbox_rect.y + 30), 3)
                pygame.draw.line(window, WHITE, (fs_checkbox_rect.x + 15, fs_checkbox_rect.y + 30), (fs_checkbox_rect.x + 34, fs_checkbox_rect.y + 8), 3)

            vol_label = font.render("Volume Level", True, WHITE)
            window.blit(vol_label, (SCREEN_W // 2 - 220, 440))
            
            pygame.draw.rect(window, WHITE if minus_button.collidepoint(mouse_pos) else GRAY, minus_button)
            minus_text = font.render("-", True, BLACK if minus_button.collidepoint(mouse_pos) else WHITE)
            window.blit(minus_text, (minus_button.x + 13, minus_button.y + 1))

            vol_percentage = f"{int(round(volume_level * 100))}%"
            vol_num_surf = font.render(vol_percentage, True, WHITE)
            text_pos_x = (minus_button.right + plus_button.left) // 2 - (vol_num_surf.get_width() // 2)
            window.blit(vol_num_surf, (text_pos_x, 440))

            pygame.draw.rect(window, WHITE if plus_button.collidepoint(mouse_pos) else GRAY, plus_button)
            plus_text = font.render("+", True, BLACK if plus_button.collidepoint(mouse_pos) else WHITE)
            window.blit(plus_text, (plus_button.x + 11, plus_button.y + 1))

            pygame.draw.rect(window, WHITE if back_button.collidepoint(mouse_pos) else GRAY, back_button)
            back_text = font.render("BACK", True, BLACK if back_button.collidepoint(mouse_pos) else WHITE)
            window.blit(back_text, (back_button.x + 80, back_button.y + 7))

        elif waiting_active:
            scroll += GAME_SPEED
            grass_x = int(scroll * GRASS_SPEED) % SCREEN_W
            window.blit(grass, (-grass_x, 0))
            window.blit(grass, (SCREEN_W - grass_x, 0))
            window.blit(player.image, player.topleft)
            
            hint = font.render("Press SPACE or Click to Start", True, WHITE)
            shadow = font.render("Press SPACE or Click to Start", True, BLACK)
            hx = SCREEN_W // 2 - hint.get_width() // 2
            window.blit(shadow, (hx + 2, SCREEN_H - 82))
            window.blit(hint, (hx, SCREEN_H - 80))

        elif game_over_active or game_active:
            for b in blocks:
                window.blit(b.image, b.topleft)
                if b.mob_image:
                    window.blit(b.mob_image, b.topleft)

            grass_x = int(scroll * GRASS_SPEED) % SCREEN_W
            window.blit(grass, (-grass_x, 0))
            window.blit(grass, (SCREEN_W - grass_x, 0))
            window.blit(player.image, player.topleft)

            if game_active:
                score_str = str(score)
                s_text = title_font.render(score_str, True, WHITE)
                sh_text = title_font.render(score_str, True, BLACK)
                text_x = SCREEN_W // 2 - s_text.get_width() // 2
                window.blit(sh_text, (text_x + 4, 54))
                window.blit(s_text, (text_x, 50))

            if game_over_active:
                overlay = pygame.Surface((SCREEN_W, SCREEN_H))
                overlay.set_alpha(150)
                overlay.fill(BLACK)
                window.blit(overlay, (0, 0))

                go_text = title_font.render("YOU DIED", True, RED)
                window.blit(go_text, (SCREEN_W // 2 - go_text.get_width() // 2, 100))

                final_score = font.render(f"Score: {score}", True, WHITE)
                window.blit(final_score, (SCREEN_W // 2 - final_score.get_width() // 2, 220))

                pygame.draw.rect(window, WHITE if reset_button.collidepoint(mouse_pos) else GRAY, reset_button)
                reset_text = font.render("TRY AGAIN", True, BLACK if reset_button.collidepoint(mouse_pos) else WHITE)
                window.blit(reset_text, (reset_button.x + 45, reset_button.y + 7))

                pygame.draw.rect(window, WHITE if change_user_button.collidepoint(mouse_pos) else GRAY, change_user_button)
                change_user_text = font.render("CHANGE NAME", True, BLACK if change_user_button.collidepoint(mouse_pos) else WHITE)
                window.blit(change_user_text, (change_user_button.x + 15, change_user_button.y + 7))

                pygame.draw.rect(window, WHITE if go_options_button.collidepoint(mouse_pos) else GRAY, go_options_button)
                go_opt_text = font.render("OPTIONS", True, BLACK if go_options_button.collidepoint(mouse_pos) else WHITE)
                window.blit(go_opt_text, (go_options_button.x + 55, go_options_button.y + 7))

                pygame.draw.rect(window, WHITE if go_menu_button.collidepoint(mouse_pos) else GRAY, go_menu_button)
                go_menu_text = font.render("MAIN MENU", True, BLACK if go_menu_button.collidepoint(mouse_pos) else WHITE)
                window.blit(go_menu_text, (go_menu_button.x + 40, go_menu_button.y + 7))

                pygame.draw.rect(window, WHITE if exit_button.collidepoint(mouse_pos) else GRAY, exit_button)
                exit_text = font.render("QUIT", True, BLACK if exit_button.collidepoint(mouse_pos) else WHITE)
                window.blit(exit_text, (exit_button.x + 95, exit_button.y + 7))

        pygame.display.update()
        await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())