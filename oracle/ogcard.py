"""Build the social share card (og-card.svg) from the live Then & Now payload.

Pure stdlib: this emits an SVG string whose headline is the current projected
peak date and whose chart is the real root roll-up curve (dot-com reference vs
the AI era, on the shared progress axis). The nightly build rasterizes the SVG
to og-image.png (rsvg-convert), so the shared card always matches the site's
current default projection.

Font stack is Arial / Liberation Sans (metric-compatible) so the browser render
and the CI rsvg render look the same across machines.
"""

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_FONT = "Arial, 'Liberation Sans', 'DejaVu Sans', sans-serif"

# chart plot box (within the 1200x630 card)
_PX0, _PX1 = 612.0, 1150.0
_PY0, _PY1 = 470.0, 152.0         # y for IMIN (bottom) and IMAX (top)
_PROG_MAX = 160.0                 # progress axis span (dot-com runs to ~156%)
_IMIN, _IMAX = -0.15, 1.10        # intensity axis span


def _fmt_nice(iso):
    if not iso or len(iso) < 10:
        return "—"
    return f"{_MON[int(iso[5:7]) - 1]} {int(iso[8:10])}, {iso[:4]}"


def _x(p):
    return round(_PX0 + (p / _PROG_MAX) * (_PX1 - _PX0), 1)


def _y(i):
    return round(_PY0 - ((i - _IMIN) / (_IMAX - _IMIN)) * (_PY0 - _PY1), 1)


def _poly(progs, ints, step=1):
    pts = []
    for k in range(0, len(progs), step):
        pts.append(f"{_x(progs[k])},{_y(ints[k])}")
    # always include the final point so the line reaches today / the bottom
    last = f"{_x(progs[-1])},{_y(ints[-1])}"
    if pts[-1] != last:
        pts.append(last)
    return " ".join(pts)


def build_svg(payload):
    root = payload["tree"]
    idot, iai = root.get("intensityDot") or [], root.get("intensityAi") or []
    pdot, pai = payload["progDot"], payload["progAi"]
    date = _fmt_nice(payload.get("headlineDate"))

    dot_line = _poly(pdot, idot)
    ai_line = _poly(pai, iai)
    base_y = _y(0.0)

    # peak of the dot-com reference (the 2000 top) and today's AI point
    pk = max(range(len(idot)), key=lambda k: idot[k]) if idot else 0
    pkx, pky = _x(pdot[pk]), _y(idot[pk])
    aix, aiy = (_x(pai[-1]), _y(iai[-1])) if iai else (pkx, base_y)

    return f'''<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg" font-family="{_FONT}">
  <defs>
    <radialGradient id="glow" cx="70%" cy="16%" r="60%">
      <stop offset="0" stop-color="#57a6ff" stop-opacity="0.14"/><stop offset="1" stop-color="#57a6ff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="#0a0d13"/>
  <rect width="1200" height="630" fill="url(#glow)"/>

  <!-- brand -->
  <rect x="64" y="42" width="44" height="44" rx="10" fill="#eef1f6"/>
  <text x="86" y="73" text-anchor="middle" font-size="21" font-weight="800" fill="#0a0d13" letter-spacing="-0.5">AI</text>
  <text x="120" y="72" font-size="26" font-weight="700" fill="#eef1f6" letter-spacing="-0.3">Bubble Oracle</text>

  <!-- headline: the live projected peak -->
  <text x="65" y="168" font-size="16" font-weight="700" fill="#57a6ff" letter-spacing="3">PROJECTED PEAK</text>
  <text x="63" y="232" font-size="52" font-weight="800" fill="#eef1f6" letter-spacing="-1.2">AI Bubble Bursts</text>
  <text x="62" y="304" font-size="62" font-weight="800" fill="#ff5a44" letter-spacing="-1.6">{date}</text>
  <text x="64" y="356" font-size="22" font-weight="400" fill="#9aa4b3">The AI boom, on the dot-com bubble's clock.</text>

  <!-- call to action -->
  <rect x="64" y="392" width="266" height="46" rx="23" fill="#122a45" stroke="#57a6ff" stroke-opacity="0.55" stroke-width="1.5"/>
  <text x="197" y="421" text-anchor="middle" font-size="18.5" font-weight="700" fill="#8fc0ff">See where we are now  &#8594;</text>

  <!-- footer -->
  <circle cx="68" cy="574" r="4" fill="#57a6ff"/>
  <text x="84" y="580" font-size="20" font-weight="600" fill="#eef1f6">aibubbleoracle.com</text>

  <!-- chart: real root roll-up (dot-com reference vs AI era, progress axis) -->
  <line x1="{_PX0}" y1="{base_y}" x2="{_PX1}" y2="{base_y}" stroke="#242c39" stroke-width="1.5"/>
  <polyline points="{dot_line}" fill="none" stroke="#8b93a3" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  <polyline points="{ai_line}" fill="none" stroke="#57a6ff" stroke-width="3.6" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M{aix},{aiy} L{pkx},{pky}" fill="none" stroke="#57a6ff" stroke-width="2.6" stroke-dasharray="2 7" stroke-linecap="round" stroke-opacity="0.75"/>
  <circle cx="{aix}" cy="{aiy}" r="7" fill="#57a6ff"/>
  <circle cx="{pkx}" cy="{pky}" r="14" fill="none" stroke="#ff5a44" stroke-opacity="0.35" stroke-width="2"/>
  <circle cx="{pkx}" cy="{pky}" r="8" fill="#ff5a44"/>

  <!-- legend -->
  <g font-size="15.5" font-weight="600">
    <line x1="628" y1="184" x2="656" y2="184" stroke="#8b93a3" stroke-width="3" stroke-linecap="round"/>
    <text x="664" y="189" fill="#b8c0cd">Dot-com  1995&#8211;2000</text>
    <line x1="628" y1="212" x2="656" y2="212" stroke="#57a6ff" stroke-width="3.6" stroke-linecap="round"/>
    <text x="664" y="217" fill="#8fc0ff">AI era  2022&#8211;now</text>
  </g>
</svg>
'''
