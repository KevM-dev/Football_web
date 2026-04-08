import requests
import math

BASE     = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
LEAGUE_AVG_SHOTS  = 11.0
LEAGUE_AVG_FOULS  = 1.5
LEAGUE_AVG_TOUCHES = 55.0   # L: league avg touches/game across all outfield positions
MIN_APPS          = 5
POS_TOUCHES       = {"M": 70, "F": 63, "D": 55}
DEFAULT_MATCH_MINS = 90.0   # E: expected minutes a starter plays

KNOWN_TEAMS = {
    "real madrid":       ("86",    "esp.1"),
    "barcelona":         ("83",    "esp.1"),
    "atletico madrid":   ("1068",  "esp.1"),
    "atletico":          ("1068",  "esp.1"),
    "sevilla":           ("243",   "esp.1"),
    "villarreal":        ("102",   "esp.1"),
    "real betis":        ("244",   "esp.1"),
    "real sociedad":     ("89",    "esp.1"),
    "valencia":          ("94",    "esp.1"),
    "bayern munich":     ("132",   "ger.1"),
    "bayern":            ("132",   "ger.1"),
    "borussia dortmund": ("124",   "ger.1"),
    "dortmund":          ("124",   "ger.1"),
    "bayer leverkusen":  ("131",   "ger.1"),
    "leverkusen":        ("131",   "ger.1"),
    "rb leipzig":        ("11420", "ger.1"),
    "leipzig":           ("11420", "ger.1"),
    "arsenal":           ("359",   "eng.1"),
    "aston villa":       ("362",   "eng.1"),
    "chelsea":           ("363",   "eng.1"),
    "liverpool":         ("364",   "eng.1"),
    "manchester city":   ("382",   "eng.1"),
    "man city":          ("382",   "eng.1"),
    "manchester united": ("360",   "eng.1"),
    "man united":        ("360",   "eng.1"),
    "man utd":           ("360",   "eng.1"),
    "newcastle":         ("361",   "eng.1"),
    "tottenham":         ("367",   "eng.1"),
    "spurs":             ("367",   "eng.1"),
    "ac milan":          ("103",   "ita.1"),
    "milan":             ("103",   "ita.1"),
    "inter milan":       ("110",   "ita.1"),
    "inter":             ("110",   "ita.1"),
    "juventus":          ("111",   "ita.1"),
    "juve":              ("111",   "ita.1"),
    "napoli":            ("114",   "ita.1"),
    "lazio":             ("112",   "ita.1"),
    "psg":               ("160",   "fra.1"),
    "paris saint-germain": ("160", "fra.1"),
    "marseille":         ("176",   "fra.1"),
    "lyon":              ("167",   "fra.1"),
    "monaco":            ("174",   "fra.1"),
}

ALL_LEAGUES = ["esp.1", "ger.1", "eng.1", "ita.1", "fra.1"]


# ── API ──────────────────────────────────────

def api_get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def get_stat(categories, name):
    for cat in categories:
        for s in cat.get("stats", []):
            if s["name"] == name:
                try:
                    return float(s["value"])
                except (ValueError, TypeError):
                    return 0.0
    return 0.0


# ── TEAM / PLAYER LOOKUP ─────────────────────

def find_team(name):
    key = name.lower().strip()
    if key in KNOWN_TEAMS:
        tid, league = KNOWN_TEAMS[key]
        return {"id": tid, "name": name.title(), "league": league}
    for k, (tid, league) in KNOWN_TEAMS.items():
        if key in k or k in key:
            return {"id": tid, "name": k.title(), "league": league}
    for league in ALL_LEAGUES:
        data = api_get(f"{BASE}/{league}/teams")
        teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        for t in teams:
            team = t["team"]
            display = team.get("displayName", "").lower()
            if key in display or display in key:
                return {"id": team["id"], "name": team["displayName"], "league": league}
    return None


def get_roster(team_id, league):
    data = api_get(f"{BASE}/{league}/teams/{team_id}/roster")
    return data.get("athletes", [])


def enrich(player):
    stats = player.get("statistics")
    base = {
        "_apps": 0, "_mins": 0, "_fouls": 0, "_fouls_drawn": 0,
        "_shots": 0, "_sot": 0, "_gc": 0, "_sf": 0,
    }
    if not stats:
        player.update(base)
        return player
    cats = stats["splits"]["categories"]
    player["_apps"]        = get_stat(cats, "appearances")
    player["_mins"]        = get_stat(cats, "minutesPlayed") or get_stat(cats, "minutes")
    # fallback: estimate minutes from appearances if ESPN doesn't carry them
    if player["_mins"] == 0 and player["_apps"] > 0:
        player["_mins"]    = player["_apps"] * DEFAULT_MATCH_MINS
    player["_fouls"]       = get_stat(cats, "foulsCommitted")
    player["_fouls_drawn"] = get_stat(cats, "foulsSuffered")
    player["_shots"]       = get_stat(cats, "totalShots")
    player["_sot"]         = get_stat(cats, "shotsOnTarget")
    player["_gc"]          = get_stat(cats, "goalsConceded")
    player["_sf"]          = get_stat(cats, "shotsFaced")
    return player


def find_in_squad(squad, name):
    key = name.lower()
    for p in squad:
        if key in p.get("fullName", "").lower() or key in p.get("lastName", "").lower():
            return p
    return None


def shots_conceded(squad):
    gks = sorted(
        [p for p in squad if p.get("position", {}).get("abbreviation", "") == "G" and p.get("statistics")],
        key=lambda p: p["_apps"], reverse=True
    )
    for gk in gks:
        if gk["_apps"] >= MIN_APPS:
            if gk["_sf"] > 0:
                return round(gk["_sf"] / gk["_apps"], 1)
            if gk["_gc"] > 0:
                return round(gk["_gc"] / gk["_apps"] * 3.5, 1)
    return LEAGUE_AVG_SHOTS


# ── ALGORITHMS ───────────────────────────────

def foul_prob(fouls, mins, target_pos, expected_mins=DEFAULT_MATCH_MINS):
    """
    Master Formula:
    P(Foul >= 1) = [1 - e^(-(F/M x E x O/L))] x 100

    F = total fouls committed this season
    M = total minutes played this season
    E = expected minutes in this match (default 90)
    O = opponent avg touches per game (estimated by position)
    L = league avg touches per game (across all outfield positions)
    """
    if mins == 0: return 0.0
    O   = POS_TOUCHES.get(target_pos, 63)
    lam = (fouls / mins) * expected_mins * (O / LEAGUE_AVG_TOUCHES)
    return round((1 - math.exp(-lam)) * 100.0, 2)


def shot_prob(total_shots, apps, opp_conc):
    if apps == 0: return 0.0
    lam = (total_shots / apps) * (opp_conc / LEAGUE_AVG_SHOTS)
    return round((1 - math.exp(-lam)) * 100.0, 2)


def sot_prob(total_sot, apps):
    if apps == 0: return 0.0
    return round((1 - math.exp(-(total_sot / apps))) * 100.0, 2)


def fouled_prob(drawn, apps, opp_fouls, opp_apps):
    if apps == 0 or opp_apps == 0: return 0.0
    lam = (drawn / apps) * ((opp_fouls / opp_apps) / LEAGUE_AVG_FOULS)
    return round((1 - math.exp(-lam)) * 100.0, 2)


# ── MATCH ANALYSIS ───────────────────────────

def run_match(team1_name, team2_name):
    t1 = find_team(team1_name)
    t2 = find_team(team2_name)
    if not t1:
        return {"error": f"Team not found: {team1_name}"}
    if not t2:
        return {"error": f"Team not found: {team2_name}"}

    s1 = [enrich(p) for p in get_roster(t1["id"], t1["league"])]
    s2 = [enrich(p) for p in get_roster(t2["id"], t2["league"])]

    t1_conc = shots_conceded(s1)
    t2_conc = shots_conceded(s2)

    foul_rows   = []
    shot_rows   = []
    sot_rows    = []
    fouled_rows = []

    def calc_fouls(defs, atts, def_team, att_team):
        for d in defs:
            if d.get("position", {}).get("abbreviation", "") != "D": continue
            if d["_fouls"] == 0 or d["_apps"] < MIN_APPS: continue
            for a in atts:
                apos = a.get("position", {}).get("abbreviation", "")
                if apos not in ("M", "F"): continue
                if a["_apps"] < MIN_APPS: continue
                prob = foul_prob(d["_fouls"], d["_mins"], apos)
                f90 = round((d["_fouls"] / d["_mins"]) * 90, 2) if d["_mins"] else 0
                foul_rows.append({
                    "committer": d["fullName"], "committer_team": def_team,
                    "f90": f90,
                    "target": a["fullName"], "target_team": att_team,
                    "touches": POS_TOUCHES.get(apos, 63), "prob": prob,
                })

    def calc_shots(players, team, opp_conc):
        for p in players:
            if p.get("position", {}).get("abbreviation", "") not in ("M", "F"): continue
            if p["_shots"] == 0 or p["_apps"] < MIN_APPS: continue
            prob = shot_prob(p["_shots"], p["_apps"], opp_conc)
            shot_rows.append({
                "player": p["fullName"], "team": team,
                "shots_pg": round(p["_shots"] / p["_apps"], 2),
                "prob": prob,
            })

    def calc_sot(players, team):
        for p in players:
            if p.get("position", {}).get("abbreviation", "") not in ("M", "F"): continue
            if p["_sot"] == 0 or p["_apps"] < MIN_APPS: continue
            prob = sot_prob(p["_sot"], p["_apps"])
            sot_rows.append({
                "player": p["fullName"], "team": team,
                "sot_pg": round(p["_sot"] / p["_apps"], 2),
                "prob": prob,
            })

    def calc_fouled(atts, att_team, defs):
        opp_fouls = sum(d["_fouls"] for d in defs if d.get("position", {}).get("abbreviation", "") == "D" and d["_apps"] >= MIN_APPS)
        opp_apps  = sum(d["_apps"]  for d in defs if d.get("position", {}).get("abbreviation", "") == "D" and d["_apps"] >= MIN_APPS)
        if opp_fouls == 0 or opp_apps == 0: return
        for a in atts:
            if a.get("position", {}).get("abbreviation", "") not in ("M", "F"): continue
            if a["_fouls_drawn"] == 0 or a["_apps"] < MIN_APPS: continue
            prob = fouled_prob(a["_fouls_drawn"], a["_apps"], opp_fouls, opp_apps)
            fouled_rows.append({
                "player": a["fullName"], "team": att_team,
                "drawn_pg": round(a["_fouls_drawn"] / a["_apps"], 2),
                "opp_fpm":  round(opp_fouls / opp_apps, 2),
                "prob": prob,
            })

    calc_fouls(s2, s1, t2["name"], t1["name"])
    calc_fouls(s1, s2, t1["name"], t2["name"])
    calc_shots(s1, t1["name"], t2_conc)
    calc_shots(s2, t2["name"], t1_conc)
    calc_sot(s1, t1["name"])
    calc_sot(s2, t2["name"])
    calc_fouled(s1, t1["name"], s2)
    calc_fouled(s2, t2["name"], s1)

    return {
        "team1": t1["name"], "team2": t2["name"],
        "t1_conc": t1_conc,  "t2_conc": t2_conc,
        "foul":   sorted(foul_rows,   key=lambda x: x["prob"], reverse=True)[:15],
        "shot":   sorted(shot_rows,   key=lambda x: x["prob"], reverse=True)[:15],
        "sot":    sorted(sot_rows,    key=lambda x: x["prob"], reverse=True)[:15],
        "fouled": sorted(fouled_rows, key=lambda x: x["prob"], reverse=True)[:15],
    }


# ── SINGLE PLAYER ────────────────────────────

def run_single(mode, player_name, player_team, opp_team=None):
    team_p = find_team(player_team)
    if not team_p:
        return {"error": f"Team not found: {player_team}"}

    squad_p = [enrich(p) for p in get_roster(team_p["id"], team_p["league"])]
    player  = find_in_squad(squad_p, player_name)
    if not player:
        return {"error": f"Player '{player_name}' not found in {team_p['name']}"}

    result = {
        "player": player["fullName"],
        "team":   team_p["name"],
        "mode":   mode,
    }

    if mode in ("shot", "fouled") and opp_team:
        team_o  = find_team(opp_team)
        if not team_o:
            return {"error": f"Team not found: {opp_team}"}
        squad_o = [enrich(p) for p in get_roster(team_o["id"], team_o["league"])]
        result["opp"] = team_o["name"]

    if mode == "foul":
        result["fouls"]    = int(player["_fouls"])
        result["mins"]     = int(player["_mins"])
        result["f90"]      = round((player["_fouls"] / player["_mins"]) * 90, 2) if player["_mins"] else 0

    elif mode == "shot":
        opp_conc = shots_conceded(squad_o)
        result["shots"]    = int(player["_shots"])
        result["apps"]     = int(player["_apps"])
        result["shots_pg"] = round(player["_shots"] / player["_apps"], 2) if player["_apps"] else 0
        result["opp_conc"] = opp_conc
        result["prob"]     = shot_prob(player["_shots"], player["_apps"], opp_conc)

    elif mode == "sot":
        result["sot"]      = int(player["_sot"])
        result["apps"]     = int(player["_apps"])
        result["sot_pg"]   = round(player["_sot"] / player["_apps"], 2) if player["_apps"] else 0
        result["prob"]     = sot_prob(player["_sot"], player["_apps"])

    elif mode == "fouled":
        defs       = [p for p in squad_o if p.get("position", {}).get("abbreviation", "") == "D" and p["_apps"] >= MIN_APPS]
        opp_fouls  = sum(d["_fouls"] for d in defs)
        opp_apps   = sum(d["_apps"]  for d in defs)
        result["drawn"]      = int(player["_fouls_drawn"])
        result["apps"]       = int(player["_apps"])
        result["drawn_pg"]   = round(player["_fouls_drawn"] / player["_apps"], 2) if player["_apps"] else 0
        result["opp_fpm"]    = round(opp_fouls / opp_apps, 2) if opp_apps else 0
        result["prob"]       = fouled_prob(player["_fouls_drawn"], player["_apps"], opp_fouls, opp_apps)

    return result
