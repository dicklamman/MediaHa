# -*- coding: utf-8 -*-
"""Configuration routes for Alist, Calibre, and Dropbox."""
import os
import json
from flask import request, jsonify, Response, stream_with_context


def register_config_routes(app, ALIST_CONFIG_PATH, CALIBRE_CONFIG_PATH, DROPBOX_CONFIG_PATH):
    """Register configuration routes."""

    # Alist settings
    @app.route('/api/alist/settings', methods=['GET'])
    def get_alist_settings():
        if os.path.exists(ALIST_CONFIG_PATH):
            with open(ALIST_CONFIG_PATH, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({})

    @app.route('/api/alist/settings', methods=['POST'])
    def save_alist_settings():
        data = request.json
        os.makedirs(os.path.dirname(ALIST_CONFIG_PATH), exist_ok=True)
        with open(ALIST_CONFIG_PATH, 'w') as f:
            json.dump(data, f)
        return jsonify({'status': 'ok'})

    @app.route('/api/alist/run', methods=['POST'])
    def run_alist():
        if os.path.exists(ALIST_CONFIG_PATH):
            with open(ALIST_CONFIG_PATH, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        from utils.alist_strm import generate_strm_generator
        
        def generate():
            gen = generate_strm_generator(config)
            for chunk in gen:
                yield chunk
        
        return Response(stream_with_context(generate()), mimetype='text/plain',
                       headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})

    # Dropbox settings
    @app.route('/api/dropbox/settings', methods=['GET'])
    def get_dropbox_settings():
        if os.path.exists(DROPBOX_CONFIG_PATH):
            with open(DROPBOX_CONFIG_PATH, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({})

    @app.route('/api/dropbox/settings', methods=['POST'])
    def save_dropbox_settings():
        data = request.json
        os.makedirs(os.path.dirname(DROPBOX_CONFIG_PATH), exist_ok=True)
        with open(DROPBOX_CONFIG_PATH, 'w') as f:
            json.dump(data, f)
        return jsonify({'status': 'ok'})

    @app.route('/api/dropbox/run', methods=['POST'])
    def run_dropbox_sync():
        data = request.json
        target = data.get('target', '')

        config = {}
        if os.path.exists(DROPBOX_CONFIG_PATH):
            with open(DROPBOX_CONFIG_PATH, 'r') as f:
                config = json.load(f)

        app_key = config.get('app_key', '')
        app_secret = config.get('app_secret', '')
        refresh_token = config.get('refresh_token', '')

        from utils.dropbox_sync import run_sync
        return Response(run_sync(target, app_key, app_secret, refresh_token), mimetype='text/plain')

    # Calibre settings
    @app.route('/api/calibre/settings', methods=['GET'])
    def get_calibre_settings():
        default_config = {
            "calibre_url": "http://localhost:8080",
            "username": "admin",
            "password": "admin",
            "epub_folder": "/media/eBook",
            "comic_folder": "/media/comic",
            "clear_before_sync": False
        }
        if os.path.exists(CALIBRE_CONFIG_PATH):
            try:
                with open(CALIBRE_CONFIG_PATH, 'r') as f:
                    return jsonify(json.load(f))
            except Exception:
                pass
        return jsonify(default_config)

    @app.route('/api/calibre/settings', methods=['POST'])
    def save_calibre_settings():
        data = request.json
        try:
            os.makedirs(os.path.dirname(CALIBRE_CONFIG_PATH), exist_ok=True)
            with open(CALIBRE_CONFIG_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            return jsonify({'status': 'ok', 'message': 'Settings saved successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
