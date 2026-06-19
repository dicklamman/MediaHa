"""OPDS catalog routes for ebook readers"""
import os
import base64
import sqlite3
from flask import request, Response, session
from pathlib import Path
import json
import datetime

CALIBRE_CONFIG_PATH = '/data/calibre_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/calibre_options.json')

def escape_xml(text):
    """Escape XML special characters"""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def register_routes(app, check_auth):
    """Register OPDS routes with the Flask app"""

    @app.route('/opds')
    def opds_catalog():
        """OPDS catalog showing all books and comics"""
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
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})
        try:
            if os.path.exists(CALIBRE_CONFIG_PATH):
                with open(CALIBRE_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
            else:
                return Response('<?xml version="1.0"?><opds><error>Config not found</error></opds>',
                              mimetype='application/xml')

            calibre_library_path = config.get('calibre_library_path', '')
            if not calibre_library_path:
                return Response('<?xml version="1.0"?><opds><error>Calibre path not set</error></opds>',
                              mimetype='application/xml')

            calibre_path = Path(calibre_library_path)
            metadata_db = calibre_path / 'metadata.db'

            if not metadata_db.exists():
                return Response('<?xml version="1.0"?><opds><error>metadata.db not found</error></opds>',
                              mimetype='application/xml')

            category = request.args.get('category', '').lower()
            series_id = request.args.get('series', '')
            series_id_int = int(series_id) if series_id and series_id.isdigit() else None

            # Build self href for this feed
            if category and series_id:
                self_href = '/opds?category=' + category + '&series=' + series_id
            elif category:
                self_href = '/opds?category=' + category
            else:
                self_href = '/opds'

            now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')

            # Use COPS-compatible OPDS format
            xml_parts = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:thr="http://purl.org/syndication/thread/1.0">',
                '  <title>MediaHa Library</title>',
                '  <id>mediaha:' + self_href.replace("/", ":").replace("?", "-").replace("&", "-") + '</id>',
                '  <updated>' + now + '</updated>',
                '  <icon>favicon.ico</icon>',
                '  <link href="/opds" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="start" title="Home"/>',
                '  <link href="' + self_href + '" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="self"/>',
                '  <link href="/opds/search" type="application/opensearchdescription+xml" rel="search" title="Search here"/>'
            ]

            conn = sqlite3.connect(str(metadata_db), timeout=30)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if not category:
                # Books entry with count
                cursor.execute("""
                    SELECT COUNT(DISTINCT b.id) as cnt FROM books b
                    JOIN data d ON b.id = d.book WHERE d.format = 'EPUB'
                """)
                book_count = cursor.fetchone()["cnt"]
                xml_parts.append('  <entry><title>Books</title><updated>' + now + '</updated><id>mediaha:nav:books</id><content type="text">' + str(book_count) + ' books</content><link href="/opds?category=book" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(book_count) + '"/></entry>')

                # Comics entry with count
                cursor.execute("""
                    SELECT COUNT(DISTINCT b.id) as cnt FROM books b
                    JOIN books_tags_link btl ON b.id = btl.book
                    JOIN tags t ON btl.tag = t.id
                    WHERE t.name = 'Comics'
                """)
                comic_count = cursor.fetchone()["cnt"]
                xml_parts.append('  <entry><title>Comics</title><updated>' + now + '</updated><id>mediaha:nav:comics</id><content type="text">' + str(comic_count) + ' comics</content><link href="/opds?category=comic" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(comic_count) + '"/></entry>')

            elif category == 'comic':
                xml_parts.append('  <link href="/opds" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="start"/>')
                xml_parts.append('  <link href="/opds?category=comic" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="self"/>')

                if not series_id:
                    # Show comic series with counts
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
                        row_id = row["id"]
                        row_name = escape_xml(row["name"])
                        row_count = row["book_count"]
                        xml_parts.append('  <entry><title>' + row_name + '</title><updated>' + now + '</updated><id>mediaha:series:' + str(row_id) + '</id><content type="text">' + str(row_count) + ' books</content><link href="/opds?category=comic&series=' + str(row_id) + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(row_count) + '"/></entry>')
                else:
                    xml_parts.append('  <link href="/opds?category=comic" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="up"/>')
                    cursor.execute("""
                        SELECT b.id, b.title, b.series_index, d.format
                        FROM books b
                        JOIN books_series_link bsl ON b.id = bsl.book
                        JOIN books_tags_link btl ON b.id = btl.book
                        JOIN tags t ON btl.tag = t.id
                        JOIN data d ON b.id = d.book
                        WHERE bsl.series = ? AND t.name = 'Comics'
                        ORDER BY b.series_index
                    """, (series_id_int,))
                    for row in cursor.fetchall():
                        ext = row["format"].lower() if row["format"] else "pdf"
                        file_url = '/fetch/' + str(row["id"]) + '/' + ext
                        title = escape_xml(row["title"])
                        xml_parts.append('  <entry><title>' + title + '</title><updated>' + now + '</updated><id>mediaha:book:' + str(row["id"]) + '</id><link href="' + file_url + '" type="application/' + ext + '+zip" rel="http://opds-spec.org/acquisition" /></entry>')

            elif category == 'book':
                xml_parts.append('  <link href="/opds" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="start"/>')
                xml_parts.append('  <link href="/opds?category=book" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="self"/>')

                if not series_id:
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
                        row_id = row["id"]
                        row_name = escape_xml(row["name"])
                        row_count = row["book_count"]
                        xml_parts.append('  <entry><title>' + row_name + '</title><updated>' + now + '</updated><id>mediaha:series:' + str(row_id) + '</id><content type="text">' + str(row_count) + ' books</content><link href="/opds?category=book&series=' + str(row_id) + '" type="application/atom+xml;profile=opds-catalog;kind=acquisition" rel="subsection" thr:count="' + str(row_count) + '"/></entry>')

                    # Standalone books with EPUB format
                    cursor.execute("""
                        SELECT b.id, b.title, a.name as author
                        FROM books b
                        LEFT JOIN books_series_link bsl ON b.id = bsl.book
                        LEFT JOIN books_authors_link bal ON b.id = bal.book
                        LEFT JOIN authors a ON bal.author = a.id
                        JOIN data d ON b.id = d.book
                        WHERE bsl.book IS NULL AND d.format = 'EPUB'
                        ORDER BY b.title
                    """)
                    for row in cursor.fetchall():
                        file_url = '/fetch/' + str(row["id"]) + '/epub'
                        author = row["author"] if row["author"] else "Unknown"
                        title = escape_xml(row["title"])
                        xml_parts.append('  <entry><title>' + title + '</title><updated>' + now + '</updated><id>mediaha:book:' + str(row["id"]) + '</id><author><name>' + escape_xml(author) + '</name></author><link href="' + file_url + '" type="application/epub+zip" rel="http://opds-spec.org/acquisition" /></entry>')
                else:
                    xml_parts.append('  <link href="/opds?category=book" type="application/atom+xml;profile=opds-catalog;kind=navigation" rel="up"/>')
                    cursor.execute("""
                        SELECT b.id, b.title, b.series_index, d.name as filename
                        FROM books b
                        JOIN books_series_link bsl ON b.id = bsl.book
                        JOIN data d ON b.id = d.book
                        WHERE bsl.series = ? AND d.format = 'EPUB'
                        ORDER BY b.series_index
                    """, (series_id_int,))
                    for row in cursor.fetchall():
                        file_url = '/fetch/' + str(row["id"]) + '/epub'
                        title = escape_xml(row["title"])
                        xml_parts.append('  <entry><title>' + title + '</title><updated>' + now + '</updated><id>mediaha:book:' + str(row["id"]) + '</id><link href="' + file_url + '" type="application/epub+zip" rel="http://opds-spec.org/acquisition" /></entry>')

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response('<?xml version="1.0"?><opds><error>' + escape_xml(str(e)) + '</error></opds>',
                            mimetype='application/xml')
