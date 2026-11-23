#!/usr/bin/env python3
"""
Generate adaptive Dark & Light GitHub Profile README headers
(`assets/hero-header.svg` and `assets/hero-header-light.svg`).

Cinema-hall spotlight reveal:
- Outside the moving spotlight beam, nothing shows (pure transparent background
  that adopts GitHub's #0d1117 dark or #ffffff light environment seamlessly).
- A soft, edge-free blurry light wanders slowly up, down, left, and right,
  revealing colored <GradientASCII /> characters only where the beam lands.
- Centered "Muhammad Uzair" (non-bold iconic iPhone Duo Liquid Glass) and
  circular frosted social icons stay anchored in place and refract the moving
  light as it passes behind them.
"""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

FONT_DIR = Path(__file__).resolve().parent / "fonts"
OUTFIT_REGULAR = FONT_DIR / "outfit-latin-400-normal.woff2"
INTER_LIGHT = FONT_DIR / "inter-latin-300-normal.woff2"
GEIST_MONO = FONT_DIR / "geist-mono-latin-300-normal.woff2"

# GitHub Primer-matched soft frosted green palettes
DARK_COLORS = ["#0e4429", "#006d32", "#26a641", "#56d364"]
LIGHT_COLORS = ["#116329", "#1a7f37", "#2da44e", "#6fdd8b"]

PROFESSIONS = [
    "Cyber Security Engineer",
    "Security Researcher",
    "Open Source Developer",
    "Self Designer",
    "DevSecOps",
    "Linux System Administration",
    "AI Automation Engineer",
]

# Exact React Bits <GradientASCII /> WebGL2 shader covering the full canvas
# (visibility is gated dynamically in SVG by the roving cinema-spotlight mask)
WEBGL_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  @font-face {
    font-family: 'Geist Mono';
    font-style: normal;
    font-weight: 300;
    src: url('data:font/woff2;base64,__GEIST_B64__') format('woff2');
  }
  html, body { margin: 0; padding: 0; background: transparent; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<script>
const MAX_COLORS = 8;
const ATLAS_CELL_W = 60;
const ATLAS_CELL_H = 100;
const ATLAS_COLUMNS = 16;
const FONT_SCALE = 0.78;
const CHARACTERS = ' =+xX0S8#@';
const COLORS = __COLORS_JSON__;
const LIGHT_MODE = __LIGHT_MODE__;
const FONT_FAMILY = '"Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

const VERTEX = `#version 300 es
out vec2 vUv;
void main() {
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  vUv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const COMMON = `
float hash12(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * 0.1031);
  q += dot(q, q.yzx + 33.33);
  return fract((q.x + q.y) * q.z);
}
`;

const FIELD = `#version 300 es
precision highp float;
precision highp int;
uniform float uAspect;
uniform float uTime;
uniform vec3 uRamp[8];
uniform int uCount;
uniform float uScale;
uniform float uSoftness;
uniform float uFlow;
uniform vec2 uSeed;
uniform float uFrame;
in vec2 vUv;
layout(location = 0) out vec4 outColor;
layout(location = 1) out vec4 outAux;
${COMMON}
vec2 hash22(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.103, 0.0973));
  q += dot(q, q.yzx + 33.33);
  return fract((q.xx + q.yz) * q.zy) * 2.0 - 1.0;
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float a = dot(hash22(i), f);
  float b = dot(hash22(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0));
  float c = dot(hash22(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0));
  float d = dot(hash22(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0));
  return 0.5 + 0.5 * mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
vec3 labToRgb(vec3 lab) {
  float l = lab.x + 0.3963377774 * lab.y + 0.2158037573 * lab.z;
  float m = lab.x - 0.1055613458 * lab.y - 0.0638541728 * lab.z;
  float s = lab.x - 0.0894841775 * lab.y - 1.2914855480 * lab.z;
  l = l * l * l; m = m * m * m; s = s * s * s;
  return vec3(
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
  );
}
vec3 encode(vec3 c) {
  c = clamp(c, 0.0, 1.0);
  return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}
vec4 tone(float t) {
  float x = smoothstep(0.15, 1.0, t) * float(uCount - 1);
  int index = int(floor(x));
  return vec4(mix(uRamp[index], uRamp[min(index + 1, uCount - 1)], fract(x)), smoothstep(0.0, 0.32, t));
}
void main() {
  // Full-field flowing aurora/horizon ASCII density so any spotlight spot reveals rich glyphs
  vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0);
  vec2 q = p / uScale;
  float n1 = noise(q * 1.45 + vec2(0.4, 0.7));
  float n2 = noise(q * 2.60 + vec2(3.1, -1.2));
  float wave = 0.5 + 0.5 * sin(q.x * 1.35 + n1 * 2.4);
  float t = clamp(0.32 + 0.44 * n1 + 0.18 * n2 + 0.12 * wave, 0.22, 0.98);
  vec4 mixed = tone(t);
  vec3 color = encode(labToRgb(mixed.rgb));
  // Wide perimeter vignette ensures spotlight never touches or clips against canvas borders
  float marginX = smoothstep(0.02, 0.12, vUv.x) * smoothstep(0.98, 0.88, vUv.x);
  float marginY = smoothstep(0.03, 0.15, vUv.y) * smoothstep(0.97, 0.85, vUv.y);
  float alpha = mixed.a * marginX * marginY;
  float dither = (hash12(gl_FragCoord.xy + uFrame * 13.7) - 0.5) / 255.0;
  outColor = clamp(vec4(color * alpha + dither * alpha, alpha), 0.0, 1.0);
  outAux = vec4(1.0, 0.0, 0.0, 1.0);
}`;

const GLYPHS = `
uniform sampler2D uField;
uniform sampler2D uAux;
uniform sampler2D uAtlas;
uniform vec2 uResolution;
uniform vec2 uCell;
uniform vec2 uOffset;
uniform vec2 uAtlasGrid;
uniform float uCount;
uniform float uDensity;
uniform float uOpacity;
uniform float uFlicker;
uniform float uDepth;
uniform float uGlyphTime;
uniform float uSeedValue;
uniform float uLight;
${COMMON}
float sampleGlyph(float index, vec2 local, vec2 coord, float soft) {
  float column = mod(index, uAtlasGrid.x);
  float row = floor(index / uAtlasGrid.x);
  vec2 atlasUv = vec2((column + local.x) / uAtlasGrid.x, (row + 1.0 - local.y) / uAtlasGrid.y);
  vec2 continuous = coord / uAtlasGrid;
  float scale = exp2(soft);
  return textureGrad(uAtlas, atlasUv, dFdx(continuous) * scale, dFdy(continuous) * scale).a;
}
vec4 glyphAt(vec2 px) {
  vec2 coord = (px - uOffset) / uCell;
  vec2 cell = floor(coord);
  vec2 local = coord - cell;
  vec2 uv = clamp(((cell + 0.5) * uCell + uOffset) / uResolution, vec2(0.0), vec2(1.0));
  vec4 field = texture(uField, uv);
  vec3 visible = uLight > 0.5 ? field.rgb + (1.0 - field.a) : field.rgb;
  float luma = dot(visible, vec3(0.2126, 0.7152, 0.0722));
  float value = uLight > 0.5 ? clamp((1.0 - luma) * 1.45, 0.0, 1.0) * field.a : luma;
  float pick = hash12(cell + uSeedValue * 7.31);
  float level = hash12(cell * 1.73 + 4.1 + uSeedValue);
  float tick = floor(uGlyphTime * 9.0 + level * 9.0);
  float wobble = (hash12(cell * 2.31 + tick * 17.7) - 0.5) * uFlicker * 0.4 + (level - 0.5) * 0.1;
  float tone = clamp(pow(value, 0.75) + wobble, 0.0, 1.0);
  float index = floor(tone * (uCount - 1.0) + 0.5);
  float present = step(pick, uDensity * mix(1.0, 0.35 + tone * 1.05, 0.5));
  float cutoff = smoothstep(0.04, 0.12, value);
  float focus = step(hash12(cell * 0.71 + 9.2 + uSeedValue), uDepth);
  float coverage = sampleGlyph(index, local, coord, focus * 1.1);
  float alpha = uOpacity * present * cutoff * coverage * mix(1.0, 0.40 + 0.60 * level, 0.55) * (1.0 - focus * 0.45);
  if (uLight < 0.5) {
    vec3 light = field.rgb * 0.65 + vec3(0.06) * field.a;
    return vec4(light * alpha, 0.72 * field.a * alpha);
  }
  vec3 ink = visible * 0.52;
  return vec4(ink * alpha, alpha);
}`;

const HALO = `#version 300 es
precision highp float;
uniform float uDownscale;
in vec2 vUv;
out vec4 outColor;
${GLYPHS}
void main() { outColor = glyphAt(gl_FragCoord.xy * uDownscale); }`;

const BLUR = `#version 300 es
precision highp float;
uniform sampler2D uSource;
uniform vec2 uStep;
in vec2 vUv;
out vec4 outColor;
void main() {
  vec4 sum = texture(uSource, vUv) * 0.2270270270;
  sum += texture(uSource, vUv + uStep * 1.3846153846) * 0.3162162162;
  sum += texture(uSource, vUv - uStep * 1.3846153846) * 0.3162162162;
  sum += texture(uSource, vUv + uStep * 3.2307692308) * 0.0702702703;
  sum += texture(uSource, vUv - uStep * 3.2307692308) * 0.0702702703;
  outColor = sum;
}`;

const COMPOSITE = `#version 300 es
precision highp float;
uniform sampler2D uHalo;
uniform float uGlow;
uniform float uGradient;
uniform float uGrain;
uniform float uFrame;
in vec2 vUv;
out vec4 outColor;
${GLYPHS}
void main() {
  vec4 base = texture(uField, vUv) * uGradient;
  vec4 glyph = glyphAt(gl_FragCoord.xy);
  vec4 halo = texture(uHalo, vUv) * uGlow;
  vec4 color;
  if (uLight < 0.5) {
    color = base + glyph + halo;
  } else {
    color = glyph + base * (1.0 - glyph.a);
    color += halo * 0.55 * (1.0 - color.a);
  }
  float grain = (hash12(gl_FragCoord.xy + uFrame * vec2(17.0, 59.0)) + hash12(gl_FragCoord.xy * 1.31 + uFrame * 7.0) - 1.0) * uGrain;
  float body = clamp(color.a, 0.0, 1.0);
  color.rgb += grain * (0.20 + body) * 0.35 * body;
  color.a = clamp(color.a, 0.0, 1.0);
  color.rgb = clamp(color.rgb, 0.0, color.a);
  outColor = color;
}`;

const toLinear = v => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const toLab = ([r, g, b]) => {
  const lr = toLinear(r), lg = toLinear(g), lb = toLinear(b);
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  ];
};
const hexRgb = h => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  return s;
}
function link(gl, frag) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VERTEX));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(p);
  const u = {};
  const count = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < count; i++) {
    const info = gl.getActiveUniform(p, i);
    const name = info.name.replace(/\[0\]$/, '');
    u[name] = gl.getUniformLocation(p, name);
  }
  return { program: p, uniforms: u };
}
function createTarget(gl, count, width, height) {
  const fb = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  const textures = Array.from({ length: count }, (_, i) => {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0 + i, gl.TEXTURE_2D, tex, 0);
    return tex;
  });
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  return { framebuffer: fb, textures, width, height };
}
function buildAtlas(gl) {
  const list = [...new Set([...CHARACTERS])];
  const columns = Math.min(ATLAS_COLUMNS, list.length);
  const rows = Math.ceil(list.length / columns);
  const c = document.createElement('canvas');
  c.width = ATLAS_CELL_W * columns;
  c.height = ATLAS_CELL_H * rows;
  const ctx = c.getContext('2d');
  ctx.font = `300 ${Math.round(ATLAS_CELL_H * FONT_SCALE)}px ${FONT_FAMILY}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#fff';
  list.forEach((ch, idx) => {
    const col = idx % columns, row = Math.floor(idx / columns);
    ctx.fillText(ch, col * ATLAS_CELL_W + ATLAS_CELL_W / 2, row * ATLAS_CELL_H + ATLAS_CELL_H / 2 + 3);
  });
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, c);
  gl.generateMipmap(gl.TEXTURE_2D);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return { texture: tex, count: list.length, grid: [columns, rows] };
}

document.fonts.ready.then(() => {
  const W = __W__, H = __H__, DPR = __DPR__;
  const canvas = document.getElementById('c');
  canvas.width = W * DPR;
  canvas.height = H * DPR;
  const gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false });
  const field = link(gl, FIELD), halo = link(gl, HALO), blur = link(gl, BLUR), comp = link(gl, COMPOSITE);
  const vao = gl.createVertexArray();
  const fieldTarget = createTarget(gl, 2, Math.round(canvas.width / 2), Math.round(canvas.height / 2));
  const haloA = createTarget(gl, 1, Math.round(canvas.width / 4), Math.round(canvas.height / 4));
  const haloB = createTarget(gl, 1, Math.round(canvas.width / 4), Math.round(canvas.height / 4));
  const atlas = buildAtlas(gl);

  const ramp = new Float32Array(MAX_COLORS * 3);
  COLORS.forEach((col, i) => ramp.set(toLab(hexRgb(col)), i * 3));

  gl.bindVertexArray(vao);
  gl.disable(gl.BLEND);
  gl.bindFramebuffer(gl.FRAMEBUFFER, fieldTarget.framebuffer);
  gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
  gl.viewport(0, 0, fieldTarget.width, fieldTarget.height);
  gl.useProgram(field.program);
  const fu = field.uniforms;
  gl.uniform1f(fu.uAspect, W / H);
  gl.uniform1f(fu.uTime, 1.4);
  gl.uniform3fv(fu.uRamp, ramp);
  gl.uniform1i(fu.uCount, COLORS.length);
  gl.uniform1f(fu.uScale, 1.0);
  gl.uniform1f(fu.uSoftness, 0.8);
  gl.uniform1f(fu.uFlow, 0.5);
  gl.uniform2f(fu.uSeed, 0.0, 0.0);
  gl.uniform1f(fu.uFrame, 7.0);
  gl.drawArrays(gl.TRIANGLES, 0, 3);

  const bindGlyphs = (prog) => {
    const u = prog.uniforms;
    const cellH = 16 * DPR;
    const cellW = cellH * (ATLAS_CELL_W / ATLAS_CELL_H);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, fieldTarget.textures[0]); gl.uniform1i(u.uField, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, fieldTarget.textures[1]); gl.uniform1i(u.uAux, 1);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, atlas.texture); gl.uniform1i(u.uAtlas, 2);
    gl.uniform2f(u.uResolution, canvas.width, canvas.height);
    gl.uniform2f(u.uCell, cellW, cellH);
    gl.uniform2f(u.uOffset, (canvas.width - Math.ceil(canvas.width / cellW) * cellW) / 2, (canvas.height - Math.ceil(canvas.height / cellH) * cellH) / 2);
    gl.uniform2f(u.uAtlasGrid, atlas.grid[0], atlas.grid[1]);
    gl.uniform1f(u.uCount, atlas.count);
    gl.uniform1f(u.uDensity, 0.85);
    gl.uniform1f(u.uOpacity, 0.82);
    gl.uniform1f(u.uFlicker, 0.25);
    gl.uniform1f(u.uDepth, 0.12);
    gl.uniform1f(u.uGlyphTime, 2.2);
    gl.uniform1f(u.uSeedValue, 0.0);
    gl.uniform1f(u.uLight, LIGHT_MODE ? 1.0 : 0.0);
  };

  gl.bindFramebuffer(gl.FRAMEBUFFER, haloA.framebuffer);
  gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
  gl.viewport(0, 0, haloA.width, haloA.height);
  gl.useProgram(halo.program);
  bindGlyphs(halo);
  gl.uniform1f(halo.uniforms.uDownscale, canvas.width / haloA.width);
  gl.drawArrays(gl.TRIANGLES, 0, 3);

  gl.useProgram(blur.program);
  gl.activeTexture(gl.TEXTURE0);
  gl.uniform1i(blur.uniforms.uSource, 0);
  gl.bindFramebuffer(gl.FRAMEBUFFER, haloB.framebuffer);
  gl.bindTexture(gl.TEXTURE_2D, haloA.textures[0]);
  gl.uniform2f(blur.uniforms.uStep, 1 / haloA.width, 0);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.bindFramebuffer(gl.FRAMEBUFFER, haloA.framebuffer);
  gl.bindTexture(gl.TEXTURE_2D, haloB.textures[0]);
  gl.uniform2f(blur.uniforms.uStep, 0, 1 / haloA.height);
  gl.drawArrays(gl.TRIANGLES, 0, 3);

  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.useProgram(comp.program);
  bindGlyphs(comp);
  gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D, haloA.textures[0]);
  gl.uniform1i(comp.uniforms.uHalo, 3);
  gl.uniform1f(comp.uniforms.uGlow, 0.34);
  gl.uniform1f(comp.uniforms.uGradient, LIGHT_MODE ? 0.62 : 0.72);
  gl.uniform1f(comp.uniforms.uGrain, 0.04);
  gl.uniform1f(comp.uniforms.uFrame, 7.0);
  gl.drawArrays(gl.TRIANGLES, 0, 3);

  const out = document.createElement('canvas');
  out.width = canvas.width; out.height = canvas.height;
  out.getContext('2d').drawImage(canvas, 0, 0);

  const img = document.createElement('img');
  img.id = 'result';
  img.src = out.toDataURL('image/png');
  document.body.appendChild(img);
});
</script>
</body>
</html>
"""


def render_gradient_ascii_webp(colors, light_mode=False, width=800, height=250, dpr=1):
    """Run the React Bits WebGL2 GradientASCII shader and return transparent RGBA WebP data URI."""
    geist_b64 = base64.b64encode(GEIST_MONO.read_bytes()).decode()
    html_src = (
        WEBGL_HTML.replace("__GEIST_B64__", geist_b64)
        .replace("__COLORS_JSON__", json.dumps(colors))
        .replace("__LIGHT_MODE__", "true" if light_mode else "false")
        .replace("__W__", str(width))
        .replace("__H__", str(height))
        .replace("__DPR__", str(dpr))
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tf:
        tf.write(html_src)
        tmp_path = tf.name
    try:
        dom = subprocess.check_output(
            [
                "google-chrome",
                "--headless",
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--virtual-time-budget=1200",
                "--dump-dom",
                tmp_path,
            ],
            stderr=subprocess.DEVNULL,
        ).decode()
    finally:
        os.unlink(tmp_path)

    m = re.search(r'<img id="result" src="data:image/png;base64,([^"]+)"', dom)
    if not m:
        raise RuntimeError("WebGL2 GradientASCII render failed in headless Chrome")
    raw_png = base64.b64decode(m.group(1))
    im = Image.open(io.BytesIO(raw_png)).convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=80, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


# Official brand paths fetched from Iconify (simple-icons & bi three-oval mark): (mult_to_24, path_d)
SOCIAL_GLYPHS = {
    "github": (
        1.0,
        "M12 .297c-6.63 0-12 5.373-12 12c0 5.303 3.438 9.8 8.205 11.385c.6.113.82-.258.82-.577"
        "c0-.285-.01-1.04-.015-2.04c-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7"
        "c-1.087-.744.084-.729.084-.729c1.205.084 1.838 1.236 1.838 1.236c1.07 1.835 2.809 1.305 3.495.998"
        "c.108-.776.417-1.305.76-1.605c-2.665-.3-5.466-1.332-5.466-5.93c0-1.31.465-2.38 1.235-3.22"
        "c-.135-.303-.54-1.523.105-3.176c0 0 1.005-.322 3.3 1.23c.96-.267 1.98-.399 3-.405"
        "c1.02.006 2.04.138 3 .405c2.28-1.552 3.285-1.23 3.285-1.23c.645 1.653.24 2.873.12 3.176"
        "c.765.84 1.23 1.91 1.23 3.22c0 4.61-2.805 5.625-5.475 5.92c.42.36.81 1.096.81 2.22"
        "c0 1.606-.015 2.896-.015 3.286c0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297"
        "c0-6.627-5.373-12-12-12",
    ),
    "linkedin": (
        1.0,
        "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037"
        "c-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85"
        "c3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.06 2.06 0 0 1-2.063-2.065"
        "a2.064 2.064 0 1 1 2.063 2.065m1.782 13.019H3.555V9h3.564zM22.225 0H1.771C.792 0 0 .774 0 1.729"
        "v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0z",
    ),
    "youtube": (
        1.0,
        "M23.498 6.186a3.02 3.02 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545"
        "s-7.505 0-9.377.505A3.02 3.02 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814"
        "a3.02 3.02 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505"
        "a3.02 3.02 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814M9.545 15.568V8.432L15.818 12z",
    ),
    "medium": (
        1.5,
        "M9.025 8c0 2.485-2.02 4.5-4.513 4.5A4.506 4.506 0 0 1 0 8"
        "c0-2.486 2.02-4.5 4.512-4.5A4.506 4.506 0 0 1 9.025 8"
        "m4.95 0c0 2.34-1.01 4.236-2.256 4.236S9.463 10.339 9.463 8"
        "c0-2.34 1.01-4.236 2.256-4.236S13.975 5.661 13.975 8"
        "M16 8c0 2.096-.355 3.795-.794 3.795c-.438 0-.793-1.7-.793-3.795"
        "c0-2.096.355-3.795.794-3.795c.438 0 .793 1.699.793 3.795",
    ),
}

SOCIAL_LINKS = {
    "github": ("GitHub", "https://github.com/uzairshahidgithub"),
    "linkedin": ("LinkedIn", "https://www.linkedin.com/in/uzairspace/"),
    "youtube": ("YouTube", "https://www.youtube.com/channel/UC7XHbPdPUP0PbILQcJfFp0w"),
    "medium": ("Medium", "https://medium.com/@iuzdiary"),
}


def build_hero_svg(name="Muhammad Uzair", light_mode=False, width=800, height=250):
    """Build transparent SVG with 2D orbital emerald spotlight transforming Title, Subtitle, & blurry frosted Iconify icons."""
    import html as _html_mod

    colors = LIGHT_COLORS if light_mode else DARK_COLORS
    bg_uri = render_gradient_ascii_webp(colors=colors, light_mode=light_mode, width=width, height=height, dpr=1)
    outfit_b64 = base64.b64encode(OUTFIT_REGULAR.read_bytes()).decode()
    inter_b64 = base64.b64encode(INTER_LIGHT.read_bytes()).decode()

    # Balanced >= 1.5 inline & vertical spacing:
    # Title (74px @ y=96) -> 32px gap (1.52x cap) -> Subtitle (29px @ y=149) -> 34px gap -> Social Icons (22px @ cy=194, 34px=1.55x inline gap)
    cx = width / 2
    cy = 96.0
    sub_y = 149.0
    icon_cy = 194.0
    icon_size = 22.0
    icon_scale = icon_size / 24.0
    icon_xs = {"github": cx - 84.0, "linkedin": cx - 28.0, "youtube": cx + 28.0, "medium": cx + 84.0}

    slot_s = 4.2
    n_prof = len(PROFESSIONS)
    cycle_s = slot_s * n_prof
    slot_pct = 100.0 / n_prof
    p_rise = slot_pct * 0.19
    p_hold = slot_pct * 0.62
    p_exit = slot_pct * 0.76
    p_end = slot_pct * 0.79

    # Dynamic 16s orbital spotlight sweep (translate + rotate + breath) across entire hero canvas
    css = f"""
@font-face{{font-family:'OutfitDisplay';font-style:normal;font-weight:400;
src:url(data:font/woff2;base64,{outfit_b64}) format('woff2');}}
@font-face{{font-family:'InterLight';font-style:normal;font-weight:300;
src:url(data:font/woff2;base64,{inter_b64}) format('woff2');}}
.glass-title{{font-family:'OutfitDisplay',-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',sans-serif;
font-size:74px;font-weight:400;letter-spacing:-0.6px}}
.split-line{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','SF Pro Text','InterLight','Helvetica Neue',system-ui,sans-serif;
font-size:29px;font-weight:300;letter-spacing:-0.25px}}
.split-ch{{will-change:opacity}}
.spot-beam{{transform-origin:{cx:.1f}px {height / 2:.1f}px;animation:cinema-wander 16s ease-in-out infinite}}
.spot-aura{{transform-origin:{cx:.1f}px {height / 2:.1f}px;animation:aura-drift 16s ease-in-out infinite}}
@keyframes cinema-wander{{
  0%,100%{{transform:translate3d(-175px,-24px,0) rotate(-6deg) scale(1.02)}}
  16%{{transform:translate3d(155px,-26px,0) rotate(6deg) scale(1.06)}}
  33%{{transform:translate3d(135px,28px,0) rotate(8deg) scale(0.96)}}
  50%{{transform:translate3d(0px,34px,0) rotate(0deg) scale(1.08)}}
  67%{{transform:translate3d(-150px,28px,0) rotate(-7deg) scale(0.97)}}
  83%{{transform:translate3d(10px,-16px,0) rotate(3deg) scale(1.05)}}
}}
@keyframes aura-drift{{
  0%,100%{{transform:translate3d(110px,18px,0) scale(0.95)}}
  33%{{transform:translate3d(-120px,-12px,0) scale(1.04)}}
  67%{{transform:translate3d(85px,24px,0) scale(1.02)}}
}}
@keyframes split-rise{{
  0%{{opacity:0;baseline-shift:-26px}}
  {p_rise:.2f}%{{opacity:1;baseline-shift:0px}}
  {p_hold:.2f}%{{opacity:1;baseline-shift:0px}}
  {p_exit:.2f}%{{opacity:0;baseline-shift:16px}}
  {p_end:.2f}%,100%{{opacity:0;baseline-shift:-26px}}
}}
@media (prefers-reduced-motion:reduce){{
  .spot-beam,.spot-aura{{animation:none!important;transform:translate3d(0,0,0)}}
  .split-ch{{animation:none!important;opacity:0;baseline-shift:0px}}
  .split-line[data-idx="0"] .split-ch{{opacity:1!important}}
}}
"""

    if light_mode:
        shadow_color = "#116329"
        shadow_op = "0.14"
        fill_stops = (
            '<stop offset="0%" stop-color="#0d4423" stop-opacity="0.54" />'
            '<stop offset="46%" stop-color="#1a7f37" stop-opacity="0.38" />'
            '<stop offset="53%" stop-color="#116329" stop-opacity="0.44" />'
            '<stop offset="100%" stop-color="#0d4423" stop-opacity="0.58" />'
        )
        spot_fill_stops = (
            '<stop offset="0%" stop-color="#0a361b" stop-opacity="0.52" />'
            '<stop offset="50%" stop-color="#1a7f37" stop-opacity="0.38" />'
            '<stop offset="100%" stop-color="#2da44e" stop-opacity="0.48" />'
        )
        rim_stops = (
            '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.52" />'
            '<stop offset="45%" stop-color="#4ac26b" stop-opacity="0.34" />'
            '<stop offset="100%" stop-color="#1a7f37" stop-opacity="0.42" />'
        )
        spot_rim_stops = (
            '<stop offset="0%" stop-color="#0d4423" stop-opacity="0.92" />'
            '<stop offset="50%" stop-color="#1a7f37" stop-opacity="0.96" />'
            '<stop offset="100%" stop-color="#2da44e" stop-opacity="0.90" />'
        )
        # Clear, visible simple frosted graphite icons with translucent mist + green shift when light lands
        soc_rest_stops = (
            '<stop offset="0%" stop-color="#24292f" stop-opacity="0.78" />'
            '<stop offset="100%" stop-color="#475569" stop-opacity="0.68" />'
        )
        soc_frost_halo = "#64748b"
        soc_halo_op = "0.26"
        soc_spot_tint = (
            '<stop offset="0%" stop-color="#0d4423" stop-opacity="0.72" />'
            '<stop offset="100%" stop-color="#16a34a" stop-opacity="0.64" />'
        )
        soc_spot_halo = "#22c55e"
        glint_top = "0.42"
        sub_color = "#116329"
        sub_op = "0.66"
        sub_spot_color = "#052e16"
        sub_spot_glow_col = "#4ade80"
        refract_slope, refract_int = "0.96", "0.02"
        beam_tint_op = "0.26"
        aura_tint_op = "0.10"
    else:
        shadow_color = "#041009"
        shadow_op = "0.52"
        fill_stops = (
            '<stop offset="0%" stop-color="#f0fdf4" stop-opacity="0.36" />'
            '<stop offset="46%" stop-color="#aff5b4" stop-opacity="0.16" />'
            '<stop offset="53%" stop-color="#3fb950" stop-opacity="0.10" />'
            '<stop offset="100%" stop-color="#f0fdf4" stop-opacity="0.30" />'
        )
        spot_fill_stops = (
            '<stop offset="0%" stop-color="#d2fedb" stop-opacity="0.48" />'
            '<stop offset="50%" stop-color="#56d364" stop-opacity="0.36" />'
            '<stop offset="100%" stop-color="#3fb950" stop-opacity="0.44" />'
        )
        rim_stops = (
            '<stop offset="0%" stop-color="#f0fdf4" stop-opacity="0.54" />'
            '<stop offset="42%" stop-color="#aff5b4" stop-opacity="0.30" />'
            '<stop offset="75%" stop-color="#3fb950" stop-opacity="0.34" />'
            '<stop offset="100%" stop-color="#f0fdf4" stop-opacity="0.50" />'
        )
        spot_rim_stops = (
            '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.98" />'
            '<stop offset="50%" stop-color="#aff5b4" stop-opacity="0.94" />'
            '<stop offset="100%" stop-color="#56d364" stop-opacity="0.90" />'
        )
        # Simple frosted pearl-silver color @ ~0.74 opacity: always clearly visible with blurry frosted aura
        soc_rest_stops = (
            '<stop offset="0%" stop-color="#f0f6fc" stop-opacity="0.78" />'
            '<stop offset="100%" stop-color="#cbd5e1" stop-opacity="0.64" />'
        )
        soc_frost_halo = "#e2e8f0"
        soc_halo_op = "0.24"
        soc_spot_tint = (
            '<stop offset="0%" stop-color="#d2fedb" stop-opacity="0.72" />'
            '<stop offset="100%" stop-color="#4ade80" stop-opacity="0.62" />'
        )
        soc_spot_halo = "#4ade80"
        glint_top = "0.66"
        sub_color = "#d2fedb"
        sub_op = "0.60"
        sub_spot_color = "#f0fdf4"
        sub_spot_glow_col = "#3fb950"
        refract_slope, refract_int = "1.46", "0.10"
        beam_tint_op = "0.22"
        aura_tint_op = "0.09"

    def _build_split_nodes(fill_hex, fill_opacity):
        nodes = []
        char_stagger_s = 0.036
        initial_offset_s = -1.75
        for idx_p, phrase in enumerate(PROFESSIONS):
            tspans = []
            for i, ch in enumerate(phrase):
                delay_s = ((idx_p * slot_s + initial_offset_s + i * char_stagger_s) % cycle_s) - cycle_s
                tspans.append(
                    f'<tspan class="split-ch" '
                    f'style="animation:split-rise {cycle_s:.2f}s cubic-bezier(0.22,1,0.36,1) {delay_s:.3f}s infinite">'
                    f'{_html_mod.escape(ch)}</tspan>'
                )
            nodes.append(
                f'<text class="split-line" data-idx="{idx_p}" xml:space="preserve" x="{cx:.1f}" y="{sub_y:.1f}" '
                f'text-anchor="middle" fill="{fill_hex}" fill-opacity="{fill_opacity}" aria-label="{_html_mod.escape(phrase)}">'
                f'{"".join(tspans)}</text>'
            )
        return "".join(nodes)

    split_rest_xml = _build_split_nodes(sub_color, sub_op)
    split_lit_xml = _build_split_nodes(sub_spot_color, "0.98")

    soc_clip_paths = []
    soc_mask_cutouts = []
    soc_blur_halos = []
    soc_spot_halos = []
    soc_base_rims = []
    soc_spot_rims = []
    for kind, ix in icon_xs.items():
        label, url = SOCIAL_LINKS[kind]
        tx = ix - icon_size / 2.0
        ty = icon_cy - icon_size / 2.0
        mult, d_str = SOCIAL_GLYPHS[kind]
        xform = f'translate({tx:.2f},{ty:.2f}) scale({icon_scale * mult:.4f})'
        soc_clip_paths.append(f'<path transform="{xform}" d="{d_str}" />')
        soc_mask_cutouts.append(f'<path transform="{xform}" d="{d_str}" fill="#000000" />')
        soc_blur_halos.append(
            f'<path transform="{xform}" d="{d_str}" fill="{soc_frost_halo}" fill-opacity="{soc_halo_op}" />'
        )
        soc_spot_halos.append(
            f'<path transform="{xform}" d="{d_str}" fill="{soc_spot_halo}" fill-opacity="0.48" />'
        )
        soc_base_rims.append(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" aria-label="{label} Profile">'
            f'<title>{label} — Muhammad Uzair (@uzairshahidgithub)</title>'
            f'<path transform="{xform}" d="{d_str}" fill="none" '
            f'stroke="url(#duo-rim)" stroke-width="{1.25 / mult:.3f}" stroke-linejoin="round" /></a>'
        )
        soc_spot_rims.append(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" aria-label="{label} Profile">'
            f'<title>{label} — Muhammad Uzair (@uzairshahidgithub)</title>'
            f'<path transform="{xform}" d="{d_str}" fill="none" stroke="url(#spot-rim)" '
            f'stroke-width="{1.65 / mult:.3f}" stroke-linejoin="round" /></a>'
        )

    seo_desc = (
        f"{name} (@uzairshahidgithub) — Cyber Security Engineer, Security Researcher, "
        "Open Source Developer, Self Designer, DevSecOps, Linux System Administration, "
        "and AI Automation Engineer."
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{name} — Interactive Profile Header">
<title>{name} (@uzairshahidgithub)</title>
<desc>{_html_mod.escape(seo_desc)}</desc>
<metadata>
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <rdf:Description rdf:about="https://github.com/uzairshahidgithub">
      <dc:title>{name} — Cyber Security Engineer &amp; AI Automation Engineer</dc:title>
      <dc:creator>{name} (uzairshahidgithub)</dc:creator>
      <dc:description>{_html_mod.escape(seo_desc)}</dc:description>
      <dc:subject>Cyber Security Engineer, Security Researcher, DevSecOps, Linux System Administration, AI Automation Engineer, Open Source Developer</dc:subject>
    </rdf:Description>
  </rdf:RDF>
</metadata>
<defs>
  <style>{css}</style>
  <clipPath id="title-clip">
    <text class="glass-title" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle">{name}</text>
  </clipPath>
  <clipPath id="soc-clip">
    {"".join(soc_clip_paths)}
  </clipPath>
  <clipPath id="split-clip">
    <rect x="0" y="{sub_y - 31:.1f}" width="{width}" height="44" />
  </clipPath>

  <!-- Outer-contour-only rim masks hide variable-font internal overlap seams on Outfit glyphs -->
  <mask id="title-rim-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
    <text class="glass-title" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" fill="#000000">{name}</text>
  </mask>
  <mask id="soc-rim-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
    {"".join(soc_mask_cutouts)}
  </mask>

  <!-- Cinema hall spotlight falloff: purely soft radial light strictly inside canvas borders -->
  <radialGradient id="spot-mask-grad" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="1.0" />
    <stop offset="44%" stop-color="#ebebeb" stop-opacity="0.92" />
    <stop offset="76%" stop-color="#686868" stop-opacity="0.42" />
    <stop offset="100%" stop-color="#000000" stop-opacity="0.0" />
  </radialGradient>
  <filter id="spot-blur" x="-30%" y="-40%" width="160%" height="180%">
    <feGaussianBlur stdDeviation="12" />
  </filter>

  <!-- Smooth outer perimeter vignette fade (prevents any border cutoff line even during extreme orbital travel) -->
  <radialGradient id="border-safe-fade" cx="50%" cy="50%" r="50%">
    <stop offset="56%" stop-color="#ffffff" stop-opacity="1.0" />
    <stop offset="82%" stop-color="#909090" stop-opacity="0.48" />
    <stop offset="97%" stop-color="#000000" stop-opacity="0.0" />
    <stop offset="100%" stop-color="#000000" stop-opacity="0.0" />
  </radialGradient>
  <mask id="perimeter-safe" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">
    <rect x="0" y="0" width="{width}" height="{height}" fill="url(#border-safe-fade)" />
  </mask>

  <!-- Only inside this orbital spotlight mask do ASCII glyphs, green light catch & specular rim flare appear -->
  <mask id="cinema-spot" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#000000" />
    <g class="spot-beam">
      <ellipse cx="{cx:.1f}" cy="{height / 2:.1f}" rx="172" ry="62"
               fill="url(#spot-mask-grad)" filter="url(#spot-blur)" />
    </g>
  </mask>

  <!-- Dual atmospheric emerald glow layers moving dynamically across environment -->
  <radialGradient id="beam-glow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{colors[3]}" stop-opacity="{beam_tint_op}" />
    <stop offset="52%" stop-color="{colors[1]}" stop-opacity="0.10" />
    <stop offset="100%" stop-color="{colors[0]}" stop-opacity="0.0" />
  </radialGradient>
  <radialGradient id="aura-glow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{colors[2]}" stop-opacity="{aura_tint_op}" />
    <stop offset="65%" stop-color="{colors[0]}" stop-opacity="0.03" />
    <stop offset="100%" stop-color="{colors[0]}" stop-opacity="0.0" />
  </radialGradient>

  <!-- Optical backdrop refraction inside Liquid Glass title & social icons -->
  <filter id="glass-refract" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="5.5" result="blur" />
    <feComponentTransfer in="blur" result="lifted">
      <feFuncR type="linear" slope="{refract_slope}" intercept="{refract_int}" />
      <feFuncG type="linear" slope="{refract_slope}" intercept="{refract_int}" />
      <feFuncB type="linear" slope="{refract_slope}" intercept="{refract_int}" />
    </feComponentTransfer>
  </filter>

  <!-- Blurry frosted aura filters for simple-color translucent social icons & illuminated subtitle -->
  <filter id="frosted-halo" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="4.0" />
  </filter>
  <filter id="spot-halo" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="5.2" />
  </filter>
  <filter id="sub-spot-glow" x="-10%" y="-40%" width="120%" height="180%">
    <feDropShadow dx="0" dy="0" stdDeviation="3.5" flood-color="{sub_spot_glow_col}" flood-opacity="0.55" />
  </filter>

  <!-- Soft elevation shadow -->
  <filter id="title-shadow" x="-15%" y="-25%" width="130%" height="150%">
    <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="{shadow_color}" flood-opacity="{shadow_op}" />
  </filter>

  <linearGradient id="duo-fill" x1="0%" y1="0%" x2="0%" y2="100%">{fill_stops}</linearGradient>
  <linearGradient id="spot-catch-fill" x1="0%" y1="0%" x2="0%" y2="100%">{spot_fill_stops}</linearGradient>
  <linearGradient id="duo-rim" x1="0%" y1="0%" x2="100%" y2="100%">{rim_stops}</linearGradient>
  <linearGradient id="spot-rim" x1="0%" y1="0%" x2="100%" y2="100%">{spot_rim_stops}</linearGradient>
  <linearGradient id="soc-rest-fill" x1="0%" y1="0%" x2="0%" y2="100%">{soc_rest_stops}</linearGradient>
  <linearGradient id="soc-spot-tint" x1="0%" y1="0%" x2="0%" y2="100%">{soc_spot_tint}</linearGradient>

  <linearGradient id="top-glint" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="{glint_top}" />
    <stop offset="38%" stop-color="#f0fdf4" stop-opacity="0.10" />
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0.00" />
  </linearGradient>
</defs>

<!-- Orbital Cinema Spotlight + secondary emerald ambient drift strictly inside perimeter-safe fade -->
<g mask="url(#perimeter-safe)">
  <g class="spot-aura">
    <ellipse cx="{cx:.1f}" cy="{height / 2:.1f}" rx="215" ry="72" fill="url(#aura-glow)" />
  </g>
  <g mask="url(#cinema-spot)">
    <g class="spot-beam">
      <ellipse cx="{cx:.1f}" cy="{height / 2:.1f}" rx="172" ry="62" fill="url(#beam-glow)" />
    </g>
    <image href="{bg_uri}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice" />
  </g>
</g>

<!-- Anchored iPhone Duo Liquid Glass Name (clean outer glass rim + spotlight refraction & light catch) -->
<g filter="url(#title-shadow)">
  <g clip-path="url(#title-clip)">
    <rect x="0" y="0" width="{width}" height="{height}" fill="url(#duo-fill)" />
    <g mask="url(#cinema-spot)">
      <image href="{bg_uri}" x="-16" y="-8" width="{width + 32}" height="{height + 16}"
             preserveAspectRatio="xMidYMid slice" filter="url(#glass-refract)" />
      <rect x="0" y="0" width="{width}" height="{height}" fill="url(#spot-catch-fill)" />
      <rect x="0" y="{cy - 58:.1f}" width="{width}" height="40" fill="url(#top-glint)" />
    </g>
  </g>
  <text class="glass-title" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle"
        fill="none" stroke="url(#duo-rim)" stroke-width="1.8" stroke-linejoin="round"
        mask="url(#title-rim-mask)">{name}</text>
  <g mask="url(#cinema-spot)">
    <text class="glass-title" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle"
          fill="none" stroke="url(#spot-rim)" stroke-width="2.1" stroke-linejoin="round"
          mask="url(#title-rim-mask)">{name}</text>
  </g>
</g>

<!-- Animated rotating React Bits SplitText profession subtitle reacting dynamically to moving spotlight -->
<g clip-path="url(#split-clip)" aria-label="Professions: {", ".join(PROFESSIONS)}">
  <g>{split_rest_xml}</g>
  <g mask="url(#cinema-spot)" filter="url(#sub-spot-glow)">{split_lit_xml}</g>
</g>

<!-- Official Iconify social icons: clearly visible simple translucent color + blurry frosted halo + spotlight light catch -->
<g filter="url(#title-shadow)">
  <!-- Blurry frosted diffused backing shapes -->
  <g filter="url(#frosted-halo)">
    {"".join(soc_blur_halos)}
  </g>
  <g mask="url(#cinema-spot)" filter="url(#spot-halo)">
    {"".join(soc_spot_halos)}
  </g>
  <!-- Crisp translucent simple-color frosted fill + spotlight refraction & emerald glow -->
  <g clip-path="url(#soc-clip)">
    <rect x="0" y="{icon_cy - 12:.1f}" width="{width}" height="24" fill="url(#soc-rest-fill)" />
    <rect x="0" y="{icon_cy - 11.5:.1f}" width="{width}" height="10" fill="url(#top-glint)" fill-opacity="0.45" />
    <g mask="url(#cinema-spot)">
      <image href="{bg_uri}" x="-16" y="-8" width="{width + 32}" height="{height + 16}"
             preserveAspectRatio="xMidYMid slice" filter="url(#glass-refract)" />
      <rect x="0" y="{icon_cy - 12:.1f}" width="{width}" height="24" fill="url(#soc-spot-tint)" />
      <rect x="0" y="{icon_cy - 11.5:.1f}" width="{width}" height="10" fill="url(#top-glint)" />
    </g>
  </g>
  <!-- Outer frosted contour rim + interactive links -->
  <g mask="url(#soc-rim-mask)">
    {"".join(soc_base_rims)}
  </g>
  <g mask="url(#cinema-spot)">
    <g mask="url(#soc-rim-mask)">
      {"".join(soc_spot_rims)}
    </g>
  </g>
</g>
</svg>
"""
    return svg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Muhammad Uzair")
    ap.add_argument("--out-dir", default="assets")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for light, suffix in ((False, ""), (True, "-light")):
        hero_svg = build_hero_svg(name=args.name, light_mode=light)
        hp = out_dir / f"hero-header{suffix}.svg"
        hp.write_text(hero_svg, encoding="utf-8")
        print(f"wrote {hp}: {len(hero_svg) // 1024} KB")


if __name__ == "__main__":
    main()
