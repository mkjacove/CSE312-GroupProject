from datetime import timedelta
from flask import Flask, request, render_template, jsonify, session
from utils.auth import auth_bp
#testaccount, theone, pass = T1h2e3%%One

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)


@app.route("/")
def home():
    return render_template("home.html")
@app.route("/change-avatar")
def avatar():
    return render_template("change-avatar.html")
@app.route("/play")
def play():
    return render_template("play.html")
@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")
@app.route("/player-statistics")
def stats():
    return render_template("player-statistics.html")
@app.route("/achievements")
def achievements():
    return render_template("achievements.html")
@app.route("/direct-messaging")
def messaging():
    return render_template("direct-messaging.html")  #Apparently, doing this just returns a 200 OK response

@app.route("/api/users/@me")
def get_current_user():
    if "username" in session:
        return jsonify({"id": True, "username": session["username"]})
    return jsonify({"id": None})

@app.route("/canvas")
def canvas():
    return render_template("canvas.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
