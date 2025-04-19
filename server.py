import os
import uuid
from datetime import timedelta, datetime
from flask import (
    Flask, request, render_template, jsonify,
    session, redirect, url_for, send_from_directory
)
from flask_socketio import SocketIO, emit
from utils.auth import auth_bp
from utils.db import users_collection
import imageio.v3 as iio

#testaccount, theone, pass = T1h2e3%%One
app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)


# Serve images
@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(
        os.path.join(app.root_path, "images"),
        filename
    )
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/change-avatar", methods=["GET", "POST"])
def avatar():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))

    if request.method == "POST":
        file = request.files.get("avatar")
        if not file or file.filename == "":
            return "No file uploaded", 400

        img = iio.imread(file.stream)

        # build unique filename
        ext = os.path.splitext(file.filename)[1].lower()
        unique_name = f"{uuid.uuid4()}{ext}"

        # Square crop
        h, w = img.shape[:2]
        side_length = min(h, w)
        cropped = img[0:side_length, 0:side_length]

        # Save
        file_path = os.path.join(app.root_path, "images/", unique_name)
        iio.imwrite(file_path, cropped)

        # update session & DB
        session["avatar"] = unique_name
        users_collection.update_one(
            {"username": session["username"]},
            {"$set": {"avatar": unique_name}})

        return redirect(url_for("avatar"))

    return render_template("change-avatar.html")


@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/player-statistics")
def stats():
    return render_template("player-statistics.html")

@app.route("/achievements")
def achievements():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("achievements.html")

@app.route("/direct-messaging")
def messaging():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("direct-messaging.html")

@app.route("/play")
def play():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template(
        "play.html",
        PLAYER_USERNAME=session["username"],
        PLAYER_AVATAR=session.get("avatar", "user.webp")
    )

@app.route("/api/users/@me")
def get_current_user():
    if "username" in session and users_collection.find_one({"username": session["username"]}):
        return jsonify({
            "id": True,
            "username": session["username"],
            "avatar": session.get("avatar", "user.webp")
        })
    return jsonify({"id": None})

# ---------- WebSocket setup for /game namespace ----------

socketio = SocketIO(app, cors_allowed_origins="*")

# Game grid settings (must match client!)
TILE_SIZE  = 50
GRID_COLS  = 500
GRID_ROWS  = 500
GRID_WIDTH = TILE_SIZE * GRID_COLS
GRID_HEIGHT= TILE_SIZE * GRID_ROWS

# Time interval for state transition (2 seconds)
TILE_STATE_TRANSITION_DELAY = timedelta(seconds=2)

# In‑memory game state
tile_states     = {}  # map "col,row" → int state
tile_timestamps = {}  # map "col,row" → datetime when set to 1
players         = {}  # sid → { x, y, username, avatar }

def _me():
    return {
        "username": session.get("username"),
        "avatar":   session.get("avatar", "user.webp")
    }

@socketio.on('connect', namespace='/game')
def ws_connect():
    sid = request.sid
    players[sid] = {
        "x": GRID_WIDTH / 2,
        "y": GRID_HEIGHT / 2,
        **_me()
    }
    emit('tile-init', {'tileStates': tile_states}, namespace='/game')
    emit('players', {'players': players}, namespace='/game', broadcast=True)

@socketio.on('move', namespace='/game')
def handle_move(data):
    sid = request.sid
    if sid not in players:
        players[sid] = {'x': 0, 'y': 0, **_me()}
    players[sid].update({
        'x': data['x'],
        'y': data['y'],
        **_me()
    })
    emit('players', {'players': players}, namespace='/game', broadcast=True)

@socketio.on('tile', namespace='/game')
def handle_tile(data):
    key = data['key']
    now = datetime.now()

    # 0 → 1
    if tile_states.get(key, 0) == 0:
        tile_states[key]     = 1
        tile_timestamps[key] = now
        emit('tile-update', {'key': key, 'state': 1},
             namespace='/game', broadcast=True)

    # 1 → 2 after delay
    due = []
    for k, st in list(tile_states.items()):
        if st == 1 and now - tile_timestamps.get(k, now) >= TILE_STATE_TRANSITION_DELAY:
            tile_states[k] = 2
            del tile_timestamps[k]
            due.append(k)

    for k in due:
        emit('tile-update', {'key': k, 'state': 2},
             namespace='/game', broadcast=True)

    # re‑broadcast clicked tile
    emit('tile-update', {'key': key, 'state': tile_states[key]},
         namespace='/game', broadcast=True)

@socketio.on('disconnect', namespace='/game')
def ws_disconnect():
    sid = request.sid
    players.pop(sid, None)
    emit('players', {'players': players}, namespace='/game', broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
