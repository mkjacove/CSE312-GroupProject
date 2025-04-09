from flask import Flask, render_template
from utils.auth import auth_bp

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"

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
    return render_template("direct-messaging.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
