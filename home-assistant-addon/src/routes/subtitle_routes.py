# -*- coding: utf-8 -*-
"""Subtitle (ASS/SSA) routes."""
import os
import re
from flask import request, jsonify


MEDIA_DIR = '/media'


def register_subtitle_routes(app):
    """Register subtitle route handlers."""

    @app.route('/api/ass/read', methods=['GET'])
    def read_ass_file():
        """Read an ASS/SSA subtitle file"""
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            return jsonify({'content': content})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ass/save', methods=['POST'])
    def save_ass_file():
        """Save an ASS/SSA subtitle file with optional time offset"""
        data = request.json
        file_name = data.get('file_name')
        content = data.get('content')
        offset_seconds = data.get('offset', 0)

        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        try:
            if content is None:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()

            if offset_seconds != 0:
                def convert_time(time_str):
                    """Convert ASS time format (H:MM:SS.CC) to seconds"""
                    match = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', time_str)
                    if match:
                        h, m, s, cs = match.groups()
                        total = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                        return total
                    return None

                def format_time(seconds):
                    """Convert seconds back to ASS time format"""
                    h = int(seconds // 3600)
                    m = int((seconds % 3600) // 60)
                    s = int(seconds % 60)
                    cs = int((seconds % 1) * 100)
                    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

                def offset_timestamp(match):
                    """Offset a timestamp by the specified amount"""
                    start = convert_time(match.group(2))
                    end = convert_time(match.group(3))
                    if start is not None and end is not None:
                        new_start = max(0, start + offset_seconds)
                        new_end = max(0, end + offset_seconds)
                        return f"{match.group(1)}{format_time(new_start)},{format_time(new_end)}"
                    return match.group(0)

                content = re.sub(
                    r'(Dialogue: \d+,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})',
                    offset_timestamp,
                    content
                )

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)

            return jsonify({
                'success': True,
                'message': f'File saved successfully' + (
                    f' with {offset_seconds:+d}s offset' if offset_seconds != 0 else ''
                )
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ass/preview', methods=['POST'])
    def preview_ass_offset():
        """Preview what the ASS file would look like with time offset applied"""
        data = request.json
        file_name = data.get('file_name')
        offset_seconds = data.get('offset', 0)

        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            preview_lines = []
            dialogue_count = 0
            max_previews = 10

            def convert_time(time_str):
                """Convert ASS time format (H:MM:SS.CC) to seconds"""
                match = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', time_str)
                if match:
                    h, m, s, cs = match.groups()
                    total = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                    return total
                return None

            def format_time(seconds):
                """Convert seconds back to ASS time format"""
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                cs = int((seconds % 1) * 100)
                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

            def preview_timestamp(match):
                nonlocal dialogue_count
                start_orig = convert_time(match.group(2))
                end_orig = convert_time(match.group(3))
                if start_orig is not None and end_orig is not None:
                    start_new = max(0, start_orig + offset_seconds)
                    end_new = max(0, end_orig + offset_seconds)
                    dialogue_count += 1
                    if dialogue_count <= max_previews:
                        preview_lines.append({
                            'index': dialogue_count,
                            'original': f"{format_time(start_orig)},{format_time(end_orig)}",
                            'modified': f"{format_time(start_new)},{format_time(end_new)}"
                        })
                    return f"{format_time(start_new)},{format_time(end_new)}"
                return match.group(0)

            re.sub(
                r'(Dialogue: \d+,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})',
                preview_timestamp,
                content
            )

            return jsonify({
                'preview': preview_lines,
                'total_dialogues': dialogue_count,
                'offset': offset_seconds
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
