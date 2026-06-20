# -*- coding: utf-8 -*-
"""Web routes for UI serving."""
import os
from flask import send_from_directory, redirect, session, make_response


def register_web_routes(app):
    """Register web routes."""
    # Use absolute path based on this file's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ui_folder = os.path.join(base_dir, 'ui')
    pages_folder = os.path.join(ui_folder, 'pages')
    js_folder = os.path.join(ui_folder, 'js')

    @app.route('/')
    def index():
        """Redirect to home page or login based on auth state."""
        if session.get("authenticated"):
            return send_from_directory(pages_folder, 'home.html')
        return send_from_directory(ui_folder, 'login.html')

    @app.route('/home.html')
    def home():
        """Serve the home page."""
        if not session.get("authenticated"):
            return send_from_directory(ui_folder, 'login.html')
        return send_from_directory(pages_folder, 'home.html')

    @app.route('/<path:filename>')
    def serve_ui(filename):
        """Serve files from ui or pages directory."""
        # Serve static files from root ui folder without auth check
        root_path = os.path.join(ui_folder, filename)
        if os.path.exists(root_path) and os.path.isfile(root_path):
            return send_from_directory(ui_folder, filename)

        # Serve JS files from js folder without auth check
        if filename.startswith('js/'):
            js_file = filename[3:]
            js_path = os.path.join(js_folder, js_file)
            if os.path.exists(js_path) and os.path.isfile(js_path):
                return send_from_directory(js_folder, js_file)

        # Serve page files - requires auth
        if not session.get("authenticated"):
            return send_from_directory(ui_folder, 'login.html')
        pages_path = os.path.join(pages_folder, filename)
        if os.path.exists(pages_path) and os.path.isfile(pages_path):
            return send_from_directory(pages_folder, filename)

        return f"File not found: {filename}", 404
