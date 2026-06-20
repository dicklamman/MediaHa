# -*- coding: utf-8 -*-
"""
MediaHa - Flask Application Entry Point

A Home Assistant add-on to convert EPUB books and enhance MP3 files.
"""
import os
import json

# =============================================================================
# Authentication Configuration
# =============================================================================

def load_auth_config():
    """
    Load addon authentication settings from Home Assistant options.
    Falls back to simple defaults if options are missing.
    """
    env_user = os.environ.get("MEDIAHA_USERNAME")
    env_pass = os.environ.get("MEDIAHA_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass

    options_path = "/data/options.json"
    username = "mediaha"
    password = "changeme"

    try:
        if os.path.exists(options_path):
            with open(options_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            username = data.get("username") or username
            password = data.get("password") or password
    except Exception:
        pass

    return username, password


AUTH_USERNAME, AUTH_PASSWORD = load_auth_config()


# =============================================================================
# Flask Application Setup
# =============================================================================

from flask import Flask, request, jsonify, redirect, session

app = Flask(__name__)
app.secret_key = "mediaha-" + (AUTH_PASSWORD or "default-secret")


# =============================================================================
# Configuration Paths
# =============================================================================

MEDIA_DIR = '/media'
CONFIG_DIR = '/data' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '..', 'config')

ALIST_CONFIG_PATH = os.path.join(CONFIG_DIR, 'alist_options.json')
CALIBRE_CONFIG_PATH = os.path.join(CONFIG_DIR, 'calibre_options.json')
DROPBOX_CONFIG_PATH = os.path.join(CONFIG_DIR, 'dropbox_options.json')


# =============================================================================
# Authentication Middleware
# =============================================================================

@app.before_request
def enforce_login():
    """Require login for API endpoints and protected routes."""
    path = request.path

    # Skip auth for static assets
    static_exts = (".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map")
    if any(path.endswith(ext) for ext in static_exts):
        return

    # Skip auth for public paths
    if path in ("/", "/login.html", "/login.js", "/favicon.ico", "/api/login", "/api/auth/status", "/health", "/opds"):
        return

    # Skip auth for static folder
    if path.startswith("/static/"):
        return

    # Allow JS files without auth
    if path.endswith(".js"):
        return

    # Allow calibre settings GET
    if path == "/api/calibre/settings" and request.method == 'GET':
        return

    # Allow fetch endpoints for OPDS readers
    if path.startswith("/fetch/"):
        return

    # Block unauthenticated API access
    if path.startswith("/api"):
        return jsonify({"error": "Unauthorized"}), 401


# =============================================================================
# Register Routes
# =============================================================================

from opds import register_routes as register_opds_routes
register_opds_routes(app, lambda u, p: u == AUTH_USERNAME and p == AUTH_PASSWORD)

from routes.auth_routes import register_auth_routes
register_auth_routes(app, AUTH_USERNAME, AUTH_PASSWORD)

from routes.web_routes import register_web_routes
register_web_routes(app)

from routes.file_routes import register_file_routes
register_file_routes(app, CALIBRE_CONFIG_PATH, ALIST_CONFIG_PATH)

from routes.audio_routes import register_audio_routes
register_audio_routes(app)

from routes.config_routes import register_config_routes
register_config_routes(app, ALIST_CONFIG_PATH, CALIBRE_CONFIG_PATH, DROPBOX_CONFIG_PATH)

from routes.special_routes import register_special_routes
register_special_routes(app)

from routes.subtitle_routes import register_subtitle_routes
register_subtitle_routes(app)

from routes.calibre_routes import register_calibre_routes
register_calibre_routes(app)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == '__main__':
    from waitress import serve
    print("Starting production WSGI server on port 5000...")
    serve(app, host='0.0.0.0', port=5000)
