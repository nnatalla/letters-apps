import re
import secrets
from flask import Blueprint, request, jsonify, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Rejestracja nowego uzytkownika z walidacją hasła i tokenem aktywacyjnym."""
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        password2 = data.get("password2") or ""

        if not email or not password:
            return jsonify({"success": False, "message": "Email i hasło są wymagane."}), 400

        if password != password2:
            return jsonify({"success": False, "message": "Hasła nie są identyczne."}), 400

        if len(password) < 8:
            return jsonify({"success": False, "message": "Hasło musi mieć co najmniej 8 znaków."}), 400

        if not re.search(r'[A-Z]', password):
            return jsonify({"success": False, "message": "Hasło musi zawierać co najmniej jedną wielką literę."}), 400

        if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password):
            return jsonify({"success": False, "message": "Hasło musi zawierać co najmniej jeden znak specjalny."}), 400

        existing = User.query.filter_by(email=email).first()
        if existing:
            if not existing.is_active:
                return jsonify({"success": False, "message": "Konto o tym emailu istnieje, ale nie zostało aktywowane.", "inactive": True}), 409
            return jsonify({"success": False, "message": "Użytkownik o tym emailu już istnieje."}), 409

        token = secrets.token_urlsafe(32)
        user = User(email=email, is_active=False, activation_token=token)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        activation_link = url_for("auth.activate", token=token, _external=True)

        return jsonify({
            "success": True,
            "message": "Konto utworzone. Sprawdź skrzynkę email aby aktywować konto.",
            "activation_link": activation_link,
            "email": email,
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Błąd rejestracji: {str(e)}"}), 500


@auth_bp.route("/activate/<token>", methods=["GET"])
def activate(token):
    """Aktywacja konta przez link z emaila."""
    user = User.query.filter_by(activation_token=token).first()
    if not user:
        return """<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8">
<title>Błąd aktywacji</title>
<style>body{font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:linear-gradient(135deg,#0f4c81,#1976d2,#42a5f5);}
.panel{background:#fff;border-radius:18px;padding:40px 36px;max-width:420px;text-align:center;
box-shadow:0 20px 60px rgba(0,0,0,.2);}h2{color:#c62828;margin-bottom:12px;}
a{display:inline-block;margin-top:20px;padding:11px 24px;background:#1976d2;color:#fff;
text-decoration:none;border-radius:10px;font-weight:700;}</style></head>
<body><div class="panel"><h2>&#10006; Nieprawidłowy link</h2>
<p style="color:#666">Link aktywacyjny jest nieprawidłowy lub wygasł.</p>
<a href="/">Wróć do logowania</a></div></body></html>""", 400

    user.is_active = True
    user.activation_token = None
    db.session.commit()

    return """<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8">
<title>Konto aktywowane</title>
<style>body{font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:linear-gradient(135deg,#0f4c81,#1976d2,#42a5f5);}
.panel{background:#fff;border-radius:18px;padding:40px 36px;max-width:420px;text-align:center;
box-shadow:0 20px 60px rgba(0,0,0,.2);}h2{color:#2e7d32;margin-bottom:12px;}
a{display:inline-block;margin-top:20px;padding:11px 24px;background:#1976d2;color:#fff;
text-decoration:none;border-radius:10px;font-weight:700;}</style></head>
<body><div class="panel"><h2>&#10003; Konto aktywowane!</h2>
<p style="color:#666">Możesz się teraz zalogować.</p>
<a href="/">Przejdź do logowania</a></div></body></html>"""


@auth_bp.route("/resend-activation", methods=["POST"])
def resend_activation():
    """Ponowne wysłanie tokenu aktywacyjnego dla nieaktywnego konta."""
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"success": False, "message": "Email jest wymagany."}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"success": False, "message": "Nie znaleziono konta o tym emailu."}), 404
        if user.is_active:
            return jsonify({"success": False, "message": "Konto jest już aktywne. Możesz się zalogować."}), 400

        token = secrets.token_urlsafe(32)
        user.activation_token = token
        db.session.commit()

        activation_link = url_for("auth.activate", token=token, _external=True)
        return jsonify({
            "success": True,
            "message": "Nowy link aktywacyjny został wygenerowany.",
            "activation_link": activation_link,
            "email": email,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Błąd: {str(e)}"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Logowanie uzytkownika."""
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not email or not password:
            return jsonify({"success": False, "message": "Email i haslo sa wymagane."}), 400

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({"success": False, "message": "Nieprawidlowy email lub haslo."}), 401

        if not user.is_active:
            return jsonify({"success": False, "message": "Konto jest nieaktywne. Aktywuj je klikając link wysłany na email.", "inactive": True}), 403

        login_user(user)
        return jsonify({"success": True, "message": "Zalogowano pomyslnie.", "user": user.to_dict()}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Blad logowania: {str(e)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Wylogowanie uzytkownika."""
    try:
        logout_user()
        return jsonify({"success": True, "message": "Wylogowano pomyslnie."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Blad wylogowania: {str(e)}"}), 500


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Dane aktualnie zalogowanego uzytkownika."""
    try:
        return jsonify({"success": True, "user": current_user.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Blad pobierania danych: {str(e)}"}), 500
