# -*- coding: utf-8 -*-
"""Audio metadata routes."""
import os
import base64
import re
import urllib.request
import json
import requests
from flask import request
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC


MEDIA_DIR = '/media'


def register_audio_routes(app):
    """Register audio metadata routes."""

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
                try:
                    audio.tags.delall('APIC')
                    cover_value = data['cover']

                    if cover_value.startswith('http://') or cover_value.startswith('https://'):
                        try:
                            with urllib.request.urlopen(cover_value, timeout=10) as response:
                                cover_data = response.read()
                                content_type = response.headers.get('Content-Type', 'image/jpeg')
                                mime = content_type.split('/')[1] if '/' in content_type else 'jpeg'
                                if mime == 'jpeg':
                                    mime = 'jpeg'
                        except Exception as e:
                            print(f"Error downloading cover from URL: {e}")
                            mime = 'jpeg'
                            cover_data = None
                    elif ',' in cover_value:
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

            audio.save()

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

            # Search MusicBrainz
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

            # Search Deezer
            if cover_source in ['deezer', 'all']:
                try:
                    deezer_res = requests.get('https://api.deezer.com/search', params={'q': search_term, 'limit': 5, 'output': 'json'})
                    if deezer_res.status_code == 200:
                        deezer_data = deezer_res.json()
                        tracks = deezer_data.get('data', [])
                        if tracks:
                            dz_idx = min(result_offset, len(tracks) - 1)
                            track = tracks[dz_idx]
                            album_data = track.get('album', {})
                            cover_url = album_data.get('cover_xl') or album_data.get('cover_big') or album_data.get('cover_medium')
                            if not cover_url:
                                cover_url = track.get('artist', {}).get('picture_xl') or track.get('artist', {}).get('picture_big')
                            if cover_url:
                                cover_data = requests.get(cover_url).content
                                cover_b64 = base64.b64encode(cover_data).decode('utf-8')
                                add_cover_option('deezer', cover_b64, cover_url)
                                search_info['deezer']['found'] = True
                except Exception as e:
                    print(f"Deezer search error: {e}")

            # Search o3ics from multiple sources
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

    def detect_language(text):
        if not text:
            return 'english'
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
            return 'japanese'
        if re.search(r'[\u4E00-\u9FFF]', text):
            return 'chinese'
        return 'english'
