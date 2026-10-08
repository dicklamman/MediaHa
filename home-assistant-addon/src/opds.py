"""OPDS catalog routes for ebook readers"""
import os
import base64
import sqlite3
from flask import request, Response, session, send_file
from pathlib import Path
import json
import datetime

CALIBRE_CONFIG_PATH = '/data/calibre_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/calibre_options.json')

def escape_xml(text):
    """Escape XML special characters"""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def slugify(text):
    """Convert text to URL-safe slug"""
    if not text:
        return ''
    text = str(text)
    # Replace spaces with underscores, remove special chars
    import re
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w\-_]', '', text)
    return text

def register_routes(app, check_auth):
    """Register OPDS routes with the Flask app"""

    def make_opds_header(title, feed_id, self_path):
        now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        return [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:thr="http://purl.org/syndication/thread/1.0">',
            '  <title>' + escape_xml(title) + '</title>',
            '  <id>' + feed_id + '</id>',
            '  <updated>' + now + '</updated>',
            '  <icon>/media/books/book.png</icon>',
            '  <link href="/opds" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="start" title="Home"/>',
            '  <link href="' + self_path + '" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="self"/>',
            '  <link href="/opds/search" type="application/opensearchdescription+xml" rel="search" title="Search here"/>'
        ]

    def make_book_entry(cursor, book_row):
        """Create a detailed book entry"""
        now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        book_id = book_row["id"]
        title = escape_xml(book_row["title"])
        
        # Get UUID for this book (use book_id as fallback)
        cursor.execute("SELECT uuid FROM books WHERE id = ?", (book_id,))
        uuid_row = cursor.fetchone()
        entry_uuid = 'urn:uuid:' + (uuid_row["uuid"] if uuid_row and uuid_row["uuid"] else str(book_id))
        
        # Get series info
        series_name = book_row["series_name"] if "series_name" in book_row.keys() else ""
        series_index = book_row["series_index"] if "series_index" in book_row.keys() else None
        series_id = book_row["series_id"] if "series_id" in book_row.keys() else None
        series_content = ''
        series_link = ''
        if series_name and series_index:
            series_slug = slugify(series_name)
            series_content = '<strong>Series:</strong>Book ' + str(int(series_index)) + ' in the ' + escape_xml(series_name) + ' series<br />'
            series_link = '  <link href="/opds/series/' + str(series_id) + '/' + series_slug + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="related" title="Book ' + str(int(series_index)) + ' in the ' + escape_xml(series_name) + ' series"/>'
        
        # Get author info
        author_name = book_row["author_name"] if "author_name" in book_row.keys() else ""
        author_id = book_row["author_id"] if "author_id" in book_row.keys() else None
        author_content = ''
        if author_name:
            author_slug = slugify(author_name)
            author_content = '<author><name>' + escape_xml(author_name) + '</name><uri>/opds/authors/' + str(author_id if author_id else '0') + '/' + author_slug + '</uri></author>'
        
        # Get metadata
        pubdate = book_row["pubdate"] if "pubdate" in book_row.keys() else ""
        issued = pubdate[:10] if pubdate else now[:10]
        language = "en"  # Default to 'en' if not found
        ext = book_row["format"] if "format" in book_row.keys() else "epub"
        ext = ext.lower()
        file_url = '/opds/fetch/' + str(book_id) + '/' + ext
        file_length = book_row["file_size"] if "file_size" in book_row.keys() and book_row["file_size"] else 0
        
        # Build entry
        entry = [
            '  <entry>',
            '    <title>' + title + '</title>',
            '    <updated>' + now + '</updated>',
            '    <id>' + entry_uuid + '</id>',
            '    <content type="text/html">' + series_content + '</content>',
            '    <link href="/opds/cover/' + str(book_id) + '" type="image/jpeg" rel="http://opds-spec.org/image"/>',
            '    <link href="/opds/cover/' + str(book_id) + '" type="image/jpeg" rel="http://opds-spec.org/image/thumbnail"/>'
        ]
        
        # Add acquisition link with metadata (include filesize for Paperback compatibility)
        acq_link = '    <link href="' + file_url + '" type="application/' + ext + '+zip" rel="http://opds-spec.org/acquisition" title="' + ext.upper() + '"'
        if file_length:
            acq_link += ' length="' + str(file_length) + '"'
        acq_link += ' />'
        entry.append(acq_link)
        
        # Add author link if available
        if author_name and author_id:
            author_slug = slugify(author_name)
            entry.append('    <link href="/opds/authors/' + str(author_id) + '/' + author_slug + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="related" title="Other books by ' + escape_xml(author_name) + '"/>')
        
        # Add series link
        if series_link:
            entry.append(series_link)
        
        # Add author and metadata
        if author_content:
            entry.append('    ' + author_content)
        entry.append('    <dcterms:issued>' + issued + '</dcterms:issued>')
        entry.append('    <published>' + issued + 'T00:00:00Z</published>')
        entry.append('    <dcterms:language>' + escape_xml(language) + '</dcterms:language>')
        entry.append('  </entry>')

        return '\n'.join(entry)

    def _authenticate(self):
        """Check Basic Auth from session or header"""
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
        return authenticated

    def _get_calibre_config(self):
        """Load Calibre config and return (calibre_path, metadata_db) or error Response"""
        if os.path.exists(CALIBRE_CONFIG_PATH):
            with open(CALIBRE_CONFIG_PATH, 'r') as f:
                config = json.load(f)
        else:
            return None, None, Response('<?xml version="1.0"?><opds><error>Config not found</error></opds>',
                                       mimetype='application/xml')

        calibre_library_path = config.get('calibre_library_path', '')
        if not calibre_library_path:
            return None, None, Response('<?xml version="1.0"?><opds><error>Calibre path not set</error></opds>',
                                        mimetype='application/xml')

        calibre_path = Path(calibre_library_path)
        # Handle Calibre's folder structure: library/books/{book_id}/
        if (calibre_path / 'books').exists() and (calibre_path / 'books').is_dir():
            calibre_path = calibre_path / 'books'
        metadata_db = Path(calibre_library_path) / 'metadata.db'

        if not metadata_db.exists():
            return None, None, Response('<?xml version="1.0"?><opds><error>metadata.db not found</error></opds>',
                                        mimetype='application/xml')

        return calibre_path, metadata_db, None

    def _get_db_connection(self, metadata_db):
        """Create a SQLite connection with row factory"""
        conn = sqlite3.connect(str(metadata_db), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_book_file(self, book_id, ext, calibre_path):
        """Find the book file for a given book ID and format extension.

        Searches for the file in this order:
        1. <book_id>/<book_id>.<ext>   (Calibre default)
        2. <book_id>/<any>.<ext>       (any matching format in book folder)
        3. <any>/<book_id>.<ext>       (file named after book_id in root)
        Returns (file_path, file_size) or (None, None) if not found.
        """
        # Normalize extension
        ext = ext.lower().lstrip('.')

        # Search in book folder
        book_folder = calibre_path / str(book_id)
        if book_folder.exists() and book_folder.is_dir():
            for f in book_folder.iterdir():
                if f.suffix.lstrip('.').lower() == ext:
                    return f, f.stat().st_size

        # Search root folder for file named <book_id>.<ext>
        for f in calibre_path.iterdir():
            if f.is_file() and f.suffix.lstrip('.').lower() == ext:
                # Match if stem is the book_id or contains it
                if f.stem == str(book_id):
                    return f, f.stat().st_size

        return None, None

    @app.route('/opds')
    @app.route('/opds/')
    def opds_root():
        """OPDS root - Books and Comics"""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            conn = _get_db_connection(metadata_db)

            xml_parts = make_opds_header('MediaHa Library', 'mediaha:root', '/opds')

            # Books entry with count
            cursor.execute("""
                SELECT COUNT(DISTINCT b.id) as cnt FROM books b
                JOIN data d ON b.id = d.book WHERE d.format = 'EPUB'
            """)
            book_count = cursor.fetchone()["cnt"]
            xml_parts.append('  <entry><title>Books</title><updated>' + datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '</updated><id>mediaha:nav:books</id><content type="text">' + str(book_count) + ' books</content><icon>/media/books/book.png</icon><link href="/opds/books" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(book_count) + '"/></entry>')

            # Comics entry with count
            cursor.execute("""
                SELECT COUNT(DISTINCT b.id) as cnt FROM books b
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                WHERE t.name = 'Comics'
            """)
            comic_count = cursor.fetchone()["cnt"]
            xml_parts.append('  <entry><title>Comics</title><updated>' + datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '</updated><id>mediaha:nav:comics</id><content type="text">' + str(comic_count) + ' comics</content><icon>/media/books/comic.png</icon><link href="/opds/comics" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(comic_count) + '"/></entry>')

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('<?xml version="1.0"?><opds><error>' + escape_xml(str(e)) + '</error></opds>',
                            mimetype='application/xml')

    @app.route('/opds/books')
    def opds_books():
        """OPDS books list - shows series and standalone books"""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            conn = _get_db_connection(metadata_db)

            xml_parts = make_opds_header('Books', 'mediaha:books', '/opds/books')

            # Show book series with counts
            cursor.execute("""
                SELECT s.id, s.name, COUNT(DISTINCT b.id) as book_count
                FROM series s
                JOIN books_series_link bsl ON s.id = bsl.series
                JOIN data d ON bsl.book = d.book
                JOIN books b ON bsl.book = b.id
                WHERE d.format = 'EPUB'
                GROUP BY s.id, s.name
                ORDER BY s.name
            """)
            for row in cursor.fetchall():
                series_slug = slugify(row["name"])
                xml_parts.append('  <entry><title>' + escape_xml(row["name"]) + '</title><updated>' + datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '</updated><id>mediaha:series:' + str(row["id"]) + '</id><content type="text">' + str(row["book_count"]) + ' books</content><link href="/opds/series/' + str(row["id"]) + '/' + series_slug + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(row["book_count"]) + '"/></entry>')

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('<?xml version="1.0"?><opds><error>' + escape_xml(str(e)) + '</error></opds>',
                            mimetype='application/xml')

    @app.route('/opds/comics')
    def opds_comics():
        """OPDS comics list - shows comic series"""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            conn = _get_db_connection(metadata_db)

            xml_parts = make_opds_header('Comics', 'mediaha:comics', '/opds/comics')

            # Show comic series with counts - use /opds/series/ for detail pages
            cursor.execute("""
                SELECT s.id, s.name, COUNT(DISTINCT b.id) as book_count
                FROM series s
                JOIN books_series_link bsl ON s.id = bsl.series
                JOIN books_tags_link btl ON bsl.book = btl.book
                JOIN tags t ON btl.tag = t.id
                JOIN books b ON bsl.book = b.id
                WHERE t.name = 'Comics'
                GROUP BY s.id, s.name
                ORDER BY s.name
            """)
            for row in cursor.fetchall():
                series_slug = slugify(row["name"])
                xml_parts.append('  <entry><title>' + escape_xml(row["name"]) + '</title><updated>' + datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '</updated><id>mediaha:series:' + str(row["id"]) + '</id><content type="text">' + str(row["book_count"]) + ' books</content><link href="/opds/series/' + str(row["id"]) + '/' + series_slug + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(row["book_count"]) + '"/></entry>')

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('<?xml version="1.0"?><opds><error>' + escape_xml(str(e)) + '</error></opds>',
                            mimetype='application/xml')

    @app.route('/opds/series/<series_id>/<path:series_name>')
    def opds_series_detail(series_id, series_name):
        """OPDS series detail - shows all books in a series"""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            conn = _get_db_connection(metadata_db)

            # Get series info
            cursor.execute("""
                SELECT s.id, s.name, COUNT(DISTINCT btl.book) as comic_count
                FROM series s
                LEFT JOIN books_series_link bsl ON s.id = bsl.series
                LEFT JOIN books_tags_link btl ON bsl.book = btl.book AND btl.tag IN (SELECT id FROM tags WHERE name = 'Comics')
                WHERE s.id = ?
                GROUP BY s.id
            """, (series_id,))
            series_row = cursor.fetchone()

            if not series_row:
                conn.close()
                return Response('<?xml version="1.0"?><opds><error>Series not found</error></opds>',
                              mimetype='application/xml')

            series_title = series_row["name"]
            comic_count = series_row["comic_count"]
            is_comic = comic_count > 0

            self_path = '/opds/series/' + series_id + '/' + slugify(series_title)
            xml_parts = make_opds_header(series_title, 'mediaha:series:' + series_id, self_path)

            # Get books in series
            if is_comic:
                cursor.execute("""
                    SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                           s.id as series_id, s.name as series_name,
                           d.format, d.name as filename, d.uncompressed_size as file_size
                    FROM books b
                    JOIN books_series_link bsl ON b.id = bsl.book
                    JOIN series s ON bsl.series = s.id
                    JOIN books_tags_link btl ON b.id = btl.book
                    JOIN tags t ON btl.tag = t.id
                    JOIN data d ON b.id = d.book
                    WHERE bsl.series = ? AND t.name = 'Comics'
                    ORDER BY b.series_index
                """, (series_id,))
            else:
                cursor.execute("""
                    SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                           s.id as series_id, s.name as series_name,
                           d.format, d.name as filename, d.uncompressed_size as file_size
                    FROM books b
                    JOIN books_series_link bsl ON b.id = bsl.book
                    JOIN series s ON bsl.series = s.id
                    JOIN data d ON b.id = d.book
                    WHERE bsl.series = ? AND d.format = 'EPUB'
                    ORDER BY b.series_index
                """, (series_id,))

            for row in cursor.fetchall():
                xml_parts.append(make_book_entry(cursor, row))

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('<?xml version="1.0"?><opds><error>' + escape_xml(str(e)) + '</error></opds>',
                            mimetype='application/xml')

    @app.route('/opds/cover/<int:book_id>')
    def opds_cover(book_id):
        """Serve book cover images for OPDS readers"""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            # Search in both book folder and root folder
            search_folders = [calibre_path / str(book_id), calibre_path]
            
            for folder in search_folders:
                if folder.exists():
                    files = list(folder.iterdir())
                    for f in files:
                        name_lower = f.name.lower()
                        if not f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                            continue
                        # Cover patterns
                        cover_patterns = ['cover', 'thumbnail']
                        name_stem = f.stem.lower()
                        for pattern in cover_patterns:
                            if pattern in name_stem:
                                return send_file(str(f))
                        # Also check if filename is just the book_id
                        if f.stem == str(book_id):
                            return send_file(str(f))
                    
                    for f in files:
                        if f.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                            return send_file(str(f))

            return Response('Not found: No cover', status=404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('Error: ' + str(e), status=500)

    @app.route('/opds/fetch/<int:book_id>/<path:ext>')
    def opds_fetch(book_id, ext):
        """Serve book files for OPDS readers (Paperback-compatible download endpoint).

        Looks up the book's file in the Calibre library folder and streams it
        with the correct MIME type. Supports EPUB, PDF, MOBI, AZW3, and CBR/CBZ.
        """
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        calibre_path, metadata_db, error = _get_calibre_config()
        if error:
            return error

        # Normalize extension (strip any path prefix dots)
        ext = ext.lower().strip('.')

        # Map extension to MIME type
        mime_map = {
            'epub': 'application/epub+zip',
            'pdf': 'application/pdf',
            'mobi': 'application/x-mobipocket-ebook',
            'azw3': 'application/x-mobipocket-ebook',
            'cbr': 'application/vnd.comicbook-rar',
            'cbz': 'application/vnd.comicbook+zip',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            'fb2': 'application/fb2+xml',
        }
        mime = mime_map.get(ext, 'application/octet-stream')

        book_path, file_size = _get_book_file(book_id, ext, calibre_path)

        if not book_path or not book_path.exists():
            return Response('File not found', status=404, mimetype='text/plain')

        return send_file(
            str(book_path),
            mimetype=mime,
            as_attachment=True,
            download_name=book_path.name
        )
