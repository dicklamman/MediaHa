# -*- coding: utf-8 -*-
"""Web routes for UI serving."""
import os
from flask import send_from_directory, redirect, session


def register_web_routes(app):
    """Register web routes."""
    # Use absolute path based on this file's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ui_folder = os.path.join(base_dir, 'ui')
    pages_folder = os.path.join(ui_folder, 'pages')
    js_folder = os.path.join(ui_folder, 'js')

    # =========================================
    # Static file routes (no auth required)
    # =========================================

    @app.route('/styles.css')
    def styles():
        """Serve the CSS file."""
        return send_from_directory(ui_folder, 'styles.css')

    @app.route('/login.js')
    def login_js():
        """Serve the login JS file."""
        return send_from_directory(ui_folder, 'login.js')

    @app.route('/favicon.ico')
    def favicon():
        """Serve the favicon."""
        favicon_path = os.path.join(ui_folder, 'favicon.ico')
        if os.path.exists(favicon_path):
            return send_from_directory(ui_folder, 'favicon.ico')
        return "", 404

    @app.route('/js/<path:filename>')
    def js_files(filename):
        """Serve JS files from the js folder."""
        return send_from_directory(js_folder, filename)

    # =========================================
    # Auth-aware page routes
    # =========================================

    @app.route('/')
    def index():
        """Serve home page or login based on auth state."""
        if session.get("authenticated"):
            return send_from_directory(pages_folder, 'home.html')
        return send_from_directory(ui_folder, 'login.html')

    @app.route('/home.html')
    def home():
        """Serve the home page."""
        if not session.get("authenticated"):
            return send_from_directory(ui_folder, 'login.html')
        return send_from_directory(pages_folder, 'home.html')

    @app.route('/login.html')
    def login_page():
        """Serve the login page if not authenticated."""
        if session.get("authenticated"):
            return send_from_directory(pages_folder, 'home.html')
        return send_from_directory(ui_folder, 'login.html')

    @app.route('/pages/<path:filename>')
    def pages_files(filename):
        """Serve page files - requires auth."""
        if not session.get("authenticated"):
            return send_from_directory(ui_folder, 'login.html')
        return send_from_directory(pages_folder, filename)

    # =========================================
    # Catch-all for other static files
    # =========================================

    @app.route('/<path:filename>')
    def serve_ui(filename):
        """Serve other files from ui directory."""
        # Try root ui folder first
        root_path = os.path.join(ui_folder, filename)
        if os.path.exists(root_path) and os.path.isfile(root_path):
            return send_from_directory(ui_folder, filename)

        # Try pages folder (requires auth)
        if not session.get("authenticated"):
            return send_from_directory(ui_folder, 'login.html')
        pages_path = os.path.join(pages_folder, filename)
        if os.path.exists(pages_path) and os.path.isfile(pages_path):
            return send_from_directory(pages_folder, filename)

        return f"File not found: {filename}", 404
