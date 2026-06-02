#!/usr/bin/env python3
"""
NBA Game Stats JSON → Interactive HTML Visualization
Usage: python nba_viz_gen.py <input.json> [output.html]
"""
import json, argparse
from collections import defaultdict
from pathlib import Path


# ─── Data Processing ──────────────────────────────────────────────────────────

def compute_period_scores(shots, box):
    fg = defaultdict(lambda: defaultdict(int))
    ft = defaultdict(lambda: defaultdict(int))
    for s in shots:
        if s["result"] == "Made":
            fg[s["period"]][s["team"]] += 3 if "3PT" in s["shot_type"] else 2
    for r in box:
        ft[r["period"]][r["team"]] += r.get("free_throws_made", 0)
    periods = sorted(set(list(fg) + list(ft)),
                     key=lambda p: (0 if p.startswith("Q") else 1, p))
    teams = sorted(set(s["team"] for s in shots))
    period_scores = {p: {t: fg[p][t] + ft[p][t] for t in teams} for p in periods}
    return period_scores, teams, periods


def process_game(game):
    shots = game["shot_plot_data"]
    box   = game["box_score_metrics"]
    period_scores, teams, periods = compute_period_scores(shots, box)
    totals = {t: sum(period_scores[p][t] for p in periods) for t in teams}
    return {
        "game_number":   game["game_number"],
        "game_id":       game["game_id"],
        "teams":         teams,
        "periods":       periods,
        "period_scores": period_scores,
        "totals":        totals,
        "shots":         shots,
        "__rawBox":      box,
    }


def build_dataset(raw):
    return {"series": raw.get("series", "NBA"), "games": [process_game(g) for g in raw["games"]]}


# ─── HTML ─────────────────────────────────────────────────────────────────────

def generate_html(dataset):
    data_json = json.dumps(dataset, separators=(",", ":"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{dataset['series']}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --font-ui:'Barlow Condensed',sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --bg:#f0ebe3;--bg2:#e6e0d6;--bg3:#d8d0c4;
  --surface:#faf8f5;--border:#ccc4b6;
  --text:#1a1612;--text2:#5a5047;--text3:#9a9088;
  --a1:#c0392b;--a2:#1a6fa8;
  --made:#27ae60;--missed:#e74c3c;
  --court-bg:#c8955a;--court-line:rgba(60,30,5,0.75);--court-paint:rgba(100,60,15,0.13);
  --hdr:#1a1612;--hdr-txt:#f0ebe3;
  --pon:#1a1612;--pont:#f0ebe3;--poff:#e6e0d6;--pofft:#5a5047;
  --sh:0 1px 8px rgba(0,0,0,.09);--shl:0 4px 20px rgba(0,0,0,.12);
  --r:9px;--stripe:rgba(0,0,0,.03);
}}
[data-theme=dark]{{
  --bg:#0d0b09;--bg2:#181410;--bg3:#222018;
  --surface:#1a1612;--border:#302820;
  --text:#f0ebe3;--text2:#a09080;--text3:#665e54;
  --a1:#e05040;--a2:#3498db;
  --made:#2ecc71;--missed:#e74c3c;
  --court-bg:#0e0a04;--court-line:rgba(190,140,50,0.70);--court-paint:rgba(190,140,50,0.09);
  --hdr:#0d0b09;--hdr-txt:#f0ebe3;
  --pon:#f0ebe3;--pont:#1a1612;--poff:#1a1612;--pofft:#a09080;
  --sh:0 1px 8px rgba(0,0,0,.4);--shl:0 4px 20px rgba(0,0,0,.55);
  --stripe:rgba(255,255,255,.022);
}}
body{{font-family:var(--font-ui);background:var(--bg);color:var(--text);min-height:100vh;transition:background .22s,color .22s;font-size:15px}}

header{{background:var(--hdr);color:var(--hdr-txt);padding:0 20px;display:flex;align-items:center;justify-content:space-between;height:40px;position:sticky;top:0;z-index:200;box-shadow:var(--shl)}}
.h-title{{font-size:17px;font-weight:900;letter-spacing:.05em;text-transform:uppercase;position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)}}
.h-sub{{font-size:10px;opacity:.45;letter-spacing:.08em;text-transform:uppercase}}
.theme-btn{{background:none;border:1px solid rgba(255,255,255,.2);color:var(--hdr-txt);cursor:pointer;padding:4px 14px;border-radius:20px;font-family:var(--font-ui);font-size:13px;font-weight:700;letter-spacing:.04em;transition:all .18s}}
.theme-btn:hover{{background:rgba(255,255,255,.1)}}

.main{{max-width:1560px;margin:0 auto;padding:14px 14px 40px}}

/* Filter bar */
.filter-bar{{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;margin-bottom:12px;justify-content:space-between}}
.fg{{display:flex;flex-direction:row;gap:4px;align-items:center}}
.fl{{font-size:9px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;color:var(--text3)}}
.pills{{display:flex;flex-wrap:wrap;gap:4px}}
.pill{{padding:4px 12px;border-radius:20px;cursor:pointer;font-family:var(--font-ui);font-size:12px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;background:var(--poff);color:var(--pofft);border:1px solid var(--border);transition:all .15s;user-select:none;white-space:nowrap}}
.pill:hover{{border-color:var(--text3)}}
.pill.active{{background:var(--pon);color:var(--pont);border-color:var(--pon)}}

/* Scoreboard row */
.scoreboard-row{{display:flex;gap:10px;margin-bottom:10px;align-items:stretch;flex-wrap:wrap}}

/* Score card — flex:1, matches player panel width */
.score-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 22px;box-shadow:var(--sh);flex:1;min-width:300px}}
.score-main{{display:flex;align-items:center;gap:24px;margin-bottom:14px;justify-content:center}}
.score-team{{text-align:center;min-width:100px}}
.stn{{font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--text3)}}
.stp{{font-size:62px;font-weight:900;line-height:1;font-family:var(--font-mono)}}
.score-sep{{font-size:20px;font-weight:900;color:var(--text3)}}
.sw{{font-size:9px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;color:var(--made);min-height:13px;margin-top:2px}}

/* Quarter grid */
.qgrid{{display:grid;background:var(--border);gap:1px;border:1px solid var(--border);border-radius:6px;overflow:hidden;font-family:var(--font-mono);font-size:12px}}
.qcell{{background:var(--surface);padding:5px 10px;text-align:center;transition:background .12s}}
.qhead{{background:var(--bg2);font-size:9px;font-weight:700;letter-spacing:.07em;color:var(--text3)}}
.qclick{{cursor:pointer}}
.qclick:hover{{background:var(--bg2)!important}}
.qact{{background:var(--pon)!important;color:var(--pont)!important;font-weight:700}}
.qtlabel{{text-align:left;font-weight:700;font-size:11px;letter-spacing:.04em}}
.qtot{{font-weight:900;cursor:pointer}}
.qtot:hover{{background:var(--bg2)!important}}
.qtot-act{{background:var(--pon)!important;color:var(--pont)!important;font-weight:900}}

/* Team stats card — fixed width matching shot chart (500px + 28px padding + 2px borders + 4px borders court-wrap = 534px) */
.ts-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px;box-shadow:var(--sh);flex-shrink:0;width:534px}}
.ts-head{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.ts-head-team{{font-size:12px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}}
.ts-head-team-0{{color:var(--a1)}}
.ts-head-team-1{{color:var(--a2)}}
.ts-head-label{{flex:1;text-align:center;font-size:9px;font-weight:700;letter-spacing:.10em;text-transform:uppercase;color:var(--text3)}}
.ts-row{{margin-bottom:7px}}
/* Bar layout: [val0] [====label====] [val1] */
.ts-bar-line{{display:flex;align-items:center;gap:6px;margin-bottom:3px}}
.ts-val{{font-family:var(--font-mono);font-size:12px;font-weight:700;min-width:36px;white-space:nowrap}}
.ts-val-0{{text-align:right;color:var(--a1)}}
.ts-val-1{{text-align:left;color:var(--a2)}}
.ts-bar-outer{{flex:1;position:relative;height:14px;background:var(--bg3);border-radius:7px;overflow:hidden}}
.ts-bar-a{{position:absolute;left:0;top:0;height:100%;background:var(--a1);opacity:.5;transition:width .35s ease;border-radius:7px 0 0 7px}}
.ts-bar-b{{position:absolute;right:0;top:0;height:100%;background:var(--a2);opacity:.5;transition:width .35s ease;border-radius:0 7px 7px 0}}
.ts-bar-label{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-size:8px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--text2);white-space:nowrap;pointer-events:none;text-shadow:0 0 4px var(--surface)}}

/* Bottom row */
.bottom-row{{display:flex;gap:10px;align-items:stretch;flex-wrap:wrap}}
.shot-panel{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px;box-shadow:var(--sh);flex-shrink:0}}
.panel-hdr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px}}
.ptitle{{font-size:9px;font-weight:700;letter-spacing:.10em;text-transform:uppercase;color:var(--text3)}}
.legend{{display:flex;gap:12px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px;font-weight:600;color:var(--text2)}}
.ld{{width:9px;height:9px;border-radius:50%}}
.court-wrap{{background:var(--court-bg);border:2px solid var(--court-line);border-radius:6px;overflow:hidden;transition:background .22s;line-height:0}}
.shot-chips{{display:flex;gap:7px;margin-top:10px;flex-wrap:wrap}}
.chip{{background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:7px 11px;min-width:76px}}
.chip-l{{font-size:8px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--text3)}}
.chip-v{{font-size:17px;font-weight:900;font-family:var(--font-mono);color:var(--text)}}
.chip-s{{font-size:9px;color:var(--text3)}}

/* Player panel */
.player-panel{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px;box-shadow:var(--sh);flex:1;min-width:0;overflow:hidden;display:flex;flex-direction:column}}
.player-panel-hdr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-shrink:0}}
.clr-btn{{font-size:10px;font-weight:700;cursor:pointer;color:var(--text3);padding:2px 8px;border-radius:10px;border:1px solid var(--border);transition:all .14s;letter-spacing:.03em}}
.clr-btn:hover{{color:var(--text);border-color:var(--text3)}}
.tbl-wrap{{overflow-x:auto;flex:1;overflow-y:auto}}
table{{width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:11.5px}}
thead th{{background:var(--bg2);padding:6px 8px;text-align:right;font-size:8.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--text3);border-bottom:1px solid var(--border);white-space:nowrap;position:sticky;top:0;z-index:1}}
thead th:first-child{{text-align:left}}
tbody tr{{border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s}}
tbody tr:nth-child(odd){{background:var(--stripe)}}
tbody tr:hover{{background:var(--bg2)!important}}
tbody tr.row-sel{{background:rgba(255,200,0,.12)!important;outline:1px solid rgba(255,200,0,.35)}}
[data-theme=dark] tbody tr.row-sel{{background:rgba(255,200,0,.10)!important;outline:1px solid rgba(255,200,0,.28)}}
td{{padding:6px 8px;text-align:right;color:var(--text)}}
td:first-child{{text-align:left;font-weight:700;font-size:11.5px;font-family:var(--font-ui);letter-spacing:.02em;white-space:nowrap}}
.badge{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:8.5px;font-weight:900;letter-spacing:.08em}}
.b0{{background:rgba(192,57,43,.14);color:var(--a1)}}
.b1{{background:rgba(26,111,168,.14);color:var(--a2)}}
[data-theme=dark] .b0{{background:rgba(224,80,64,.18)}}
[data-theme=dark] .b1{{background:rgba(52,152,219,.18)}}

@media(max-width:860px){{
  .bottom-row{{flex-direction:column}}
  .stp{{font-size:44px}}
  .score-card{{min-width:unset}}
  .ts-card{{width:100%}}
}}
</style>
</head>
<body>
<header>
  <div><div class="h-sub">Stats Dashboard</div><div class="h-title" id="series-title"></div></div>
  <button class="theme-btn" onclick="toggleTheme()" id="theme-btn">☀ Light</button>
</header>
<div class="main">
  <div class="filter-bar">
    <div class="fg"><div class="fl">Game</div><div class="pills" id="gpills"></div></div>
    <div class="fg"><div class="fl">Team</div><div class="pills" id="tpills"></div></div>
  </div>

  <div class="scoreboard-row">
    <div class="ts-card">
      <div class="ts-head">
        <span class="ts-head-team ts-head-team-0" id="ts-team0">–</span>
        <span class="ts-head-label">Team Stats <span id="ts-plbl" style="font-weight:400"></span></span>
        <span class="ts-head-team ts-head-team-1" id="ts-team1">–</span>
      </div>
      <div id="ts-rows"></div>
    </div>
    <div class="score-card">
      <div class="score-main">
        <div class="score-team"><div class="stn" id="tn0">–</div><div class="stp" id="tp0">–</div><div class="sw" id="tw0"></div></div>
        <div class="score-sep">–</div>
        <div class="score-team"><div class="stn" id="tn1">–</div><div class="stp" id="tp1">–</div><div class="sw" id="tw1"></div></div>
      </div>
      <div class="tbl-wrap"><div class="qgrid" id="qgrid"></div></div>
    </div>
  </div>

  <div class="bottom-row">
    <div class="shot-panel">
      <div class="panel-hdr">
        <div class="ptitle">Shot Chart <span id="shot-lbl" style="color:var(--text2);font-weight:400"></span></div>
        <div class="legend">
          <div class="li"><div class="ld" style="background:var(--made)"></div>Made</div>
          <div class="li"><div class="ld" style="border:1.5px solid var(--missed);background:transparent"></div>Missed</div>
          <div class="li"><div class="ld" style="background:var(--made);outline:2px solid white;outline-offset:-3px;border-radius:50%"></div>3PT</div>
        </div>
      </div>
      <div class="court-wrap"><svg id="court-svg" xmlns="http://www.w3.org/2000/svg" style="display:block"></svg></div>
      <div class="shot-chips" id="shot-chips"></div>
    </div>
    <div class="player-panel">
      <div class="player-panel-hdr">
        <div class="ptitle">Player Stats <span id="plyr-lbl" style="color:var(--text2);font-weight:400"></span></div>
        <div class="clr-btn" id="clr-btn" onclick="clearPlayer()" style="display:none">✕ Clear</div>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr id="pthead">
            <th style="text-align:left;cursor:pointer" data-col="name" data-base="Player" onclick="sortBy(this)">Player</th>
            <th></th>
            <th style="cursor:pointer" data-col="min" data-base="MIN" onclick="sortBy(this)">MIN</th>
            <th style="cursor:pointer" data-col="pts" data-base="PTS" onclick="sortBy(this)">PTS</th>
            <th style="cursor:pointer" data-col="fgm" data-base="FG" onclick="sortBy(this)">FG</th>
            <th style="cursor:pointer" data-col="m3" data-base="3P" onclick="sortBy(this)">3P</th>
            <th style="cursor:pointer" data-col="ftm" data-base="FT" onclick="sortBy(this)">FT</th>
            <th style="cursor:pointer" data-col="reb" data-base="REB" onclick="sortBy(this)">REB</th>
            <th style="cursor:pointer" data-col="ast" data-base="AST" onclick="sortBy(this)">AST</th>
            <th style="cursor:pointer" data-col="stl" data-base="STL" onclick="sortBy(this)">STL</th>
            <th style="cursor:pointer" data-col="blk" data-base="BLK" onclick="sortBy(this)">BLK</th>
            <th style="cursor:pointer" data-col="tov" data-base="TOV" onclick="sortBy(this)">TOV</th>
          </tr></thead>
          <tbody id="ptbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
const DS = {data_json};

// ── State ────────────────────────────────────────────────────────────────────
const S = {{gi:0, period:"ALL", team:"ALL", player:"ALL", dark:true, sortCol:"pts", sortDir:-1}};

// ── Theme ────────────────────────────────────────────────────────────────────
function toggleTheme(){{
  S.dark=!S.dark;
  document.documentElement.setAttribute("data-theme",S.dark?"dark":"light");
  document.getElementById("theme-btn").textContent=S.dark?"☀ Light":"☾ Dark";
  drawCourt(); replot();
}}
document.documentElement.setAttribute("data-theme","dark");

// ── Court Drawing — NBA spec ─────────────────────────────────────────────────
// NBA coords: basket=(0,0), baseline at y=-52.5, half-court at y=417.5
// SVG: W=500, H=560, basket at svg(250, 487.5)
// svgX = nbaX + 250
// svgY = 487.5 - nbaY  (y-flip: larger nbaY → smaller svgY → higher on screen)
const W=500, H=560, Y0=487.5;
const sx=nx=>nx+250;
const sy=ny=>Y0-ny;

function drawCourt(){{
  const svg=document.getElementById("court-svg");
  svg.setAttribute("viewBox",`0 0 ${{W}} ${{H}}`);
  svg.setAttribute("width",W); svg.setAttribute("height",H);
  const cs=getComputedStyle(document.documentElement);
  const cBg=cs.getPropertyValue("--court-bg").trim();
  const cL=cs.getPropertyValue("--court-line").trim();
  const cP=cs.getPropertyValue("--court-paint").trim();
  const sw=1.5;

  // helpers
  const L=(x1,y1,x2,y2,extra="")=>`<line x1="${{sx(x1)}}" y1="${{sy(y1)}}" x2="${{sx(x2)}}" y2="${{sy(y2)}}" stroke="${{cL}}" stroke-width="${{sw}}" ${{extra}}/>`;
  const C=(nx,ny,r,fill="none",stroke=cL,strokeW=sw,dash="")=>`<circle cx="${{sx(nx)}}" cy="${{sy(ny)}}" r="${{r}}" fill="${{fill}}" stroke="${{stroke}}" stroke-width="${{strokeW}}" ${{dash?`stroke-dasharray="${{dash}}"`:""}}/>`;
  // Arc: from NBA point (x1,y1) to (x2,y2), radius r, large-arc, sweep
  const A=(x1,y1,x2,y2,r,large,sweep,extra="")=>
    `<path d="M ${{sx(x1)}} ${{sy(y1)}} A ${{r}} ${{r}} 0 ${{large}} ${{sweep}} ${{sx(x2)}} ${{sy(y2)}}" fill="none" stroke="${{cL}}" stroke-width="${{sw}}" ${{extra}}/>`;

  let h=`<rect width="${{W}}" height="${{H}}" fill="${{cBg}}"/>`;

  // ── Court boundary ──
  // Sidelines: from baseline (y=-52.5) to half-court (y=417.5)
  h+=L(-250,-52.5,-250,417.5);   // left sideline
  h+=L(250,-52.5,250,417.5);     // right sideline
  // Baseline
  h+=L(-250,-52.5,250,-52.5);
  // Half-court line
  h+=L(-250,417.5,250,417.5);

  // ── Paint / Key ──
  // NBA: basket is 5.25ft from baseline. FT line is 19ft from baseline.
  // -> FT line is (19-5.25)*10 = 137.5 units from basket.
  // Paint: 16ft wide (160 units), baseline (y=-52.5) to FT line (y=137.5).
  h+=`<rect x="${{sx(-80)}}" y="${{sy(137.5)}}" width="160" height="${{sy(-52.5)-sy(137.5)}}" fill="${{cP}}" stroke="${{cL}}" stroke-width="${{sw}}"/>`;

  // ── Free-throw line ──
  h+=L(-80,137.5,80,137.5);

  // ── Free-throw circle (r=60, 6ft radius) ──
  // Center at (0,137.5). Top at y=197.5, well inside 3PT arc (r=237.5) ✓
  // Upper half (toward half-court): solid
  h+=A(-60,137.5,60,137.5,60,0,1);
  // Lower half (toward basket): dashed
  h+=A(-60,137.5,60,137.5,60,0,0,'stroke-dasharray="6,5"');

  // ── Backboard ── (30 units each side = 6ft wide, at y=-12.5)
  h+=L(-30,-12.5,30,-12.5);

  // ── Basket ── (r=7.5, 9-inch radius rim)
  h+=C(0,0,7.5,"none",cL,2);

  // ── Restricted area arc ── (r=40, bows away from hoop = toward half-court)
  // Hoop is at bottom (svgY=487.5). Away from hoop = upward in SVG = smaller svgY.
  // From left(-40,0) to right(40,0): CW sweep=1 bows downward (toward hoop) — wrong.
  // CCW sweep=0 bows upward (away from hoop) — but SVG y-axis is flipped vs NBA y.
  // After y-flip: sx(-40)<sx(40), sy(0)=487.5. CW in SVG from left→right goes DOWN.
  // We want arc bowing UP (away from hoop), so use sweep=0 (CCW in SVG = up).
  // HOWEVER: with NBA→SVG y-flip, nbaY>0 maps to svgY<487.5 (upward on screen).
  // Going left→right (sx(-40) to sx(40)) CCW in SVG = top arc = bows toward smaller svgY = AWAY from hoop ✓
  h+=A(-40,0,40,0,40,0,1);
  h+=L(-40,-12.5,-40,0);
  h+=L(40,-12.5,40,0);

  // ── 3-point line ──
  // Corner straights: from baseline (y=-52.5) to y=89, at x=±220
  h+=L(-220,-52.5,-220,89);
  h+=L(220,-52.5,220,89);
  // Arc: center=basket(0,0), r=237.5, from (-220,89) to (220,89)
  // Must bow AWAY from hoop (upward on screen = toward half-court).
  // Left→right with sweep=1 (CW in SVG) bows upward after y-flip ✓
  h+=A(-220,89,220,89,237.5,0,1);

  // ── Half-court circles ──
  // Center circle at (0,417.5), r=60 (6ft radius)
  h+=C(0,417.5,60,"none",cL,sw);
  // Center tip-off circle r=2 (small dot)
  h+=C(0,417.5,20,"none",cL,sw);

  // ── Lane markings ── NBA block positions from baseline: 7,8,11,14ft -> from basket: 17.5,27.5,57.5,87.5
  [17.5,27.5,57.5,87.5].forEach(y=>{{[-80,y,-92,y].concat();[[-80,y,-92,y],[80,y,92,y]].forEach(coords=>{{const[x1,y1,x2,y2]=coords;h+=L(x1,y1,x2,y2);}});}});

  // ── Shots layer placeholder ──
  h+=`<g id="shots-layer"></g>`;
  svg.innerHTML=h;
}}

// ── Shot plotting ─────────────────────────────────────────────────────────────
function filteredShots(ignorePlayer=false, ignoreTeam=false){{
  const g=DS.games[S.gi]; let shots=g.shots;
  if(S.period!=="ALL") shots=shots.filter(s=>s.period===S.period);
  if(!ignoreTeam && S.team!=="ALL")   shots=shots.filter(s=>s.team===S.team);
  if(!ignorePlayer && S.player!=="ALL") shots=shots.filter(s=>s.player_name===S.player);
  return shots;
}}
function filteredBox(ignorePlayer=false, ignoreTeam=false){{
  const g=DS.games[S.gi]; let box=g.__rawBox;
  if(S.period!=="ALL") box=box.filter(r=>r.period===S.period);
  if(!ignoreTeam && S.team!=="ALL")   box=box.filter(r=>r.team===S.team);
  if(!ignorePlayer && S.player!=="ALL") box=box.filter(r=>r.player_name===S.player);
  return box;
}}

function replot(){{
  const shots=filteredShots();  // shots respect player filter
  const layer=document.getElementById("shots-layer");
  if(!layer)return;
  let html="";
  shots.forEach(s=>{{
    const px=sx(s.loc_x), py=sy(s.loc_y);
    if(px<-20||px>W+20||py<-20||py>H+20) return;
    const tip=`${{s.player_name}} (${{s.team}}) · ${{s.period}} · ${{s.shot_type}} · ${{s.shot_zone}}`;
    const is3=s.shot_type.includes("3PT");
    if(s.result==="Made"){{
      html+=`<circle cx="${{px}}" cy="${{py}}" r="5.5" fill="var(--made)" fill-opacity=".82"><title>${{tip}}</title></circle>`;
      if(is3) html+=`<circle cx="${{px}}" cy="${{py}}" r="3" fill="white" fill-opacity=".55" pointer-events="none"/>`;
    }}else{{
      html+=`<line x1="${{px-4.5}}" y1="${{py-4.5}}" x2="${{px+4.5}}" y2="${{py+4.5}}" stroke="var(--missed)" stroke-width="2" stroke-opacity=".75"/>
             <line x1="${{px+4.5}}" y1="${{py-4.5}}" x2="${{px-4.5}}" y2="${{py+4.5}}" stroke="var(--missed)" stroke-width="2" stroke-opacity=".75"><title>${{tip}}</title></line>`;
      if(is3) html+=`<circle cx="${{px}}" cy="${{py}}" r="3" fill="none" stroke="var(--missed)" stroke-width="1.2" stroke-opacity=".7" pointer-events="none"/>`;
    }}
  }});
  layer.innerHTML=html;
}}

// ── Shot chips ────────────────────────────────────────────────────────────────
function updateShotChips(shots){{
  const t=shots.length, m=shots.filter(s=>s.result==="Made").length;
  const m3=shots.filter(s=>s.result==="Made"&&s.shot_type.includes("3PT")).length;
  const a3=shots.filter(s=>s.shot_type.includes("3PT")).length;
  const pct=(a,b)=>b?(100*a/b).toFixed(1)+"%":"–";
  document.getElementById("shot-chips").innerHTML=`
    <div class="chip"><div class="chip-l">FG</div><div class="chip-v">${{m}}/${{t}}</div><div class="chip-s">${{pct(m,t)}}</div></div>
    <div class="chip"><div class="chip-l">3PT</div><div class="chip-v">${{m3}}/${{a3}}</div><div class="chip-s">${{pct(m3,a3)}}</div></div>
    <div class="chip"><div class="chip-l">2PT</div><div class="chip-v">${{m-m3}}/${{t-a3}}</div><div class="chip-s">${{pct(m-m3,t-a3)}}</div></div>`;
  const parts=[];
  if(S.period!=="ALL") parts.push(S.period);
  if(S.team!=="ALL") parts.push(S.team);
  if(S.player!=="ALL") parts.push(S.player);
  document.getElementById("shot-lbl").textContent=parts.length?`· ${{parts.join(" · ")}}` :"";
}}

// ── Score ─────────────────────────────────────────────────────────────────────
function updateScore(game){{
  const [t0,t1]=game.teams, ps=game.period_scores, tot=game.totals;
  document.getElementById("tn0").textContent=t0;
  document.getElementById("tn1").textContent=t1||"–";
  let p0,p1;
  if(S.period==="ALL"){{p0=tot[t0]||0;p1=tot[t1]||0;}}
  else{{p0=(ps[S.period]||{{}})[t0]||0;p1=(ps[S.period]||{{}})[t1]||0;}}
  document.getElementById("tp0").textContent=p0;
  document.getElementById("tp1").textContent=p1;
  document.getElementById("tw0").textContent=(S.period==="ALL"&&p0>p1)?"WINNER":"";
  document.getElementById("tw1").textContent=(S.period==="ALL"&&p1>p0)?"WINNER":"";
  // Quarter grid
  const periods=game.periods;
  const qg=document.getElementById("qgrid");
  qg.style.gridTemplateColumns=`54px ${{periods.map(()=>"1fr").join(" ")}} 48px`;
  let h=`<div class="qcell qhead qtlabel">Team</div>`;
  periods.forEach(p=>{{
    const on=S.period===p?" qact":"";
    h+=`<div class="qcell qhead qclick${{on}}" onclick="setPeriod('${{p}}')">${{p}}</div>`;
  }});
  h+=`<div class="qcell qhead qtot${{S.period==="ALL"?" qtot-act":""}} qclick" onclick="setPeriod('ALL')">Tot</div>`;
  [t0,t1].forEach(t=>{{
    h+=`<div class="qcell qtlabel">${{t}}</div>`;
    periods.forEach(p=>{{
      const on=S.period===p?" qact":"";
      h+=`<div class="qcell qclick${{on}}" onclick="setPeriod('${{p}}')">${{(ps[p]||{{}})[t]||0}}</div>`;
    }});
    h+=`<div class="qcell qtot${{S.period==="ALL"?" qtot-act":""}} qclick" onclick="setPeriod('ALL')">${{tot[t]||0}}</div>`;
  }});
  qg.innerHTML=h;
}}

// ── Team stats ────────────────────────────────────────────────────────────────
function calcTS(shots,box,team){{
  const s=shots.filter(x=>x.team===team), b=box.filter(x=>x.team===team);
  const fgm=s.filter(x=>x.result==="Made").length, fga=s.length;
  const m3=s.filter(x=>x.result==="Made"&&x.shot_type.includes("3PT")).length;
  const a3=s.filter(x=>x.shot_type.includes("3PT")).length;
  const ftm=b.reduce((a,r)=>a+r.free_throws_made,0);
  const fta=b.reduce((a,r)=>a+(r.free_throws_made+r.free_throws_missed),0);
  const pts=s.filter(x=>x.result==="Made"&&!x.shot_type.includes("3PT")).length*2+m3*3+ftm;
  const reb=b.reduce((a,r)=>a+r.rebounds,0), ast=b.reduce((a,r)=>a+r.assists,0);
  const stl=b.reduce((a,r)=>a+r.steals,0), blk=b.reduce((a,r)=>a+r.blocks,0);
  const tov=b.reduce((a,r)=>a+r.turnovers,0);
  return {{pts,fgm,fga,m3,a3,ftm,fta,reb,ast,stl,blk,tov}};
}}

function updateTeamStats(shots,box,teams){{
  const [t0,t1]=teams;
  const ts0=calcTS(shots,box,t0), ts1=calcTS(shots,box,t1);
  document.getElementById("ts-team0").textContent=t0;
  document.getElementById("ts-team1").textContent=t1;
  document.getElementById("ts-plbl").textContent=S.period!=="ALL"?`· ${{S.period}}`:"";
  const pct=(m,a)=>a?(100*m/a).toFixed(1)+"%":"–";
  const rows=[
    ["PTS",    "pts",  t=>ts0.pts,t=>ts1.pts, "pts",  v=>v],
    ["FG",     "fgm",  t=>ts0.fgm,t=>ts1.fgm,"fg",   _=>`${{ts0.fgm}}/${{ts0.fga}}`,_=>`${{ts1.fgm}}/${{ts1.fga}}`],
    ["3PT",    "m3",   t=>ts0.m3, t=>ts1.m3,  "3pt",  _=>`${{ts0.m3}}/${{ts0.a3}}`,_=>`${{ts1.m3}}/${{ts1.a3}}`],
    ["FT",     "ftm",  t=>ts0.ftm,t=>ts1.ftm, "ft",   _=>`${{ts0.ftm}}/${{ts0.fta}}`,_=>`${{ts1.ftm}}/${{ts1.fta}}`],
    ["REB",    "reb",  t=>ts0.reb,t=>ts1.reb, "reb",  v=>v],
    ["AST",    "ast",  t=>ts0.ast,t=>ts1.ast, "ast",  v=>v],
    ["STL",    "stl",  t=>ts0.stl,t=>ts1.stl, "stl",  v=>v],
    ["BLK",    "blk",  t=>ts0.blk,t=>ts1.blk, "blk",  v=>v],
    ["TOV",    "tov",  t=>ts0.tov,t=>ts1.tov, "tov",  v=>v],
  ];

  // Each row: [label, key, n0fn, n1fn, barLabel, v0fmt?, v1fmt?]
  let h="";
  [
    ["PTS",  ts0.pts, ts1.pts, ts0.pts, ts1.pts],
    ["FG",   ts0.fgm, ts1.fgm, `${{ts0.fgm}}/${{ts0.fga}}`, `${{ts1.fgm}}/${{ts1.fga}}`],
    ["3PT",  ts0.m3,  ts1.m3,  `${{ts0.m3}}/${{ts0.a3}}`,   `${{ts1.m3}}/${{ts1.a3}}`],
    ["FT",   ts0.ftm, ts1.ftm, `${{ts0.ftm}}/${{ts0.fta}}`, `${{ts1.ftm}}/${{ts1.fta}}`],
    ["REB",  ts0.reb, ts1.reb, ts0.reb, ts1.reb],
    ["AST",  ts0.ast, ts1.ast, ts0.ast, ts1.ast],
    ["STL",  ts0.stl, ts1.stl, ts0.stl, ts1.stl],
    ["BLK",  ts0.blk, ts1.blk, ts0.blk, ts1.blk],
    ["TOV",  ts0.tov, ts1.tov, ts0.tov, ts1.tov],
  ].forEach(([label,n0,n1,v0,v1])=>{{
    const total=(n0+n1)||1;
    const w0=Math.max(2,Math.round(100*n0/total));
    const w1=Math.max(2,100-w0);
    h+=`<div class="ts-row">
      <div class="ts-bar-line">
        <div class="ts-val ts-val-0">${{v0}}</div>
        <div class="ts-bar-outer">
          <div class="ts-bar-a" style="width:${{w0}}%"></div>
          <div class="ts-bar-b" style="width:${{w1}}%"></div>
          <div class="ts-bar-label">${{label}}</div>
        </div>
        <div class="ts-val ts-val-1">${{v1}}</div>
      </div>
    </div>`;
  }});
  document.getElementById("ts-rows").innerHTML=h;
}}

// ── Player stats ──────────────────────────────────────────────────────────────
function calcPlayers(shots,box){{
  const pm={{}};
  shots.forEach(s=>{{
    if(!pm[s.player_name]) pm[s.player_name]={{team:s.team,min:0,fgm:0,fga:0,m3:0,a3:0,ftm:0,fta:0,pts:0,reb:0,ast:0,stl:0,blk:0,tov:0}};
    const p=pm[s.player_name]; p.team=s.team; p.fga++;
    const is3=s.shot_type.includes("3PT"); if(is3)p.a3++;
    if(s.result==="Made"){{p.fgm++;p.pts+=is3?3:2;if(is3)p.m3++;}}
  }});
  box.forEach(r=>{{
    if(!pm[r.player_name]) pm[r.player_name]={{team:r.team,min:0,fgm:0,fga:0,m3:0,a3:0,ftm:0,fta:0,pts:0,reb:0,ast:0,stl:0,blk:0,tov:0}};
    const p=pm[r.player_name]; p.team=r.team;
    if(r.minutes!=null){{const ms=String(r.minutes);if(ms.includes(":")){{const[mm,ss]=ms.split(":");p.min+=parseInt(mm)+parseInt(ss)/60;}}else{{p.min+=parseFloat(ms)||0;}}}}
    p.ftm+=r.free_throws_made; p.fta+=r.free_throws_made+r.free_throws_missed;
    p.pts+=r.free_throws_made; p.reb+=r.rebounds; p.ast+=r.assists;
    p.stl+=r.steals; p.blk+=r.blocks; p.tov+=r.turnovers;
  }});
  return pm;
}}

function updatePlayerStats(teams){{
  // Player stats always show all players (filtered by period+team but NOT by player)
  const shots=filteredShots(true);   // ignorePlayer=true
  const box=filteredBox(true);
  const pct=(m,a)=>a?(100*m/a).toFixed(1)+"%":"–";
  const pm=calcPlayers(shots,box);
  let rows=Object.entries(pm);
  if(S.team!=="ALL") rows=rows.filter(([,s])=>s.team===S.team);
  const sc=S.sortCol, sd=S.sortDir;
  rows.sort((a,b)=>{{
    const va=sc==="name"?a[0]:a[1][sc]||0;
    const vb=sc==="name"?b[0]:b[1][sc]||0;
    return sd*(typeof va==="string"?va.localeCompare(vb):va-vb);
  }});
  // Update header indicators
  document.querySelectorAll("#pthead th[data-col]").forEach(th=>{{
    const base=th.dataset.base;
    th.textContent=base+(th.dataset.col===sc?(sd===-1?" ▼":" ▲"):"");
  }});
  const tbody=document.getElementById("ptbody");
  tbody.innerHTML=rows.map(([name,s])=>{{
    const ti=teams.indexOf(s.team);
    const sel=S.player===name?" row-sel":"";
    return `<tr class="${{sel}}" onclick="setPlayer('${{name.replace(/'/g,"\\\\'")}}')" title="Click to filter shot chart">
      <td>${{name}}</td>
      <td><span class="badge b${{ti>=0?ti:0}}">${{s.team}}</span></td>
      <td>${{s.min>0?Math.round(s.min):"–"}}</td>
      <td>${{s.pts}}</td><td>${{s.fgm}}/${{s.fga}}</td>
      <td>${{s.m3}}/${{s.a3}}</td>
      <td>${{s.ftm}}/${{s.fta}}</td>
      <td>${{s.reb}}</td><td>${{s.ast}}</td><td>${{s.stl}}</td><td>${{s.blk}}</td><td>${{s.tov}}</td>
    </tr>`;
  }}).join("");
  const lbl=[]; if(S.team!=="ALL")lbl.push(S.team); if(S.period!=="ALL")lbl.push(S.period);
  document.getElementById("plyr-lbl").textContent=lbl.length?`· ${{lbl.join(" · ")}}` :"";
  document.getElementById("clr-btn").style.display=S.player!=="ALL"?"":"none";
}}

// ── Pills ─────────────────────────────────────────────────────────────────────
function pills(id,items,active,fn){{
  document.getElementById(id).innerHTML=items.map(([v,l])=>
    `<div class="pill${{v===active?" active":""}}" onclick="${{fn}}('${{v}}')">
    ${{l}}</div>`).join("");
}}

// ── Render ────────────────────────────────────────────────────────────────────
function render(){{
  const game=DS.games[S.gi], teams=game.teams;
  // Game pills: score + OT
  const gp=DS.games.map((g,i)=>{{
    const t=g.teams,tot=g.totals;
    const ots=g.periods.filter(p=>p.startsWith("OT"));
    return [String(i),`G${{g.game_number}} ${{tot[t[0]]}}–${{tot[t[1]]}}${{ots.length?` (${{ots.join("+")}})` :""}}`];
  }});
  pills("gpills",gp,String(S.gi),"setGame");
  pills("tpills",[["ALL","All"],...teams.map(t=>[t,t])],S.team,"setTeam");
  document.getElementById("series-title").textContent=DS.series;

  // Shots for chart respect player filter; stats do not
  const shots=filteredShots();   // for chart + chips
  const box=filteredBox();
  const shotsForStats=filteredShots(true, true);  // ignore player and team for team stats
  const boxForStats=filteredBox(true, true);

  updateScore(game);
  updateTeamStats(shotsForStats,boxForStats,teams);
  replot();
  updateShotChips(shots);
  updatePlayerStats(teams);
}}

// ── Handlers ──────────────────────────────────────────────────────────────────
function setGame(i){{S.gi=parseInt(i);S.period="ALL";S.team="ALL";S.player="ALL";render();}}
function setTeam(t){{S.team=t;S.player="ALL";render();}}
function setPeriod(p){{S.period=(p==="ALL"||S.period===p)?"ALL":p;render();}}
function setPlayer(n){{S.player=S.player===n?"ALL":n;render();}}
function clearPlayer(){{S.player="ALL";render();}}

function sortBy(th){{
  const col=th.dataset.col;
  if(S.sortCol===col){{S.sortDir*=-1;}}
  else{{S.sortCol=col;S.sortDir=-1;}}
  render();
}}
drawCourt();
render();
</script>
</body>
</html>"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input"); parser.add_argument("output",nargs="?")
    args=parser.parse_args()
    src=Path(args.input); dst=Path(args.output) if args.output else src.with_suffix(".html")
    with open(src) as f: raw=json.load(f)
    dataset=build_dataset(raw)
    with open(dst,"w") as f: f.write(generate_html(dataset))
    print(f"✓ {dst}  ({dst.stat().st_size//1024} KB)")
    for g in dataset["games"]:
        t=g["teams"]; tot=g["totals"]
        ots=[p for p in g["periods"] if p.startswith("OT")]
        print(f"  G{g['game_number']}: {t[0]} {tot[t[0]]}–{tot[t[1]]} {t[1]}  {'  '.join(ots)}")

if __name__=="__main__": main()
