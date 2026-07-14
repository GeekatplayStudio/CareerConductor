"""Shared visual layer for the control panel: dark glassmorphism theme, gradient
hero, glass metric cards, and a self-contained 3D agent-network animation.

DESIGN NOTES (for readers):
- Everything is self-contained — no CDN fonts, no external JS libraries. The 3D
  network is ~100 lines of vanilla canvas code doing its own perspective
  projection, so the app works fully offline and nothing can break when a CDN
  changes.
- Streamlit widgets can't be wrapped in arbitrary HTML, so the theme works by
  styling Streamlit's own containers via their stable data-testid hooks:
  metrics become tilting glass cards, expanders become "sliding sheets" with a
  3D hover lift, buttons get gradient + glow. Pages opt in with one call:
  apply_theme().
- The network component doubles as a status display: `active=True` (used while
  the pipeline runs) speeds rotation and multiplies the signal pulses flowing
  between nodes — the same visual, calm on the dashboard, busy while working.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

ACCENT = "#22d3ee"        # cyan — primary accent
ACCENT_2 = "#a78bfa"      # violet — secondary accent

_GLOBAL_CSS = """
<style>
/* ---------- canvas: deep space gradient instead of flat gray ---------- */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1100px 500px at 85% -10%, rgba(167,139,250,.14), transparent 60%),
    radial-gradient(900px 450px at -10% 15%, rgba(34,211,238,.12), transparent 55%),
    linear-gradient(180deg, #0b1020 0%, #0d1226 55%, #0b0f1e 100%);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(15,20,40,.92), rgba(11,15,30,.96));
  border-right: 1px solid rgba(148,163,184,.12);
  backdrop-filter: blur(12px);
}

/* ---------- typography ---------- */
h1, h2, h3 { letter-spacing: -0.02em; }
h2 {
  background: linear-gradient(90deg, #e2e8f0, #94a3b8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

/* ---------- glass metric cards with 3D hover tilt ---------- */
[data-testid="stMetric"] {
  background: linear-gradient(145deg, rgba(30,41,66,.65), rgba(17,24,44,.65));
  border: 1px solid rgba(148,163,184,.16);
  border-radius: 16px;
  padding: 14px 18px;
  backdrop-filter: blur(10px);
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
  transform-style: preserve-3d;
}
[data-testid="stMetric"]:hover {
  transform: perspective(700px) rotateX(4deg) translateY(-4px);
  border-color: rgba(34,211,238,.45);
  box-shadow: 0 18px 40px -18px rgba(34,211,238,.35);
}
[data-testid="stMetricValue"] { color: #22d3ee; }

/* ---------- expanders as 3D sliding sheets ---------- */
[data-testid="stExpander"] {
  background: linear-gradient(150deg, rgba(30,41,66,.55), rgba(15,21,40,.6));
  border: 1px solid rgba(148,163,184,.15) !important;
  border-radius: 14px;
  backdrop-filter: blur(8px);
  transition: transform .3s ease, box-shadow .3s ease, border-color .3s ease;
}
[data-testid="stExpander"]:hover {
  transform: perspective(900px) rotateX(2.5deg) translateY(-3px);
  border-color: rgba(167,139,250,.4) !important;
  box-shadow: 0 22px 44px -20px rgba(167,139,250,.35);
}

/* ---------- buttons: gradient + glow ---------- */
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
  background: linear-gradient(90deg, #0891b2, #7c3aed);
  border: 0; border-radius: 10px;
  box-shadow: 0 8px 22px -10px rgba(34,211,238,.55);
  transition: transform .2s ease, box-shadow .2s ease;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px -10px rgba(124,58,237,.6);
}
.stButton > button { border-radius: 10px; }

/* ---------- dataframes / editors: glass panels ---------- */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  border: 1px solid rgba(148,163,184,.15);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 16px 40px -24px rgba(0,0,0,.7);
}

/* ---------- sliders: accent track ---------- */
[data-testid="stSlider"] [role="slider"] {
  background: #22d3ee;
  box-shadow: 0 0 0 4px rgba(34,211,238,.25), 0 0 14px rgba(34,211,238,.7);
}

/* ---------- inputs ---------- */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background: rgba(15,21,40,.7);
  border-radius: 10px;
}
</style>
"""


def apply_theme() -> None:
    """Inject the global look. Call once per page, right after set_page_config."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    """Gradient headline block used at the top of pages."""
    st.markdown(
        f"""
        <div style="padding:6px 0 2px 0;">
          <div style="font-size:2.6rem;font-weight:800;letter-spacing:-0.03em;line-height:1.1;
                      background:linear-gradient(90deg,#22d3ee 0%,#a78bfa 55%,#f0abfc 100%);
                      -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            {title}</div>
          <div style="color:#94a3b8;font-size:1.02rem;margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def agent_network(height: int = 240, active: bool = False, label: str = "") -> None:
    """Animated 3D network: nodes on a slowly rotating sphere-ish cloud, edges
    between near neighbors, and signal pulses traveling along edges.

    Pure vanilla canvas — the 3D is a hand-rolled perspective projection
    (rotate points around Y, divide x/y by depth). `active` cranks rotation
    speed and pulse density so the same component reads "idle dashboard" or
    "agents working right now".
    """
    config = json.dumps({"active": bool(active), "label": label})
    components.html(
        """
<div style="position:relative;width:100%;height:100%;">
<canvas id="net" style="width:100%;height:100%;display:block;"></canvas>
<div id="lbl" style="position:absolute;left:16px;bottom:12px;font-family:ui-sans-serif,system-ui;
     font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:#67e8f9;opacity:.85;"></div>
</div>
<script>
const CFG = """ + config + """;
const canvas = document.getElementById('net');
const ctx = canvas.getContext('2d');
document.getElementById('lbl').textContent = CFG.label;
function fit() {
  canvas.width = canvas.clientWidth * devicePixelRatio;
  canvas.height = canvas.clientHeight * devicePixelRatio;
}
fit(); addEventListener('resize', fit);

// --- 3D point cloud -------------------------------------------------------
const N = 46, R = 190;
const pts = [];
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647; // deterministic
for (let i = 0; i < N; i++) {
  // spherical-ish shell with jitter -> looks organic, keeps nodes spread out
  const th = rnd() * Math.PI * 2, ph = Math.acos(2 * rnd() - 1);
  const r = R * (0.55 + 0.45 * rnd());
  pts.push({ x: r*Math.sin(ph)*Math.cos(th), y: r*Math.cos(ph)*0.62, z: r*Math.sin(ph)*Math.sin(th) });
}
// edges join near neighbors once, up front
const edges = [];
for (let i = 0; i < N; i++) for (let j = i+1; j < N; j++) {
  const dx = pts[i].x-pts[j].x, dy = pts[i].y-pts[j].y, dz = pts[i].z-pts[j].z;
  if (Math.hypot(dx,dy,dz) < R*0.62) edges.push([i,j]);
}
// signal pulses travel edge->edge
const PULSES = CFG.active ? 26 : 9;
const pulses = Array.from({length: PULSES}, () => ({ e: (edges.length*rnd())|0, t: rnd(), v: 0.004 + rnd()*0.012 }));

let a = 0;
function project(p, W, H) {
  const ca = Math.cos(a), sa = Math.sin(a);
  const x = p.x*ca - p.z*sa, z = p.x*sa + p.z*ca;
  const s = 620 / (620 + z + 260);            // perspective divide
  return { X: W/2 + x*s*devicePixelRatio, Y: H/2 + p.y*s*devicePixelRatio, s, z };
}
function frame() {
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0,0,W,H);
  a += CFG.active ? 0.0065 : 0.0022;
  const pr = pts.map(p => project(p, W, H));

  for (const [i,j] of edges) {                 // edges, depth-faded
    const A = pr[i], B = pr[j];
    const alpha = 0.05 + 0.16 * Math.min(A.s, B.s);
    ctx.strokeStyle = `rgba(103,232,249,${alpha})`;
    ctx.lineWidth = devicePixelRatio * 0.7;
    ctx.beginPath(); ctx.moveTo(A.X, A.Y); ctx.lineTo(B.X, B.Y); ctx.stroke();
  }
  for (const p of pulses) {                    // traveling signals with glow
    p.t += p.v * (CFG.active ? 1.8 : 1);
    if (p.t >= 1) { p.t = 0; p.e = (Math.random()*edges.length)|0; }
    const [i,j] = edges[p.e], A = pr[i], B = pr[j];
    const X = A.X + (B.X-A.X)*p.t, Y = A.Y + (B.Y-A.Y)*p.t;
    const g = ctx.createRadialGradient(X,Y,0,X,Y,9*devicePixelRatio);
    g.addColorStop(0,'rgba(240,171,252,.95)'); g.addColorStop(1,'rgba(167,139,250,0)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(X,Y,9*devicePixelRatio,0,7); ctx.fill();
  }
  for (const P of pr) {                        // nodes, sized by depth
    const rad = (1.6 + 2.6*P.s) * devicePixelRatio;
    ctx.fillStyle = `rgba(34,211,238,${0.35+0.6*P.s})`;
    ctx.beginPath(); ctx.arc(P.X,P.Y,rad,0,7); ctx.fill();
  }
  requestAnimationFrame(frame);
}
frame();
</script>
        """,
        height=height,
    )
