"""
Cinematic 30-Second Motion Graphics Animation Video for Satyahd.
Crafted with Senior Lead Motion Design principles:
- 1080p Full HD (1920x1080 @ 30fps = 900 frames, exactly 30.00s)
- Unhurried, natural voiceover pacing (rate="+5%") with crystal clarity
- Zero personal intro/names: pure crisis-to-solution narrative
- High-fidelity animated application mockup showcasing the live Satyahd platform in action:
  * Sleek browser window with macOS dots and live SSL URL
  * Incoming customer chat bubble sliding in
  * Rogue LLM draft intercepted by dynamic laser scanline
  * Real-time guardrail telemetry inspector with rule trigger breakdown
  * Autonomous bounded safe rewrite transition with Ed25519 signature
- Kinetic typography, rotating cyber radar sweep, 3D grid perspective, and blockchain ledger
- 125 BPM cyber synth score with sub-bass, kick, and voice ducking
"""

import os
import sys
import math
import asyncio
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

OUT_DIR = os.path.abspath("reports/video_assets/v10_cinematic")
os.makedirs(OUT_DIR, exist_ok=True)

FINAL_VIDEO = os.path.abspath("Satyahd_30s_Official_Animation.mp4")

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_FRAMES = 900  # Exactly 30.00 seconds
SAMPLE_RATE = 44100

FONT_DIR = r"C:\Windows\Fonts"
FONT_HERO = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 82)
FONT_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 54)
FONT_SUBTITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 26)
FONT_HEADING = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 36)
FONT_BODY = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 20)
FONT_BODY_BOLD = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 21)
FONT_MONO = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 19)
FONT_MONO_SMALL = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 15)
FONT_BADGE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 16)
FONT_TICKER = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 14)

# Color Palette
C_BG = (3, 3, 5)
C_SURFACE = (12, 12, 16)
C_SURFACE_ELEVATED = (20, 20, 26)
C_BORDER = (40, 40, 48)
C_CHAMPAGNE = (214, 180, 163)
C_BRONZE = (100, 52, 20)
C_TITANIUM = (206, 192, 184)
C_GREEN = (0, 229, 117)
C_RED = (230, 38, 56)
C_RED_BG = (28, 6, 10)
C_CYAN = (0, 210, 255)
C_GOLD = (255, 195, 80)
C_WHITE = (255, 255, 255)


# -----------------------------------------------------------------------------
# 1. AUDIO SYNTHESIS & SOUND DESIGN (30.00s Master)
# -----------------------------------------------------------------------------

async def generate_cinematic_speech():
    """Generates 5 crisp, natural-speed voiceover segments without personal intro."""
    import edge_tts

    segments = [
        ("act1.mp3", "AI agents are everywhere, but the industry has a fatal blindspot.", "+5%"),
        ("act2.mp3", "Rogue chatbot promises create legal liability, and prompts cannot stop it.", "+5%"),
        ("act3.mp3", "Enter Satyahd, intercepting and bounding rogue commitments in milliseconds.", "+5%"),
        ("act4.mp3", "Every decision is sealed in an Ed25519 hash chain.", "+5%"),
        ("act5.mp3", "Zero trust, zero liability, in five lines of code.", "+5%")
    ]

    for fname, text, rate in segments:
        out_p = os.path.join(OUT_DIR, fname)
        comm = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate=rate)
        await comm.save(out_p)
        dur = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", out_p]
        ).decode().strip()
        print(f"  Generated {fname}: {float(dur):.2f}s | {text}")


def build_cinematic_audio():
    """Generates 125 BPM cyber soundtrack with bass drops, risers, and mixes voiceover."""
    print("\n[Step 1/3] Generating voiceover segments with ChristopherNeural (Natural Pacing)...")
    asyncio.run(generate_cinematic_speech())

    total_samples = int(30.0 * SAMPLE_RATE)
    master_audio = np.zeros(total_samples, dtype=np.float32)

    # 1. Procedural 125 BPM Cyber Synth Soundtrack
    t = np.linspace(0, 30.0, total_samples, endpoint=False)
    
    # Kick drum envelope (125 BPM = 0.48s per beat)
    beat_period = 60.0 / 125.0
    beat_t = t % beat_period
    kick_env = np.exp(-18 * beat_t)
    sub_kick = 0.35 * np.sin(2 * np.pi * (50 + 70 * np.exp(-30 * beat_t)) * beat_t) * kick_env
    
    # Hi-hat rhythm on 1/8 notes
    hat_env = np.exp(-55 * (t % (beat_period / 2)))
    noise = np.random.uniform(-1, 1, total_samples) * hat_env * 0.05

    # Cinematic deep sub drone (F minor: 43.6Hz & 87.3Hz)
    drone = 0.12 * np.sin(2 * np.pi * 43.6 * t) + 0.08 * np.sin(2 * np.pi * 87.3 * t)

    # Synth bass arpeggiator (driving 1/16th notes)
    arp_notes = [87.3, 103.8, 130.8, 155.6, 174.6]
    arp = np.zeros_like(t)
    step_t = beat_period / 4.0
    for i, freq in enumerate(arp_notes):
        mask = ((t / step_t).astype(int) % len(arp_notes)) == i
        env = np.exp(-35 * (t % step_t))
        arp += 0.08 * np.sin(2 * np.pi * freq * t) * env * mask

    music = sub_kick + noise + drone + arp

    # Smooth fade out in final 1.5s
    fade_start = int(28.5 * SAMPLE_RATE)
    music[fade_start:] *= np.linspace(1.0, 0.0, total_samples - fade_start)

    # 2. Place voiceover clips at exact scene timestamps
    # Act 1: 0.3s | Act 2: 5.8s | Act 3: 11.8s | Act 4: 17.5s | Act 5: 23.4s
    scene_starts = [0.3, 5.8, 11.8, 17.5, 23.4]

    for idx, start_sec in enumerate(scene_starts):
        mp3_p = os.path.join(OUT_DIR, f"act{idx+1}.mp3")
        wav_p = os.path.join(OUT_DIR, f"act{idx+1}.wav")
        subprocess.run(["ffmpeg", "-y", "-i", mp3_p, "-ar", str(SAMPLE_RATE), "-ac", "1", wav_p],
                       capture_output=True, check=True)

        with wave.open(wav_p, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            voice = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        start_sample = int(start_sec * SAMPLE_RATE)
        end_sample = min(start_sample + len(voice), total_samples)
        v_slice = voice[:end_sample - start_sample]

        # Voice ducking: lower music volume during speech
        duck_end = min(end_sample + int(0.2 * SAMPLE_RATE), total_samples)
        music[start_sample:duck_end] *= 0.30
        master_audio[start_sample:end_sample] += v_slice * 1.55  # Clear voice presence

    final_mix = np.clip(master_audio + music, -0.98, 0.98)
    master_wav = os.path.join(OUT_DIR, "master_cinematic_30s.wav")

    with wave.open(master_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((final_mix * 32767.0).astype(np.int16).tobytes())

    print(f"  Master 30s Audio Track Created: {master_wav}")
    return master_wav


# -----------------------------------------------------------------------------
# 2. MOTION GRAPHICS & VISUAL ENGINE
# -----------------------------------------------------------------------------

# Continuous background dust particles
np.random.seed(42)
PARTICLES = [
    {
        "x": np.random.uniform(0, WIDTH),
        "y": np.random.uniform(0, HEIGHT),
        "speed": np.random.uniform(1.2, 3.8),
        "size": np.random.uniform(1.5, 4.0),
        "color": C_CHAMPAGNE if np.random.rand() > 0.4 else C_CYAN
    }
    for _ in range(60)
]

def draw_particles(draw, frame_idx):
    """Draws drifting cyber dust particles."""
    for p in PARTICLES:
        y = (p["y"] - frame_idx * p["speed"]) % HEIGHT
        x = (p["x"] + math.sin(frame_idx * 0.05 + p["speed"]) * 12) % WIDTH
        r = p["size"]
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=p["color"])


def draw_perspective_grid(draw, frame_idx, color=(35, 30, 45)):
    """Draws an animated 3D cyber grid on the floor."""
    vanishing_y = 660
    offset = (frame_idx * 4.0) % 50
    for i in range(11):
        prog = ((i * 50 + offset) / 550.0) ** 1.9
        y = int(vanishing_y + prog * (HEIGHT - vanishing_y))
        if y < HEIGHT:
            draw.line([(0, y), (WIDTH, y)], fill=color, width=1)

    for x in range(-WIDTH, 2 * WIDTH, 80):
        draw.line([(WIDTH // 2, vanishing_y), (x, HEIGHT)], fill=(25, 20, 30), width=1)


def draw_hud_brackets(draw, cx, cy, w, h, color=C_CHAMPAGNE, bracket_len=24, width=2):
    """Draws sleek sci-fi HUD corner brackets."""
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = cx + w // 2, cy + h // 2

    # Top-Left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=color, width=width)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=color, width=width)
    # Top-Right
    draw.line([(x2, y1), (x2 - bracket_len, y1)], fill=color, width=width)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=color, width=width)
    # Bottom-Left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=color, width=width)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=color, width=width)
    # Bottom-Right
    draw.line([(x2, y2), (x2 - bracket_len, y2)], fill=color, width=width)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=color, width=width)


def draw_marquee_ribbon(draw, frame_idx, y=14):
    """Draws high-contrast 11x continuous marquee hero ticker."""
    text = "⚡ 11X DIGITAL WORKER PLATFORM  //  ZERO-TRUST SATYAHD GUARDRAIL  //  SUB-18MS REAL-TIME STREAMING  //  100% CONTAINMENT ACROSS ADVERSARIAL ATTACKS  //  "
    offset = int(frame_idx * 4.5) % 950
    full_text = text * 4
    draw.rectangle([(0, y - 10), (WIDTH, y + 24)], fill=(0, 0, 0))
    draw.line([(0, y + 24), (WIDTH, y + 24)], fill=C_BORDER, width=1)
    draw.text((20 - offset, y - 5), full_text, fill=C_TITANIUM, font=FONT_TICKER)


# -----------------------------------------------------------------------------
# SCENE 1: THE GLOBAL CRISIS (Frames 0 - 174, 0.0s - 5.8s)
# -----------------------------------------------------------------------------

def render_act_1(f):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    draw_particles(draw, f)
    draw_perspective_grid(draw, f)
    draw_marquee_ribbon(draw, f)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    t = f / 30.0

    # Top Tag
    draw.rectangle([(cx - 240, 75), (cx + 240, 115)], fill=(15, 15, 20), outline=C_BORDER, width=1)
    draw.text((cx - 220, 83), "GLOBAL AI INDUSTRY ALERT // 2026", fill=C_CHAMPAGNE, font=FONT_BADGE)

    # Massive Scale Kinetic Typography
    ease = min(1.0, f / 24.0)
    scale_y = int(cy - 120 + (1.0 - ease) * 40)
    draw.text((cx - 500, scale_y), "THE BILLION-DOLLAR", fill=C_WHITE, font=FONT_HERO)
    draw.text((cx - 390, scale_y + 90), "AI BLINDSPOT", fill=C_CHAMPAGNE, font=FONT_HERO)

    # Animated Rotating Cyber Radar Sweep
    radar_cx, radar_cy = cx, cy + 180
    for r in [90, 180, 270]:
        draw.ellipse([(radar_cx - r, radar_cy - r), (radar_cx + r, radar_cy + r)], outline=(30, 30, 45), width=1)

    # Radar sweep line
    angle = f * 0.08
    sweep_x = radar_cx + int(270 * math.cos(angle))
    sweep_y = radar_cy + int(270 * math.sin(angle))
    draw.line([(radar_cx, radar_cy), (sweep_x, sweep_y)], fill=(0, 180, 220), width=2)

    # Global Agent Network Topology Visualization (7 nodes)
    nodes = [
        (cx - 380, cy + 130),
        (cx - 180, cy + 160),
        (cx + 40, cy + 120),
        (cx + 260, cy + 170),
        (cx + 420, cy + 110),
        (cx - 80, cy + 240),
        (cx + 180, cy + 240)
    ]

    # Draw connection lines
    for i in range(len(nodes) - 1):
        draw.line([nodes[i], nodes[i+1]], fill=(40, 40, 55), width=2)
        # Moving data packet along the edge
        pack_prog = ((f * 3 + i * 20) % 100) / 100.0
        px = int(nodes[i][0] + pack_prog * (nodes[i+1][0] - nodes[i][0]))
        py = int(nodes[i][1] + pack_prog * (nodes[i+1][1] - nodes[i][1]))
        draw.ellipse([(px - 3, py - 3), (px + 3, py + 3)], fill=C_CYAN)

    draw.line([nodes[1], nodes[5]], fill=(40, 40, 55), width=1)
    draw.line([nodes[3], nodes[6]], fill=(40, 40, 55), width=1)

    # Glowing nodes
    for i, (nx, ny) in enumerate(nodes):
        pulse = 1.0 + 0.25 * math.sin(t * 8 + i)
        nr = int(12 * pulse)
        is_rogue = (i % 2 == 0)
        draw.ellipse([(nx - nr, ny - nr), (nx + nr, ny + nr)], fill=C_RED if is_rogue else C_CYAN)
        draw.ellipse([(nx - nr - 6, ny - nr - 6), (nx + nr + 6, ny + nr + 6)],
                     outline=C_RED if is_rogue else C_CYAN, width=1)

    # Floating alert badges
    if f > 25:
        draw.rectangle([(nodes[0][0] - 130, nodes[0][1] - 45), (nodes[0][0] + 130, nodes[0][1] - 15)],
                       fill=(30, 8, 12), outline=C_RED, width=1)
        draw.text((nodes[0][0] - 118, nodes[0][1] - 42), "⚠️ ROGUE COMMITMENT", fill=C_RED, font=FONT_MONO_SMALL)

    if f > 50:
        draw.rectangle([(nodes[4][0] - 120, nodes[4][1] - 45), (nodes[4][0] + 120, nodes[4][1] - 15)],
                       fill=(30, 8, 12), outline=C_RED, width=1)
        draw.text((nodes[4][0] - 108, nodes[4][1] - 42), "⚠️ PROMISED 90% OFF", fill=C_RED, font=FONT_MONO_SMALL)

    # Ticking Risk Counter at bottom
    risk_num = min(1450000, int(f * 26000))
    draw.rectangle([(cx - 480, HEIGHT - 180), (cx + 480, HEIGHT - 90)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
    draw.text((cx - 420, HEIGHT - 165), f"ENTERPRISE AI AGENTS DEPLOYED: {risk_num:,}", fill=C_WHITE, font=FONT_HEADING)
    draw.text((cx - 320, HEIGHT - 118), "STATUS: 100% EXPOSED TO CIVIL COURT LIABILITY", fill=C_RED, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 2: THE LEGAL CRISIS // MOFFATT v. AIR CANADA (Frames 174 - 354, 5.8s - 11.8s)
# -----------------------------------------------------------------------------

def render_act_2(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_RED_BG)
    draw = ImageDraw.Draw(img)

    f_global = 174 + f_rel
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2

    # Flashing Warning Hazard Stripes along Top and Bottom
    hazard_offset = (f_rel * 4) % 40
    for x in range(-40, WIDTH + 40, 40):
        draw.polygon([(x + hazard_offset, 48), (x + hazard_offset + 20, 48),
                      (x + hazard_offset + 5, 68), (x + hazard_offset - 15, 68)], fill=(80, 20, 25))
        draw.polygon([(x + hazard_offset, HEIGHT - 75), (x + hazard_offset + 20, HEIGHT - 75),
                      (x + hazard_offset + 5, HEIGHT - 55), (x + hazard_offset - 15, HEIGHT - 55)], fill=(80, 20, 25))

    # Emergency Flashing Header
    flash_color = C_RED if (f_rel // 6) % 2 == 0 else (255, 120, 130)
    draw.rectangle([(cx - 450, 80), (cx + 450, 140)], fill=(45, 10, 16), outline=flash_color, width=2)
    draw.text((cx - 410, 93), "🚨 CRITICAL CIVIL COURT PRECEDENT ESTABLISHED", fill=flash_color, font=FONT_HEADING)

    # High-Tech Tribunal Ruling Card
    card_top = 170
    card_h = 320
    draw.rectangle([(cx - 630, card_top), (cx + 630, card_top + card_h)], fill=(20, 8, 12), outline=(120, 30, 40), width=2)
    draw_hud_brackets(draw, cx, card_top + card_h // 2, 1260, card_h, color=C_RED, bracket_len=30, width=2)

    draw.text((cx - 580, card_top + 25), "CASE LAW: MOFFATT v. AIR CANADA (2024 BCCRT 149)", fill=C_RED, font=FONT_BODY_BOLD)
    draw.line([(cx - 580, card_top + 65), (cx + 580, card_top + 65)], fill=(90, 30, 40), width=1)

    ruling_text = (
        '"Air Canada argued that its customer service chatbot was a separate legal entity\n'
        'responsible for its own actions. The tribunal rejected this defense completely,\n'
        'ruling enterprises are strictly legally liable for all promises and misrepresentations\n'
        'hallucinated by their AI agents on their websites."'
    )
    draw.text((cx - 580, card_top + 85), ruling_text, fill=C_WHITE, font=FONT_BODY, spacing=10)

    # Dynamic Liability Damages Counter
    exposure = min(250000, int(f_rel * 1450))
    exp_text = f"LEGAL LIABILITY EXPOSURE: ${exposure:,}"
    draw.rectangle([(cx - 480, 520), (cx + 480, 610)], fill=(35, 10, 15), outline=C_RED, width=2)
    draw.text((cx - 325, 545), exp_text, fill=flash_color, font=FONT_HEADING)

    # Core Reality Callout
    draw.rectangle([(cx - 630, 645), (cx + 630, 755)], fill=(16, 16, 16), outline=C_BORDER, width=1)
    draw.text((cx - 510, 670), "⚡ SYSTEM PROMPTS & GUARDRAIL PROMPTS FAIL IN COURT", fill=C_WHITE, font=FONT_BODY_BOLD)
    draw.text((cx - 420, 710), "Probabilistic model weights cannot mathematically guarantee zero violations.", fill=C_TITANIUM, font=FONT_BODY)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 3: THE APPLICATION IN ACTION (Frames 354 - 525, 11.8s - 17.5s)
# -----------------------------------------------------------------------------

def render_act_3(f_rel):
    """
    High-fidelity animated desktop application mockup showcasing Satyahd live:
    - Floating browser window with macOS controls and URL bar (http://127.0.0.1:8000/)
    - Left side: Kaveri Digital Worker Chat with incoming customer prompt and rogue LLM draft
    - Center: Vertical animated scanning laser barrier with energy sparks
    - Right side: Satyahd Guardrail Real-Time Telemetry Inspector with live status morph & bounded rewrite
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 354 + f_rel
    draw_particles(draw, f_global)
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2

    # Title & Subtitle
    draw.text((cx - 180, 52), "SATYAHD", fill=C_WHITE, font=FONT_TITLE)
    draw.text((cx - 300, 118), "THE RUNTIME ZERO-TRUST POLICY FIREWALL", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)

    # Floating Browser Application Mockup
    # Outer Window Dimensions
    win_w = 1720
    win_h = 750
    win_x1 = (WIDTH - win_w) // 2
    win_y1 = 168
    win_x2 = win_x1 + win_w
    win_y2 = win_y1 + win_h

    # Window Background with Champagne/Bronze border
    draw.rectangle([(win_x1, win_y1), (win_x2, win_y2)], fill=(10, 10, 14), outline=C_BORDER, width=2)
    draw_hud_brackets(draw, cx, win_y1 + win_h // 2, win_w + 10, win_h + 10, color=C_CHAMPAGNE, bracket_len=26, width=2)

    # Window Chrome / Title Bar
    bar_h = 44
    draw.rectangle([(win_x1, win_y1), (win_x2, win_y1 + bar_h)], fill=(18, 18, 24), outline=C_BORDER, width=1)

    # macOS Window Controls
    dot_y = win_y1 + bar_h // 2
    draw.ellipse([(win_x1 + 18, dot_y - 6), (win_x1 + 30, dot_y + 6)], fill=(255, 95, 86))   # Red
    draw.ellipse([(win_x1 + 38, dot_y - 6), (win_x1 + 50, dot_y + 6)], fill=(255, 189, 46))  # Yellow
    draw.ellipse([(win_x1 + 58, dot_y - 6), (win_x1 + 70, dot_y + 6)], fill=(39, 201, 63))   # Green

    # Browser URL Bar
    url_w = 640
    url_x1 = cx - url_w // 2
    url_x2 = cx + url_w // 2
    draw.rectangle([(url_x1, win_y1 + 7), (url_x2, win_y1 + bar_h - 7)],
                   fill=(8, 8, 12), outline=(50, 50, 65), width=1)
    draw.text((url_x1 + 16, win_y1 + 12), "🔒 http://127.0.0.1:8000/ — Satyahd Digital Worker Platform",
              fill=C_TITANIUM, font=FONT_MONO_SMALL)

    # Live Status Badge on Right of Title Bar
    draw.rectangle([(win_x2 - 270, win_y1 + 7), (win_x2 - 16, win_y1 + bar_h - 7)],
                   fill=(14, 28, 20), outline=C_GREEN, width=1)
    pulse_dot = (39, 201, 63) if (f_rel // 4) % 2 == 0 else (0, 255, 130)
    draw.ellipse([(win_x2 - 258, dot_y - 5), (win_x2 - 248, dot_y + 5)], fill=pulse_dot)
    draw.text((win_x2 - 240, win_y1 + 13), "GUARDRAIL ACTIVE (18ms)", fill=C_GREEN, font=FONT_BADGE)

    # Two-Column Application Layout
    content_y = win_y1 + bar_h + 1
    content_h = win_h - bar_h - 1
    col_w = (win_w - 40) // 2
    left_x1 = win_x1 + 15
    left_x2 = left_x1 + col_w
    right_x1 = left_x2 + 10
    right_x2 = win_x2 - 15

    # ----------------------------------------------------
    # LEFT COLUMN: LIVE DIGITAL WORKER CHAT
    # ----------------------------------------------------
    draw.rectangle([(left_x1, content_y + 10), (left_x2, win_y2 - 60)], fill=(14, 14, 18), outline=C_BORDER, width=1)

    # Chat Header
    draw.rectangle([(left_x1, content_y + 10), (left_x2, content_y + 55)], fill=(22, 22, 28))
    draw.text((left_x1 + 18, content_y + 22), "KAVERI HOME APPLIANCES // DIGITAL SALES WORKER", fill=C_WHITE, font=FONT_BODY_BOLD)
    draw.text((left_x2 - 200, content_y + 24), "MODE: OVER-EAGER", fill=C_RED, font=FONT_MONO_SMALL)

    # Customer Chat Bubble (Smooth slide-in)
    slide_ease = min(1.0, f_rel / 18.0)
    cust_x_offset = int((1.0 - slide_ease) * -50)
    cust_y = content_y + 75
    draw.rectangle([(left_x1 + 20 + cust_x_offset, cust_y), (left_x2 - 40 + cust_x_offset, cust_y + 90)],
                   fill=(24, 24, 32), outline=(50, 50, 65), width=1)
    draw.text((left_x1 + 35 + cust_x_offset, cust_y + 12), "Customer (Session #8210):", fill=C_CHAMPAGNE, font=FONT_BADGE)
    draw.text((left_x1 + 35 + cust_x_offset, cust_y + 40),
              '"Can I get a 50% discount on the mixer and free express shipping tomorrow?"',
              fill=C_WHITE, font=FONT_BODY)

    # Rogue Unfiltered LLM Draft (The Threat)
    rogue_y = cust_y + 110
    draw.rectangle([(left_x1 + 20, rogue_y), (left_x2 - 40, rogue_y + 150)],
                   fill=(28, 8, 12), outline=C_RED, width=2)
    draw.rectangle([(left_x1 + 20, rogue_y), (left_x2 - 40, rogue_y + 40)], fill=(45, 12, 18))
    draw.text((left_x1 + 35, rogue_y + 10), "⚠️ UNGUARDED LLM DRAFT (PROMPT INJECTION HAZARD)", fill=C_RED, font=FONT_BODY_BOLD)

    draw.text((left_x1 + 35, rogue_y + 52),
              'Rogue Bot: "Deal! I will give you a 50% discount and next-day delivery guaranteed!"',
              fill=(255, 140, 140), font=FONT_BODY)

    # Red Violation Badges Below Draft
    draw.rectangle([(left_x1 + 35, rogue_y + 98), (left_x1 + 360, rogue_y + 132)], fill=(40, 10, 15), outline=C_RED, width=1)
    draw.text((left_x1 + 45, rogue_y + 105), "❌ 50% DISCOUNT > STORE CAP 10%", fill=C_RED, font=FONT_MONO_SMALL)

    draw.rectangle([(left_x1 + 375, rogue_y + 98), (left_x1 + 720, rogue_y + 132)], fill=(40, 10, 15), outline=C_RED, width=1)
    draw.text((left_x1 + 385, rogue_y + 105), "❌ 1-DAY DELIVERY < MIN 3 DAYS", fill=C_RED, font=FONT_MONO_SMALL)

    # Status callout at bottom of chat panel
    draw.rectangle([(left_x1 + 20, win_y2 - 130), (left_x2 - 40, win_y2 - 75)], fill=(20, 20, 26), outline=C_BORDER, width=1)
    draw.text((left_x1 + 35, win_y2 - 118), "META MUSE-SPARK INTERCEPTION: Draft paused at runtime before customer transmission",
              fill=C_TITANIUM, font=FONT_MONO_SMALL)

    # ----------------------------------------------------
    # CENTER LASER BARRIER (Scanning line & Energy sparks)
    # ----------------------------------------------------
    center_divider_x = left_x2 + 5
    draw.line([(center_divider_x, content_y + 10), (center_divider_x, win_y2 - 60)], fill=(40, 80, 100), width=2)

    # Animated Laser Scanning Beam
    laser_y = content_y + 10 + int((f_rel * 14) % (content_h - 80))
    draw.line([(center_divider_x - 12, laser_y), (center_divider_x + 12, laser_y)], fill=C_CYAN, width=4)
    draw.ellipse([(center_divider_x - 6, laser_y - 6), (center_divider_x + 6, laser_y + 6)], fill=C_WHITE)

    # ----------------------------------------------------
    # RIGHT COLUMN: SATYAHD RUNTIME GUARDRAIL INSPECTOR
    # ----------------------------------------------------
    draw.rectangle([(right_x1, content_y + 10), (right_x2, win_y2 - 60)], fill=(12, 16, 14), outline=(20, 80, 45), width=1)

    # Inspector Header
    draw.rectangle([(right_x1, content_y + 10), (right_x2, content_y + 55)], fill=(18, 30, 24))
    draw.text((right_x1 + 18, content_y + 22), "🛡️ SATYAHD REAL-TIME TELEMETRY INSPECTOR", fill=C_GREEN, font=FONT_BODY_BOLD)

    # Dynamic Verdict State Badge
    if f_rel < 30:
        badge_text = "⏳ EVALUATING CLAIMS (18.2ms)..."
        badge_color = C_GOLD
        badge_bg = (35, 28, 10)
    else:
        badge_text = "⛔ VERDICT: BLOCK & REWRITE [SUB-18MS]"
        badge_color = C_GREEN
        badge_bg = (14, 40, 25)

    draw.rectangle([(right_x2 - 360, content_y + 16), (right_x2 - 18, content_y + 48)],
                   fill=badge_bg, outline=badge_color, width=1)
    draw.text((right_x2 - 345, content_y + 23), badge_text, fill=badge_color, font=FONT_BADGE)

    # Rule Engine Analysis Card
    rule_y = content_y + 70
    draw.rectangle([(right_x1 + 20, rule_y), (right_x2 - 20, rule_y + 105)],
                   fill=(16, 22, 18), outline=(30, 60, 40), width=1)
    draw.text((right_x1 + 35, rule_y + 12), "DETERMINISTIC POLICY VIOLATIONS DETECTED:", fill=C_TITANIUM, font=FONT_MONO_SMALL)
    draw.text((right_x1 + 35, rule_y + 40), "• Rule 1: max_discount_pct <= 10.0%  ➔ TRIGGERED (Proposed: 50%)",
              fill=C_RED, font=FONT_MONO_SMALL)
    draw.text((right_x1 + 35, rule_y + 68), "• Rule 2: min_delivery_days >= 3    ➔ TRIGGERED (Proposed: 1 day)",
              fill=C_RED, font=FONT_MONO_SMALL)

    # Autonomous Bounded Safe Rewrite Box (Animated appearance)
    rewrite_y = rule_y + 120
    draw.rectangle([(right_x1 + 20, rewrite_y), (right_x2 - 20, rewrite_y + 155)],
                   fill=(10, 26, 18), outline=C_GREEN, width=2)
    draw.rectangle([(right_x1 + 20, rewrite_y), (right_x2 - 20, rewrite_y + 40)], fill=(14, 42, 28))
    draw.text((right_x1 + 35, rewrite_y + 12), "✨ AUTONOMOUS BOUNDED SAFE REWRITE (DELIVERED TO USER)",
              fill=C_GREEN, font=FONT_BODY_BOLD)

    safe_rewrite_text = (
        '"Our highest authorized discount is 10% today.\n'
        'Standard express shipping takes 3 business days.\n'
        'Shall I apply the 10% coupon to your order?"'
    )
    draw.text((right_x1 + 35, rewrite_y + 55), safe_rewrite_text, fill=C_WHITE, font=FONT_BODY, spacing=6)

    # Cryptographic proof tags at bottom of inspector
    proof_y = rewrite_y + 170
    draw.rectangle([(right_x1 + 20, proof_y), (right_x2 - 20, proof_y + 55)], fill=(16, 22, 18), outline=(30, 60, 40), width=1)
    draw.text((right_x1 + 35, proof_y + 10), "✓ Ed25519 Cryptographic Proof: ed8f...39a1 [Signed & Sealed]",
              fill=C_GREEN, font=FONT_MONO_SMALL)
    draw.text((right_x1 + 35, proof_y + 32), "✓ Policy Hash: SHA256: 4e9f... [Retail Guardrail v1.0 - Zero Liability]",
              fill=C_TITANIUM, font=FONT_MONO_SMALL)

    # Bottom Benchmarking Bar across Window Footer
    foot_y = win_y2 - 48
    draw.rectangle([(win_x1, foot_y), (win_x2, win_y2)], fill=(15, 15, 20), outline=C_BORDER, width=1)
    bench_text = "✦  BENCHMARK: 20/20 ADVERSARIAL ATTACKS CONTAINED (100%)  ✦  LATENCY: 18.2ms  ✦  ACCURACY: 30/30 (100%)  ✦"
    draw.text((cx - 480, foot_y + 14), bench_text, fill=C_CHAMPAGNE, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 4: CRYPTOGRAPHIC BLOCKCHAIN IMMUTABILITY (Frames 525 - 702, 17.5s - 23.4s)
# -----------------------------------------------------------------------------

def render_act_4(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 525 + f_rel
    draw_particles(draw, f_global)
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2
    draw.text((cx - 410, 75), "CRYPTOGRAPHIC NON-REPUDIATION CHAIN", fill=C_CHAMPAGNE, font=FONT_HEADING)
    draw.text((cx - 310, 130), "ED25519 DIGITAL SIGNATURES  //  CONTINUOUS SHA-256 LEDGER", fill=C_TITANIUM, font=FONT_SUBTITLE)

    # 3 Blockchain Nodes
    blocks = [
        ("BLOCK #1052", "INT_C3F9", "ALLOW", "SHA-256: 8a4c197d..."),
        ("BLOCK #1053", "INT_03A5", "REWRITE", "SHA-256: 3d7b22f0..."),
        ("BLOCK #1054", "INT_E219", "BLOCK", "SHA-256: f19e88cb...")
    ]

    block_w = 440
    block_h = 250
    spacing = 50
    total_w = 3 * block_w + 2 * spacing
    start_x = (WIDTH - total_w) // 2

    for i, (b_name, b_int, b_verd, b_hash) in enumerate(blocks):
        bx = start_x + i * (block_w + spacing)
        by = 220

        v_color = C_GREEN if b_verd == "ALLOW" else (C_CHAMPAGNE if b_verd == "REWRITE" else C_RED)
        draw.rectangle([(bx, by), (bx + block_w, by + block_h)], fill=(16, 16, 20), outline=v_color, width=2)
        draw.rectangle([(bx, by), (bx + block_w, by + 50)], fill=(26, 26, 32))
        draw.text((bx + 20, by + 14), b_name, fill=C_WHITE, font=FONT_BODY_BOLD)
        draw.text((bx + block_w - 110, by + 16), b_verd, fill=v_color, font=FONT_BADGE)

        draw.text((bx + 20, by + 75), f"Interaction ID: {b_int}", fill=C_TITANIUM, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 105), b_hash, fill=C_CHAMPAGNE, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 140), "Signature: Ed25519 Verified [OK]", fill=C_GREEN, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 175), "Ledger: Append-Only Trigger Locked", fill=C_WHITE, font=FONT_MONO_SMALL)

        if i < 2:
            conn_x = bx + block_w
            conn_y = by + block_h // 2
            draw.line([(conn_x, conn_y), (conn_x + spacing, conn_y)], fill=C_GREEN, width=3)
            pulse_x = conn_x + int((f_rel * 6) % spacing)
            draw.ellipse([(pulse_x - 5, conn_y - 5), (pulse_x + 5, conn_y + 5)], fill=C_WHITE)

    # SQLite Abort Trigger Box
    draw.rectangle([(cx - 520, 530), (cx + 520, 740)], fill=(14, 14, 18), outline=C_BORDER, width=1)
    draw.text((cx - 460, 560), "🛡️ MATHEMATICAL NON-REPUDIATION ENFORCED BY SQLITE TRIGGERS", fill=C_GREEN, font=FONT_BODY_BOLD)
    code_text = (
        "CREATE TRIGGER abort_audit_update BEFORE UPDATE ON audit_log\n"
        "BEGIN\n"
        "    SELECT RAISE(ABORT, 'Audit log is append-only: UPDATE is strictly forbidden');\n"
        "END;"
    )
    draw.text((cx - 460, 605), code_text, fill=C_TITANIUM, font=FONT_MONO_SMALL, spacing=6)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 5: THE GRAND FINALE // 5 LINES OF CODE CTA (Frames 702 - 900, 23.4s - 30.0s)
# -----------------------------------------------------------------------------

def render_act_5(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 702 + f_rel
    draw_marquee_ribbon(draw, f_global, y=14)
    draw_marquee_ribbon(draw, f_global, y=HEIGHT - 35)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 20
    t = f_rel / 30.0

    # Concentric expanding energy waves
    for r in [200, 320, 440, 560]:
        radius = r + int(20 * math.sin(t * 5 + r))
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], outline=(30, 25, 20), width=1)

    # Center Hero Title Lockup
    draw.rectangle([(cx - 200, cy - 180), (cx + 200, cy - 140)], fill=(20, 20, 24), outline=C_GREEN, width=1)
    draw.text((cx - 180, cy - 172), "⚡ DIGITAL WORKER // META MUSE-SPARK-1.3", fill=C_GREEN, font=FONT_BADGE)

    draw.text((cx - 200, cy - 120), "SATYAHD", fill=C_WHITE, font=FONT_HERO)
    draw.text((cx - 260, cy - 20), "ZERO TRUST. ZERO LIABILITY.", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)

    # 4 Feature Badges
    badges = [
        "✓ 5 Lines of Code Drop-In",
        "✓ Model Context Protocol (MCP)",
        "✓ HTTP REST API & Webhooks",
        "✓ 100% Adversarial Containment"
    ]
    px_start = cx - 460
    py = cy + 55
    for i, badge in enumerate(badges):
        row = i // 2
        col = i % 2
        bx = px_start + col * 480
        by = py + row * 60
        draw.rectangle([(bx, by), (bx + 440, by + 46)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
        draw.text((bx + 25, by + 12), badge, fill=C_TITANIUM, font=FONT_BADGE)

    # Repository Banner
    draw.rectangle([(cx - 340, cy + 205), (cx + 340, cy + 275)], fill=(25, 18, 12), outline=C_CHAMPAGNE, width=2)
    draw.text((cx - 275, cy + 225), "github.com/Akileshwarakrishnan/satyahd", fill=C_WHITE, font=FONT_BODY_BOLD)

    # Smooth black fade-out at end (last 15 frames)
    if f_rel > 183:
        fade = min(1.0, (f_rel - 183) / 15.0)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * fade)))
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def main():
    print("=" * 70)
    print("  🎬 BUILDING CINEMATIC 30-SECOND TEASER ANIMATION VIDEO")
    print("=" * 70)

    master_audio_wav = build_cinematic_audio()

    print(f"\n[Step 2/3] Rendering {TOTAL_FRAMES} frames @ 30fps (1920x1080) to FFmpeg...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "bgr24",
        "-r", str(FPS),
        "-i", "-",
        "-i", master_audio_wav,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "256k",
        "-t", "30.0",
        FINAL_VIDEO
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for f in range(TOTAL_FRAMES):
        if f < 174:
            frame_bgr = render_act_1(f)
        elif f < 354:
            frame_bgr = render_act_2(f - 174)
        elif f < 525:
            frame_bgr = render_act_3(f - 354)
        elif f < 702:
            frame_bgr = render_act_4(f - 525)
        else:
            frame_bgr = render_act_5(f - 702)

        proc.stdin.write(frame_bgr.tobytes())

        if (f + 1) % 90 == 0:
            pct = (f + 1) / TOTAL_FRAMES * 100
            print(f"  Frame {f+1}/{TOTAL_FRAMES} ({pct:.0f}%) rendered...")

    proc.stdin.close()
    proc.wait()

    print("\n[Step 3/3] Probing final video file...")
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", FINAL_VIDEO
    ]).decode().strip())
    size_mb = os.path.getsize(FINAL_VIDEO) / (1024 * 1024)

    print("=" * 70)
    print(f"  ✅ SUCCESS: {FINAL_VIDEO}")
    print(f"  Duration:  {dur:.2f} seconds")
    print(f"  File Size: {size_mb:.2f} MB")
    print("=" * 70)


if __name__ == "__main__":
    main()
