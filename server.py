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
import random

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
tile_states = {
    1: {},
    2: {},
    3: {}
}
tile_timestamps = {
    1: {},
    2: {},
    3: {}
}
players         = {}  # sid → { x, y, username, board_level, avatar }

def _me():
    return {
        "username": session.get("username"),
        "avatar":   session.get("avatar", "user.webp")
    }

def find_random_white_tile(board_level):
    """Find a random (x, y) on a white tile (state == 0)."""
    for _ in range(250):
        col = random.randint(0, GRID_COLS - 1)
        row = random.randint(0, GRID_ROWS - 1)
        key = f"{col},{row}"
        print("yummy board ", board_level, tile_states[board_level])
        if key not in tile_states[board_level] or tile_states[board_level][key] == 0:
            x = col * TILE_SIZE + TILE_SIZE / 2
            y = row * TILE_SIZE + TILE_SIZE / 2
            return x, y
    # fallback: center if nothing found
    return GRID_WIDTH / 2, GRID_HEIGHT / 2

@socketio.on('connect', namespace='/game')
def ws_connect():
    sid = request.sid

    spawn_x, spawn_y = find_random_white_tile(1)
    players[sid] = {
        "x": spawn_x,
        "y": spawn_y,
        "board_level": 1,
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
    sid = request.sid
    player = players.get(sid)
    if not player:
        return

    board = player.get('board_level', 1)
    key = data['key']
    now = datetime.now()

    if tile_states[board].get(key, 0) == 0:
        tile_states[board][key] = 1
        tile_timestamps[board][key] = now
        emit('tile-update', {'key': key, 'state': 1, 'board': board},
             namespace='/game', broadcast=True)

    # 1 ➔ 2 after delay
    due = []
    for k, st in list(tile_states[board].items()):
        if st == 1 and now - tile_timestamps[board].get(k, now) >= TILE_STATE_TRANSITION_DELAY:
            tile_states[board][k] = 2
            del tile_timestamps[board][k]
            due.append(k)

    for k in due:
        emit('tile-update', {'key': k, 'state': 2, 'board': board},
             namespace='/game', broadcast=True)

    # re‑broadcast clicked tile
    emit('tile-update', {'key': key, 'state': tile_states[board].get(key, 0), 'board': board},
         namespace='/game', broadcast=True)

@socketio.on('reset', namespace='/game')
def handle_reset():
    sid = request.sid
    player = players.get(sid)
    if not player:
        return

    current_board = player.get('board_level', 1)
    if current_board < 3:
        # move player to next board
        players[sid]['board_level'] = current_board + 1

        # reposition player back to a random location
        spawn_x, spawn_y = find_random_white_tile(board_level=current_board + 1)
        players[sid]['x'] = spawn_x
        players[sid]['y'] = spawn_y

        # tell client maybe (optional: pop-up "Level 2!")
        emit('chat', {'text': f"{player['username']} advanced to Board {current_board+1}!"}, namespace='/game', broadcast=True)

    else:
        # eliminate player
        emit('chat', {'text': f"{player['username']} was eliminated!"}, namespace='/game', broadcast=True)

        # notify *only* the eliminated player to redirect
        emit('eliminated', {'redirect': '/'}, namespace='/game', to=sid)

        players.pop(sid, None)
        emit('players', {'players': players}, namespace='/game', broadcast=True)


@socketio.on('disconnect', namespace='/game')
def ws_disconnect():
    sid = request.sid
    players.pop(sid, None)
    emit('players', {'players': players}, namespace='/game', broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
