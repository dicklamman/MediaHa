const fs = require('fs');
const fPath = 'home-assistant-addon/src/main.py';
let text = fs.readFileSync(fPath, 'utf8');
let target = `        title = audio.tags['TIT2'].text[0] if audio.tags and 'TIT2' in audio.tags else ""
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
            pass`;

let newCode = `        title = audio.tags['TIT2'].text[0] if audio.tags and 'TIT2' in audio.tags else ""
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

        # Search iTunes for cover/album/artist/title
        cover_b64 = None
        mime_type = "image/jpeg"
        try:
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
            pass`;

let targetB = target.replace(/\r\n/g, '\n');
let codeB = text.replace(/\r\n/g, '\n');

if (codeB.includes(targetB)) {
    codeB = codeB.replace(targetB, newCode);
    fs.writeFileSync(fPath, codeB);
    console.log('Success in Node!');
} else {
    console.log('Not found in Node!');
}
