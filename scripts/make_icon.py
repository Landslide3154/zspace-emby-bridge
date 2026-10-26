"""生成应用图标：满幅超椭圆底板 + 白色剪影 + 剪影投影（本机 app-icon 规范）。

用法：
  python scripts/make_icon.py            # 生成各尺寸 + 对比图
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
PLATE = (61, 90, 254)        # #3D5AFE
SHADOW = (10, 16, 48)
OUT = Path("app/assets")
PREVIEW = Path("docs/icon")


def superellipse_points(size: int, radius: float, n: float, steps: int = 720) -> list[tuple[float, float]]:
    cx = cy = size / 2
    r = radius
    pts = []
    for i in range(steps):
        theta = 2 * math.pi * i / steps
        c, s = math.cos(theta), math.sin(theta)
        x = cx + r * math.copysign(abs(c) ** (2 / n), c)
        y = cy + r * math.copysign(abs(s) ** (2 / n), s)
        pts.append((x, y))
    return pts


def plate_mask(size: int, ss: int = 4) -> Image.Image:
    big = size * ss
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon(superellipse_points(big, 0.35 * big, 4), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def glyph_mask(size: int, variant: str = "bridge", ss: int = 4) -> Image.Image:
    """白色剪影：占可见区 0.72 左右。"""
    big = size * ss
    layer = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(layer)
    u = big / 1024  # 设计网格单位

    if variant == "bridge":
        # 拱桥：半圆拱 + 两条桥墩，拱下留一枚播放三角
        deck_y = 470 * u
        span = 440 * u
        left, right = 512 * u - span / 2, 512 * u + span / 2
        thick = 96 * u
        draw.arc([left, deck_y - span / 2 + 60 * u, right, deck_y + span / 2 + 60 * u],
                 start=180, end=360, fill=255, width=int(thick))
        # 桥墩
        draw.rounded_rectangle([left, deck_y - 20 * u, left + thick, deck_y + 260 * u], radius=thick / 2, fill=255)
        draw.rounded_rectangle([right - thick, deck_y - 20 * u, right, deck_y + 260 * u], radius=thick / 2, fill=255)
        # 播放三角（拱洞中间）
        tri_h = 250 * u
        tri_w = 220 * u
        cx, cy = 512 * u, deck_y + 150 * u
        draw.polygon(
            [(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)],
            fill=255,
        )
    elif variant == "ring":
        r = 300 * u
        thick = int(70 * u)
        draw.arc([512 * u - r, 512 * u - r, 512 * u + r, 512 * u + r], start=40, end=320, fill=255, width=thick)
        draw.arc([512 * u - r, 512 * u - r, 512 * u + r, 512 * u + r], start=220, end=500, fill=255, width=thick)
        tri_h, tri_w = 260 * u, 230 * u
        cx, cy = 540 * u, 512 * u
        draw.polygon([(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)], fill=255)
    elif variant == "deck":
        tri_h, tri_w = 340 * u, 300 * u
        cx, cy = 500 * u, 470 * u
        draw.polygon([(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)], fill=255)
        draw.rounded_rectangle([250 * u, 700 * u, 774 * u, 790 * u], radius=45 * u, fill=255)
    elif variant == "openring":
        # 底部开口的圆环（桥拱）+ 播放三角
        r = 330 * u
        thick = int(86 * u)
        box = [512 * u - r, 512 * u - r, 512 * u + r, 512 * u + r]
        draw.arc(box, start=118, end=422, fill=255, width=thick)
        tri_h, tri_w = 250 * u, 225 * u
        cx, cy = 545 * u, 500 * u
        draw.polygon(
            [(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)],
            fill=255,
        )
    elif variant == "split":
        # 播放三角被一道竖向接缝分成两块：左边略下沉，象征「桥接」
        tri_h, tri_w = 360 * u, 330 * u
        cx, cy = 512 * u, 512 * u
        draw.polygon(
            [(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)],
            fill=255,
        )
        # 把接缝右侧整体上移一点，形成错位的两块
        right = layer.crop((int(cx + 20 * u), 0, big, big))
        layer.paste(Image.new("L", right.size, 0), (int(cx + 20 * u), 0))
        layer.paste(right, (int(cx + 20 * u), int(-26 * u)))
        draw.line([(cx + 20 * u, 0), (cx - 70 * u, big)], fill=0, width=int(30 * u))
    else:  # arcdeck：播放三角 + 一道桥拱
        tri_h, tri_w = 330 * u, 290 * u
        cx, cy = 500 * u, 430 * u
        draw.polygon([(cx - tri_w / 2, cy - tri_h / 2), (cx - tri_w / 2, cy + tri_h / 2), (cx + tri_w / 2, cy)], fill=255)
        thick = 84 * u
        draw.arc([242 * u, 560 * u, 782 * u, 1000 * u], start=200, end=340, fill=255, width=int(thick))

    return layer.resize((size, size), Image.LANCZOS)


def compose(size: int, variant: str = "bridge", plate_color: tuple[int, int, int] = PLATE) -> Image.Image:
    ss = 4
    plate = plate_mask(size, ss)
    glyph = glyph_mask(size, variant, ss)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base = Image.new("RGBA", (size, size), plate_color + (255,))
    canvas.paste(base, (0, 0), plate)

    # 剪影投影：偏移 (0.006,0.024)×剪影边长，模糊 0.055×边长，alpha 0.50
    edge = size * 0.72
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow.paste(SHADOW + (128,), (0, 0), glyph)
    shadow = shadow.filter(ImageFilter.GaussianBlur(edge * 0.055))
    canvas.alpha_composite(shadow, (int(edge * 0.006), int(edge * 0.024)))

    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    canvas.paste(white, (0, 0), glyph)
    return canvas


def sheet(variants: tuple[str, ...] = ("bridge", "ring", "deck")) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    sizes = (256, 96, 64, 48)
    pad = 24
    cell_w = 256 + pad * 2
    width = cell_w * len(variants)
    height = sum(s + pad for s in sizes) + pad
    canvas = Image.new("RGBA", (width, height), (245, 246, 248, 255))
    for col, variant in enumerate(variants):
        y = pad // 2
        for size in sizes:
            icon = compose(size, variant)
            canvas.alpha_composite(icon, (col * cell_w + pad, y))
            y += size + pad
    canvas.save(PREVIEW / "preview.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 64, 128, 192, 256, 512, 1024):
        compose(size, "openring").save(OUT / f"icon-{size}.png")
    compose(256, "openring").save(OUT / "icon.png")
    sheet(("openring", "ring", "bridge"))
    print("生成完成：", OUT, PREVIEW / "preview.png")


if __name__ == "__main__":
    main()
