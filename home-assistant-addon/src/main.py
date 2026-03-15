from flask import Flask, request, jsonify, send_from_directory
import os
from utils.epub_converter import convert_to_hk_traditional_chinese

app = Flask(__name__)

MEDIA_DIR = '/media'

@app.route('/')
def index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), 'index.html')

@app.route('/<path:filename>')
def serve_ui(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), filename)

@app.route('/api/files', methods=['GET'])
def list_files():
    sub_dir = request.args.get('dir', '')
    target_dir = os.path.abspath(os.path.join(MEDIA_DIR, sub_dir))

    # Security: Ensure we don't traverse outside MEDIA_DIR
    if not target_dir.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(target_dir):
        return jsonify([])

    # For music directory, recursively get all audio files
    if 'music' in sub_dir.lower() or sub_dir == '':
        items = get_all_audio_files(target_dir, MEDIA_DIR)
    else:
        items = []
        for item in os.listdir(target_dir):
            full_path = os.path.join(target_dir, item)
            rel_path = os.path.relpath(full_path, MEDIA_DIR)

            # Windows compatibility for rel_path
            rel_path = rel_path.replace('\\\\', '/')

            if os.path.isdir(full_path):
                items.append({'name': item, 'type': 'folder', 'path': rel_path})
            elif item.lower().endswith(('.epub', '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.lrc', '.jpg', '.jpeg', '.png', '.strm', '.mp4')):
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
    lyrics = ""
    if os.path.exists(lrc_path):
        try:
            with open(lrc_path, 'r', encoding='utf-8-sig') as f:
                lyrics = f.read()
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
        'lyrics': lyrics,
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
            import base64
            from mutagen.id3 import APIC
            try:
                b64_data = data['cover'].split(',')[-1]
                cover_data = base64.b64decode(b64_data)
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=cover_data
                    )
                )
            except Exception:
                pass
        
        # Save ID3 tags to the MP3 file
        audio.save()
        
        # Handle lyrics
        lrc_path = os.path.splitext(file_path)[0] + '.lrc'
        if 'lyrics' in data:
            if data['lyrics'].strip():
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(data['lyrics'])
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

        # Search iTunes for cover/album/artist/title (try JP store first for Japanese metadata)
        cover_b64 = None
        mime_type = "image/jpeg"
        try:
            # Try JP store first to get original Japanese text instead of romaji/english
            itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': 1, 'country': 'jp', 'lang': 'ja_jp'})
            if not (itunes_res.status_code == 200 and itunes_res.json().get('results')):
                # Fallback to general search if not found in JP store
                itunes_res = requests.get('https://itunes.apple.com/search', params={'term': search_term, 'media': 'music', 'limit': 1})
                
            if itunes_res.status_code == 200 and itunes_res.json().get('results'):
                track = itunes_res.json()['results'][0]
                
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
        except Exception:
            pass

        # Search lrcLib
        lyrics = ""
        try:
            lrc_res = requests.get('https://lrclib.net/api/search', params={'track_name': title, 'artist_name': artist})
            if lrc_res.status_code == 200 and lrc_res.json():
                best_match = lrc_res.json()[0]
                lyrics = best_match.get('syncedLyrics') or best_match.get('plainLyrics') or ""
                if not album: album = best_match.get('albumName', album)
                if not artist: artist = best_match.get('artistName', artist)
                if not title: title = best_match.get('trackName', title)
        except Exception:
            pass

        return jsonify({
            'title': title,
            'artist': artist,
            'album': album,
            'lyrics': lyrics,
            'cover': f"data:{mime_type};base64,{cover_b64}" if cover_b64 else None
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

@app.route('/api/lyrics/ruby', methods=['POST'])
def lyrics_ruby():
    text = request.json.get('text', '')
    if not text:
        return jsonify({'result': ''})
    try:
        import pykakasi
        import re
        
        # Check if contains any Japanese characters (indicating Japanese lyrics)
        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text):
             return jsonify({'result': text})

        kks = pykakasi.kakasi()
        result = []
        # Process line by line to prevent multi-line strings breaking pykakasi tokenization
        for line in text.split('\n'):
            line_res = []
            for item in kks.convert(line):
                orig = item['orig']
                hira = item['hira']
                # Add ruby for ALL kanji that have a hiragana reading (for Japanese)
                if hira and orig != hira:
                    line_res.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
                else:
                    line_res.append(orig)
            result.append("".join(line_res))
        return jsonify({'result': "\n".join(result)})
    except ImportError:
        return jsonify({'result': text}) # Fallback if module fails

if __name__ == '__main__':
    from waitress import serve
    print("Starting production WSGI server on port 5000...")
    serve(app, host='0.0.0.0', port=5000)
