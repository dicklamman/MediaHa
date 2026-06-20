# -*- coding: utf-8 -*-
"""Authentication routes."""
from flask import jsonify, request, session, redirect


def register_auth_routes(app, AUTH_USERNAME, AUTH_PASSWORD):
    """Register authentication routes."""

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.json or {}
        username = data.get("username", "")
        password = data.get("password", "")

        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session["authenticated"] = True
            return jsonify({"success": True})

        return jsonify({"error": "Invalid username or password"}), 401

    @app.route('/api/logout', methods=['POST'])
    def logout():
        session.clear()
        return jsonify({"success": True})

    @app.route('/api/auth/status', methods=['GET'])
    def auth_status():
        """Check if the current user is authenticated"""
        return jsonify({"authenticated": session.get("authenticated", False)})
