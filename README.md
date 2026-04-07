# Football Probability Predictor

A web-based football analytics tool that calculates player and match probabilities using live season stats from the ESPN API.

---

## How to Run

```bash
pip install flask requests
python app.py
```
Then open **http://localhost:5000** in your browser.

Or double-click **`run.bat`** on Windows — it installs dependencies, starts the server, and opens the browser automatically.

---

## Data Source

All stats are pulled live from the **ESPN unofficial API** — no API key required.

Stats used per player:
- `foulsCommitted` — total fouls committed this season
- `foulsSuffered` — total fouls drawn this season
- `totalShots` — total shots this season
- `shotsOnTarget` — total shots on target this season
- `appearances` — matches played
- `shotsFaced` / `goalsConceded` — used for GK-derived team defensive stats

---

## Algorithms

### 1. Foul Probability
> *How likely is a specific defender to foul a specific attacker/midfielder?*

**Inputs:**
- Defender's fouls committed per match
- Target player's estimated touches per 90 (estimated by position: MF = 70, FW = 63)

**Formula:**
```
fouls_per_match     = fouls_committed / appearances
fouls_match_%       = min(fouls_per_match / 3.0, 1.0) × 100
touch_factor        = touches_per_90 / 100

P(foul) = fouls_match_% × touch_factor
```

**Logic:** A defender who commits more fouls per match has a higher base probability. That base is then scaled by how active the target player is on the ball — more touches means more chances to be in a foul situation. The cap of 3 fouls per match represents a realistic maximum foul rate (beyond that is treated as 100%).

---

### 2. Shot Probability
> *How likely is a player to take at least one shot in a match?*

**Inputs:**
- Player's total shots and appearances (derives shots per game)
- Opposition team's shots conceded per match (derived from GK stats)
- League average shots conceded per match (~11)

**Formula:**
```
shots_per_game      = total_shots / appearances
defensive_factor    = opp_shots_conceded / league_avg (11.0)
λ (lambda)          = shots_per_game × defensive_factor

P(≥1 shot) = 1 − e^(−λ)
```

**Logic:** Uses a **Poisson distribution** — the standard model for counting rare independent events over a fixed time period. Lambda represents the expected number of shots. The defensive factor adjusts upward if the opposition leaks more shots than average, and downward if they are defensively solid. A lambda of 0 gives 0% probability; as lambda grows, probability approaches 100%.

---

### 3. Shot on Target Probability
> *How likely is a player to register at least one shot on target in a match?*

**Inputs:**
- Player's total shots on target and appearances

**Formula:**
```
sot_per_match       = shots_on_target / appearances
λ (lambda)          = sot_per_match

P(≥1 SOT) = 1 − e^(−λ)
```

**Logic:** Same Poisson model as shot probability, but applied to shots on target. No opposition factor is applied here — a shot on target is already a quality outcome that reflects the player's own skill and decision-making, not just the volume of attempts allowed by the defense.

---

### 4. Fouled Probability
> *How likely is a player to be fouled at least once in a match?*

**Inputs:**
- Player's fouls drawn per match
- Opposition defenders' combined fouls committed per match
- League average fouls committed per match (~1.5)

**Formula:**
```
drawn_per_match     = fouls_drawn / appearances
opp_fouls_per_match = opp_total_fouls / opp_total_appearances
opp_factor          = opp_fouls_per_match / league_avg (1.5)
λ (lambda)          = drawn_per_match × opp_factor

P(getting fouled) = 1 − e^(−λ)
```

**Logic:** Two-sided model. It combines the player's natural ability to draw fouls (some players are fouled far more than others due to pace, dribbling, or positioning) with how aggressive the opposition's defensive unit is. A player who draws many fouls facing a dirty defensive line produces a high lambda and therefore a high probability. The league average normalises the opposition factor so that a typical defense gives a neutral multiplier of 1.0.

---

## Why Poisson?

The Poisson distribution models the probability of a given number of events occurring in a fixed interval when:
- Events are independent
- The average rate is known
- Events cannot happen simultaneously

Football events like shots and fouls fit this well — they happen at a roughly constant rate per 90 minutes and are largely independent of each other. The formula `P(≥1 event) = 1 − e^(−λ)` gives the probability that at least one event occurs, which is the most useful output for match prediction.

---

## Shots Conceded Estimation

ESPN does not expose a direct team "shots conceded per match" stat. It is derived from the starting goalkeeper's season record:

```
if shotsFaced available:
    shots_conceded = shotsFaced / appearances

elif goalsConceded available:
    shots_conceded = (goalsConceded / appearances) × 3.5

else:
    shots_conceded = league average (11.0)
```

The 3.5 multiplier is based on the typical conversion rate in top European football (~1 goal per 3–4 shots on target).

---

## Probability Color Guide

| Color  | Range   | Meaning                        |
|--------|---------|--------------------------------|
| Green  | ≥ 70%   | High probability — likely      |
| Yellow | 40–69%  | Medium probability — possible  |
| Red    | < 40%   | Low probability — unlikely     |

---

## Minimum Appearances Filter

Players with fewer than **5 appearances** are excluded from all calculations. This prevents small sample sizes from producing misleading probabilities (e.g. a player who committed 3 fouls in 1 game would otherwise show a 100% foul rate).

---

## Tech Stack

| Layer    | Technology          |
|----------|---------------------|
| Backend  | Python / Flask      |
| Data     | ESPN unofficial API |
| Frontend | HTML / CSS / JS     |
| Hosting  | Render.com (free)   |

---

## Contact

- Email: kevinjrm@yahoo.com
- X: [@HendrixTVv](https://x.com/HendrixTVv)
