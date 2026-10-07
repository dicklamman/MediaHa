# -*- coding: utf-8 -*-
"""SubSonic API routes for Navidrome/SubSonic clients."""
import os
import base64
import hashlib
import time
import re
from flask import request, Response, session
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

    def make_response_xml(content, status='ok', version='1.16.1'):
        """Create SubSonic XML response."""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<subsonic-response status="{status}" version="{version}">
{content}
</subsonic-response>'''

    def escape_xml(text):
        """Escape XML special characters."""
        if not text:
            return ''
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

    # =========================================================================
    # System Endpoints
    # =========================================================================

    @app.route('/subsonic/rest/ping')
    def subsonic_ping():
        """Ping endpoint - server health check."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        return Response(make_response_xml('<ping/>'), mimetype='application/xml')

    @app.route('/subsonic/rest/getLicense')
    def subsonic_license():
        """Get license info (always valid for open source)."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        license_xml = '''<license valid="true" email="mediaha@localhost" licenseExpires="9999999999999">
    <licenseOwner>MediaHa</licenseOwner>
</license>'''
        return Response(make_response_xml(license_xml), mimetype='application/xml')

    # =========================================================================
    # Music Library Endpoints
    # =========================================================================

    @app.route('/subsonic/rest/getMusicFolders')
    def subsonic_music_folders():
        """Get music folders."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        folders_xml = '''<musicFolders>
    <musicFolder id="1" name="Music"/>
</musicFolders>'''
        return Response(make_response_xml(folders_xml), mimetype='application/xml')

    @app.route('/subsonic/rest/getArtists')
    def subsonic_get_artists():
        """Get all artists."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        artists = {}
        index_map = {}

        # Scan media directory
        media_path = os.path.join(MEDIA_DIR)
        if os.path.exists(media_path):
            for folder in os.listdir(media_path):
                folder_path = os.path.join(media_path, folder)
                if os.path.isdir(folder_path):
                    # This is an artist folder
                    artist_name = folder
                    first_char = artist_name[0].upper() if artist_name else '#'
                    if not first_char.isalpha():
                        first_char = '#'

                    if first_char not in index_map:
                        index_map[first_char] = []

                    # Count albums
                    album_count = 0
                    for subfolder in os.listdir(folder_path):
                        subfolder_path = os.path.join(folder_path, subfolder)
                        if os.path.isdir(subfolder_path):
                            album_count += 1
                        elif subfolder.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg')):
                            album_count += 1

                    index_map[first_char].append({
                        'id': f"artist_{hashlib.md5(folder.encode()).hexdigest()[:8]}",
                        'name': artist_name,
                        'albumCount': album_count
                    })

        # Build XML
        artists_xml = '<artists index="true">'
        for index in sorted(index_map.keys()):
            for artist in sorted(index_map[index], key=lambda x: x['name']):
                artists_xml += f'''<artist id="{escape_xml(artist['id'])}" name="{escape_xml(artist['name'])}" albumCount="{artist['albumCount']}"/>'''
        artists_xml += '</artists>'

        return Response(make_response_xml(artists_xml), mimetype='application/xml')

    @app.route('/subsonic/rest/getArtist')
    def subsonic_get_artist():
        """Get artist details with albums."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        artist_id = request.args.get('id', '')
        folder_name = artist_id.replace('artist_', '')

        # Find artist folder
        media_path = os.path.join(MEDIA_DIR)
        artist_name = None
        artist_folder = None

        for folder in os.listdir(media_path):
            folder_path = os.path.join(media_path, folder)
            if os.path.isdir(folder_path):
                fid = f"artist_{hashlib.md5(folder.encode()).hexdigest()[:8]}"
                if fid == artist_id:
                    artist_name = folder
                    artist_folder = folder_path
                    break

        if not artist_folder:
            return Response(make_response_xml('<error code="notFound" message="Artist not found"/>', 'failed'),
                          mimetype='application/xml')

        albums_xml = '<artist id="{0}" name="{1}">'.format(
            escape_xml(artist_id), escape_xml(artist_name))

        # List albums
        for subfolder in os.listdir(artist_folder):
            subfolder_path = os.path.join(artist_folder, subfolder)
            if os.path.isdir(subfolder_path):
                album_id = f"album_{hashlib.md5(subfolder.encode()).hexdigest()[:8]}"
                albums_xml += f'<album id="{album_id}" name="{escape_xml(subfolder)}" artist="{escape_xml(artist_name)}" songCount="0" duration="0"/>'

        albums_xml += '</artist>'

        return Response(make_response_xml(albums_xml), mimetype='application/xml')

    @app.route('/subsonic/rest/getAlbum')
    def subsonic_get_album():
        """Get album details with songs."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        album_id = request.args.get('id', '')

        # Find album folder
        media_path = os.path.join(MEDIA_DIR)
        album_folder = None
        artist_name = None
        album_name = None

        for folder in os.listdir(media_path):
            folder_path = os.path.join(media_path, folder)
            if os.path.isdir(folder_path):
                fid = f"album_{hashlib.md5(folder.encode()).hexdigest()[:8]}"
                if fid == album_id:
                    album_folder = folder_path
                    artist_name = folder  # folder is artist name
                    album_name = album_id.replace('album_', '')
                    break

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
            return Response(make_response_xml('<error code="notFound" message="Album not found"/>', 'failed'),
                          mimetype='application/xml')

        # Get cover art
        cover_id = None
        for f in os.listdir(album_folder):
            if f.lower().startswith('cover') or f.lower().startswith('folder'):
                cover_id = f"cover_{hashlib.md5(f.encode()).hexdigest()[:8]}"

        album_xml = f'''<album id="{escape_xml(album_id)}" name="{escape_xml(album_name)}" artist="{escape_xml(artist_name)}" coverArt="{cover_id or album_id}">'''

        # List songs
        song_count = 0
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
            elif song_file.lower().endswith('.flac'):
                try:
                    from mutagen.flac import FLAC
                    audio = FLAC(song_path)
                    if audio.tags:
                        if 'TITLE' in audio.tags:
                            title = audio.tags['TITLE'][0]
                        duration = int(audio.info.length)
                except:
                    pass

            song_count += 1
            total_duration += duration

            # Check for LRC lyrics
            lrc_path = os.path.splitext(song_path)[0] + '.lrc'
            has_lyrics = 'true' if os.path.exists(lrc_path) else 'false'

            album_xml += f'''<song id="{song_id}" parent="{album_id}" title="{escape_xml(title)}" album="{escape_xml(album_name)}" artist="{escape_xml(artist_name)}" duration="{duration}" hasLyrics="{has_lyrics}"/>'''

        album_xml += f'</album>'

        return Response(make_response_xml(album_xml), mimetype='application/xml')

    @app.route('/subsonic/rest/getMusicDirectory')
    def subsonic_music_directory():
        """Get music directory (generic folder view)."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        mid = request.args.get('id', '')
        media_path = os.path.join(MEDIA_DIR)

        # If root, show artists
        if mid == '0' or mid == 'root':
            return subsonic_get_artists()

        # Find directory
        dir_path = None
        dir_name = mid

        for folder in os.listdir(media_path):
            folder_path = os.path.join(media_path, folder)
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
            return Response(make_response_xml('<error code="notFound" message="Directory not found"/>', 'failed'),
                          mimetype='application/xml')

        dir_xml = f'<directory id="{escape_xml(mid)}" name="{escape_xml(dir_name)}">'

        for entry in sorted(os.listdir(dir_path)):
            entry_path = os.path.join(dir_path, entry)
            if os.path.isdir(entry_path):
                entry_id = f"album_{hashlib.md5(entry.encode()).hexdigest()[:8]}"
                dir_xml += f'<child id="{entry_id}" title="{escape_xml(entry)}" isDir="true"/>'
            elif entry.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                entry_id = f"song_{hashlib.md5(entry.encode()).hexdigest()[:8]}"
                dir_xml += f'<child id="{entry_id}" title="{escape_xml(os.path.splitext(entry)[0])}" isDir="false"/>'

        dir_xml += '</directory>'

        return Response(make_response_xml(dir_xml), mimetype='application/xml')

    @app.route('/subsonic/rest/getSong')
    def subsonic_get_song():
        """Get single song details."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        song_id = request.args.get('id', '')

        # Find song in media directory
        song_path = None
        media_path = os.path.join(MEDIA_DIR)

        for root, dirs, files in os.walk(media_path):
            for f in files:
                if f.lower().endswith(('.mp3', '.flac', '.m4a', '.ogg', '.wav')):
                    sid = f"song_{hashlib.md5(f.encode()).hexdigest()[:8]}"
                    if sid == song_id:
                        song_path = os.path.join(root, f)
                        break

        if not song_path:
            return Response(make_response_xml('<error code="notFound" message="Song not found"/>', 'failed'),
                          mimetype='application/xml')

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
        has_lyrics = os.path.exists(lrc_path)

        song_xml = f'''<song id="{escape_xml(song_id)}" title="{escape_xml(title)}" artist="{escape_xml(artist)}" album="{escape_xml(album)}" duration="{duration}" hasLyrics="{'true' if has_lyrics else 'false'}"/>'''

        return Response(make_response_xml(song_xml), mimetype='application/xml')

    # =========================================================================
    # Streaming & Download
    # =========================================================================

    @app.route('/subsonic/rest/stream')
    def subsonic_stream():
        """Stream audio file."""
        if not auth_required():
            return Response('Unauthorized', status=401)

        song_id = request.args.get('id', '')
        max_bitrate = request.args.get('maxBitRate', '0')

        # Find song
        song_path = None
        media_path = os.path.join(MEDIA_DIR)

        for root, dirs, files in os.walk(media_path):
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
        size = request.args.get('size', '0')

        media_path = os.path.join(MEDIA_DIR)
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
                elif art_id.startswith('album_') or art_id.startswith('artist_'):
                    # Check in current directory for cover image
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
        """Get lyrics for a song - looks for .lrc file in same folder as audio."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        artist = request.args.get('artist', '')
        title = request.args.get('title', '')

        lyrics_text = ""

        # Search for matching LRC file in /media/music
        media_path = os.path.join(MEDIA_DIR)

        # Normalize title for matching
        search_title = title.lower().strip() if title else ""

        for root, dirs, files in os.walk(media_path):
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

        lyrics_xml = f'<lyrics artist="{escape_xml(artist)}" title="{escape_xml(title)}"><![CDATA[{lyrics_text}]]></lyrics>'
        return Response(make_response_xml(lyrics_xml), mimetype='application/xml')

    # =========================================================================
    # Search
    # =========================================================================

    @app.route('/subsonic/rest/search')
    def subsonic_search():
        """Search for music."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        query = request.args.get('query', '')
        if not query:
            query = request.args.get('q', '')

        media_path = os.path.join(MEDIA_DIR)
        query_lower = query.lower()

        search_xml = '<searchResult>'

        # Search files
        for root, dirs, files in os.walk(media_path):
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
                    search_xml += f'''<song id="{song_id}" title="{escape_xml(title)}" artist="{escape_xml(artist)}"/>'''

        search_xml += '</searchResult>'
        return Response(make_response_xml(search_xml), mimetype='application/xml')

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
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        return Response(make_response_xml('<playlists><playlist id="0" name="Favorites"/></playlists>'),
                       mimetype='application/xml')

    @app.route('/subsonic/rest/getPlaylist')
    def subsonic_get_playlist():
        """Get playlist details."""
        if not auth_required():
            return Response(make_response_xml('<error code="credentials" message="Invalid credentials"/>', 'failed'),
                          mimetype='application/xml')

        playlist_id = request.args.get('id', '')
        return Response(make_response_xml(f'<playlist id="{escape_xml(playlist_id)}" name="Favorites"/>'),
                       mimetype='application/xml')
