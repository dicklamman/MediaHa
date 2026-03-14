$text = Get-Content 'home-assistant-addon/src/main.py' -Raw

$new_code = @"

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

        if not title:
            title = os.path.splitext(os.path.basename(file_path))[0]
            artist = artist or "Unknown Artist"

        # Search lrcLib
        lyrics = ""
        try:
            lrc_res = requests.get('https://lrclib.net/api/search', params={'track_name': title, 'artist_name': artist})
            if lrc_res.status_code == 200 and lrc_res.json():
                best_match = lrc_res.json()[0]
                lyrics = best_match.get('syncedLyrics') or best_match.get('plainLyrics') or ""
        except Exception:
            pass
        
        # Search iTunes for cover/album
        cover_b64 = None
        mime_type = "image/jpeg"
        try:
            itunes_res = requests.get('https://itunes.apple.com/search', params={'term': f"{title} {artist}", 'media': 'music', 'limit': 1})
            if itunes_res.status_code == 200 and itunes_res.json().get('results'):
                track = itunes_res.json()['results'][0]
                if not album and 'collectionName' in track:
                    album = track['collectionName']
                
                cover_url = track.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                if cover_url:
                    cover_data = requests.get(cover_url).content
                    cover_b64 = base64.b64encode(cover_data).decode('utf-8')
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
