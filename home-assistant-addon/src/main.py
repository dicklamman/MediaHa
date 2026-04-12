# -*- coding: utf-8 -*-
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

    # Get direct contents only (non-recursive)
    items = []
    for item in os.listdir(target_dir):
        full_path = os.path.join(target_dir, item)
        rel_path = os.path.relpath(full_path, MEDIA_DIR)

        # Windows compatibility for rel_path
        rel_path = rel_path.replace('\\', '/')

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
            import base64
            from mutagen.id3 import APIC
            try:
                # First remove all existing APIC (cover) tags
                audio.tags.delall('APIC')
                
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

if __name__ == '__main__':
    from waitress import serve
    print("Starting production WSGI server on port 5000...")
    serve(app, host='0.0.0.0', port=5000)
