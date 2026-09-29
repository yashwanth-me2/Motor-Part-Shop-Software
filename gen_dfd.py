# Draws the two Data Flow Diagrams as plain SVG (DeMarco-Yourdon notation):
#   rectangle = external entity, circle = process, open box = data store, arrow = data flow
import math

FONT = 'font-family="Arial, Helvetica, sans-serif"'


def svg_start(w, h, title):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>',
        f'<rect width="{w}" height="{h}" fill="#fff"/>',
        '<defs><marker id="a" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
        f'<text x="{w/2}" y="30" text-anchor="middle" font-size="20" font-weight="bold" fill="#222">{title}</text>',
    ]


def entity(x, y, w, h, name):
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#e8f1fb" stroke="#2b5c8a" stroke-width="2"/>',
            f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" font-size="16" font-weight="bold">{name}</text>']


def process(cx, cy, r, num, lines):
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff4e0" stroke="#a0661a" stroke-width="2"/>',
           f'<text x="{cx}" y="{cy-r/2+6}" text-anchor="middle" font-size="14" font-weight="bold">{num}</text>',
           f'<line x1="{cx-r*0.8}" y1="{cy-r/2+14}" x2="{cx+r*0.8}" y2="{cy-r/2+14}" stroke="#a0661a"/>']
    y0 = cy + 4 - (len(lines) - 1) * 8 + 8
    for i, t in enumerate(lines):
        out.append(f'<text x="{cx}" y="{y0+i*17}" text-anchor="middle" font-size="14">{t}</text>')
    return out


def store(x, y, w, h, sid, name):
    # open-ended box: top line, bottom line, left end + id cell
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#eef7ee" stroke="none"/>',
            f'<path d="M{x+w},{y} L{x},{y} L{x},{y+h} L{x+w},{y+h}" fill="none" stroke="#3c7a3c" stroke-width="2"/>',
            f'<line x1="{x+40}" y1="{y}" x2="{x+40}" y2="{y+h}" stroke="#3c7a3c" stroke-width="2"/>',
            f'<text x="{x+20}" y="{y+h/2+5}" text-anchor="middle" font-size="14" font-weight="bold">{sid}</text>',
            f'<text x="{x+40+(w-40)/2}" y="{y+h/2+5}" text-anchor="middle" font-size="15">{name}</text>']


def label(x, y, text):
    lines = text.split('|')
    wmax = max(len(t) for t in lines) * 7 + 10
    h = 17 * len(lines) + 4
    out = [f'<rect x="{x-wmax/2}" y="{y-h/2}" width="{wmax}" height="{h}" fill="#fff" opacity="0.92"/>']
    for i, t in enumerate(lines):
        out.append(f'<text x="{x}" y="{y-h/2+15+i*17}" text-anchor="middle" font-size="13" fill="#333">{t}</text>')
    return out


def flow(points, text=None, at=0.5, dx=0, dy=0):
    pts = " ".join(f"{x},{y}" for x, y in points)
    out = [f'<polyline points="{pts}" fill="none" stroke="#333" stroke-width="1.6" marker-end="url(#a)"/>']
    if text:
        (x1, y1), (x2, y2) = points[0], points[1]
        if len(points) > 2:  # put label on the longest segment
            segs = list(zip(points, points[1:]))
            (x1, y1), (x2, y2) = max(segs, key=lambda s: math.dist(*s))
        out += label(x1 + (x2 - x1) * at + dx, y1 + (y2 - y1) * at + dy, text)
    return out


def save(name, parts):
    with open(name, "w") as f:
        f.write("\n".join(parts + ["</svg>"]))


# ---------------- Level 0 (context diagram) ----------------
s = svg_start(1000, 360, "DFD Level 0 (Context Diagram) – MPSS")
s += flow([(190, 180), (430, 180)], "vendor details, part details,|sale details, restock quantity", dy=-32)
s += flow([(430, 215), (190, 215)], "order list, daily revenue,|monthly sales graph", dy=32)
s += flow([(570, 200), (800, 200)], "printed order list|(part no., amount, address)", dy=-30)
s += entity(40, 165, 150, 70, "Shop Owner")
s += process(500, 200, 75, "0", ["Motor Part Shop", "Software (MPSS)"])
s += entity(800, 165, 150, 70, "Vendor")
save("dfd0.svg", s)

# ---------------- Level 1 ----------------
s = svg_start(1200, 770, "DFD Level 1 – MPSS")
s.append('<g transform="translate(0,22)">')
# order list goes back to the owner along the top
s += flow([(1060, 272), (1060, 38), (105, 38), (105, 355)], "order list (part no., amount, vendor address)", at=0.25)
# owner <-> processes
s += flow([(180, 365), (394, 128)], "vendor / part details,|restock qty", at=0.45, dx=-20)
s += flow([(180, 378), (393, 282)], "part no., quantity", at=0.55, dy=-6)
s += flow([(393, 497), (180, 398)], "daily revenue", at=0.45, dy=6)
s += flow([(396, 632), (180, 410)], "monthly sales|graph", at=0.45, dx=-10, dy=10)
# P1 -> stores
s += flow([(507, 98), (700, 90)], "vendor record", dy=-14)
s += flow([(500, 140), (700, 258)], "part record,|new stock", at=0.55, dx=-10)
# P2 <-> D2, P2 -> D3
s += flow([(700, 263), (508, 258)], "price, stock", dy=-14)
s += flow([(508, 284), (700, 282)], "reduced stock", dy=14)
s += flow([(488, 312), (700, 548)], "sale record", at=0.5, dx=34)
# D3 -> P4, P5
s += flow([(700, 564), (506, 512)], "sales of the day", at=0.5, dy=-12)
s += flow([(700, 578), (502, 636)], "sales of the month", at=0.5, dy=14)
# stores -> P3
s += flow([(880, 100), (1022, 287)], "vendor|address", at=0.45, dx=-10)
s += flow([(880, 275), (1003, 318)], "stock", dy=-12)
s += flow([(880, 560), (1024, 375)], "last 28 days|of sales", at=0.5, dx=-8)
# P3 -> vendor
s += flow([(1060, 388), (1060, 560)], "printed order list", dx=0)

s += entity(30, 355, 150, 60, "Shop Owner")
s += entity(990, 560, 140, 60, "Vendor")
s += process(450, 110, 58, "1.0", ["Manage Vendors,", "Parts &amp; Stock"])
s += process(450, 270, 58, "2.0", ["Record Sale"])
s += process(450, 505, 58, "4.0", ["Daily Revenue"])
s += process(450, 650, 58, "5.0", ["Monthly Graph"])
s += process(1060, 330, 58, "3.0", ["Generate", "Order List"])
s += store(700, 68, 180, 44, "D1", "Vendors")
s += store(700, 248, 180, 44, "D2", "Parts")
s += store(700, 540, 180, 44, "D3", "Sales")
s.append("</g>")
save("dfd1.svg", s)
