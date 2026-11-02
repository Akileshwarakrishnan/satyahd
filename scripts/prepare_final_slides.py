"""
Standardizes all 7 slides from user uploads into crisp 1920x1080 images:
- Correct sequence: 1 (Cover), 2 (Air Canada), 3 (Architecture), 4 (Red-Team), 5 (Audit), 6 (Benchmarks), 7 (Integration)
- Restores Slide 3 (removing snipping tool banner)
- Renders high-res Slide 7 matching exact styling
"""

import os
from PIL import Image, ImageDraw, ImageFont

USER_UPLOAD_DIR = r"C:\Users\Akileshwarakrishnan\.gemini\antigravity\brain\56b0c021-dad4-44f5-9adf-ac8e5b2c115f\.user_uploaded"
OUT_DIR = "reports/video_assets"
os.makedirs(OUT_DIR, exist_ok=True)

TARGET_W, TARGET_H = 1920, 1080

FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
FONT_R = "C:/Windows/Fonts/segoeui.ttf"
FONT_CODE = "C:/Windows/Fonts/consola.ttf"

BG_COLOR = (234, 237, 242)     # #EAEDF2
TEXT_NAVY = (22, 28, 38)       # #161C26
TEXT_ORANGE = (217, 91, 48)    # #D95B30
TEXT_MUTED = (90, 102, 121)    # #5A6679
CARD_FILL = (214, 221, 232)    # #D6DDE8
CARD_ORANGE = (250, 140, 94)   # #FA8C5E

def standardize_image(im_path, target_w=1920, target_h=1080):
    im = Image.open(im_path).convert("RGB")
    # Resize keeping aspect ratio, centered on matching background
    w, h = im.size
    aspect = w / h
    target_aspect = target_w / target_h
    
    if abs(aspect - target_aspect) < 0.05:
        return im.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    # Otherwise fit inside
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Pick corner pixel color as canvas background
    corner_col = im.getpixel((5, 5))
    canvas = Image.new("RGB", (target_w, target_h), corner_col)
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas

def make_clean_slide3():
    # Build a pristine high-res Slide 3
    im = Image.new("RGB", (TARGET_W, TARGET_H), BG_COLOR)
    draw = ImageDraw.Draw(im)
    
    f_tag = ImageFont.truetype(FONT_B, 24)
    f_title = ImageFont.truetype(FONT_B, 52)
    f_sub = ImageFont.truetype(FONT_R, 28)
    f_card_title = ImageFont.truetype(FONT_B, 34)
    f_card_body = ImageFont.truetype(FONT_R, 24)
    
    # Tag
    draw.text((100, 100), "SYSTEM ARCHITECTURE", fill=TEXT_ORANGE, font=f_tag)
    # Title
    draw.text((100, 145), "Satyahd: An External Gate Checks Every Agent Action", fill=TEXT_NAVY, font=f_title)
    # Subtitle
    draw.text((100, 225), "Middleware between the agent and the customer, with 48.2ms overhead.", fill=TEXT_MUTED, font=f_sub)
    
    cards = [
        # (x, y, w, h, title, body)
        (100, 310, 820, 290, "Stage 1: Intercept", "Catches outbound text and tool calls before they leave the model."),
        (980, 310, 840, 290, "Stage 2: Extract Promises", "Meta muse-spark-1.3 pulls out claims, refunds, discounts, and SLAs."),
        (100, 640, 820, 290, "Stage 3: Verify Policy", "Pure Python rules check each promise. Zero hallucination risk."),
        (980, 640, 840, 290, "Stage 4: Decide and Seal", "Emits ALLOW, REWRITE, or HARD BLOCK. Signed with Ed25519.")
    ]
    
    for cx, cy, cw, ch, ctitle, cbody in cards:
        draw.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=16, fill=CARD_FILL)
        draw.text((cx + 40, cy + 45), ctitle, fill=TEXT_NAVY, font=f_card_title)
        # wrap body
        draw.text((cx + 40, cy + 120), cbody, fill=TEXT_MUTED, font=f_card_body)
        
    return im

def make_clean_slide7():
    # Build a pristine high-res Slide 7
    im = Image.new("RGB", (TARGET_W, TARGET_H), BG_COLOR)
    draw = ImageDraw.Draw(im)
    
    f_tag = ImageFont.truetype(FONT_B, 24)
    f_title = ImageFont.truetype(FONT_B, 52)
    f_sub = ImageFont.truetype(FONT_R, 28)
    f_card_title = ImageFont.truetype(FONT_B, 34)
    f_body = ImageFont.truetype(FONT_R, 24)
    f_code = ImageFont.truetype(FONT_CODE if os.path.exists(FONT_CODE) else FONT_R, 23)
    f_quote = ImageFont.truetype(FONT_B, 26)
    
    # Tag
    draw.text((100, 90), "DEVELOPER EXPERIENCE & DEPLOYMENT", fill=TEXT_ORANGE, font=f_tag)
    # Title
    draw.text((100, 135), "Universal Integration: 3 Lines of Code to Total Protection", fill=TEXT_NAVY, font=f_title)
    # Subtitle
    draw.text((100, 215), "Drop-in middleware for any LLM framework or cloud stack.", fill=TEXT_MUTED, font=f_sub)
    
    # Left Box: Integration
    draw.rounded_rectangle((100, 300, 920, 780), radius=16, fill=CARD_FILL)
    draw.text((140, 340), "Integration", fill=TEXT_NAVY, font=f_card_title)
    code_text = (
        "from satyahd import SatyahdCallbackHandler\n\n"
        "# Attach to any LangChain / LlamaIndex agent\n"
        "agent = create_agent(\n"
        "    llm=meta_llama3_model,\n"
        "    callbacks=[SatyahdCallbackHandler(\n"
        "        policy='airline.json'\n"
        "    )]\n"
        ")\n\n"
        "# Or query universal REST API:\n"
        "POST /v1/verify  {\"draft\": \"...\", \"mode\": \"rewrite\"}\n"
        "POST /v1/verify/action  {\"tool\": \"issue_refund\"}"
    )
    draw.text((140, 410), code_text, fill=TEXT_NAVY, font=f_code)
    
    # Right Box: The Ask & Production Rollout
    draw.rounded_rectangle((980, 300, 1820, 780), radius=16, fill=CARD_FILL)
    draw.text((1020, 340), "The Ask & Production Rollout", fill=TEXT_NAVY, font=f_card_title)
    
    draw.text((1020, 410), "Pilot Satyahd in production for an enterprise agent workflow:", fill=TEXT_NAVY, font=f_body)
    
    bullets = [
        "• 3-line drop-in for fast containerized or cloud testing",
        "• Lightweight Docker footprint (< 150MB) for Kubernetes sidecars",
        "• Zero-friction on-premise, air-gapped deployment if needed",
        "• Verifiably 100% policy-contained from day one",
        "• JSON rule packs empower legal teams without retraining models"
    ]
    by = 470
    for b in bullets:
        draw.text((1020, by), b, fill=TEXT_MUTED, font=f_body)
        by += 50
        
    # Bottom Quote
    draw.text((100, 830), "“The indispensable safety harness before autonomous AI meets the real world.”", fill=TEXT_ORANGE, font=f_quote)
    return im

def main():
    uploads = {
        1: os.path.join(USER_UPLOAD_DIR, "media_1793556533646_b508c7f0.png"), # Cover
        2: os.path.join(USER_UPLOAD_DIR, "media_1793556587632_039a6886.png"), # Air Canada
        3: os.path.join(USER_UPLOAD_DIR, "media_1793556592934_4afb8b53.png"), # Arch
        4: os.path.join(USER_UPLOAD_DIR, "media_1793556602287_e1f96393.png"), # Red-team
        5: os.path.join(USER_UPLOAD_DIR, "media_1793556763314_5f1e35c1.png"), # Audit (Upload 6)
        6: os.path.join(USER_UPLOAD_DIR, "media_1793556608593_971c43e5.png"), # Bench (Upload 5)
        7: os.path.join(USER_UPLOAD_DIR, "media_1793556766047_1a1dc887.jpg"), # Integration (Upload 7)
    }
    
    print("Standardizing all 7 slides...")
    # Slide 1
    im1 = standardize_image(uploads[1])
    im1.save(os.path.join(OUT_DIR, "slide_01.png"))
    print("Saved slide_01.png")
    
    # Slide 2
    im2 = standardize_image(uploads[2])
    im2.save(os.path.join(OUT_DIR, "slide_02.png"))
    print("Saved slide_02.png")
    
    # Slide 3 (clean version)
    im3 = make_clean_slide3()
    im3.save(os.path.join(OUT_DIR, "slide_03.png"))
    print("Saved slide_03.png (clean without snipping tool)")
    
    # Slide 4
    im4 = standardize_image(uploads[4])
    im4.save(os.path.join(OUT_DIR, "slide_04.png"))
    print("Saved slide_04.png")
    
    # Slide 5 (Audit trail)
    im5 = standardize_image(uploads[5])
    im5.save(os.path.join(OUT_DIR, "slide_05.png"))
    print("Saved slide_05.png")
    
    # Slide 6 (Benchmarks)
    im6 = standardize_image(uploads[6])
    im6.save(os.path.join(OUT_DIR, "slide_06.png"))
    print("Saved slide_06.png")
    
    # Slide 7 (clean high-res)
    im7 = make_clean_slide7()
    im7.save(os.path.join(OUT_DIR, "slide_07.png"))
    print("Saved slide_07.png (clean high-res)")
    
    print("All 7 slides prepared successfully!")

if __name__ == "__main__":
    main()
