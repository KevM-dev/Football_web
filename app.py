from flask import Flask, render_template, request, jsonify
import re
import predictor

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/match", methods=["POST"])
def api_match():
    data   = request.get_json()
    team1  = data.get("team1", "").strip()
    team2  = data.get("team2", "").strip()
    if not team1 or not team2:
        return jsonify({"error": "Both team names are required."}), 400
    result = predictor.run_match(team1, team2)
    return jsonify(result)


@app.route("/api/single", methods=["POST"])
def api_single():
    data        = request.get_json()
    mode        = data.get("mode", "")
    player_name = data.get("player", "").strip()
    player_team = data.get("player_team", "").strip()
    opp_team    = data.get("opp_team", "").strip()
    if not player_name or not player_team:
        return jsonify({"error": "Player name and team are required."}), 400
    result = predictor.run_single(mode, player_name, player_team, opp_team)
    return jsonify(result)


@app.route("/api/ucl", methods=["GET"])
def api_ucl():
    date_str = request.args.get("date", "").strip()
    if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"error": "A valid date (YYYY-MM-DD) is required."}), 400
    espn_date = date_str.replace("-", "")
    result = predictor.get_ucl_fixtures(espn_date)
    return jsonify(result)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
