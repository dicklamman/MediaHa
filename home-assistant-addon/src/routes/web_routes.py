# -*- coding: utf-8 -*-
"""Web routes for UI serving."""
import os
from flask import send_from_directory


def register_web_routes(app):
    """Register web routes."""

    @app.route('/')
    def index():
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), '..', 'ui'),
            'index.html'
        )

    @app.route('/<path:filename>')
    def serve_ui(filename):
        # Check if file exists in root ui folder first
        root_path = os.path.join(os.path.dirname(__file__), '..', 'ui', filename)
        if os.path.exists(root_path):
            return send_from_directory(
                os.path.join(os.path.dirname(__file__), '..', 'ui'),
                filename
            )
        # Otherwise try pages folder
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), '..', 'ui', 'pages'),
            filename
        )
