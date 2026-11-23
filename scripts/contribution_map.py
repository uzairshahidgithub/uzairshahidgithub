#!/usr/bin/env python3
"""
Linked contribution map: a spider-web style, transparent-background SVG.

  * center            : your avatar
  * rounded squares   : organizations you contribute to (logo + name + count)
  * circles           : other people whose projects you contribute to
  * wires             : curved, with a slow low-intensity neon spark

Standard library only. The SVG is self-contained: avatars and the Poppins font
are embedded as base64, because GitHub does not load external resources inside
an SVG shown in a README.

Usage:
  GITHUB_TOKEN=... python contribution_map.py --user uzairshahidgithub
  python contribution_map.py --demo            # offline preview with fake data
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"
UA = "contribution-map/2.0"
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILES = {400: "poppins-latin-400-normal.woff2",
              500: "poppins-latin-500-normal.woff2",
              600: "poppins-latin-600-normal.woff2"}

NEON = "#00ff9c"
PLATE = "#0e1014"      # dim black
BORDER = "#3b4048"     # grey border
BORDER_HI = "#59616c"


# --------------------------------------------------------------------------- #
# GitHub data
# --------------------------------------------------------------------------- #
def gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def _sel():
    return (
        "repository{ owner{ __typename login avatarUrl(size:120) "
        "... on Organization{ name } ... on User{ name } } } contributions{ totalCount }"
    )


def collect(login, token):
    """Return (my_avatar_url, {owner_login: {name, avatar_url, count, kind}})."""
    me = gql(
        "query($l:String!){ user(login:$l){ createdAt avatarUrl(size:200) } }",
        {"l": login}, token,
    )["user"]
    start = dt.datetime.fromisoformat(me["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)

    query = f"""
    query($login:String!,$from:DateTime!,$to:DateTime!){{
      user(login:$login){{
        contributionsCollection(from:$from,to:$to){{
          commitContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          pullRequestContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          issueContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          pullRequestReviewContributionsByRepository(maxRepositories:100){{ {_sel()} }}
        }}
      }}
    }}"""

    owners = {}
    cursor = start
    while cursor < now:
        end = min(cursor + dt.timedelta(days=365), now)
        coll = gql(
            query,
            {"login": login, "from": cursor.isoformat(), "to": end.isoformat()},
            token,
        )["user"]["contributionsCollection"]
        for bucket in coll.values():
            for item in bucket:
                owner = item["repository"]["owner"]
                key = owner["login"]
                if key.lower() == login.lower():
                    continue  # your own repositories are not part of the map
                entry = owners.setdefault(key, {
                    "name": owner.get("name") or key,
                    "avatar_url": owner["avatarUrl"],
                    "kind": "org" if owner["__typename"] == "Organization" else "user",
                    "count": 0,
                })
                entry["count"] += item["contributions"]["totalCount"]
        cursor = end
    return me["avatarUrl"], owners


def fetch_data_uri(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            ctype = resp.headers.get("Content-Type", "image/png").split(";")[0]
            return f"data:{ctype};base64,{base64.b64encode(resp.read()).decode()}"
    except Exception as exc:
        print(f"avatar fetch failed for {url}: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape(str(s), quote=True)


def short(s, n=18):
    return s if len(s) <= n else s[: n - 1] + "…"


def font_css():
    out = []
    for weight, fname in FONT_FILES.items():
        path = FONT_DIR / fname
        if not path.exists():
            print(f"font missing: {path} (falling back to system fonts)", file=sys.stderr)
            continue
        b64 = base64.b64encode(path.read_bytes()).decode()
        out.append(
            "@font-face{font-family:'Poppins';font-style:normal;font-weight:%d;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}" % (weight, b64)
        )
    return "".join(out)


CSS = """
text{font-family:'Poppins','Segoe UI',Helvetica,Arial,sans-serif}
.nm{font-size:10px;font-weight:500;fill:#c9d1d9;letter-spacing:.1px}
.ct{font-size:9px;font-weight:400;fill:#5fd9a3;letter-spacing:.2px}
.ring{fill:none;stroke:#8b949e;stroke-opacity:.13;stroke-width:1;stroke-dasharray:2 7}
.wire{fill:none;stroke:%(neon)s;stroke-linecap:round;stroke-dasharray:100;
      animation:draw 1.1s cubic-bezier(.3,.7,.2,1) both}
.spark{fill:none;stroke:%(neon)s;stroke-width:1.7;stroke-linecap:round;
       stroke-dasharray:3.5 196.5;stroke-dashoffset:3.5;stroke-opacity:.8;
       animation:spark linear infinite both}
.node,.center{transform-box:fill-box;transform-origin:50%% 50%%;animation:pop .75s cubic-bezier(.2,.8,.2,1) both}
.center{animation-name:rise;animation-duration:.8s}
.pulse{fill:none;stroke:%(neon)s;stroke-width:1;stroke-opacity:0;
       transform-box:fill-box;transform-origin:50%% 50%%;animation:pulse 5s ease-out infinite both}
.init{font-weight:600;fill:%(neon)s}
@keyframes draw{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}
@keyframes spark{from{stroke-dashoffset:3.5}to{stroke-dashoffset:-196.5}}
@keyframes pop{from{opacity:0;transform:translate(var(--dx),var(--dy)) scale(.78)}
               to{opacity:1;transform:translate(0,0) scale(1)}}
@keyframes rise{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}
@keyframes pulse{0%%{stroke-opacity:.30;transform:scale(1)}100%%{stroke-opacity:0;transform:scale(1.75)}}
@media (prefers-color-scheme:light){
  .nm{fill:#24292f}.ct{fill:#1a7f4b}.ring{stroke:#57606a;stroke-opacity:.22}
  .wire,.spark{stroke:#00a86b}
}
@media (prefers-reduced-motion:reduce){
  .wire,.spark,.node,.center,.pulse{animation:none!important}
}
""" % {"neon": NEON}


def plate(shape, x, y, r, clip_id, data_uri, label):
    """Dim-black plate with grey border and the avatar inside.
    shape 'org' -> rounded square, 'user' -> circle."""
    pad = 3.5
    if shape == "org":
        outer = (f'<rect x="{x - r - pad:.1f}" y="{y - r - pad:.1f}" width="{2 * (r + pad):.1f}" '
                 f'height="{2 * (r + pad):.1f}" rx="{(r + pad) * 0.42:.1f}" fill="{PLATE}" '
                 f'stroke="{BORDER}" stroke-width="1.4"/>')
        clip = (f'<clipPath id="{clip_id}"><rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r:.1f}" '
                f'height="{2 * r:.1f}" rx="{r * 0.36:.1f}"/></clipPath>')
    else:
        outer = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + pad:.1f}" fill="{PLATE}" '
                 f'stroke="{BORDER}" stroke-width="1.4"/>')
        clip = f'<clipPath id="{clip_id}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/></clipPath>'
    if data_uri:
        inner = (f'<image href="{data_uri}" x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r:.1f}" '
                 f'height="{2 * r:.1f}" clip-path="url(#{clip_id})" preserveAspectRatio="xMidYMid slice"/>')
    else:
        inner = (f'<text class="init" x="{x:.1f}" y="{y + r * 0.34:.1f}" text-anchor="middle" '
                 f'font-size="{r * 0.95:.0f}">{esc(label[:1].upper())}</text>')
    return clip, outer + inner


def node_radius(kind, ratio):
    return (22 + 11 * math.sqrt(ratio)) if kind == "org" else (16 + 9 * math.sqrt(ratio))


def wire_points(cx, cy, cr, x, y, r):
    """Quadratic wire from the center plate edge to the node plate edge."""
    dx, dy = x - cx, y - cy
    dist = math.hypot(dx, dy)
    ux, uy = dx / dist, dy / dist
    sx, sy = cx + ux * (cr + 9), cy + uy * (cr + 9)
    ex, ey = x - ux * (r + 8), y - uy * (r + 8)
    mx, my = (sx + ex) / 2, (sy + ey) / 2
    curve = 0.10 * dist
    return (sx, sy, mx - uy * curve, my + ux * curve, ex, ey)


def clearance(cx, cy, cr, node, others):
    """Smallest gap between this node's wire and the plates of the other nodes."""
    sx, sy, qx, qy, ex, ey = wire_points(cx, cy, cr, node["x"], node["y"], node["r"])
    best = 1e9
    for k in range(1, 26):
        t = k / 26
        bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * qx + t * t * ex
        by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * qy + t * t * ey
        for o in others:
            best = min(best, math.hypot(bx - o["x"], by - o["y"]) - (o["r"] + 9))
            ly = o["y"] - o["r"] - 16 if math.sin(o["ang"]) < -0.35 else o["y"] + o["r"] + 24
            for dx in (-48, -24, 0, 24, 48):
                best = min(best, math.hypot(bx - (o["x"] + dx), by - ly) - 12)
    return best


def plan(orgs, people):
    """Ring sizes per group and canvas half-size."""
    if orgs and people:
        groups = [("org", orgs, (205, 140)), ("user", people, (390, 240))]
    else:
        items = orgs or people
        k = len(items)
        ring = (230, 150) if k <= 4 else ((290, 190) if k <= 9 else (340, 215))
        groups = [("org" if orgs else "user", items, ring)]
    outer = groups[-1][2]
    return groups, outer[0] + 78, outer[1] + 84


def place(groups, cx, cy, cr):
    """Place nodes on their rings. Outer-ring nodes are rotated to the angle that keeps
    their wires furthest away from the inner nodes, so no wire runs under another plate."""
    placed = []
    for gi, (kind, items, (rx, ry)) in enumerate(groups):
        peak = max((i["count"] for i in items), default=1) or 1
        n = len(items)

        def build(offset):
            out = []
            for i, item in enumerate(items):
                ang = -math.pi / 2 + offset + 2 * math.pi * i / n
                ratio = item["count"] / peak
                out.append({"item": item, "kind": kind, "ring": (rx, ry), "ang": ang,
                            "x": cx + rx * math.cos(ang), "y": cy + ry * math.sin(ang),
                            "r": node_radius(kind, ratio), "ratio": ratio})
            return out

        if gi == 0:
            nodes = build(0.0)
        else:
            inner = list(placed)
            step = 2 * math.pi / n
            best_off, best_gap = 0.0, -1e9
            for k in range(0, 120):
                off = step * k / 120
                cand = build(off)
                gap = min(clearance(cx, cy, cr, c, inner) for c in cand)
                if gap > best_gap:
                    best_off, best_gap = off, gap
            nodes = build(best_off)
        placed.extend(nodes)
    return placed


def render(user, user_avatar, orgs, people):
    groups, half_w, half_h = plan(orgs, people)
    W, H = int(2 * half_w), int(2 * half_h)
    cx, cy = half_w, half_h
    cr = 40
    placed = place(groups, cx, cy, cr)

    rings, wires, sparks, nodes, defs = [], [], [], [], []

    # concentric "web" rings
    ring_sizes = [g[2] for g in groups]
    for rx, ry in ring_sizes:
        rings.append(f'<ellipse class="ring" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>')
    rings.append(f'<ellipse class="ring" cx="{cx}" cy="{cy}" rx="{ring_sizes[0][0] * 0.55:.0f}" '
                 f'ry="{ring_sizes[0][1] * 0.55:.0f}"/>')

    for idx, node in enumerate(placed):
        item, kind, ang = node["item"], node["kind"], node["ang"]
        x, y, r, ratio = node["x"], node["y"], node["r"], node["ratio"]

        sx, sy, qx, qy, ex, ey = wire_points(cx, cy, cr, x, y, r)
        d = f"M{sx:.1f} {sy:.1f}Q{qx:.1f} {qy:.1f} {ex:.1f} {ey:.1f}"

        t_wire = 0.55 + 0.11 * idx
        t_node = t_wire + 0.8
        t_spark = t_wire + 2.0 + (idx * 0.43) % 2.6
        sw = 0.9 + 0.8 * ratio
        wires.append(
            f'<path class="wire" pathLength="100" d="{d}" stroke-width="{sw:.2f}" '
            f'stroke-opacity="{0.20 + 0.18 * ratio:.2f}" style="animation-delay:{t_wire:.2f}s"/>'
        )
        sparks.append(
            f'<path class="spark" pathLength="100" d="{d}" '
            f'style="animation-duration:{3.4 + (idx * 0.37) % 2.2:.2f}s;animation-delay:{t_spark:.2f}s"/>'
        )

        clip, body = plate(kind, x, y, r, f"c{idx}", item.get("avatar"), item["name"])
        defs.append(clip)
        above = math.sin(ang) < -0.35
        if above:
            ny_, cy_ = y - r - 21, y - r - 10
        else:
            ny_, cy_ = y + r + 18, y + r + 30
        label = "Organization" if kind == "org" else "Person"
        nodes.append(
            f'<g class="node" style="--dx:{cx - x:.0f}px;--dy:{cy - y:.0f}px;animation-delay:{t_node:.2f}s">'
            f'<title>{esc(item["name"])} ({label}): {item["count"]:,} contributions</title>'
            f'{body}'
            f'<text class="nm" x="{x:.1f}" y="{ny_:.1f}" text-anchor="middle">{esc(short(item["name"]))}</text>'
            f'<text class="ct" x="{x:.1f}" y="{cy_:.1f}" text-anchor="middle">{item["count"]:,}</text></g>'
        )

    # center: just my avatar
    defs.append(f'<clipPath id="cc"><circle cx="{cx}" cy="{cy}" r="{cr}"/></clipPath>')
    if user_avatar:
        c_img = (f'<image href="{user_avatar}" x="{cx - cr}" y="{cy - cr}" width="{2 * cr}" height="{2 * cr}" '
                 f'clip-path="url(#cc)" preserveAspectRatio="xMidYMid slice"/>')
    else:
        c_img = (f'<text class="init" x="{cx}" y="{cy + 15}" text-anchor="middle" font-size="42">'
                 f'{esc(user[:1].upper())}</text>')
    center = (
        f'<circle class="pulse" cx="{cx}" cy="{cy}" r="{cr + 6}" style="animation-delay:1.6s"/>'
        f'<g class="center">'
        f'<circle cx="{cx}" cy="{cy}" r="{cr + 5}" fill="{PLATE}" stroke="{BORDER_HI}" stroke-width="1.6"/>'
        f'{c_img}</g>'
    )

    defs.insert(0, f'<style>{font_css()}{CSS}</style>')
    defs.insert(1,
        f'<filter id="glow" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
        f'<feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )

    total = sum(n["item"]["count"] for n in placed)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="Contribution map for {esc(user)}">'
        f'<title>{esc(user)}: {total:,} contributions across {len(placed)} organizations and people</title>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g>{"".join(rings)}</g>'
        f'<g>{"".join(wires)}</g>'
        f'<g filter="url(#glow)">{"".join(sparks)}</g>'
        f'<g>{"".join(nodes)}</g>'
        f'{center}'
        f'</svg>\n'
    )


# --------------------------------------------------------------------------- #
def _demo_avatar(label, hue):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue},45%,38%)"/><stop offset="1" stop-color="hsl({(hue + 40) % 360},55%,22%)"/>'
        '</linearGradient></defs><rect width="100" height="100" fill="url(#g)"/>'
        f'<text x="50" y="66" font-size="48" font-family="Arial" font-weight="700" text-anchor="middle" '
        f'fill="rgba(255,255,255,.85)">{label[:1].upper()}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def demo_data():
    orgs = [("Codemo Open Source Labs", 412), ("redline-security", 268), ("agentforge", 190),
            ("sandbox-works", 143), ("sigma-rules", 97), ("zero-trust-kit", 64)]
    people = [("Ali Raza", 58), ("mchen", 41), ("sarah-k", 33), ("n0va", 27),
              ("Tariq Aziz", 19), ("lena-dev", 12), ("pwn-ninja", 8), ("dr-fuzz", 5)]
    mk = lambda lst, k, base: [
        {"name": n, "count": c, "kind": k, "avatar": _demo_avatar(n, (base + i * 47) % 360)}
        for i, (n, c) in enumerate(lst)
    ]
    return mk(orgs, "org", 150), mk(people, "user", 20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", ""))
    ap.add_argument("--out", default="assets/contribution-map.svg")
    ap.add_argument("--top-orgs", type=int, default=8, help="max organizations shown")
    ap.add_argument("--top-people", type=int, default=10, help="max people shown")
    ap.add_argument("--no-people", action="store_true", help="organizations only")
    ap.add_argument("--exclude", default="", help="comma-separated logins to hide")
    ap.add_argument("--demo", action="store_true", help="offline preview with fake data")
    args = ap.parse_args()

    if args.demo:
        user = args.user or "uzairshahidgithub"
        user_avatar = _demo_avatar(user, 160)
        orgs, people = demo_data()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token or not args.user:
            sys.exit("Need --user and GITHUB_TOKEN (or use --demo).")
        user = args.user
        avatar_url, raw = collect(user, token)
        user_avatar = fetch_data_uri(avatar_url)
        hide = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
        by_kind = {"org": [], "user": []}
        for login, o in raw.items():
            if login.lower() in hide:
                continue
            by_kind[o["kind"]].append({"name": o["name"], "count": o["count"],
                                       "kind": o["kind"], "avatar_url": o["avatar_url"]})
        orgs = sorted(by_kind["org"], key=lambda o: o["count"], reverse=True)[: args.top_orgs]
        people = [] if args.no_people else sorted(
            by_kind["user"], key=lambda o: o["count"], reverse=True)[: args.top_people]
        for item in orgs + people:           # only fetch avatars for what is drawn
            item["avatar"] = fetch_data_uri(item.pop("avatar_url"))

    orgs.sort(key=lambda o: o["count"], reverse=True)
    people.sort(key=lambda o: o["count"], reverse=True)
    svg = render(user, user_avatar, orgs, people)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {args.out}: {len(orgs)} organizations, {len(people)} people, {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
