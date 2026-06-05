"""Actor logo from the OFFICIAL yt-dlp >_dlp mark (yt-dlp/.github/banner.svg).
Produces a faithful white-tile version and a dark-tile app-icon version."""

from PIL import Image, ImageDraw, ImageFont

SRC = "/tmp/ytdlp-trans.png"  # transparent high-res render of banner.svg
S = 512
SS = S * 4
OUT = "/Users/atrey/Desktop/code/yt-dlp-video-link-extractor/assets"
RED = (237, 28, 36)

# --- isolate the top >_dlp mark cluster (banner also has a tagline row) ---
src = Image.open(SRC).convert("RGBA")
W, H = src.size
alpha = src.split()[3].load()
rows = [any(alpha[x, y] > 25 for x in range(0, W, 4)) for y in range(H)]
clusters, start, gap = [], None, 0
for y in range(H + 1):
    on = y < H and rows[y]
    if on:
        start = y if start is None else start
        gap = 0
    elif start is not None:
        gap += 1
        if gap > int(H * 0.05):
            clusters.append((start, y - gap))
            start = None
my0, my1 = clusters[0]                       # top cluster = the >_dlp glyph
mark = src.crop((0, my0, W, my1 + 1))
mark = mark.crop(mark.split()[3].getbbox())  # tight to the glyph
mw, mh = mark.size


def font(size):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build(tile_rgb, name):
    img = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    mask = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SS - 1, SS - 1], radius=int(SS * 0.205), fill=255)
    img.paste(Image.new("RGBA", (SS, SS), tile_rgb + (255,)), (0, 0), mask)
    # big mark, centered both axes
    scale = min(SS * 0.86 / mw, SS * 0.66 / mh)
    nm = mark.resize((int(mw * scale), int(mh * scale)), Image.LANCZOS)
    img.alpha_composite(nm, ((SS - nm.width) // 2, (SS - nm.height) // 2))
    out = img.resize((S, S), Image.LANCZOS)
    out.save(f"{OUT}/{name}")
    return name


build((255, 255, 255), "logo_white.png")   # faithful, matches original bg
build((13, 17, 23), "logo_dark.png")        # dark app-icon, mark pops
print("wrote logo_white.png + logo_dark.png (512x512) from official yt-dlp mark")
