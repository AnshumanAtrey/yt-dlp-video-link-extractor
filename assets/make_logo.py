"""Generate the actor logo: a play button (video) + a chain link (the extracted
link) on a dark rounded tile. 512x512 PNG, Apify store spec."""

from PIL import Image, ImageDraw, ImageFont

S = 512
SS = S * 4  # supersample, downscale at the end for crisp edges


def lerp(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


img = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))

# --- dark gradient rounded-square tile ---
top, bot = (30, 41, 61), (12, 16, 22)  # #1e293d -> #0c1016
grad = Image.new("RGB", (1, SS))
for y in range(SS):
    grad.putpixel((0, y), lerp(top, bot, y / SS))
grad = grad.resize((SS, SS))
mask = Image.new("L", (SS, SS), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SS - 1, SS - 1], radius=int(SS * 0.205), fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
d.rounded_rectangle([SS * 0.028, SS * 0.028, SS * 0.972, SS * 0.972],
                    radius=int(SS * 0.17), outline=(255, 255, 255, 30), width=int(SS * 0.005))

# --- play triangle (yt-dlp red), cleanly rounded corners via curve-joined stroke ---
red = (255, 78, 78)
cx, cy = SS * 0.40, SS * 0.435
w, h = SS * 0.155, SS * 0.19
pts = [(cx - w, cy - h), (cx + w * 1.35, cy), (cx - w, cy + h)]
d.polygon(pts, fill=red)
d.line(pts + [pts[0]], fill=red, width=int(SS * 0.045), joint="curve")  # rounds the corners

# --- chain link (cyan): two overlapping capsules in a centered canvas, then 45 deg ---
cyan = (45, 222, 196)
LK = int(SS * 0.42)
lc = Image.new("RGBA", (LK, LK), (0, 0, 0, 0))
lcd = ImageDraw.Draw(lc)
lw = int(LK * 0.12)
cw, ch = LK * 0.46, LK * 0.27
cyc = LK * 0.5
for ax in (LK * 0.31, LK * 0.59):  # two capsules overlapping in the middle = a link
    lcd.rounded_rectangle([ax - cw / 2, cyc - ch / 2, ax + cw / 2, cyc + ch / 2],
                          radius=ch / 2, outline=cyan, width=lw)
lc = lc.rotate(45, resample=Image.BICUBIC, expand=False)
img.alpha_composite(lc, (int(SS * 0.49), int(SS * 0.255)))

# --- wordmark ---
def load_font(size):
    for p in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


d = ImageDraw.Draw(img)
font = load_font(int(SS * 0.082))
text = "yt-dlp"
tb = d.textbbox((0, 0), text, font=font)
d.text(((SS - (tb[2] - tb[0])) / 2 - tb[0], SS * 0.775 - tb[1]), text, font=font, fill=(226, 232, 240))

out = img.resize((S, S), Image.LANCZOS)
out.save("/Users/atrey/Desktop/code/yt-dlp-video-link-extractor/assets/logo.png")
flat = Image.new("RGB", (S, S), (12, 16, 22))
flat.paste(out, (0, 0), out)
flat.save("/Users/atrey/Desktop/code/yt-dlp-video-link-extractor/assets/logo_flat.png")
print("wrote assets/logo.png + logo_flat.png (512x512)")
