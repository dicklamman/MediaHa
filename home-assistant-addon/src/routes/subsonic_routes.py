# -*- coding: utf-8 -*-
"""SubSonic API routes for Navidrome/SubSonic clients."""
import os
import base64
import hashlib
import time
import re
from flask import request, Response, jsonify, send_file
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT

MEDIA_DIR = '/media/music'


def register_subsonic_routes(app, username, password):
    """Register SubSonic API compatible routes."""

    # =========================================================================
    # Authentication
    # =========================================================================

    def auth_required():
        """Check SubSonic authentication."""
        user = request.args.get('u') or request.form.get('u')
        password_arg = request.args.get('p') or request.form.get('p')
        token = request.args.get('t') or request.form.get('t')
        salt = request.args.get('s') or request.form.get('s')

        # Check password (plain text or token)
        if user == username:
            if password_arg == password:
                return True
            # Check token auth: token = md5(password + salt)
            if token and salt:
                expected = hashlib.md5(f"{password}{salt}".encode()).hexdigest()
                if token == expected:
                    return True

        return False

    def is_json():
        """Check if client wants JSON format."""
        fmt = request.args.get('f', 'xml')
        return fmt == 'json'

    def escape_xml(text):
        """Escape XML special characters."""
        if not text:
            return ''
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

    def ok_response(data):
        """Return response in XML or JSON format."""
        if is_json():
            return jsonify({'status': 'ok', 'version': '1.16.1', **data})
        else:
            xml = build_xml(data)
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<subsonic-response status="ok" version="1.16.1">
{xml}
</subsonic-response>''', mimetype='application/xml')

    def error_response(code, message):
        """Return error in XML or JSON format."""
        if is_json():
            return jsonify({'status': 'failed', 'error': {'code': code, 'message': message}}), 400
        else:
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<subsonic-response status="failed" version="1.16.1">
<error code="{code}" message="{escape_xml(message)}"/>
</subsonic-response>''', mimetype='application/xml', status=400)

    def build_xml(data, indent=''):
        """Build XML string from dict/list."""
        xml = ''
        if isinstance(data, dict):
            for key, val in data.items():
                if val is None or val == '':
                    continue
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            attrs = ' '.join(f'{k}="{escape_xml(str(v))}"' for k, v in item.items() if v is not None and v != '')
                            xml += f'{indent}<{key} {attrs}/>\n'
                        else:
                            xml += f'{indent}<{key}>{escape_xml(str(item))}</{key}>\n'
                elif isinstance(val, dict):
                    xml += f'{indent}<{key}>\n{build_xml(val, indent + "  ")}{indent}</{key}>\n'
                else:
                    xml += f'{indent}<{key}>{escape_xml(str(val))}</{key}>\n'
        return xml

    # =========================================================================
    # System Endpoints
    # =========================================================================

    @app.route('/subsonic/rest/ping')
    def subsonic_ping():
        """Ping endpoint - server health check."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')
        return ok_response({'ping': {}})

    @app.route('/subsonic/rest/getLicense')
    def subsonic_license():
        """Get license info (always valid for open source)."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        data = {'license': {
            'valid': 'true',
            'email': 'mediaha@localhost',
            'licenseExpires': '9999999999999',
            'licenseOwner': 'MediaHa'
        }}
        return ok_response(data)

    # =========================================================================
    # Music Library Endpoints
    # =========================================================================

    @app.route('/subsonic/rest/getMusicFolders')
    def subsonic_music_folders():
        """Get music folders."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        data = {'musicFolders': {'musicFolder': [{'id': '1', 'name': 'Music'}]}}
        return ok_response(data)

    @app.route('/subsonic/rest/getIndexes')
    def subsonic_get_indexes():
        """Get indexes - list of artists with their folders."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        index_map = {}
        media_path = MEDIA_DIR

        if os.path.exists(media_path):
            for folder in os.listdir(media_path):
                folder_path = os.path.join(media_path, folder)
                if os.path.isdir(folder_path):
                    first_char = folder[0].upper() if folder else '#'
                    if not first_char.isalpha():
                        first_char = '#'

                    if first_char not in index_map:
                        index_map[first_char] = []

                    artist_id = f"artist_{hashlib.md5(folder.encode()).hexdigest()[:8]}"
                    index_map[first_char].append({
                        'id': artist_id,
                        'name': folder
                    })

        # Build indexes structure
        indexes = []
        for index_char in sorted(index_map.keys()):
            indexes.append({
                'name': index_char,
                'artist': index_map[index_char]
            })

        data = {'indexes': {'index': indexes, 'lastModified': int(time.time())}}
        return ok_response(data)

    @app.route('/subsonic/rest/getArtists')
    def subsonic_get_artists():
        """Get all artists (Subsonic 1.16+)."""
        return subsonic_get_indexes()

    @app.route('/subsonic/rest/getArtist')
    def subsonic_get_artist():
        """Get artist details with albums."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        artist_id = request.args.get('id', '')

        # Find artist folder
        artist_name = None
        artist_folder = None

        for folder in os.listdir(MEDIA_DIR):
            folder_path = os.path.join(MEDIA_DIR, folder)
            if os.path.isdir(folder_path):
                fid = f"artist_{hashlib.md5(folder.encode()).hexdigest()[:8]}"
                if fid == artist_id:
                    artist_name = folder
                    artist_folder = folder_path
                    break

        if not artist_folder:
            return error_response('notFound', 'Artist not found')

        # List albums
        albums = []
        for subfolder in os.listdir(artist_folder):
            subfolder_path = os.path.join(artist_folder, subfolder)
            if os.path.isdir(subfolder_path):
                album_id = f"album_{hashlib.md5(subfolder.encode()).hexdigest()[:8]}"
                song_count = sum(1 for f in os.listdir(subfolder_path) if f.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')))
                albums.append({
                    'id': album_id,
                    'name': subfolder,
                    'artist': artist_name,
                    'songCount': str(song_count),
                    'coverArt': album_id
                })

        data = {'artist': {'id': artist_id, 'name': artist_name, 'album': albums}}
        return ok_response(data)

    @app.route('/subsonic/rest/getAlbum')
    def subsonic_get_album():
        """Get album details with songs."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        album_id = request.args.get('id', '')

        # Find album folder
        album_folder = None
        artist_name = None
        album_name = None

        for folder in os.listdir(MEDIA_DIR):
            folder_path = os.path.join(MEDIA_DIR, folder)
            if os.path.isdir(folder_path):
                # Check subfolders
                for subfolder in os.listdir(folder_path):
                    subfolder_path = os.path.join(folder_path, subfolder)
                    if os.path.isdir(subfolder_path):
                        fid = f"album_{hashlib.md5(subfolder.encode()).hexdigest()[:8]}"
                        if fid == album_id:
                            album_folder = subfolder_path
                            artist_name = folder
                            album_name = subfolder
                            break

        if not album_folder:
            return error_response('notFound', 'Album not found')

        # Get cover art
        cover_id = album_id

        songs = []
        total_duration = 0

        for song_file in sorted(os.listdir(album_folder)):
            if not song_file.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                continue

            song_path = os.path.join(album_folder, song_file)
            song_id = f"song_{hashlib.md5(song_file.encode()).hexdigest()[:8]}"

            # Read metadata
            title = os.path.splitext(song_file)[0]
            duration = 0

            if song_file.lower().endswith('.mp3'):
                try:
                    audio = MP3(song_path, ID3=ID3)
                    if audio.tags:
                        if 'TIT2' in audio.tags:
                            title = audio.tags['TIT2'].text[0]
                        duration = int(audio.info.length)
                except:
                    pass

            # Check for LRC lyrics
            lrc_path = os.path.splitext(song_path)[0] + '.lrc'
            has_lyrics = 'true' if os.path.exists(lrc_path) else 'false'

            total_duration += duration

            songs.append({
                'id': song_id,
                'parent': album_id,
                'title': title,
                'album': album_name,
                'artist': artist_name,
                'duration': str(duration),
                'hasLyrics': has_lyrics,
                'isVideo': 'false',
                'type': 'music'
            })

        data = {
            'album': {
                'id': album_id,
                'name': album_name,
                'artist': artist_name,
                'coverArt': cover_id,
                'song': songs
            }
        }
        return ok_response(data)

    @app.route('/subsonic/rest/getMusicDirectory')
    def subsonic_music_directory():
        """Get music directory (generic folder view)."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        mid = request.args.get('id', '')

        # If root, return indexes
        if mid == '0' or mid == 'root' or not mid:
            return subsonic_get_indexes()

        # Find directory
        dir_path = None
        dir_name = mid

        for folder in os.listdir(MEDIA_DIR):
            folder_path = os.path.join(MEDIA_DIR, folder)
            if os.path.isdir(folder_path):
                fid = f"artist_{hashlib.md5(folder.encode()).hexdigest()[:8]}"
                if fid == mid:
                    dir_path = folder_path
                    dir_name = folder
                    break

                # Check subfolders
                for subfolder in os.listdir(folder_path):
                    subfolder_path = os.path.join(folder_path, subfolder)
                    if os.path.isdir(subfolder_path):
                        fid = f"album_{hashlib.md5(subfolder.encode()).hexdigest()[:8]}"
                        if fid == mid:
                            dir_path = subfolder_path
                            dir_name = subfolder
                            break

        if not dir_path:
            return error_response('notFound', 'Directory not found')

        children = []
        for entry in sorted(os.listdir(dir_path)):
            entry_path = os.path.join(dir_path, entry)
            if os.path.isdir(entry_path):
                entry_id = f"album_{hashlib.md5(entry.encode()).hexdigest()[:8]}"
                children.append({'id': entry_id, 'title': entry, 'isDir': 'true'})
            elif entry.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                entry_id = f"song_{hashlib.md5(entry.encode()).hexdigest()[:8]}"
                children.append({'id': entry_id, 'title': os.path.splitext(entry)[0], 'isDir': 'false'})

        data = {'directory': {'id': mid, 'name': dir_name, 'child': children}}
        return ok_response(data)

    @app.route('/subsonic/rest/getSong')
    def subsonic_get_song():
        """Get single song details."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        song_id = request.args.get('id', '')

        # Find song in media directory
        song_path = None

        for root, dirs, files in os.walk(MEDIA_DIR):
            for f in files:
                if f.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                    sid = f"song_{hashlib.md5(f.encode()).hexdigest()[:8]}"
                    if sid == song_id:
                        song_path = os.path.join(root, f)
                        break

        if not song_path:
            return error_response('notFound', 'Song not found')

        # Read metadata
        title = os.path.splitext(os.path.basename(song_path))[0]
        artist = os.path.basename(os.path.dirname(song_path))
        album = artist
        duration = 0

        if song_path.lower().endswith('.mp3'):
            try:
                audio = MP3(song_path, ID3=ID3)
                if audio.tags:
                    if 'TIT2' in audio.tags:
                        title = audio.tags['TIT2'].text[0]
                    if 'TPE1' in audio.tags:
                        artist = audio.tags['TPE1'].text[0]
                    if 'TALB' in audio.tags:
                        album = audio.tags['TALB'].text[0]
                    duration = int(audio.info.length)
            except:
                pass

        # Check for lyrics
        lrc_path = os.path.splitext(song_path)[0] + '.lrc'
        has_lyrics = 'true' if os.path.exists(lrc_path) else 'false'

        data = {
            'song': {
                'id': song_id,
                'title': title,
                'artist': artist,
                'album': album,
                'duration': str(duration),
                'hasLyrics': has_lyrics
            }
        }
        return ok_response(data)

    # =========================================================================
    # Streaming & Download
    # =========================================================================

    @app.route('/subsonic/rest/stream')
    def subsonic_stream():
        """Stream audio file."""
        if not auth_required():
            return Response('Unauthorized', status=401)

        song_id = request.args.get('id', '')

        # Find song
        song_path = None

        for root, dirs, files in os.walk(MEDIA_DIR):
            for f in files:
                if f.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                    sid = f"song_{hashlib.md5(f.encode()).hexdigest()[:8]}"
                    if sid == song_id:
                        song_path = os.path.join(root, f)
                        break

        if not song_path or not os.path.exists(song_path):
            return Response('Not found', status=404)

        # Determine mime type
        mime_type = 'audio/mpeg'
        if song_path.lower().endswith('.flac'):
            mime_type = 'audio/flac'
        elif song_path.lower().endswith('.m4a'):
            mime_type = 'audio/mp4'
        elif song_path.lower().endswith('.ogg'):
            mime_type = 'audio/ogg'
        elif song_path.lower().endswith('.wav'):
            mime_type = 'audio/wav'

        return send_file(song_path, mimetype=mime_type)

    @app.route('/subsonic/rest/download')
    def subsonic_download():
        """Download audio file."""
        return subsonic_stream()

    # =========================================================================
    # Cover Art
    # =========================================================================

    @app.route('/subsonic/rest/getCoverArt')
    def subsonic_cover_art():
        """Get cover art."""
        if not auth_required():
            return Response('Unauthorized', status=401)

        art_id = request.args.get('id', '')

        media_path = MEDIA_DIR
        cover_path = None

        # Find cover art
        for root, dirs, files in os.walk(media_path):
            # Check for embedded cover in MP3
            for f in files:
                if f.lower().endswith('.mp3'):
                    sid = f"song_{hashlib.md5(f.encode()).hexdigest()[:8]}"
                    if sid == art_id:
                        song_path = os.path.join(root, f)
                        try:
                            audio = MP3(song_path, ID3=ID3)
                            if audio.tags:
                                for tag in audio.tags.values():
                                    if tag.FrameID == 'APIC':
                                        return Response(tag.data, mimetype=tag.mime)
                        except:
                            pass

            # Check for cover image files
            for f in files:
                if f.lower().startswith(('cover', 'folder', 'album', 'front')):
                    fid = f"cover_{hashlib.md5(f.encode()).hexdigest()[:8]}"
                    if fid == art_id:
                        cover_path = os.path.join(root, f)
                        break

            # Check for album/artist folder cover
            if not cover_path:
                for cf in ['cover.jpg', 'cover.jpeg', 'cover.png', 'folder.jpg', 'folder.png']:
                    cp = os.path.join(root, cf)
                    if os.path.exists(cp):
                        cover_path = cp
                        break

        if cover_path and os.path.exists(cover_path):
            ext = os.path.splitext(cover_path)[1].lower()
            mime = 'image/jpeg'
            if ext == '.png':
                mime = 'image/png'
            return send_file(cover_path, mimetype=mime)

        return Response('Not found', status=404)

    # =========================================================================
    # Lyrics
    # =========================================================================

    @app.route('/subsonic/rest/getLyrics')
    def subsonic_get_lyrics():
        """Get lyrics for a song - looks for .lrc file in same folder."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        artist = request.args.get('artist', '')
        title = request.args.get('title', '')

        lyrics_text = ""

        # Normalize title for matching
        search_title = title.lower().strip() if title else ""

        for root, dirs, files in os.walk(MEDIA_DIR):
            for f in files:
                if not f.lower().endswith('.lrc'):
                    continue

                lrc_path = os.path.join(root, f)
                lrc_title = os.path.splitext(f)[0].lower().strip()

                # Match by title in filename
                if search_title and (search_title in lrc_title or lrc_title in search_title):
                    try:
                        with open(lrc_path, 'r', encoding='utf-8-sig') as lf:
                            lyrics_text = lf.read()
                            break
                    except:
                        pass

                # Also check embedded lyrics in MP3
                mp3_path = os.path.splitext(lrc_path)[0] + '.mp3'
                if os.path.exists(mp3_path):
                    try:
                        audio = MP3(mp3_path, ID3=ID3)
                        if audio.tags:
                            for tag in audio.tags.values():
                                if tag.FrameID == 'USLT':
                                    lyrics_text = tag.text
                                    break
                    except:
                        pass

            if lyrics_text:
                break

        data = {'lyrics': {'artist': artist, 'title': title, '@text': lyrics_text}}
        return ok_response(data)

    # =========================================================================
    # Search
    # =========================================================================

    @app.route('/subsonic/rest/search')
    def subsonic_search():
        """Search for music."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        query = request.args.get('query', '')
        if not query:
            query = request.args.get('q', '')

        query_lower = query.lower()
        songs = []

        # Search files
        for root, dirs, files in os.walk(MEDIA_DIR):
            for f in files:
                if not f.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                    continue

                song_path = os.path.join(root, f)
                song_id = f"song_{hashlib.md5(f.encode()).hexdigest()[:8]}"

                # Read metadata
                title = os.path.splitext(f)[0]
                artist = os.path.basename(os.path.dirname(song_path))

                if song_path.lower().endswith('.mp3'):
                    try:
                        audio = MP3(song_path, ID3=ID3)
                        if audio.tags:
                            if 'TIT2' in audio.tags:
                                title = audio.tags['TIT2'].text[0]
                            if 'TPE1' in audio.tags:
                                artist = audio.tags['TPE1'].text[0]
                    except:
                        pass

                # Check if matches query
                if (query_lower in title.lower() or query_lower in artist.lower() or
                    query_lower in f.lower()):
                    songs.append({
                        'id': song_id,
                        'title': title,
                        'artist': artist
                    })

        data = {'searchResult': {'song': songs}}
        return ok_response(data)

    @app.route('/subsonic/rest/search2')
    def subsonic_search2():
        """Search with structured results."""
        return subsonic_search()

    @app.route('/subsonic/rest/search3')
    def subsonic_search3():
        """Search with structured results (v3)."""
        return subsonic_search()

    # =========================================================================
    # Playlists
    # =========================================================================

    @app.route('/subsonic/rest/getPlaylists')
    def subsonic_get_playlists():
        """Get user playlists."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        data = {'playlists': {'playlist': [{'id': '0', 'name': 'Favorites'}]}}
        return ok_response(data)

    @app.route('/subsonic/rest/getPlaylist')
    def subsonic_get_playlist():
        """Get playlist details."""
        if not auth_required():
            return error_response('credentials', 'Invalid credentials')

        playlist_id = request.args.get('id', '')
        data = {'playlist': {'id': playlist_id, 'name': 'Favorites', 'entry': []}}
        return ok_response(data)
