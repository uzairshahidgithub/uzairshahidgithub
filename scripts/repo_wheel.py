#!/usr/bin/env python3
"""
Generate adaptive Dark & Light Repository OptionWheel SVG slices
(`assets/wheel-{i}.svg` and `assets/wheel-{i}-light.svg`) modeled after the
React Bits <OptionWheel side="right" /> component, plus optionally sync
README.md and docs/index.html so live repository updates stay automated end-to-end.
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import re
import urllib.request
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"
OUTFIT_REGULAR = FONT_DIR / "outfit-latin-400-normal.woff2"
POPPINS_MEDIUM = FONT_DIR / "poppins-latin-500-normal.woff2"

DEFAULT_REPOS = [
    "Libre-Merger",
    "Study-Deep-Learning",
    "cs101-offline-ctf",
    "api-security-scanner",
    "Fedora-Security-Automation",
    "Ransomware-IR-Purple-Team-Exercise-Lab",
    "Advanced-Steganography-Payload-Concealment-Detection-Lab",
    "Detection-Engineering-Alert-Tuning-Threat-Hunting-Lab",
    "WiFi-Security-Honeypots-Network-Surveillance-Lab",
]

EXCLUDED_REPOS = {
    "uzairshahidgithub",
    "codemo-labs",
    "udemy-jams-bot",
    "terminal-github-profile",
    "setup-git",
    "cybersecuriy-learning",
    "currency-converter",
    "university-management-project",
    "cpp-object-oriented-programming",
    "cpp-programming-fundamentals",
    "coke-animated-logo",
    "cybertrek-registration",
}

FULL_W = 640
ROW_H = 40


def fetch_top_repos(user, limit=9, token=None):
    """Fetch live non-fork, non-archived repositories with rich metadata (never falls back unless network fails)."""
    url = f"https://api.github.com/users/{user}/repos?per_page=100&sort=updated"
    headers = {"User-Agent": "repo-wheel/1.0", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        picked = [
            {
                "name": repo["name"],
                "description": (repo.get("description") or "").strip(),
                "url": repo.get("html_url") or f"https://github.com/{user}/{repo['name']}",
                "language": repo.get("language") or "",
                "topics": repo.get("topics") or [],
            }
            for repo in data
            if not repo.get("fork")
            and not repo.get("archived")
            and repo.get("size", 0) > 10
            and repo["name"].lower() not in EXCLUDED_REPOS
        ][:limit]
        if picked:
            return picked
    except Exception:
        pass
    return [
        {
            "name": name,
            "description": "",
            "url": f"https://github.com/{user}/{name}",
            "language": "",
            "topics": [],
        }
        for name in DEFAULT_REPOS[:limit]
    ]


def _lerp_hex(c1, c2, t):
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _fonts():
    return (
        base64.b64encode(OUTFIT_REGULAR.read_bytes()).decode(),
        base64.b64encode(POPPINS_MEDIUM.read_bytes()).decode(),
    )


def build_row_svg(
    title,
    index,
    mid_index,
    dark_mode=True,
    width=FULL_W,
    row_height=ROW_H,
    anchor_x=490.0,
    curve=1.35,
    tilt_deg=1.55,
    blur_step=0.22,
    fade_step=0.14,
    min_opacity=0.40,
):
    """Render one OptionWheel row slice following side='right' circular arc math."""
    d = index - mid_index
    dist = abs(d)
    p = max(0.0, 1.0 - min(dist, 1.0))

    tilt_rad = math.radians(tilt_deg)
    R = (row_height * 1.10) / tilt_rad if tilt_rad > 0.0005 else 0.0
    ang = max(-math.pi / 2, min(math.pi / 2, d * tilt_rad))
    arc_x = R * (1.0 - math.cos(ang)) * curve if R > 0 else 0.0
    x_pos = min(width - 18.0, anchor_x + arc_x * 6.8)

    opacity = max(min_opacity, 1.0 - dist * fade_step)
    blur_px = min(0.95, dist * blur_step)

    rest_col, active_col = ("#8b949e", "#f0f6fc") if dark_mode else ("#6e7781", "#1f2328")
    fill_col = _lerp_hex(rest_col, active_col, p)

    font_size = 22.0 if dist == 0 else max(16.0, 20.0 - dist * 0.9)
    outfit_b64, poppins_b64 = _fonts()
    font_family = "WheelMedium" if dist == 0 else "WheelReg"
    font_b64 = poppins_b64 if dist == 0 else outfit_b64
    font_weight = 500 if dist == 0 else 400

    min_left_margin = 20.0
    est_width = len(title) * font_size * 0.54
    if x_pos - est_width < min_left_margin:
        font_size = max(11.5, (x_pos - min_left_margin) / max(1.0, len(title) * 0.54))
        est_width = len(title) * font_size * 0.54

    raw_rot = -math.degrees(ang) * 0.80
    max_swing = max(2.0, (row_height - font_size * 1.05) / 2.0 - 2.0)
    max_deg = math.degrees(math.asin(min(0.99, max_swing / max(1.0, est_width * 0.52))))
    rot_deg = max(-max_deg, min(max_deg, raw_rot))
    pivot_x = x_pos - est_width / 2.0
    pivot_y = row_height / 2.0

    y_mid = row_height / 2.0 + font_size * 0.34
    blur_filter = (
        f'<filter id="owb" x="-15%" y="-60%" width="130%" height="220%">'
        f'<feGaussianBlur stdDeviation="{blur_px:.2f}" /></filter>'
        if blur_px > 0.05
        else ""
    )
    filter_attr = ' filter="url(#owb)"' if blur_px > 0.05 else ""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {row_height}" '
        f'width="{width}" height="{row_height}" role="img" aria-label="{html.escape(title)}">'
        f'<title>{html.escape(title)}</title>'
        f'<defs>'
        f'<style>'
        f'@font-face{{font-family:\'{font_family}\';font-style:normal;font-weight:{font_weight};'
        f'src:url(data:font/woff2;base64,{font_b64}) format(\'woff2\');}}'
        f'.ow-t{{font-family:\'{font_family}\',-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
        f'font-size:{font_size:.1f}px;font-weight:{font_weight};letter-spacing:-0.3px}}'
        f'</style>'
        f'{blur_filter}'
        f'</defs>'
        f'<g transform="rotate({rot_deg:.2f} {pivot_x:.1f} {pivot_y:.1f})"{filter_attr}>'
        f'<text class="ow-t" x="{x_pos:.1f}" y="{y_mid:.1f}" text-anchor="end" '
        f'fill="{fill_col}" fill-opacity="{opacity:.3f}">{html.escape(title)}</text>'
        f'</g>'
        f'</svg>\n'
    )


def build_launch_svg(dark_mode=True):
    """Build standalone circular frosted arrow icon button (no text) linking to interactive wheel."""
    size = 42
    c = size / 2.0
    r = 19.0
    if dark_mode:
        fill, fill_op = "#238636", "0.22"
        frost_op = "0.08"
        stroke, stroke_op = "#3fb950", "0.52"
        icon_col = "#f0fdf4"
    else:
        fill, fill_op = "#1a7f37", "0.10"
        frost_op = "0.42"
        stroke, stroke_op = "#1a7f37", "0.38"
        icon_col = "#1a7f37"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'role="img" aria-label="Open Interactive Repository Wheel">'
        f'<title>Open Interactive Repository Wheel</title>'
        f'<defs>'
        f'<radialGradient id="launch-sheen" cx="30%" cy="25%" r="75%">'
        f'<stop offset="0%" stop-color="#ffffff" stop-opacity="{frost_op}" />'
        f'<stop offset="100%" stop-color="#ffffff" stop-opacity="0.0" />'
        f'</radialGradient>'
        f'</defs>'
        f'<circle cx="{c:.1f}" cy="{c:.1f}" r="{r:.1f}" fill="{fill}" fill-opacity="{fill_op}" />'
        f'<circle cx="{c:.1f}" cy="{c:.1f}" r="{r:.1f}" fill="url(#launch-sheen)" '
        f'stroke="{stroke}" stroke-opacity="{stroke_op}" stroke-width="1.2" />'
        f'<g transform="translate(11,11)" fill="none" stroke="{icon_col}" '
        f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M5 15L15 5" />'
        f'<path d="M7 5h8v8" />'
        f'</g>'
        f'</svg>\n'
    )


def sync_readme(readme_path, user, repos_meta):
    """Replace the REPO_WHEEL_START..REPO_WHEEL_END block in README.md with current wheel slices & SEO alt tags."""
    p = Path(readme_path)
    src = p.read_text(encoding="utf-8")
    mid_idx = len(repos_meta) // 2
    rows = []
    for idx, meta in enumerate(repos_meta):
        repo = meta["name"]
        desc = meta.get("description") or f"{repo} open-source repository by Muhammad Uzair (@{user})"
        alt_txt = f"{repo} — {desc}"
        pic = (
            f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/wheel-{idx}.svg" />'
            f'<source media="(prefers-color-scheme: light)" srcset="assets/wheel-{idx}-light.svg" />'
            f'<img src="assets/wheel-{idx}.svg" alt="{html.escape(alt_txt)}" /></picture>'
        )
        if idx == mid_idx:
            row = f'  <a href="https://github.com/{user}/{repo}" target="_blank" rel="noopener noreferrer" title="{html.escape(alt_txt)}">{pic}</a>'
        else:
            row = f'  {pic}'
        if idx < len(repos_meta) - 1:
            row += "<br />"
        rows.append(row)
    block = (
        "<!-- REPO_WHEEL_START -->\n"
        '<div align="center">\n'
        "  <!-- Repository OptionWheel: only active white centered item is clickable on GitHub (scripts/repo_wheel.py) -->\n"
        + "\n".join(rows)
        + "\n</div>\n\n<br />\n\n"
        '<div align="center">\n'
        f'  <a href="https://{user}.github.io/{user}/" target="_blank" rel="noopener noreferrer" title="Open Interactive Repository Wheel &amp; Portfolio for Muhammad Uzair (@{user})">'
        '<picture><source media="(prefers-color-scheme: dark)" srcset="assets/wheel-launch.svg" />'
        '<source media="(prefers-color-scheme: light)" srcset="assets/wheel-launch-light.svg" />'
        '<img src="assets/wheel-launch.svg" alt="Open Interactive Repository Wheel for Muhammad Uzair" width="42" height="42" /></picture></a>\n'
        "</div>\n"
        "<!-- REPO_WHEEL_END -->"
    )
    updated, count = re.subn(
        r"<!-- REPO_WHEEL_START -->[\s\S]*?<!-- REPO_WHEEL_END -->",
        lambda _: block,
        src,
        count=1,
    )
    if count:
        p.write_text(updated, encoding="utf-8")
        print(f"synced wheel rows in {p}")


def sync_docs(docs_dir, user, repos_meta):
    """Keep docs/index.html (JS + JSON-LD + semantic list), docs/llms.txt, and docs/sitemap.xml live-synced."""
    d_dir = Path(docs_dir)
    d_dir.mkdir(parents=True, exist_ok=True)
    repos = [m["name"] for m in repos_meta]
    mid_idx = len(repos) // 2

    index_path = d_dir / "index.html"
    if index_path.is_file():
        src = index_path.read_text(encoding="utf-8")
        js_arr = "[\n        " + ",\n        ".join(f"'{r}'" for r in repos) + "\n      ]"
        src = re.sub(r"(let\s+REPOS\s*=\s*)\[[\s\S]*?\](\s*;)", rf"\g<1>{js_arr}\g<2>", src, count=1)
        src = re.sub(r"(defaultSelected\s*:\s*)\d+", rf"\g<1>{mid_idx}", src, count=1)

        item_list = [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": m["name"],
                "url": m["url"],
                **({"description": m["description"]} if m.get("description") else {}),
            }
            for i, m in enumerate(repos_meta)
        ]
        items_json = json.dumps(item_list, indent=2)
        src = re.sub(
            r'("itemListElement"\s*:\s*)\[[\s\S]*?\](\s*\})',
            lambda match: match.group(1) + items_json.replace("\n", "\n      ") + match.group(2),
            src,
            count=1,
        )
        list_html = "\n".join(
            f'      <li><a href="{html.escape(m["url"])}">{html.escape(m["name"])}</a>'
            + (f' — {html.escape(m["description"])}' if m.get("description") else "")
            + "</li>"
            for m in repos_meta
        )
        src = re.sub(
            r"<!-- SEO_REPOS_START -->[\s\S]*?<!-- SEO_REPOS_END -->",
            lambda _: f"<!-- SEO_REPOS_START -->\n{list_html}\n      <!-- SEO_REPOS_END -->",
            src,
            count=1,
        )
        index_path.write_text(src, encoding="utf-8")
        print(f"synced fallback repos & SEO metadata in {index_path}")

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    llms_lines = [
        f"# Muhammad Uzair (@{user})",
        "",
        "> Cyber Security Engineer, Security Researcher, Open Source Developer, Self Designer, DevSecOps, Linux System Administration & AI Automation Engineer.",
        "",
        "## Identity & Official Profiles",
        f"- GitHub: https://github.com/{user}",
        f"- Interactive Repository Showcase: https://{user}.github.io/{user}/",
        "- LinkedIn: https://www.linkedin.com/in/uzairspace/",
        "- YouTube: https://www.youtube.com/channel/UC7XHbPdPUP0PbILQcJfFp0w",
        "- Medium: https://medium.com/@iuzdiary",
        "- Link Hub: https://dott.bio/uzairshahid",
        "",
        "## Core Specializations",
        "- Cyber Security Engineering & AppSec (OWASP, ZAP, Burp Suite, Semgrep, Snyk, Metasploit)",
        "- Blue Team, Purple Team & Detection Engineering (DFIR, Splunk, Elastic, Suricata, Zeek, Wireshark)",
        "- DevSecOps & Cloud Infrastructure (Linux, Fedora, Debian, Docker, Kubernetes, Terraform, Ansible, HashiCorp Vault, AWS, Azure, GCP)",
        "- AI Security Guardrails & Automation (NVIDIA NeMo Guardrails, LangChain, CrewAI, AutoGen, n8n, Ollama, Hugging Face)",
        "",
        "## Featured Public Repositories",
    ]
    for m in repos_meta:
        extra = f" — {m['description']}" if m.get("description") else ""
        lang = f" [{m['language']}]" if m.get("language") else ""
        llms_lines.append(f"- [{m['name']}]({m['url']}){lang}{extra}")
    llms_lines.extend(["", f"_Auto-updated on {today} UTC_"])
    (d_dir / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>https://{user}.github.io/{user}/</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        "    <changefreq>daily</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "  <url>\n"
        f"    <loc>https://{user}.github.io/{user}/llms.txt</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        "    <changefreq>daily</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    (d_dir / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", "uzairshahidgithub"))
    ap.add_argument("--out-dir", default="assets")
    ap.add_argument("--limit", type=int, default=9)
    ap.add_argument("--live", action="store_true", help="fetch latest public repos from GitHub API")
    ap.add_argument("--update-readme", action="store_true", help="sync wheel links inside README.md")
    ap.add_argument("--update-docs", action="store_true", help="sync fallback repos & SEO files in docs/")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if args.live:
        repos_meta = fetch_top_repos(args.user, limit=args.limit, token=token)
    else:
        repos_meta = [
            {"name": r, "description": "", "url": f"https://github.com/{args.user}/{r}", "language": "", "topics": []}
            for r in DEFAULT_REPOS[: args.limit]
        ]
    mid_idx = len(repos_meta) // 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("wheel-*.svg"):
        old.unlink()

    for idx, meta in enumerate(repos_meta):
        for dark, suffix in ((True, ""), (False, "-light")):
            svg = build_row_svg(meta["name"], idx, mid_idx, dark_mode=dark, width=FULL_W)
            (out_dir / f"wheel-{idx}{suffix}.svg").write_text(svg, encoding="utf-8")

    for dark, suffix in ((True, ""), (False, "-light")):
        (out_dir / f"wheel-launch{suffix}.svg").write_text(build_launch_svg(dark_mode=dark), encoding="utf-8")

    if args.update_readme:
        sync_readme("README.md", args.user, repos_meta)
    if args.update_docs:
        sync_docs("docs", args.user, repos_meta)

    print(f"wrote {len(repos_meta)} wheel rows + interactive launch pill centered at '{repos_meta[mid_idx]['name']}'")


if __name__ == "__main__":
    main()
