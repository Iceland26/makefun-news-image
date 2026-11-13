#!/usr/bin/env python3
"""news-image-01: a world-news front page rendered procedurally (stdlib only).
A clean newspaper front page: masthead, a stylised globe, a red 'BREAKING'
banner, and columns of headline 'text' (light grey bars of varying width).
Deterministic; writes entry.png to $MAKEFUN_OUTPUT_DIR.
"""
import os, zlib, struct, math

W = H = 640


def clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def smooth(lo, hi, x):
    t = (x - lo) / (hi - lo)
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def sd_circle(px, py, cx, cy, r):
    return math.hypot(px - cx, py - cy) - r


def sd_rrect(px, py, cx, cy, hw, hh, rr):
    qx = abs(px - cx) - hw + rr
    qy = abs(py - cy) - hh + rr
    ax = max(qx, 0.0)
    ay = max(qy, 0.0)
    return math.hypot(ax, ay) + min(max(qx, qy), 0.0) - rr


PAPER = (0.96, 0.95, 0.91)
EDGE = (0.85, 0.82, 0.76)
INK = (0.13, 0.14, 0.16)
GRAY = (0.50, 0.50, 0.53)
RED = (0.78, 0.10, 0.12)
BLUE = (0.16, 0.35, 0.65)
GREEN = (0.20, 0.50, 0.28)


def seg_dist(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    L2 = abx * abx + aby * aby
    t = ((px - ax) * abx + (py - ay) * aby) / L2 if L2 > 0 else 0.0
    t = clamp01(t)
    return math.hypot(px - (ax + abx * t), py - (ay + aby * t))


def render():
    rows = []
    rng = lambda n: (n * 2654435761 % 4294967296) / 4294967296
    for y in range(H):
        py = y + 0.5
        row = bytearray()
        for x in range(W):
            px = x + 0.5
            # paper with subtle vignette
            col = PAPER
            dcen = math.hypot(px - W / 2, py - H / 2)
            col = mix(col, EDGE, smooth(220.0, 460.0, dcen))

            # masthead bar (top dark strip)
            if 40 < py < 96 and 60 < px < 580:
                col = mix(col, INK, 0.92)
            # masthead "title" (big light band)
            if 54 < py < 84 and 90 < px < 560:
                col = mix(col, (0.93, 0.90, 0.82), 0.9)

            # red BREAKING banner
            dbr = sd_rrect(px, py, 340, 136, 150, 22, 4)
            if dbr < 0:
                col = mix(col, RED, smooth(0.0, -3.0, dbr))
            if dbr < 0 and sd_rrect(px, py, 340, 130, 150, 14, 3) < 0:
                col = mix(col, (0.93, 0.88, 0.85), 0.85)

            # globe (blue circle + green continents + white graticule)
            dg = sd_circle(px, py, 170, 260, 66)
            if dg < 0:
                col = mix(col, BLUE, smooth(0.0, -4.0, dg))
                # graticule: latitude arcs
                for glat in (-30, -12, 6, 24):
                    gy = 260 + glat
                    ry = 66 * math.cos(glat / 66.0 * 1.2)
                    darc = abs(sd_circle(px, py, 170, gy, ry)) if False else \
                        seg_dist(px, py, 170 - ry - 5, gy, 170 + ry + 5, gy)
                    if dg < 0 and darc < 2.2:
                        col = mix(col, (0.85, 0.90, 0.97), 0.5)
                # vertical meridian
                if dg < 0 and abs(px - 170) < 2.2:
                    col = mix(col, (0.85, 0.90, 0.97), 0.5)
                # continents (blobs)
                for cx_, cy_, r_ in ((148, 240, 20), (170, 276, 24), (196, 250, 16), (150, 278, 12)):
                    dcc = sd_circle(px, py, cx_, cy_, r_)
                    if dcc < 0:
                        col = mix(col, GREEN, smooth(0.0, -4.0, dcc))

            # headline text bars (columns under the banner)
            def textbar(cx_, cy_, hw_, hh_):
                d = sd_rrect(px, py, cx_, cy_, hw_, hh_, 2)
                return d

            bars = []
            for col_x, base_y in ((90, 190), (230, 190), (370, 190), (510, 190)):
                for k in range(5):
                    wdt = 50 + 44 * rng(col_x * 7 + k * 3 + 1)
                    bars.append((col_x, base_y + k * 26, wdt, 7))
            for bx, by, bw, bh in bars:
                d = textbar(bx, by, bw, bh)
                if d < 0:
                    col = mix(col, GRAY, smooth(bh, bh - 2.0, d) * 0.8 if d > -bh else 1.0)

            # horizontal rules between columns
            for ry in (176, 300, 340, 380, 420, 460, 500, 540):
                if abs(py - ry) < 2.5 and 70 < px < 570:
                    col = mix(col, INK, 0.55)

            row += bytes((int(clamp01(col[0]) * 255 + 0.5),
                          int(clamp01(col[1]) * 255 + 0.5),
                          int(clamp01(col[2]) * 255 + 0.5)))
        rows.append(bytes(row))
    return rows


def chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))


def write_png(path, rows):
    raw = b''.join(b'\x00' + r for r in rows)
    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
           + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)


def main():
    outdir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(outdir, exist_ok=True)
    write_png(os.path.join(outdir, 'entry.png'), render())


if __name__ == '__main__':
    main()
