"""
Generates the circular presenter headshot bubble for the demo video.
"""

import os
from PIL import Image, ImageDraw

def create_presenter_bubble():
    img_path = "reports/video_assets/presenter.jpg"
    out_path = "reports/video_assets/presenter_bubble.png"
    
    if not os.path.exists(img_path):
        print(f"{img_path} not found")
        return
        
    im = Image.open(img_path).convert("RGBA")
    size = (240, 240)
    im = im.resize(size, Image.Resampling.LANCZOS)
    
    # Create circular mask
    mask = Image.new("L", size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, size[0], size[1]), fill=255)
    
    # Apply circular mask
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    output.paste(im, (0, 0), mask=mask)
    
    # Add border ring (Cyan / Orange)
    draw_out = ImageDraw.Draw(output)
    draw_out.ellipse((2, 2, size[0] - 3, size[1] - 3), outline=(56, 189, 248, 255), width=6)
    
    output.save(out_path)
    print(f"Created presenter bubble: {out_path}")

if __name__ == "__main__":
    create_presenter_bubble()
