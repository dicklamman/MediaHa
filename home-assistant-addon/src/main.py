# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory, session, redirect, Response
import os
import base64
import re
import urllib.request
import json
import requests
import subprocess
import zipfile
import sqlite3
from pathlib import Path
import xml.etree.ElementTree as ET
from utils.epub_converter import convert_to_hk_traditional_chinese
from opds import register_routes as register_opds_routes

def extract_epub_metadata(epub_path):
    """
    Extract comprehensive metadata from an EPUB file.
    Returns dict with title, authors, cover, language, publisher, identifier, description, tags, date.
    """
    result = {
        'title': None, 'authors': [], 'cover_data': None, 'cover_name': None,
        'language': None, 'publisher': None, 'identifier': None,
        'description': None, 'tags': [], 'date': None
    }
    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            # Find container.xml to get content.opf location
            container = zf.read('META-INF/container.xml').decode('utf-8')
            root = ET.fromstring(container)
            rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
            if rootfile is not None:
                opf_path = rootfile.get('full-path')
                opf_content = zf.read(opf_path).decode('utf-8')
                opf_root = ET.fromstring(opf_content)
                ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
                
                # Get title
                title_el = opf_root.find('.//dc:title', ns)
                if title_el is not None and title_el.text:
                    result['title'] = title_el.text.strip()
                
                # Get authors/creators
                for creator in opf_root.findall('.//dc:creator', ns):
                    if creator.text:
                        result['authors'].append(creator.text.strip())
                
                # Get language
                lang_el = opf_root.find('.//dc:language', ns)
                if lang_el is not None and lang_el.text:
                    result['language'] = lang_el.text.strip()
                
                # Get publisher
                pub_el = opf_root.find('.//dc:publisher', ns)
                if pub_el is not None and pub_el.text:
                    result['publisher'] = pub_el.text.strip()
                
                # Get identifier (ISBN or UUID)
                for id_el in opf_root.findall('.//dc:identifier', ns):
                    if id_el.text:
                        id_text = id_el.text.strip()
                        id_val = id_el.text.strip()
                        # Check scheme attribute or content
                        scheme = id_el.get('{http://purl.org/dc/elements/1.1/}scheme') or id_el.get('scheme') or ''
                        if 'isbn' in scheme.lower() or 'isbn' in id_text.lower():
                            result['identifier'] = id_text
                        elif not result['identifier']:
                            result['identifier'] = id_text
                
                # Get description/synopsis
                desc_el = opf_root.find('.//dc:description', ns)
                if desc_el is not None and desc_el.text:
                    result['description'] = desc_el.text.strip()
                
                # Get tags/subjects
                for subj in opf_root.findall('.//dc:subject', ns):
                    if subj.text:
                        result['tags'].append(subj.text.strip())
                
                # Get date
                date_el = opf_root.find('.//dc:date', ns)
                if date_el is not None and date_el.text:
                    result['date'] = date_el.text.strip()
                
                # Get cover image
                cover_id = None
                meta_cover = opf_root.find('.//opf:meta[@name="cover"]', ns)
                if meta_cover is not None:
                    cover_id = meta_cover.get('content')
                if not cover_id:
                    for item in opf_root.findall('.//opf:item', ns):
                        props = item.get('properties', '')
                        if 'cover-image' in props:
                            cover_id = item.get('id')
                            break
                
                if cover_id:
                    for item in opf_root.findall('.//opf:item', ns):
                        if item.get('id') == cover_id:
                            href = item.get('href')
                            if href:
                                opf_dir = opf_path.rsplit('/', 1)[0] if '/' in opf_path else ''
                                cover_path = f"{opf_dir}/{href}" if opf_dir else href
                                cover_path = cover_path.lstrip('/')
                                try:
                                    result['cover_data'] = zf.read(cover_path)
                                    result['cover_name'] = os.path.basename(href)
                                except:
                                    pass
                            break
    except Exception as e:
        pass
    return result

def load_auth_config():
    """
    Load addon authentication settings from Home Assistant options.
    Falls back to simple defaults if options are missing.
    """
    # Environment variables override addon options (optional escape hatch)
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
        # On any error, keep defaults
        pass

    return username, password


AUTH_USERNAME, AUTH_PASSWORD = load_auth_config()

def check_auth(username, password):
    """Check if username and password are valid"""
    return username == AUTH_USERNAME and password == AUTH_PASSWORD

app = Flask(__name__)
app.secret_key = "mediaha-" + (AUTH_PASSWORD or "default-secret")

# Register OPDS routes
register_opds_routes(app, check_auth)

MEDIA_DIR = '/media'


@app.before_request
def enforce_login():
    """
    Require login for all HTML pages and API endpoints, except the login page
    and static assets.
    """
    path = request.path

    # Public paths
    if path in ("/api/login", "/api/auth/status", "/health", "/login.html", "/favicon.ico", "/opds"):
        return

    # Allow GET for calibre settings (for loading form on tab switch)
    if path == "/api/calibre/settings" and request.method == 'GET':
        return

    # Allow login.js (needed for the login page)
    if path in ("/js/login.js", "/login.js"):
        return

    # Protect all JS files (except login.js which is handled above)
    # Users must be authenticated to access any other JS
    if path.endswith(".js"):
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
        return

    # Allow static assets (CSS/fonts/images) but NOT JS
    static_exts = (
        ".css", ".png", ".jpg", ".jpeg", ".gif",
        ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map"
    )
    if path.startswith("/static/") or any(path.endswith(ext) for ext in static_exts):
        return

    # Already authenticated
    if session.get("authenticated"):
        return

    # Protect APIs with JSON 401
    if path.startswith("/api") or path == "/convert":
        return jsonify({"error": "Unauthorized"}), 401

    # Allow OPDS feed downloads (for COPS/Yomu readers)
    if path.startswith("/fetch/") or path.startswith("/fetch?"):
        return

    # For HTML pages, redirect to login
    if path == "/" or path.endswith(".html"):
        return redirect("/login.html")

    # Everything else falls through (e.g. media downloads) but still requires auth
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/')
def index():
    # If not authenticated, before_request will redirect to /login.html
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), 'index.html')

@app.route('/<path:filename>')
def serve_ui(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), filename)


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

@app.route('/api/files', methods=['GET'])
def list_files():
    sub_dir = request.args.get('dir', '')
    target_dir = os.path.abspath(os.path.join(MEDIA_DIR, sub_dir))

    # Security: Ensure we don't traverse outside MEDIA_DIR
    if not target_dir.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(target_dir):
        return jsonify([])

    # Get direct contents only (non-recursive)
    items = []
    for item in os.listdir(target_dir):
        full_path = os.path.join(target_dir, item)
        rel_path = os.path.relpath(full_path, MEDIA_DIR)

        # Windows compatibility for rel_path
        rel_path = rel_path.replace('\\', '/')

        if os.path.isdir(full_path):
            items.append({'name': item, 'type': 'folder', 'path': rel_path})
        elif item.lower().endswith(('.epub', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.lrc', '.jpg', '.jpeg', '.png', '.strm', '.mp4', '.ass', '.ssa')):
            items.append({'name': item, 'type': 'file', 'path': rel_path})

    # Sort folders first, then files
    items.sort(key=lambda x: (0 if x.get('type') == 'folder' else 1, x.get('name', '').lower()))
    return jsonify(items)

def get_all_audio_files(directory, base_dir):
    """Recursively get all audio files from directory and subdirectories"""
    items = []
    audio_extensions = ('.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.lrc')
    dir_extensions = ('.epub', '.jpg', '.jpeg', '.png', '.strm', '.mp4')

    for root, dirs, files in os.walk(directory):
        rel_root = os.path.relpath(root, base_dir).replace('\\\\', '/')

        # Add subdirectories as folders (only at the first level)
        if root == directory:
            for d in dirs:
                items.append({'name': d, 'type': 'folder', 'path': os.path.join(rel_root, d).replace('\\\\', '/')})

        # Add audio files from all subdirectories
        for f in files:
            if f.lower().endswith(audio_extensions) or f.lower().endswith(dir_extensions):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, base_dir).replace('\\\\', '/')
                items.append({'name': f, 'type': 'file', 'path': rel_path})

    return items

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


# OPDS/Calibre fetch endpoint for readers like Yomu
@app.route('/fetch/<int:book_id>/<format>', methods=['GET'])
def fetch_book(book_id, format):
    """Serve book files for OPDS/Calibre-Web readers (COPS/Yomu)"""
    import threading
    import queue as Queue
    
    try:
        # Check authentication for OPDS readers
        authenticated = session.get("authenticated", False)
        if not authenticated:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Basic '):
                try:
                    encoded = auth_header[6:]
                    decoded = base64.b64decode(encoded).decode('utf-8')
                    username, password = decoded.split(':', 1)
                    if check_auth(username, password):
                        session["authenticated"] = True
                        authenticated = True
                except:
                    pass
        
        if not authenticated:
            resp = jsonify({'error': 'Authentication required'})
            resp.headers['WWW-Authenticate'] = 'Basic realm="MediaHa"'
            return resp, 401

        calibre_library = request.args.get('calibre_library')
        if not calibre_library:
            config_path = CALIBRE_CONFIG_PATH
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    calibre_library = config.get('calibre_library_path', '')

        if not calibre_library:
            return jsonify({'error': 'Calibre library not configured'}), 400

        calibre_path = Path(calibre_library)
        
        # Handle Calibre's folder structure: library/books/{book_id}/
        if (calibre_path / 'books').exists() and (calibre_path / 'books').is_dir():
            calibre_path = calibre_path / 'books'
        
        metadata_db = Path(calibre_library) / 'metadata.db'

        if not metadata_db.exists():
            return jsonify({'error': 'metadata.db not found', 'path': str(metadata_db)}), 500

        # Get file path from Calibre database
        conn = sqlite3.connect(str(metadata_db), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name, format FROM data WHERE book = ? AND format = ?", (book_id, format.upper()))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'error': f'Format {format} not found for book {book_id}'}), 404

        filename = row[0]
        if not os.path.splitext(filename)[1]:
            filename = filename + '.' + format.lower()
        book_folder = calibre_path / str(book_id)
        file_path = book_folder / filename
        format_lower = format.lower()

        # Try Alist streaming first if configured (for network/cloud storage)
        alist_config_path = ALIST_CONFIG_PATH
        if os.path.exists(alist_config_path):
            try:
                with open(alist_config_path, 'r') as f:
                    alist_config = json.load(f)
                    alist_url = alist_config.get('alist_url')
                    username = alist_config.get('username', 'admin')
                    password = alist_config.get('password', '')
                    if alist_url:
                        try:
                            from utils.alist_strm import get_alist_token, get_file_sign
                            token = get_alist_token(alist_url, username, password)
                            remote_path = str(book_folder / filename)
                            sign = get_file_sign(alist_url, remote_path, token)
                            if sign:
                                stream_url = f"{alist_url.rstrip('/')}/d{remote_path}?sign={sign}"
                                return redirect(stream_url)
                        except Exception:
                            pass  # Fall through to local file if Alist fails
            except Exception:
                pass  # Fall through to local file if Alist fails

        def path_exists_quick(p):
            try:
                return p.exists()
            except:
                return False
        
        # Try multiple strategies to find the file
        found_file = None
        
        # Strategy 1: Exact path in book folder
        if path_exists_quick(file_path):
            found_file = file_path
        
        # Strategy 2: Exact path in root Calibre folder
        if not found_file:
            root_file = calibre_path / filename
            if path_exists_quick(root_file):
                found_file = root_file
        
        # Strategy 3: Search entire Calibre library folder for file by name
        if not found_file:
            title_without_ext = os.path.splitext(filename)[0]
            for f in calibre_path.iterdir():
                if f.is_file():
                    # Match by exact name or partial match
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
            # List ALL files in Calibre root for debugging
            all_files = [f.name for f in calibre_path.iterdir() if f.is_file()][:20]
            all_dirs = [d.name for d in calibre_path.iterdir() if d.is_dir()][:20]
            return jsonify({
                'error': 'Book file not found',
                'book_id': book_id,
                'format': format,
                'searched_filename': filename,
                'calibre_root': str(calibre_path),
                'book_folder': str(book_folder),
                'book_folder_exists': path_exists_quick(book_folder),
                'book_folder_contents': [f.name for f in book_folder.iterdir()] if path_exists_quick(book_folder) else [],
                'root_files_sample': all_files,
                'root_dirs_sample': all_dirs
            }), 404

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
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


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

    # Calculate new absolute path
    parent_dir = os.path.dirname(old_abs_path)
    new_abs_path = os.path.join(parent_dir, new_name)

    try:
        os.rename(old_abs_path, new_abs_path)
        return jsonify({'message': 'Renamed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert', methods=['POST'])
def convert():
    file_name = request.json.get('file_name')
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    input_path = os.path.join(MEDIA_DIR, file_name)
    if not os.path.exists(input_path):
        return jsonify({'error': 'File not found'}), 404

    output_path = convert_to_hk_traditional_chinese(input_path)
    return jsonify({'message': 'Conversion successful', 'output_file': output_path})

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB

import base64

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    file_name = request.args.get('file_name')
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
    if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    # Read Lyrics
    lrc_path = os.path.splitext(file_path)[0] + '.lrc'
    o3ics = ""
    if os.path.exists(lrc_path):
        try:
            with open(lrc_path, 'r', encoding='utf-8-sig') as f:
                o3ics = f.read()
        except Exception:
            pass

    # Read ID3 tags
    title = os.path.splitext(os.path.basename(file_path))[0]
    artist = ""
    album = ""
    cover_b64 = None
    mime_type = "image/jpeg"

    try:
        audio = MP3(file_path, ID3=ID3)
        if audio.tags:
            if 'TIT2' in audio.tags:
                title = audio.tags['TIT2'].text[0]
            if 'TPE1' in audio.tags:
                artist = audio.tags['TPE1'].text[0]
            if 'TALB' in audio.tags:
                album = audio.tags['TALB'].text[0]
            for tag in audio.tags.values():
                if tag.FrameID == 'APIC':
                    cover_b64 = base64.b64encode(tag.data).decode('utf-8')
                    mime_type = tag.mime
                    break
    except Exception:
        pass

    return jsonify({
        'title': title,
        'artist': artist,
        'album': album,
        'o3ics': o3ics,
        'cover': f"data:{mime_type};base64,{cover_b64}" if cover_b64 else None
    })

@app.route('/api/metadata', methods=['POST'])
def update_metadata():
    data = request.json
    file_name = data.get('file_name')
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
    if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    try:
        audio = MP3(file_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        
        if 'title' in data:
            audio.tags.add(TIT2(encoding=3, text=data['title']))
        if 'artist' in data:
            audio.tags.add(TPE1(encoding=3, text=data['artist']))
        if 'album' in data:
            audio.tags.add(TALB(encoding=3, text=data['album']))
        if 'cover' in data and data['cover']:
            from mutagen.id3 import APIC
            try:
                # First remove all existing APIC (cover) tags
                audio.tags.delall('APIC')

                cover_value = data['cover']

                # Check if it's a URL (starts with http:// or https://)
                if cover_value.startswith('http://') or cover_value.startswith('https://'):
                    # It's a URL, download the image
                    try:
                        with urllib.request.urlopen(cover_value, timeout=10) as response:
                            cover_data = response.read()
                            content_type = response.headers.get('Content-Type', 'image/jpeg')
                            if '/' in content_type:
                                mime = content_type.split('/')[1]
                                if mime == 'jpeg':
                                    mime = 'jpeg'
                            else:
                                mime = 'jpeg'
                    except Exception as e:
                        print(f"Error downloading cover from URL: {e}")
                        mime = 'jpeg'
                        cover_data = None
                elif ',' in cover_value:
                    # It's a base64 data URL, extract and decode
                    b64_data = cover_value.split(',')[-1]
                    cover_data = base64.b64decode(b64_data)
                    mime = 'jpeg'
                else:
                    cover_data = None

                if cover_data:
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/' + mime,
                            type=3,
                            desc='Cover',
                            data=cover_data
                        )
                    )
            except Exception as e:
                print(f"Error saving cover: {e}")
                pass
        
        # Save ID3 tags to the MP3 file
        audio.save()
        
        # Handle o3ics
        lrc_path = os.path.splitext(file_path)[0] + '.lrc'
        if 'o3ics' in data:
            if data['o3ics'].strip():
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(data['o3ics'])
            else:
                if os.path.exists(lrc_path):
                    os.remove(lrc_path)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/enhance', methods=['POST'])
def enhance_metadata():
    data = request.json
    file_name = data.get('file_name')
    result_offset = data.get('offset', 0)
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
    if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    try:
        import requests
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3
        import base64

        audio = MP3(file_path, ID3=ID3)
        title = audio.tags['TIT2'].text[0] if audio.tags and 'TIT2' in audio.tags else ""
        artist = audio.tags['TPE1'].text[0] if audio.tags and 'TPE1' in audio.tags else ""
        album = audio.tags['TALB'].text[0] if audio.tags and 'TALB' in audio.tags else ""

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        if not title or not artist:
            if " - " in base_name:
                parts = base_name.split(" - ", 1)
                if not artist: artist = parts[0].strip()
                if not title: title = parts[1].strip()
            else:
                if not title: title = base_name.strip()

        search_term = f"{title} {artist}".strip()

        cover_source = data.get('cover_source', 'itunes')

        search_info = {
            'itunes': {'search_term': search_term, 'found': False},
            'musicbrainz': {'search_term': search_term, 'found': False},
            'deezer': {'search_term': search_term, 'found': False},
            'lrclib': {'search_track': title, 'search_artist': artist, 'found': False},
            'musixmatch': {'search_track': title, 'search_artist': artist, 'found': False},
            'genius': {'search_track': title, 'search_artist': artist, 'found': False}
        }

        import re
        def detect_language(text):
            if not text:
                return 'english'
            if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
                return 'japanese'
            if re.search(r'[\u4E00-\u9FFF]', text):
                return 'chinese'
            return 'english'

        orig_language = detect_language(title + ' ' + artist)
        search_info['detected_language'] = orig_language

        cover_options = []
        default_cover = None
        mime_type = "image/jpeg"

        def add_cover_option(source, cover_data_b64, cover_url=None):
            nonlocal default_cover
            cover_options.append({
                'source': source,
                'cover': f"data:{mime_type};base64,{cover_data_b64}" if cover_data_b64 else None,
                'url': cover_url
            })
            if default_cover is None and cover_data_b64:
                default_cover = f"data:{mime_type};base64,{cover_data_b64}"

        # Search iTunes
        try:
            itunes_limit = max(10, result_offset + 1)
            
            if orig_language == 'japanese':
                itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit, 'country': 'jp', 'lang': 'ja_jp'})
                if not (itunes_res.status_code == 200 and itunes_res.json().get('results')):
                    itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit})
            elif orig_language == 'chinese':
                itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit, 'country': 'tw', 'lang': 'zh_tw'})
                if not (itunes_res.status_code == 200 and itunes_res.json().get('results')):
                    itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit})
            else:
                itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit, 'country': 'us'})
                if not (itunes_res.status_code == 200 and itunes_res.json().get('results')):
                    itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': itunes_limit, 'country': 'jp', 'lang': 'ja_jp'})
                    
            if itunes_res.status_code == 200 and itunes_res.json().get('results'):
                results = itunes_res.json()['results']
                track_idx = min(result_offset, len(results) - 1)
                track = results[track_idx] if results else None
                if track:
                    search_info['itunes']['found'] = True
                    search_info['itunes']['offset'] = result_offset
                    search_info['itunes']['total_results'] = len(results)
                    
                    if not album or album.lower() == 'unknown album':
                        album = track.get('collectionName', album)
                    if not artist or artist.lower() == 'unknown artist':
                        artist = track.get('artistName', artist)
                    if not title or title == base_name:
                        title = track.get('trackName', title)

                    cover_url = track.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                    if cover_url:
                        cover_data = requests.get(cover_url).content
                        cover_b64 = base64.b64encode(cover_data).decode('utf-8')
                        add_cover_option('itunes', cover_b64, cover_url)
        except Exception:
            pass

        # Search MusicBrainz for cover
        if cover_source in ['musicbrainz', 'all']:
            try:
                mb_search = requests.get('https://musicbrainz.org/ws/2/release/', params={
                    'query': f'recording:"{title}" AND artist:"{artist}"',
                    'fmt': 'json',
                    'limit': 5
                }, headers={'User-Agent': 'MediaHa/1.0'})
                if mb_search.status_code == 200:
                    mb_data = mb_search.json()
                    releases = mb_data.get('releases', [])
                    if releases:
                        mb_idx = min(result_offset, len(releases) - 1)
                        release = releases[mb_idx]
                        release_id = release.get('id', '')
                        if release_id:
                            cover_res = requests.get(f'https://coverartarchive.org/release/{release_id}/front')
                            if cover_res.status_code == 200:
                                cover_data = cover_res.content
                                cover_b64 = base64.b64encode(cover_data).decode('utf-8')
                                add_cover_option('musicbrainz', cover_b64, f'https://coverartarchive.org/release/{release_id}/front')
                                search_info['musicbrainz']['found'] = True
            except Exception:
                pass

        # Search Deezer for cover
        if cover_source in ['deezer', 'all']:
            try:
                deezer_res = requests.get('https://api.deezer.com/search', params={'q': search_term, 'limit': 5, 'output': 'json'})
                if deezer_res.status_code == 200:
                    deezer_data = deezer_res.json()
                    tracks = deezer_data.get('data', [])
                    if tracks:
                        dz_idx = min(result_offset, len(tracks) - 1)
                        track = tracks[dz_idx]
                        # Deezer provides multiple cover sizes
                        album = track.get('album', {})
                        cover_url = album.get('cover_xl') or album.get('cover_big') or album.get('cover_medium')
                        if not cover_url:
                            cover_url = track.get('artist', {}).get('picture_xl') or track.get('artist', {}).get('picture_big')
                        if cover_url:
                            cover_data = requests.get(cover_url).content
                            cover_b64 = base64.b64encode(cover_data).decode('utf-8')
                            add_cover_option('deezer', cover_b64, cover_url)
                            search_info['deezer']['found'] = True
            except Exception as e:
                print(f"Deezer search error: {e}")
                pass

        # Search o3ics from multiple free sources
        o3ics_options = []
        o3ics = ""

        # 1. Search lrcLib
        lrclib_results = []
        try:
            lrclib_limit = max(10, result_offset + 1)
            lrc_res = requests.get('https://lrclib.net/api/search', params={'track_name': title, 'artist_name': artist, 'limit': lrclib_limit})
            if lrc_res.status_code == 200:
                lrclib_results = lrc_res.json()
            
            if not lrclib_results and title:
                lrc_res = requests.get('https://lrclib.net/api/search', params={'track_name': title, 'limit': lrclib_limit})
                if lrc_res.status_code == 200:
                    lrclib_results = lrc_res.json()
                search_info['lrclib']['fallback_to_title'] = True
            
            if lrclib_results:
                lrclib_idx = min(result_offset, len(lrclib_results) - 1)
                best_match = lrclib_results[lrclib_idx] if lrclib_results else None
                if best_match:
                    o3ics_text = best_match.get('syncedLyrics') or best_match.get('plainLyrics') or ""
                    if o3ics_text:
                        o3ics_options.append({'source': 'lrclib', 'o3ics': o3ics_text})
                        if not o3ics:
                            o3ics = o3ics_text
                    search_info['lrclib']['found'] = True
                    search_info['lrclib']['offset'] = result_offset
                    search_info['lrclib']['total_results'] = len(lrclib_results)
                    if not album: album = best_match.get('albumName', album)
                    if not artist: artist = best_match.get('artistName', artist)
                    if not title: title = best_match.get('trackName', title)
        except Exception:
            pass

        # 2. Search MusixMatch
        try:
            mm_search = requests.get('https://www.musixmatch.com/search', params={'pattern': search_term}, timeout=10)
            if mm_search.status_code == 200:
                search_info['musixmatch']['found'] = True
        except Exception:
            pass

        # 3. Search Genius
        try:
            genius_search = requests.get('https://genius.com/api/search/song', params={'q': search_term}, timeout=10)
            if genius_search.status_code == 200:
                genius_data = genius_search.json()
                hits = genius_data.get('response', {}).get('hits', [])
                if hits:
                    song_id = hits[0].get('result', {}).get('id')
                    if song_id:
                        o3ics_page = requests.get(f'https://genius.com/api/songs/{song_id}', timeout=10)
                        if o3ics_page.status_code == 200:
                            o3ics_data = o3ics_page.json()
                            o3ics_text = o3ics_data.get('response', {}).get('song', {}).get('o3ics', {}).get('plain', '')
                            if not o3ics_text:
                                o3ics_text = o3ics_data.get('response', {}).get('song', {}).get('description', {}).get('plain', '')
                            if o3ics_text:
                                o3ics_options.append({'source': 'genius', 'o3ics': o3ics_text})
                                if not o3ics:
                                    o3ics = o3ics_text
                                search_info['genius']['found'] = True
        except Exception:
            pass

        return jsonify({
            'title': title,
            'artist': artist,
            'album': album,
            'o3ics': o3ics,
            'o3ics_options': o3ics_options,
            'cover': default_cover,
            'cover_options': cover_options,
            'search_info': search_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


import json
ALIST_CONFIG_PATH = '/data/alist_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/alist_options.json')

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

from flask import Response
import json
import os

CALIBRE_CONFIG_PATH = '/data/calibre_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/calibre_options.json')

@app.route('/api/calibre/settings', methods=['GET'])
def get_calibre_settings():
    """Get Calibre-Web settings"""
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
    """Save Calibre-Web settings"""
    data = request.json
    try:
        os.makedirs(os.path.dirname(CALIBRE_CONFIG_PATH), exist_ok=True)
        with open(CALIBRE_CONFIG_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        return jsonify({'status': 'ok', 'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/calibre/sync', methods=['POST'])
def sync_calibre():
    """Sync EPUB files to Calibre library using Calibre's library API (with SQL fallback)"""
    from pathlib import Path
    import shutil
    import sqlite3
    import uuid

    def generate():
        try:
            if os.path.exists(CALIBRE_CONFIG_PATH):
                with open(CALIBRE_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
            else:
                yield json.dumps({'type': 'error', 'message': 'Please configure Calibre settings first'}) + '\n'
                return

            epub_folder = config.get('epub_folder', '/media/eBook')
            calibre_library_path = config.get('calibre_library_path', '')

            if not epub_folder or not calibre_library_path:
                yield json.dumps({'type': 'error', 'message': 'Please configure both EPUB folder and Calibre library path'}) + '\n'
                return

            epub_path = Path(epub_folder)
            calibre_path = Path(calibre_library_path)

            if not epub_path.exists() or not calibre_path.exists():
                yield json.dumps({'type': 'error', 'message': 'Folder not found'}) + '\n'
                return

            epub_files = list(epub_path.rglob("*.epub"))
            total = len(epub_files)

            if total == 0:
                yield json.dumps({'type': 'error', 'message': 'No EPUB files found'}) + '\n'
                return

            yield json.dumps({'type': 'log', 'message': f'Found {total} EPUB files', 'level': 'info'}) + '\n'
            yield json.dumps({'type': 'log', 'message': f'Calibre library: {calibre_library_path}', 'level': 'info'}) + '\n'

            # Try to use Calibre API
            use_calibre = False
            try:
                from calibre.library import db
                from calibre.ebooks.metadata.book.base import Metadata
                use_calibre = True
                yield json.dumps({'type': 'log', 'message': 'Using Calibre library API', 'level': 'info'}) + '\n'
            except ImportError:
                yield json.dumps({'type': 'log', 'message': 'Calibre library not available, using direct SQL', 'level': 'info'}) + '\n'

            metadata_db = calibre_path / 'metadata.db'
            books_folder = calibre_path / 'books'

            try:
                conn = sqlite3.connect(str(metadata_db))
                cursor = conn.cursor()

                # Find EPUB books to delete (keep non-EPUB books like comics)
                cursor.execute("SELECT DISTINCT book FROM data WHERE format = 'EPUB'")
                epub_book_ids = [b[0] for b in cursor.fetchall()]

                if epub_book_ids:
                    yield json.dumps({'type': 'log', 'message': f'Cleaning up {len(epub_book_ids)} old EPUB entries...', 'level': 'info'}) + '\n'
                    # Delete links
                    cursor.execute("DELETE FROM books_authors_link WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                    cursor.execute("DELETE FROM books_series_link WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                    cursor.execute("DELETE FROM data WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                    cursor.execute("DELETE FROM books WHERE id IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                    # Delete book folders
                    for bid in epub_book_ids:
                        old_dir = books_folder / str(bid)
                        if old_dir.exists():
                            shutil.rmtree(old_dir)

                # Recreate schema if needed
                cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                for (trigger,) in cursor.fetchall():
                    try:
                        cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                    except:
                        pass

                    # Create schema for COPS compatibility (HA COPS needs these tables)
                    schema = """
                        CREATE TABLE IF NOT EXISTS languages (id INTEGER PRIMARY KEY, lang_code TEXT UNIQUE NOT NULL);
                        CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                        CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
                        CREATE TABLE IF NOT EXISTS identifiers (id INTEGER PRIMARY KEY, type TEXT, val TEXT);
                        CREATE TABLE IF NOT EXISTS books_identifiers (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, type TEXT, val TEXT);
                        CREATE TABLE IF NOT EXISTS books_languages_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL);
                        CREATE TABLE IF NOT EXISTS books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL);
                        CREATE TABLE IF NOT EXISTS books_tags_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL);
                    """
                    for stmt in schema.strip().split(';'):
                        stmt = stmt.strip()
                        if stmt and not stmt.startswith('--'):
                            try:
                                cursor.execute(stmt)
                            except:
                                pass

                    conn.commit()
                    conn.close()

                yield json.dumps({'type': 'log', 'message': 'Library cleared', 'level': 'info'}) + '\n'

                # STEP 2: Import
                yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
                yield json.dumps({'type': 'log', 'message': '=' * 50, 'level': 'info'}) + '\n'
                yield json.dumps({'type': 'log', 'message': 'STEP 2: Importing EPUB files', 'level': 'info'}) + '\n'
                yield json.dumps({'type': 'log', 'message': '=' * 50, 'level': 'info'}) + '\n'

                success_count = 0
                error_count = 0
                conn = None
                cursor = None

                if use_calibre:
                    cache = dbc.new_api
                else:
                    # Direct SQL - single connection
                    conn = sqlite3.connect(str(metadata_db), timeout=30)
                    conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(books_authors_link)")
                    authors_link_cols = {row[1] for row in cursor.fetchall()}
                    yield json.dumps({'type': 'log', 'message': f'DEBUG: books_authors_link columns: {authors_link_cols}', 'level': 'info'}) + '\n'
                    cursor.execute("PRAGMA table_info(books_series_link)")
                    series_link_cols = {row[1] for row in cursor.fetchall()}
                    yield json.dumps({'type': 'log', 'message': f'DEBUG: books_series_link columns: {series_link_cols}', 'level': 'info'}) + '\n'

                for idx, epub_file in enumerate(epub_files, 1):
                    yield json.dumps({'type': 'progress', 'current': idx, 'total': total, 'message': f'Importing: {epub_file.relative_to(epub_path)}'}) + '\n'

                    try:
                        rel_path = epub_file.relative_to(epub_path)
                        parts = rel_path.parts

                        if len(parts) >= 3:
                            series_name = parts[-2]
                        elif len(parts) == 2:
                            series_name = parts[0]
                        else:
                            series_name = ''

                        book_title = rel_path.stem

                        series_index = 1.0
                        match = re.search(r'(\d+(?:\.\d+)?)', book_title)
                        if match:
                            series_index = float(match.group(1))

                        if use_calibre:
                            meta = extract_epub_metadata(epub_file)
                            epub_title = meta['title'] or book_title
                            epub_authors = meta['authors'] if meta['authors'] else ['Unknown']
                            mi = Metadata(epub_title, authors=epub_authors)
                            if series_name:
                                mi.series = series_name
                                mi.series_index = series_index
                            if meta['cover_data']:
                                import io
                                mi.cover = io.BytesIO(meta['cover_data'])
                            format_map = {'EPUB': str(epub_file)}
                            ids, _ = cache.add_books([(mi, format_map)], add_duplicates=False)
                            if ids:
                                success_count += 1
                                series_info = f" [Series: {series_name} #{series_index}]" if series_name else ""
                                author_info = f" by {', '.join(epub_authors[:2])}" if epub_authors and epub_authors[0] != 'Unknown' else ""
                                yield json.dumps({'type': 'log', 'message': f'✓ {epub_title}{author_info}{series_info}', 'level': 'success'}) + '\n'
                            else:
                                error_count += 1
                                yield json.dumps({'type': 'log', 'message': f'✗ {epub_file.name}: Failed', 'level': 'error'}) + '\n'
                        else:
                            # Extract metadata from EPUB
                            meta = extract_epub_metadata(epub_file)
                            epub_title = meta['title'] or book_title
                            epub_authors = meta['authors'] if meta['authors'] else ['Unknown']
                            
                            # Direct SQL import
                            cursor.execute("SELECT MAX(id) FROM books")
                            max_id = cursor.fetchone()[0] or 0
                            book_id = max_id + 1

                            book_dir = books_folder / str(book_id)
                            book_dir.mkdir(exist_ok=True)
                            safe_title = re.sub(r'[<>:"/\\|?*]', '_', epub_title)[:100]
                            shutil.copy2(epub_file, book_dir / f"{safe_title}.epub")

                            # Extract cover if available
                            cover_filename = None
                            has_cover = 0
                            if meta['cover_data']:
                                ext = os.path.splitext(meta['cover_name'] or 'cover.jpg')[1] or '.jpg'
                                cover_filename = f"cover{ext}"
                                with open(book_dir / cover_filename, 'wb') as f:
                                    f.write(meta['cover_data'])
                                has_cover = 1

                            cursor.execute('''
                                INSERT INTO books (id, title, sort, author_sort, series_index, path, uuid, has_cover, last_modified)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2000-01-01 00:00:00+00:00')
                            ''', (book_id, epub_title, epub_title, epub_authors[0], series_index, f"books/{book_id}", str(uuid.uuid4()), has_cover))

                            cursor.execute('''
                                INSERT INTO data (book, format, name, uncompressed_size)
                                VALUES (?, 'EPUB', ?, ?)
                            ''', (book_id, safe_title, epub_file.stat().st_size))

                            # Handle multiple authors
                            for author_name in epub_authors:
                                cursor.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
                                row = cursor.fetchone()
                                author_id = row[0] if row else None
                                if not author_id:
                                    cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", (author_name, author_name))
                                    author_id = cursor.lastrowid
                                cols = ['book'] + [c for c in authors_link_cols if c != 'id']
                                vals = [book_id] + [author_id if c in ('author', 'authors') else 0 for c in cols[1:]]
                                placeholders = ', '.join(['?' for _ in cols])
                                cursor.execute(f"INSERT INTO books_authors_link ({', '.join(cols)}) VALUES ({placeholders})", vals)

                            # Publisher - COPS schema: book, publisher (not publisher_id)
                            if meta['publisher']:
                                cursor.execute("SELECT id FROM publishers WHERE name = ?", (meta['publisher'],))
                                row = cursor.fetchone()
                                pub_id = row[0] if row else None
                                if not pub_id:
                                    cursor.execute("INSERT INTO publishers (name, sort) VALUES (?, ?)", (meta['publisher'], meta['publisher']))
                                    pub_id = cursor.lastrowid
                                try:
                                    cursor.execute("INSERT OR IGNORE INTO books_publishers_link (book, publisher) VALUES (?, ?)", (book_id, pub_id))
                                except:
                                    pass

                            # Tags/Subjects
                            for tag_name in meta['tags'][:20]:  # Limit tags
                                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                                row = cursor.fetchone()
                                tag_id = row[0] if row else None
                                if not tag_id:
                                    cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                                    tag_id = cursor.lastrowid
                                cursor.execute("INSERT OR IGNORE INTO books_tags_link (book, tag) VALUES (?, ?)", (book_id, tag_id))

                            # Identifier (ISBN or custom) - COPS/HA COPS schema: id, book, type, val
                            if meta['identifier']:
                                cursor.execute("SELECT 1 FROM books_identifiers WHERE book = ?", (book_id,))
                                if not cursor.fetchone():
                                    cursor.execute("INSERT INTO books_identifiers (book, type, val) VALUES (?, 'ISBN', ?)", (book_id, meta['identifier']))

                            # Language - COPS/HA COPS compatibility
                            if meta['language']:
                                lang_code = meta['language'][:10]
                                cursor.execute("SELECT id FROM languages WHERE lang_code = ?", (lang_code,))
                                row = cursor.fetchone()
                                lang_id = row[0] if row else None
                                if not lang_id:
                                    cursor.execute("INSERT INTO languages (lang_code) VALUES (?)", (lang_code,))
                                    lang_id = cursor.lastrowid
                                # COPS schema uses lang_code integer, but Calibre uses direct string link
                                try:
                                    cursor.execute("INSERT OR IGNORE INTO books_languages_link (book, lang_code) VALUES (?, ?)", (book_id, lang_id))
                                except:
                                    pass

                            # Description as comments
                            if meta['description']:
                                cursor.execute("INSERT INTO comments (book, text) VALUES (?, ?)", (book_id, meta['description'][:10000]))

                            if series_name:
                                cursor.execute("SELECT id FROM series WHERE name = ?", (series_name,))
                                row = cursor.fetchone()
                                if row:
                                    series_id = row[0]
                                else:
                                    cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (series_name, series_name))
                                    series_id = cursor.lastrowid
                                cols = ['book', 'series'] + [c for c in series_link_cols if c not in ('id', 'book', 'series')]
                                vals = [book_id, series_id]
                                for c in cols[2:]:
                                    if c == 'series_index':
                                        vals.append(series_index)
                                    else:
                                        vals.append(0)
                                placeholders = ', '.join(['?' for _ in cols])
                                cursor.execute(f"INSERT INTO books_series_link ({', '.join(cols)}) VALUES ({placeholders})", vals)

                            conn.commit()
                            success_count += 1
                            series_info = f" [{series_name} #{series_index}]" if series_name else ""
                            author_info = f" by {epub_authors[0]}" if epub_authors and epub_authors[0] != 'Unknown' else ""
                            yield json.dumps({'type': 'log', 'message': f'✓ {epub_title}{author_info}{series_info}', 'level': 'success'}) + '\n'

                    except Exception as e:
                        if not use_calibre:
                            conn.rollback()
                        error_count += 1
                        yield json.dumps({'type': 'log', 'message': f'✗ {epub_file.name}: {str(e)}', 'level': 'error'}) + '\n'

                if not use_calibre:
                    conn.close()

                yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
                if error_count > 0:
                    yield json.dumps({'type': 'error', 'message': f'Completed with errors: {success_count} succeeded, {error_count} failed'}) + '\n'
                else:
                    yield json.dumps({'type': 'success', 'message': f'Sync completed! {success_count} books imported'}) + '\n'

            except Exception as e:
                import traceback
                yield json.dumps({'type': 'error', 'message': f'Sync failed: {str(e)}\n{traceback.format_exc()}'}) + '\n'

        except Exception as e:
            import traceback
            yield json.dumps({'type': 'error', 'message': f'Sync error: {str(e)}\n{traceback.format_exc()}'}) + '\n'

    return app.response_class(generate(), mimetype='application/json')


@app.route('/api/comic/sync', methods=['POST'])
def sync_comics():
    """Sync comic files (PDF, CBZ) to Calibre library"""
    def generate():
        try:
            from pathlib import Path
            import uuid
            import re
            import sqlite3

            if os.path.exists(CALIBRE_CONFIG_PATH):
                with open(CALIBRE_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
            else:
                yield json.dumps({'type': 'error', 'message': 'Please configure Calibre settings first'}) + '\n'
                return

            comic_folder = config.get('comic_folder', '/media/comic')
            calibre_library_path = config.get('calibre_library_path', '')

            if not comic_folder or not calibre_library_path:
                yield json.dumps({'type': 'error', 'message': 'Please configure both comic folder and Calibre library path'}) + '\n'
                return

            comic_path = Path(comic_folder)
            calibre_path = Path(calibre_library_path)

            if not comic_path.exists() or not calibre_path.exists():
                yield json.dumps({'type': 'error', 'message': 'Folder not found'}) + '\n'
                return

            # Find all comic chapters (pdf, cbz files)
            comic_extensions = {'.pdf', '.cbz', '.cbr', '.cb7'}
            chapters = []
            for ext in comic_extensions:
                chapters.extend(comic_path.rglob(f"*{ext}"))

            total = len(chapters)
            if total == 0:
                yield json.dumps({'type': 'error', 'message': 'No comic files found'}) + '\n'
                return

            yield json.dumps({'type': 'log', 'message': f'Found {total} comic chapters', 'level': 'info'}) + '\n'
            yield json.dumps({'type': 'log', 'message': f'Calibre library: {calibre_library_path}', 'level': 'info'}) + '\n'

            metadata_db = calibre_path / 'metadata.db'
            books_folder = calibre_path / 'books'
            conn = sqlite3.connect(str(metadata_db))
            cursor = conn.cursor()

            # Setup schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            for (trigger,) in cursor.fetchall():
                try:
                    cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                except:
                    pass

            schema = """
                CREATE TABLE IF NOT EXISTS languages (id INTEGER PRIMARY KEY, lang_code TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                CREATE TABLE IF NOT EXISTS series (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS identifiers (id INTEGER PRIMARY KEY, type TEXT, val TEXT);
                CREATE TABLE IF NOT EXISTS books_identifiers (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, type TEXT, val TEXT);
                CREATE TABLE IF NOT EXISTS books_languages_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS books_tags_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS books_series_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, series INTEGER NOT NULL);
            """
            for stmt in schema.strip().split(';'):
                stmt = stmt.strip()
                if stmt:
                    try:
                        cursor.execute(stmt)
                    except:
                        pass

            success_count = 0
            error_count = 0

            # Delete existing books with Comics tag before resync
            cursor.execute("SELECT id FROM tags WHERE name = 'Comics'")
            row = cursor.fetchone()
            if row:
                comics_tag_id = row[0]
                cursor.execute("SELECT book FROM books_tags_link WHERE tag = ?", (comics_tag_id,))
                old_book_ids = [b[0] for b in cursor.fetchall()]
                if old_book_ids:
                    yield json.dumps({'type': 'log', 'message': f'Cleaning up {len(old_book_ids)} old entries...', 'level': 'info'}) + '\n'
                    # Delete links
                    cursor.execute("DELETE FROM books_tags_link WHERE tag = ?", (comics_tag_id,))
                    cursor.execute("DELETE FROM books_authors_link WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                    cursor.execute("DELETE FROM books_series_link WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                    cursor.execute("DELETE FROM data WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                    cursor.execute("DELETE FROM books WHERE id IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                    # Delete book folders
                    for bid in old_book_ids:
                        old_dir = books_folder / str(bid)
                        if old_dir.exists():
                            import shutil
                            shutil.rmtree(old_dir)

            # Get max book ID
            cursor.execute("SELECT MAX(id) FROM books")
            max_book_id = cursor.fetchone()[0] or 0

            # Group chapters by comic name (parent folder)
            comics = {}  # comic_name -> list of (original_name, file_path, file_format)
            for chapter_file in chapters:
                comic_name = chapter_file.parent.name
                original_name = chapter_file.name  # Keep original filename with extension
                file_format = chapter_file.suffix[1:].upper()  # e.g., PDF, CBZ
                if comic_name not in comics:
                    comics[comic_name] = []
                comics[comic_name].append((original_name, str(chapter_file), file_format))

            yield json.dumps({'type': 'log', 'message': f'Found {len(comics)} comic series', 'level': 'info'}) + '\n'

            for comic_name, chapter_list in sorted(comics.items()):
                try:
                    safe_comic = re.sub(r'[<>:"/\\|?*]', '_', comic_name)

                    # Add or get series for this comic
                    cursor.execute("SELECT id FROM series WHERE name = ?", (comic_name,))
                    row = cursor.fetchone()
                    series_id = row[0] if row else None
                    if not series_id:
                        cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (comic_name, comic_name))
                        series_id = cursor.lastrowid

                    # Sort chapters naturally
                    import re as regex_module
                    def natural_sort_key(s):
                        return [int(c) if c.isdigit() else c.lower() for c in regex_module.split(r'(\d+)', s)]

                    chapter_list.sort(key=lambda x: natural_sort_key(x[0]))

                    # Create each chapter as separate book in series
                    for idx, (original_name, file_path, file_format) in enumerate(chapter_list):
                        max_book_id += 1
                        book_id = max_book_id

                        book_dir = books_folder / str(book_id)
                        book_dir.mkdir(exist_ok=True)

                        uuid_str = str(uuid.uuid4())
                        chapter_idx = idx + 1

                        cursor.execute('''
                            INSERT INTO books (id, title, sort, author_sort, series_index, path, uuid, has_cover, last_modified)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 0, '2000-01-01 00:00:00+00:00')
                        ''', (book_id, f"{comic_name} - {Path(original_name).stem}", f"{comic_name} - {Path(original_name).stem}", 'Unknown', chapter_idx, f"books/{book_id}", uuid_str))

                        # Link to series
                        cursor.execute("INSERT OR IGNORE INTO books_series_link (book, series) VALUES (?, ?)", (book_id, series_id))

                        # Link tag for comics
                        cursor.execute("SELECT id FROM tags WHERE name = 'Comics'")
                        row = cursor.fetchone()
                        tag_id = row[0] if row else None
                        if not tag_id:
                            cursor.execute("INSERT INTO tags (name) VALUES ('Comics')")
                            tag_id = cursor.lastrowid
                        cursor.execute("INSERT OR IGNORE INTO books_tags_link (book, tag) VALUES (?, ?)", (book_id, tag_id))

                        # Add author
                        cursor.execute("SELECT id FROM authors WHERE name = 'Unknown'")
                        row = cursor.fetchone()
                        author_id = row[0] if row else None
                        if not author_id:
                            cursor.execute("INSERT INTO authors (name, sort) VALUES ('Unknown', 'Unknown')")
                            author_id = cursor.lastrowid
                        cursor.execute("INSERT OR IGNORE INTO books_authors_link (book, author) VALUES (?, ?)", (book_id, author_id))

                        # Copy comic file to library
                        import shutil
                        dest_file = book_dir / original_name
                        shutil.copy2(chapter_file, dest_file)

                        # Extract cover image from first page
                        cover_extracted = False
                        if file_format == 'CBZ':
                            try:
                                import zipfile
                                with zipfile.ZipFile(chapter_file, 'r') as zf:
                                    images = [f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                                    if images:
                                        first_img = sorted(images)[0]
                                        img_data = zf.read(first_img)
                                        cover_path = book_dir / 'cover.jpg'
                                        with open(cover_path, 'wb') as cf:
                                            cf.write(img_data)
                                        cover_extracted = True
                            except:
                                pass
                        elif file_format == 'PDF':
                            try:
                                import fitz  # PyMuPDF
                                doc = fitz.open(chapter_file)
                                if len(doc) > 0:
                                    page = doc[0]
                                    mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                                    clip = page.rect
                                    pix = page.get_pixmap(matrix=mat)
                                    cover_path = book_dir / 'cover.jpg'
                                    pix.save(str(cover_path))
                                    cover_extracted = True
                                doc.close()
                            except:
                                pass

                        # Update has_cover flag
                        if cover_extracted:
                            cursor.execute('UPDATE books SET has_cover = 1 WHERE id = ?', (book_id,))

                        # Add format - use filename without extension for COPS
                        chapter_file = Path(file_path)
                        file_size = chapter_file.stat().st_size
                        db_name = chapter_file.stem  # filename without extension

                        cursor.execute('''
                            INSERT INTO data (book, format, name, uncompressed_size)
                            VALUES (?, ?, ?, ?)
                        ''', (book_id, file_format, db_name, file_size))

                    success_count += 1
                    yield json.dumps({'type': 'log', 'message': f'✓ {comic_name} ({len(chapter_list)} chapters)', 'level': 'success'}) + '\n'

                except Exception as e:
                    error_count += 1
                    yield json.dumps({'type': 'log', 'message': f'✗ {comic_name}: {str(e)}', 'level': 'error'}) + '\n'

            conn.commit()
            conn.close()

            # Clean up empty folders in library
            import shutil
            for item in books_folder.iterdir():
                if item.is_dir() and not any(item.iterdir()):
                    shutil.rmtree(item)

            yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
            if error_count > 0:
                yield json.dumps({'type': 'error', 'message': f'Completed: {success_count} comics, {error_count} errors'}) + '\n'
            else:
                yield json.dumps({'type': 'success', 'message': f'Sync completed! {success_count} comics imported'}) + '\n'

        except Exception as e:
            import traceback
            yield json.dumps({'type': 'error', 'message': f'Sync failed: {str(e)}\n{traceback.format_exc()}'}) + '\n'

    return app.response_class(generate(), mimetype='application/json')


@app.route('/api/alist/run', methods=['POST'])
def run_alist():
    if os.path.exists(ALIST_CONFIG_PATH):
        with open(ALIST_CONFIG_PATH, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    from utils.alist_strm import generate_strm_generator
    return Response(generate_strm_generator(config), mimetype='text/plain')

DROPBOX_CONFIG_PATH = '/data/dropbox_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/dropbox_options.json')

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

@app.route('/api/o3ics/ruby', methods=['POST'])
def o3ics_ruby():
    text = request.json.get('text', '')
    if not text:
        return jsonify({'result': ''})
    try:
        import pykakasi
        import re

        text = re.sub(r'([?-?]+)([\u3040-\u309F\u30A0-\u30FF]+)\)', r'\1', text)
        
        print(f"After removing parens: {text[:100]}")

        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
             print(f"No Japanese chars found in text, returning original")
             return jsonify({'result': text})

        print(f"Japanese text detected, processing with pykakasi")
        kks = pykakasi.kakasi()
        kks.setMode('H', 'H')
        kks.setMode('K', 'H')
        kks.setMode('J', 'H')
        result = []

        print(f"Processing text with pykakasi (first 100 chars): {text[:100]}")
        for line in text.split('\n'):
            line_res = []
            if not line.strip():
                result.append(line)
                continue
            try:
                items = kks.convert(line)
                print(f"Converted line '{line[:30]}...' got {len(items)} items")
                for item in items:
                    orig = item['orig']
                    hira = item['hira']
                    if hira and orig != hira:
                        line_res.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
                    else:
                        line_res.append(orig)
                print(f"Result for line: {''.join(line_res)[:50]}...")
            except Exception as e:
                print(f"pykakasi conversion error for line: {line}, error: {e}")
                line_res.append(line)
            result.append("".join(line_res))
        final_result = "\n".join(result)
        print(f"Final result (first 100 chars): {final_result[:100]}")
        return jsonify({'result': final_result})
    except ImportError:
        return jsonify({'result': text})
    except Exception as e:
        print(f"o3ics_ruby error: {e}")
        return jsonify({'result': text})

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
        import re

        if content is None:
            # Just read the file
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

        # Apply time offset if specified
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
                # Group 1: "Dialogue: \d+," (prefix)
                # Group 2: First timestamp
                # Group 3: Second timestamp
                start = convert_time(match.group(2))
                end = convert_time(match.group(3))
                if start is not None and end is not None:
                    new_start = max(0, start + offset_seconds)
                    new_end = max(0, end + offset_seconds)
                    # Include the prefix (group 1) in the replacement
                    return f"{match.group(1)}{format_time(new_start)},{format_time(new_end)}"
                return match.group(0)

            # ASS Dialogue line format: Layer, Start, End, Style, ...
            # Pattern to match Dialogue lines with timestamps
            content = re.sub(
                r'(Dialogue: \d+,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})',
                offset_timestamp,
                content
            )

        # Save the file
        with open(file_path, 'w', encoding='utf-8-sig') as f:
            f.write(content)

        return jsonify({'success': True, 'message': f'File saved successfully' + (f' with {offset_seconds:+d}s offset' if offset_seconds != 0 else '')})
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
        import re

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        # Show preview of first 10 dialogue lines with offset
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

        # Only process Dialogue lines for preview
        modified = re.sub(
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

if __name__ == '__main__':
    from waitress import serve
    print("Starting production WSGI server on port 5000...")
    serve(app, host='0.0.0.0', port=5000)
