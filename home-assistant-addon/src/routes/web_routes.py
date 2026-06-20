# -*- coding: utf-8 -*-
"""Web routes for UI serving."""
import os
from flask import send_from_directory


def register_web_routes(app):
    """Register web routes."""
    # Use absolute path based on this file's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ui_folder = os.path.join(base_dir, 'ui')
    pages_folder = os.path.join(ui_folder, 'pages')
    js_folder = os.path.join(ui_folder, 'js')

    @app.route('/')
    def index():
        """Serve the redirect page to home."""
        return send_from_directory(ui_folder, 'index.html')

    @app.route('/<path:filename>')
    def serve_ui(filename):
        """Serve files from ui or pages directory."""
        # Check if it's a file in the root ui folder (styles.css, login.html, etc.)
        root_path = os.path.join(ui_folder, filename)
        if os.path.exists(root_path) and os.path.isfile(root_path):
            return send_from_directory(ui_folder, filename)

        # Check if it's a JS file in the js folder
        if filename.startswith('js/'):
            js_file = filename[3:]  # Remove 'js/' prefix
            js_path = os.path.join(js_folder, js_file)
            if os.path.exists(js_path) and os.path.isfile(js_path):
                return send_from_directory(js_folder, js_file)

        # Otherwise try pages folder
        pages_path = os.path.join(pages_folder, filename)
        if os.path.exists(pages_path) and os.path.isfile(pages_path):
            return send_from_directory(pages_folder, filename)

        # If neither found, return 404
        return f"File not found: {filename}", 404
