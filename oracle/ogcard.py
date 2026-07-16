"""Build the social share card (og-card.svg) from the live Then & Now payload.

Pure stdlib: this emits an SVG string whose headline is the current projected
peak date and whose chart is the real root roll-up. The dot-com reference arc
is grey; the AI era is blue and is mapped onto the dot-com clock so it meets
the grey curve at TODAY (today's AI level equals its equivalent point on the
dot-com climb). A red dashed line marks the PEAK; TODAY is a cool white line.
The two warm accents (the red date and the red peak line) pull the eye from
the headline to the peak.

The nightly build rasterizes the SVG to og-image.png (rsvg-convert), so the
shared card always matches the site's current default projection. Font stack
is Arial / Liberation Sans (metric-compatible) so the browser render and the
CI rsvg render look the same across machines.
"""

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_FONT = "Arial, 'Liberation Sans', 'DejaVu Sans', sans-serif"

# big chart plot box (fills most of the 1200x630 card; heading overlays the
# empty top-left sky above the low left flank of the curve)
_PX0, _PX1 = 60.0, 1152.0
_PY0, _PY1 = 560.0, 150.0          # y for IMIN (bottom) and IMAX (top)
_PROG_MAX = 158.0                  # progress axis span (dot-com runs to ~156%)
_IMIN, _IMAX = -0.15, 1.12         # intensity axis span


def _fmt_nice(iso):
    if not iso or len(iso) < 10:
        return "—"
    return f"{_MON[int(iso[5:7]) - 1]} {int(iso[8:10])}, {iso[:4]}"


def _x(p):
    return round(_PX0 + (p / _PROG_MAX) * (_PX1 - _PX0), 1)


def _y(i):
    return round(_PY0 - ((i - _IMIN) / (_IMAX - _IMIN)) * (_PY0 - _PY1), 1)


def build_svg(payload):
    root = payload["tree"]
    idot, iai = root.get("intensityDot") or [], root.get("intensityAi") or []
    pdot, pai = payload["progDot"], payload["progAi"]
    date = _fmt_nice(payload.get("headlineDate"))

    # TODAY sits where today's AI level meets the dot-com climb (the engine's
    # equivalent point); map the AI line's x onto [0, equivProg] so it lands
    # on the grey curve there.
    eq = root.get("equiv") or {}
    equiv_prog = eq.get("progress")
    if equiv_prog is None:
        equiv_prog = pai[-1] if pai else 70.0
    ai_last = pai[-1] if pai else 1.0
    today_int = iai[-1] if iai else (eq.get("intensity") or 0.0)

    grey = " ".join(f"{_x(pdot[k])},{_y(idot[k])}" for k in range(len(idot)))
    blue = " ".join(f"{_x(equiv_prog * pai[k] / ai_last)},{_y(iai[k])}"
                    for k in range(len(pai)))

    pk = max(range(len(idot)), key=lambda k: idot[k]) if idot else 0
    pkx, pky = _x(pdot[pk]), _y(idot[pk])
    tx, ty = _x(equiv_prog), _y(today_int)
    base_y = _y(0.0)

    return f'''<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg" font-family="{_FONT}">
  <defs>
    <radialGradient id="glow" cx="60%" cy="12%" r="65%">
      <stop offset="0" stop-color="#57a6ff" stop-opacity="0.12"/><stop offset="1" stop-color="#57a6ff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="#0a0d13"/>
  <rect width="1200" height="630" fill="url(#glow)"/>

  <!-- ===== chart: real root roll-up, dot-com reference vs AI era ===== -->
  <line x1="{_PX0}" y1="{base_y}" x2="{_PX1}" y2="{base_y}" stroke="#232b39" stroke-width="1.5"/>

  <!-- TODAY marker (cool white) -->
  <line x1="{tx}" y1="150" x2="{tx}" y2="{base_y}" stroke="#eef1f6" stroke-opacity="0.45" stroke-width="1.6" stroke-dasharray="4 6"/>
  <text x="{tx}" y="141" text-anchor="middle" font-size="17" font-weight="700" fill="#eef1f6" letter-spacing="1">TODAY</text>

  <!-- PEAK marker (warm red) -->
  <line x1="{pkx}" y1="150" x2="{pkx}" y2="{base_y}" stroke="#ff5a44" stroke-opacity="0.85" stroke-width="2" stroke-dasharray="3 4"/>
  <text x="{pkx}" y="141" text-anchor="middle" font-size="17" font-weight="700" fill="#ff5a44" letter-spacing="1">PEAK</text>

  <polyline points="{grey}" fill="none" stroke="#8b93a3" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"/>
  <polyline points="{blue}" fill="none" stroke="#57a6ff" stroke-width="4.4" stroke-linejoin="round" stroke-linecap="round"/>

  <circle cx="{tx}" cy="{ty}" r="9" fill="#57a6ff"/>
  <circle cx="{tx}" cy="{ty}" r="16" fill="none" stroke="#57a6ff" stroke-opacity="0.4" stroke-width="2"/>
  <circle cx="{pkx}" cy="{pky}" r="17" fill="none" stroke="#ff5a44" stroke-opacity="0.35" stroke-width="2"/>
  <circle cx="{pkx}" cy="{pky}" r="9" fill="#ff5a44"/>

  <!-- legend -->
  <g font-size="19" font-weight="600">
    <line x1="864" y1="176" x2="898" y2="176" stroke="#8b93a3" stroke-width="3.4" stroke-linecap="round"/>
    <text x="908" y="182" fill="#c2cad6">Dot-com  1995&#8211;2000</text>
    <line x1="864" y1="208" x2="898" y2="208" stroke="#57a6ff" stroke-width="4.4" stroke-linecap="round"/>
    <text x="908" y="214" fill="#8fc0ff">AI era  2022&#8211;now</text>
  </g>

  <!-- ===== heading, overlaid on the empty top-left of the chart ===== -->
  <rect x="42" y="42" width="44" height="44" rx="10" fill="#eef1f6"/>
  <text x="64" y="73" text-anchor="middle" font-size="21" font-weight="800" fill="#0a0d13" letter-spacing="-0.5">AI</text>
  <text x="98" y="72" font-size="26" font-weight="700" fill="#eef1f6" letter-spacing="-0.3">Bubble Oracle</text>

  <text x="45" y="152" font-size="15" font-weight="700" fill="#57a6ff" letter-spacing="2.5">PROJECTED PEAK</text>
  <text x="42" y="214" font-size="52" font-weight="800" fill="#eef1f6" letter-spacing="-1.4">AI Bubble Bursts:</text>
  <text x="42" y="286" font-size="60" font-weight="800" fill="#ff5a44" letter-spacing="-1.8">{date}</text>

  <rect x="44" y="330" width="266" height="46" rx="23" fill="#122a45" stroke="#57a6ff" stroke-opacity="0.55" stroke-width="1.5"/>
  <text x="177" y="359" text-anchor="middle" font-size="18.5" font-weight="700" fill="#8fc0ff">See where we are now  &#8594;</text>

  <!-- footer -->
  <circle cx="48" cy="596" r="4" fill="#57a6ff"/>
  <text x="64" y="602" font-size="20" font-weight="600" fill="#eef1f6">aibubbleoracle.com</text>
</svg>
'''
