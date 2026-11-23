#!/usr/bin/env python3
"""
Generate adaptive Dark & Light one-row technology marquee SVGs
(`assets/tech-loop.svg` and `assets/tech-loop-light.svg`) modeled after the
React Bits <LogoLoop /> component (layout='line', direction='left',
smootherstep fadeOut mask at 12% on both ends).
"""
import argparse
import base64
import concurrent.futures
import html
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

UA = "Mozilla/5.0"

# All 53 technologies from the profile README in order, using reliable/theme-safe sources
# Mode-sensitive entries use callable(dark: bool) -> url or transform tag
TECHS = [
    # Programming
    ("Python", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg"),
    ("C++", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg"),
    ("JavaScript", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/javascript/javascript-original.svg"),
    ("TypeScript", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/typescript/typescript-original.svg"),
    ("Go", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original.svg"),
    ("Rust", lambda d: f"https://cdn.simpleicons.org/rust/{'e6edf3' if d else '1f2328'}"),
    ("Bash", lambda d: ("https://cdn.jsdelivr.net/gh/devicons/devicon/icons/bash/bash-original.svg", "bash")),
    ("PowerShell", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/powershell/powershell-original.svg"),
    # Web
    ("HTML5", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/html5/html5-original.svg"),
    ("CSS3", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/css3/css3-original.svg"),
    ("Node.js", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nodejs/nodejs-original.svg"),
    ("React", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg"),
    # Operating Systems
    ("Linux", lambda d: ("https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-plain.svg", "mono")),
    ("Debian", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/debian/debian-original.svg"),
    ("Kali Linux", lambda d: f"https://cdn.simpleicons.org/kalilinux/{'8ec5fc' if d else '557C94'}"),
    ("Ubuntu", "https://cdn.simpleicons.org/ubuntu/E95420"),
    ("Windows Server", "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/windows11/windows11-original.svg"),
    # Cloud & Infrastructure
    ("Microsoft Azure", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/azure/azure-original.svg"),
    ("AWS", lambda d: ("https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/amazon-web-services/default.svg", "aws")),
    ("Google Cloud", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/googlecloud/googlecloud-original.svg"),
    ("Cloudflare", "https://cdn.simpleicons.org/cloudflare/F38020"),
    ("Supabase", "https://cdn.simpleicons.org/supabase/3FCF8E"),
    ("HashiCorp Vault", lambda d: ("https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/vault/default.svg", "vault")),
    # Networking / Security
    ("Wireshark", "https://cdn.simpleicons.org/wireshark/1679A7"),
    ("Nmap", "https://upload.wikimedia.org/wikipedia/commons/7/73/Logo_nmap.png"),
    ("Suricata", "https://logzbucket.s3.eu-west-1.amazonaws.com/logz-docs/shipper-logos/suricata-logo.png"),
    ("Zeek", lambda d: ("https://zeek.org/wp-content/uploads/2020/04/zeek-logo-without-text.png", "zeek")),
    ("OWASP", lambda d: f"https://cdn.simpleicons.org/owasp/{'e6edf3' if d else '1f2328'}"),
    ("Burp Suite", "https://cdn.simpleicons.org/burpsuite/FF6633"),
    ("Metasploit", "https://cdn.simpleicons.org/metasploit/2596CD"),
    # AppSec
    ("OWASP ZAP", "https://raw.githubusercontent.com/wiki/zaproxy/zaproxy/images/zap32x32.png"),
    ("Snyk", lambda d: f"https://cdn.simpleicons.org/snyk/{'9d8df1' if d else '4C4A73'}"),
    ("Semgrep", lambda d: ("https://raw.githubusercontent.com/returntocorp/semgrep/develop/semgrep.svg", "semgrep")),
    # SIEM / Detection
    ("Splunk", lambda d: f"https://cdn.simpleicons.org/splunk/{'e6edf3' if d else '1f2328'}"),
    ("Elastic", lambda d: f"https://cdn.simpleicons.org/elastic/{'38bdf8' if d else '005571'}"),
    # Containers / DevSecOps
    ("Docker", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/docker/docker-original.svg"),
    ("Kubernetes", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/kubernetes/kubernetes-original.svg"),
    ("Terraform", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/terraform/terraform-original.svg"),
    ("Ansible", lambda d: ("https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ansible/ansible-original.svg", "ansible")),
    # Databases
    ("SQLite", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/sqlite/sqlite-original.svg"),
    ("Microsoft SQL Server", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/microsoftsqlserver/microsoftsqlserver-plain.svg"),
    ("PostgreSQL", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg"),
    ("MongoDB", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/mongodb/mongodb-original.svg"),
    # Development
    ("Git", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/git/git-original.svg"),
    ("GitHub", lambda d: f"https://cdn.simpleicons.org/github/{'e6edf3' if d else '1f2328'}"),
    ("Visual Studio Code", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vscode/vscode-original.svg"),
    # AI Guardrails & Orchestration & Serving
    ("NVIDIA NeMo Guardrails", lambda d: "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/nvidia/default.svg" if d else "https://cdn.simpleicons.org/nvidia/76B900"),
    ("LangChain", "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/langchain-corporate/default.svg"),
    ("n8n", "https://cdn.simpleicons.org/n8n/EA4B71"),
    ("CrewAI", "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/crewai/default.svg"),
    ("Microsoft AutoGen", lambda d: ("https://microsoft.github.io/autogen/0.2/img/ag.svg", "autogen")),
    ("Ollama", lambda d: f"https://cdn.simpleicons.org/ollama/{'e6edf3' if d else '1f2328'}"),
    ("Hugging Face", "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/huggingface/default.svg"),
]

# Dynamic language/topic expansion catalog: appended automatically when detected in user's edited repos
EXTRA_TECH_CATALOG = {
    "jupyter notebook": ("Jupyter", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/jupyter/jupyter-original.svg"),
    "jupyter": ("Jupyter", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/jupyter/jupyter-original.svg"),
    "fedora": ("Fedora", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fedora/fedora-plain.svg"),
    "rhel": ("Red Hat", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/redhat/redhat-original.svg"),
    "java": ("Java", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/java/java-original.svg"),
    "kotlin": ("Kotlin", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/kotlin/kotlin-original.svg"),
    "c#": ("C#", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/csharp/csharp-original.svg"),
    "ruby": ("Ruby", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ruby/ruby-original.svg"),
    "php": ("PHP", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/php/php-original.svg"),
    "swift": ("Swift", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/swift/swift-original.svg"),
    "dart": ("Dart", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/dart/dart-original.svg"),
    "lua": ("Lua", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/lua/lua-original.svg"),
    "fastapi": ("FastAPI", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fastapi/fastapi-original.svg"),
    "django": ("Django", lambda d: f"https://cdn.simpleicons.org/django/{'44b78b' if d else '092e20'}"),
    "flask": ("Flask", lambda d: f"https://cdn.simpleicons.org/flask/{'e6edf3' if d else '1f2328'}"),
    "nextjs": ("Next.js", lambda d: f"https://cdn.simpleicons.org/nextdotjs/{'e6edf3' if d else '1f2328'}"),
    "next.js": ("Next.js", lambda d: f"https://cdn.simpleicons.org/nextdotjs/{'e6edf3' if d else '1f2328'}"),
    "vue": ("Vue.js", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vuejs/vuejs-original.svg"),
    "vuejs": ("Vue.js", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vuejs/vuejs-original.svg"),
    "svelte": ("Svelte", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/svelte/svelte-original.svg"),
    "redis": ("Redis", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/redis/redis-original.svg"),
    "graphql": ("GraphQL", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/graphql/graphql-plain.svg"),
    "nginx": ("Nginx", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nginx/nginx-original.svg"),
    "podman": ("Podman", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/podman/podman-original.svg"),
    "gitlab": ("GitLab", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/gitlab/gitlab-original.svg"),
    "grafana": ("Grafana", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/grafana/grafana-original.svg"),
    "prometheus": ("Prometheus", "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/prometheus/prometheus-original.svg"),
    "libreoffice": ("LibreOffice", "https://cdn.simpleicons.org/libreoffice/18A303"),
    "wireshark": ("Wireshark", "https://cdn.simpleicons.org/wireshark/1679A7"),
}


def discover_user_techs(user, token=None):
    """Discover extra technologies from live repository languages and topics so stack stays auto-synced."""
    if not user:
        return []
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(f"https://api.github.com/users/{user}/repos?per_page=100", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            repos = json.load(r)
    except Exception:
        return []

    seen_names = {name.lower() for name, _ in TECHS}
    extras = []
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue
        candidates = []
        if repo.get("language"):
            candidates.append(repo["language"].strip().lower())
        for tp in repo.get("topics") or []:
            candidates.append(str(tp).strip().lower())
        for key in candidates:
            if key in EXTRA_TECH_CATALOG:
                disp_name, spec = EXTRA_TECH_CATALOG[key]
                if disp_name.lower() not in seen_names:
                    seen_names.add(disp_name.lower())
                    extras.append((disp_name, spec))
    return extras


def _fetch(url):
    last_exc = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except Exception as exc:
            last_exc = exc
            time.sleep(0.6 * (2 ** attempt))
    raise last_exc


def _downscale_png_to_webp_uri(raw_bytes, max_px=64, invert=False):
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    if invert:
        r, g, b, a = im.split()
        from PIL import ImageOps
        im = Image.merge("RGBA", (ImageOps.invert(r), ImageOps.invert(g), ImageOps.invert(b), a))
    w, h = im.size
    scale = min(max_px / max(w, 1), max_px / max(h, 1), 1.0)
    if scale < 1.0:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=90, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def _process_svg(raw_bytes, tag, dark_mode):
    txt = raw_bytes.decode("utf-8", "ignore")
    if tag == "autogen":
        # Microsoft AutoGen embeds a giant raster PNG inside an SVG wrapper; extract & shrink it
        m = re.search(r'xlink:href="data:image/[^;]+;base64,([^"]+)"', txt)
        if m:
            return _downscale_png_to_webp_uri(base64.b64decode(m.group(1)), max_px=64)
    elif tag == "semgrep":
        # Extract the crisp 3-circle Semgrep symbol alone (without ultra-wide wordmark text)
        m = re.search(r'(<g id="semgrep-ellipsis"[\s\S]*?</g>)', txt)
        if m:
            txt = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -60 520 320">'
                f'{m.group(1)}</svg>'
            )
    elif tag == "aws":
        if not dark_mode:
            txt = txt.replace('fill="#ffffff"', 'fill="#232F3E"')
    elif tag == "vault":
        if not dark_mode:
            txt = txt.replace('#FFEC6E', '#EAB308').replace('#ffec6e', '#eab308')
    elif tag == "mono":
        color = "#e6edf3" if dark_mode else "#1f2328"
        txt = re.sub(r"<svg([^>]*)>", rf'<svg\1 fill="{color}">', txt, count=1)
    elif tag == "bash":
        if dark_mode:
            txt = txt.replace("#293138", "#e6edf3")
    elif tag == "ansible":
        if dark_mode:
            txt = txt.replace("#1A1918", "#e6edf3").replace("#FFF", "#0d1117")
    return "data:image/svg+xml;base64," + base64.b64encode(txt.encode("utf-8")).decode()


def fetch_icon_uri(spec, dark_mode):
    name, src = spec
    try:
        resolved = src(dark_mode) if callable(src) else src
        url, tag = resolved if isinstance(resolved, tuple) else (resolved, None)
        raw = _fetch(url)
        if url.lower().endswith(".png"):
            uri = _downscale_png_to_webp_uri(raw, max_px=64, invert=(tag == "zeek" and dark_mode))
        else:
            uri = _process_svg(raw, tag, dark_mode)
        return name, uri
    except Exception as exc:
        print(f"skipping tech icon '{name}': {exc}", file=sys.stderr)
        return None


def smootherstep(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def fade_stops(fade_width=0.12):
    """Exact 13-step smootherstep fade mask from React Bits <LogoLoop />."""
    span = max(0.0, min(0.5, fade_width)) * 100.0
    stops = []
    for i in range(13):
        a = smootherstep(i / 12.0)
        stops.append(f'<stop offset="{(span * i / 12.0):.3f}%" stop-color="#ffffff" stop-opacity="{a:.4f}" />')
    for i in range(12, -1, -1):
        a = smootherstep(i / 12.0)
        stops.append(f'<stop offset="{(100.0 - span * i / 12.0):.3f}%" stop-color="#ffffff" stop-opacity="{a:.4f}" />')
    return "".join(stops)


def build_loop_svg(dark_mode=True, width=640, height=56, logo_size=38, gap=36, speed=84.0, specs=None):
    """Build self-contained one-row LogoLoop SVG with seamless marquee + edge fade mask."""
    tech_list = specs if specs is not None else TECHS
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        raw_items = list(ex.map(lambda sp: fetch_icon_uri(sp, dark_mode), tech_list))
    items = [it for it in raw_items if it is not None]

    pitch = logo_size + gap
    period = len(items) * pitch
    duration = period / max(1.0, speed)
    y_pos = (height - logo_size) / 2.0

    defs_imgs = []
    track_items = []
    for idx, (name, uri) in enumerate(items):
        defs_imgs.append(
            f'<image id="ic{idx}" href="{uri}" width="{logo_size}" height="{logo_size}" '
            f'preserveAspectRatio="xMidYMid meet" />'
        )
    # Render 2 seamless copies so wrap-around is invisible across the viewport
    for copy_idx in range(2):
        base_x = copy_idx * period
        for idx, (name, _) in enumerate(items):
            x_pos = base_x + idx * pitch
            track_items.append(
                f'<g transform="translate({x_pos},{y_pos:.1f})">'
                f'<title>{html.escape(name)}</title>'
                f'<use href="#ic{idx}" />'
                f'</g>'
            )

    css = f"""
.loop-track{{will-change:transform;animation:logoloop {duration:.2f}s linear infinite}}
@keyframes logoloop{{from{{transform:translate3d(0px,0,0)}}to{{transform:translate3d(-{period}px,0,0)}}}}
@media (prefers-reduced-motion:reduce){{.loop-track{{animation:none!important}}}}
"""
    tech_names = ", ".join(html.escape(name) for name, _ in items)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Technologies marquee: {tech_names}">
<title>Technologies &amp; Security Stack ({len(items)})</title>
<desc>Languages, Cloud, DevSecOps, Networking, Security Tools, and AI Frameworks used by Muhammad Uzair: {tech_names}</desc>
<defs>
  <style>{css}</style>
  <linearGradient id="fade-grad" x1="0%" y1="0%" x2="100%" y2="0%">{fade_stops(0.12)}</linearGradient>
  <mask id="edge-fade">
    <rect x="0" y="0" width="{width}" height="{height}" fill="url(#fade-grad)" />
  </mask>
  {"".join(defs_imgs)}
</defs>
<g mask="url(#edge-fade)">
  <g class="loop-track">{"".join(track_items)}</g>
</g>
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", "uzairshahidgithub"))
    ap.add_argument("--out-dir", default="assets")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    extras = discover_user_techs(args.user, token=token)
    full_specs = list(TECHS) + extras

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dark_svg = build_loop_svg(dark_mode=True, specs=full_specs)
    dark_path = out_dir / "tech-loop.svg"
    dark_path.write_text(dark_svg, encoding="utf-8")
    print(f"wrote {dark_path}: {len(full_specs)} icons ({len(extras)} discovered), {len(dark_svg) // 1024} KB")

    light_svg = build_loop_svg(dark_mode=False, specs=full_specs)
    light_path = out_dir / "tech-loop-light.svg"
    light_path.write_text(light_svg, encoding="utf-8")
    print(f"wrote {light_path}: {len(full_specs)} icons ({len(extras)} discovered), {len(light_svg) // 1024} KB")


if __name__ == "__main__":
    main()
