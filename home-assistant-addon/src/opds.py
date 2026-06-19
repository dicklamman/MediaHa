"""OPDS catalog routes for ebook readers"""
import os
import base64
import sqlite3
from flask import request, Response, session
from pathlib import Path
import json

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
        # Check authentication via session or basic auth header
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
                config = {}

            calibre_path = Path(config.get('calibre_library_path', ''))
            metadata_db = calibre_path / 'metadata.db'

            if not metadata_db.exists():
                return Response('<?xml version="1.0"?><opds><error>Calibre not configured</error></opds>',
                              mimetype='application/xml')

            conn = sqlite3.connect(str(metadata_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get category parameter (book/comic)
            category = request.args.get('category', '').lower()
            series_id = request.args.get('series', '')

            def generate_opds():
                yield '<?xml version="1.0" encoding="UTF-8"?>\n'
                yield '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="https://tools.ietf.org/html/rfc4946">\n'
                yield '  <title>MediaHa Library</title>\n'

                if not category:
                    # Root: show categories
                    yield '  <link rel="start" href="/opds" />\n'

                    # Books category
                    yield '  <entry>\n'
                    yield '    <title>Books</title>\n'
                    yield '    <link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=book" />\n'
                    yield '  </entry>\n'

                    # Comics category
                    yield '  <entry>\n'
                    yield '    <title>Comics</title>\n'
                    yield '    <link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=comic" />\n'
                    yield '  </entry>\n'

                elif category == 'comic':
                    # Comics: show series
                    if not series_id:
                        yield '  <link rel="start" href="/opds" />\n'
                        yield '  <link rel="up" href="/opds" />\n'

                        cursor.execute("""
                            SELECT DISTINCT s.id, s.name
                            FROM series s
                            JOIN books_series_link bsl ON s.id = bsl.series
                            LEFT JOIN books_tags_link btl ON bsl.book = btl.book
                            LEFT JOIN tags t ON btl.tag = t.id AND t.name = 'Comics'
                            WHERE t.id IS NOT NULL
                            ORDER BY s.name
                        """)
                        series_count = 0
                        for row in cursor.fetchall():
                            series_count += 1
                            yield '  <entry>\n'
                            yield f'    <title>{escape_xml(row["name"])}</title>\n'
                            yield f'    <link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=comic&series={row["id"]}" />\n'
                            yield '  </entry>\n'
                        if series_count == 0:
                            # No series with Comics tag - show all series
                            cursor.execute("""
                                SELECT DISTINCT s.id, s.name
                                FROM series s
                                JOIN books_series_link bsl ON s.id = bsl.series
                                ORDER BY s.name
                            """)
                            for row in cursor.fetchall():
                                yield '  <entry>\n'
                                yield f'    <title>{escape_xml(row["name"])}</title>\n'
                                yield f'    <link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=comic&series={row["id"]}" />\n'
                                yield '  </entry>\n'
                    else:
                        # Show books in series
                        cursor.execute("SELECT name FROM series WHERE id = ?", (series_id,))
                        series_row = cursor.fetchone()
                        series_name = series_row["name"] if series_row else "Unknown"

                        yield '  <link rel="start" href="/opds" />\n'
                        yield '  <link rel="up" href="/opds?category=comic" />\n'

                        cursor.execute("""
                            SELECT b.id, b.title, b.series_index, d.name as filename, d.format
                            FROM books b
                            JOIN books_series_link bsl ON b.id = bsl.book
                            JOIN data d ON b.id = d.book
                            WHERE bsl.series = ?
                            ORDER BY b.series_index
                        """, (series_id,))
                        for row in cursor.fetchall():
                            ext = row["format"].lower() if row["format"] else "pdf"
                            file_url = f'/library/books/{row["id"]}/{row["filename"]}.{ext}'
                            yield '  <entry>\n'
                            yield f'    <title>{escape_xml(row["title"])}</title>\n'
                            yield f'    <link type="application/{ext}" href="{file_url}" />\n'
                            yield '  </entry>\n'

                elif category == 'book':
                    # Books: show all EPUB books
                    yield '  <link rel="start" href="/opds" />\n'
                    yield '  <link rel="up" href="/opds" />\n'

                    cursor.execute("""
                        SELECT b.id, b.title, a.name as author, d.name as filename
                        FROM books b
                        LEFT JOIN books_authors_link bal ON b.id = bal.book
                        LEFT JOIN authors a ON bal.author = a.id
                        JOIN data d ON b.id = d.book
                        WHERE d.format = 'EPUB'
                        ORDER BY b.title
                    """)
                    for row in cursor.fetchall():
                        file_url = f'/library/books/{row["id"]}/{row["filename"]}.epub'
                        author = row["author"] if row["author"] else "Unknown"
                        yield '  <entry>\n'
                        yield f'    <title>{escape_xml(row["title"])}</title>\n'
                        yield f'    <author><name>{escape_xml(author)}</name></author>\n'
                        yield f'    <link type="application/epub+zip" href="{file_url}" />\n'
                        yield '  </entry>\n'

                yield '</feed>'

            conn.close()
            return Response(generate_opds(), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            return Response(f'<?xml version="1.0"?><opds><error>{escape_xml(str(e))}</error></opds>',
                            mimetype='application/xml')
