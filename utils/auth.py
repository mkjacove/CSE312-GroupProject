from flask import Blueprint, render_template, request, redirect, url_for, abort, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import users_collection
import re

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
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            print(f"✅ Logged in as {username}")
            session.permanent = True
            session["username"] = user["username"]
            session["avatar"] = user.get("avatar", "user.webp")
            return "logged in", 200
        else:
            print("❌ Invalid login")
            return "Invalid username or password.", 401

    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if users_collection.find_one({"username": username}):
            print("❌ Username already exists")
            # Return HTTP 400 Bad Request for this error
            return "Username already exists.", 400

        valid, message = is_valid_password(password)
        if not valid:
            print(f"❌ {message}")
            # Return HTTP 400 Bad Request for invalid password
            return message, 400

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({"username": username, "password": hashed_password, "avatar": "user.webp"})

        print(f"✅ Registered user: {username}")
        return "User is registered now!", 200

    return render_template("register.html")

@auth_bp.route("/logout")
def logout():
    username = session.get("username")
    if username:
        print(f"✅ User logged out: {username}")
    session.clear()
    return redirect(url_for("home"))
