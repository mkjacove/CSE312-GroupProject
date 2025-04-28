from flask import Blueprint, render_template, request, redirect, url_for, abort, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import users_collection
import re
from flask import current_app

auth_bp = Blueprint("auth", __name__, url_prefix="")

def is_valid_password(password):
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must include at least one special character."
    return True, None

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            print(f"✅ Logged in as {username}")
            current_app.logger.info(f"{username} successfully logged in")
            session.permanent = True
            session["username"] = user["username"]
            session["avatar"] = user.get("avatar", "user.webp")
            session["current_tiles"] = 0
            session["games_played"] = user.get("games_played")
            session["average_tiles"] = user.get("average_tiles")
            session["games_won"] = user.get("games_won")

            return "logged in", 200
        else:
            print("❌ Invalid login")
            current_app.logger.info(f"A user tried to log in as {username}, but the username or password was incorrect")

            return "Invalid username or password.", 401

    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if users_collection.find_one({"username": username}):

            print("❌ Username already exists")
            current_app.logger.info(f"{username} tried to register, but that username already exists")

            # Return HTTP 400 Bad Request for this error
            return "Username already exists.", 400

        valid, message = is_valid_password(password)
        if not valid:
            print(f"❌ {message}")
            current_app.logger.info(f"{username} tried to register, but their password was invalid")

            # Return HTTP 400 Bad Request for invalid password
            return message, 400

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({"username": username, "password": hashed_password, "avatar": "user.webp",
                                     "current_tiles": 0, "games_played":0,"games_won":0, "average_tiles":0})

        print(f"✅ Registered user: {username}")
        current_app.logger.info(f"{username} successfully registered")

        return "User is registered now!", 200

    return render_template("register.html")

@auth_bp.route("/logout")
def logout():
    username = session.get("username")
    if username:
        print(f"✅ User logged out: {username}")
        current_app.logger.info(f"{username} logged out successfully")

    session.clear()
    return redirect(url_for("home"))
