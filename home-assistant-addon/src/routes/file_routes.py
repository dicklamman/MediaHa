# -*- coding: utf-8 -*-
"""File operation routes."""
import os
import base64
import json
import sqlite3
from pathlib import Path
from flask import jsonify, request, send_from_directory, redirect, session, Response


MEDIA_DIR = '/media'


def register_file_routes(app, CALIBRE_CONFIG_PATH, ALIST_CONFIG_PATH, AUTH_USERNAME=None, AUTH_PASSWORD=None):
    """Register file operation routes."""
    _AUTH_USERNAME = AUTH_USERNAME
    _AUTH_PASSWORD = AUTH_PASSWORD

    @app.route('/api/files', methods=['GET'])
    def list_files():
        sub_dir = request.args.get('dir', '')
        target_dir = os.path.abspath(os.path.join(MEDIA_DIR, sub_dir))

        if not target_dir.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(target_dir):
            return jsonify([])

        items = []
        for item in os.listdir(target_dir):
            full_path = os.path.join(target_dir, item)
            rel_path = os.path.relpath(full_path, MEDIA_DIR).replace('\\', '/')

            if os.path.isdir(full_path):
                items.append({'name': item, 'type': 'folder', 'path': rel_path})
            elif item.lower().endswith(('.epub', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.lrc', '.jpg', '.jpeg', '.png', '.strm', '.mp4', '.ass', '.ssa')):
                items.append({'name': item, 'type': 'file', 'path': rel_path})

        items.sort(key=lambda x: (0 if x.get('type') == 'folder' else 1, x.get('name', '').lower()))
        return jsonify(items)

    @app.route('/api/download', methods=['GET'])
    def download_file():
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        return send_from_directory(directory, filename)

    @app.route('/api/rename', methods=['POST'])
    def rename_item():
        data = request.json
        old_rel_path = data.get('old_path')
        new_name = data.get('new_name')

        if not old_rel_path or not new_name:
            return jsonify({'error': 'Missing parameters'}), 400

        old_abs_path = os.path.abspath(os.path.join(MEDIA_DIR, old_rel_path))
        if not old_abs_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(old_abs_path):
            return jsonify({'error': 'File or folder not found'}), 404

        parent_dir = os.path.dirname(old_abs_path)
        new_abs_path = os.path.join(parent_dir, new_name)

        try:
            os.rename(old_abs_path, new_abs_path)
            return jsonify({'message': 'Renamed successfully'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/convert-file', methods=['POST'])
    def convert_file_htmx():
        """HTMX endpoint for file conversion - returns HTML instead of JSON."""
        file_path = None

        # Try form data first (hx-include sends as form data)
        file_path = request.form.get('file_path')

        # Fallback to JSON
        if not file_path:
            try:
                data = request.get_json(force=True, silent=True)
                if data:
                    file_path = data.get('file_path')
            except:
                pass

        if not file_path:
            return '<p class="error">No file selected</p>'

        abs_path = os.path.abspath(os.path.join(MEDIA_DIR, file_path))
        if not abs_path.startswith(os.path.abspath(MEDIA_DIR)):
            return '<p class="error">Access denied</p>'

        if not os.path.exists(abs_path):
            return '<p class="error">File not found</p>'

        try:
            from utils.epub_converter import convert_to_hk_traditional_chinese

            output_filename = convert_to_hk_traditional_chinese(abs_path)
            return f'''
                <p class="success">Conversion complete!</p>
                <p>Output: {output_filename}</p>
            '''
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f'<p class="error">Error: {str(e)}</p>'

    @app.route('/fetch/<int:book_id>/<format>', methods=['GET'])
    @app.route('/opds/fetch/<int:book_id>/<format>', methods=['GET'])
    def fetch_book(book_id, format):
        """Serve book files for OPDS/Calibre-Web readers (COPS/Yomu)"""
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        try:
            authenticated = session.get("authenticated", False)
            if not authenticated:
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Basic '):
                    try:
                        encoded = auth_header[6:]
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        username, password = decoded.split(':', 1)
                        if username == _AUTH_USERNAME and password == _AUTH_PASSWORD:
                            session["authenticated"] = True
                            authenticated = True
                    except:
                        pass

            if not authenticated:
                return Response('Authentication required', status=401, mimetype='text/plain',
                               headers={'WWW-Authenticate': 'Basic realm="MediaHa"'})

            calibre_library = request.args.get('calibre_library')
            if not calibre_library:
                if os.path.exists(CALIBRE_CONFIG_PATH):
                    with open(CALIBRE_CONFIG_PATH, 'r') as f:
                        config = json.load(f)
                        calibre_library = config.get('calibre_library_path', '')

            if not calibre_library:
                return Response(f'Calibre library not configured: {CALIBRE_CONFIG_PATH}', status=400, mimetype='text/plain')

            calibre_path = Path(calibre_library)
            metadata_db = Path(calibre_library) / 'metadata.db'

            if not metadata_db.exists():
                return Response(f'metadata.db not found: {metadata_db}', status=500, mimetype='text/plain')

            books_folder = calibre_path / 'books' if (calibre_path / 'books').exists() else calibre_path

            conn = sqlite3.connect(str(metadata_db), timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT name, format FROM data WHERE book = ? AND format = ?", (book_id, format.upper()))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response(f'Format {format.upper()} not found for book {book_id}', status=404, mimetype='text/plain')

            filename = row[0]
            if not os.path.splitext(filename)[1]:
                filename = filename + '.' + format.lower()
            book_folder = books_folder / str(book_id)
            file_path = book_folder / filename
            format_lower = format.lower()

            # Try Alist streaming first
            if os.path.exists(ALIST_CONFIG_PATH):
                try:
                    with open(ALIST_CONFIG_PATH, 'r') as f:
                        alist_config = json.load(f)
                        alist_url = alist_config.get('alist_url')
                        alist_user = alist_config.get('username', 'admin')
                        alist_pass = alist_config.get('password', '')
                        if alist_url:
                            try:
                                from utils.alist_strm import get_alist_token, get_file_sign
                                token = get_alist_token(alist_url, alist_user, alist_pass)
                                remote_path = str(book_folder / filename)
                                sign = get_file_sign(alist_url, remote_path, token)
                                if sign:
                                    stream_url = f"{alist_url.rstrip('/')}/d{remote_path}?sign={sign}"
                                    return redirect(stream_url)
                            except Exception as e:
                                logger.debug(f'Alist streaming failed: {e}')
                                pass
                except Exception:
                    pass

            def path_exists_quick(p):
                try:
                    return p.exists()
                except:
                    return False

            found_file = None

            # Strategy 1: Exact path in book folder
            if path_exists_quick(file_path):
                found_file = file_path

            # Strategy 2: Exact path in root Calibre folder
            if not found_file:
                root_file = calibre_path / filename
                if path_exists_quick(root_file):
                    found_file = root_file

            # Strategy 3: Search entire Calibre library folder
            if not found_file:
                title_without_ext = os.path.splitext(filename)[0]
                for f in calibre_path.iterdir():
                    if f.is_file():
                        if f.name == filename or f.stem == title_without_ext or title_without_ext in f.stem:
                            if f.suffix.lower() == f'.{format_lower}':
                                found_file = f
                                break

            # Strategy 4: Search book folder for any matching format file
            if not found_file and path_exists_quick(book_folder):
                for f in book_folder.iterdir():
                    if f.suffix.lower() == f'.{format_lower}':
                        found_file = f
                        break

            if not found_file:
                return Response(f'Book file not found: {filename} in {book_folder}', status=404, mimetype='text/plain')

            file_path = found_file
            file_folder = file_path.parent
            filename = file_path.name

            response = send_from_directory(str(file_folder), filename)
            if format_lower == 'epub':
                response.headers['Content-Type'] = 'application/epub+zip'
            elif format_lower == 'mobi':
                response.headers['Content-Type'] = 'application/x-mobipocket-ebook'
            elif format_lower == 'pdf':
                response.headers['Content-Type'] = 'application/pdf'
            safe_filename = filename.encode('ascii', 'replace').decode('ascii').replace('?', '_')
            response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
            return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(f'Error: {str(e)}\n{traceback.format_exc()}', status=500, mimetype='text/plain')
