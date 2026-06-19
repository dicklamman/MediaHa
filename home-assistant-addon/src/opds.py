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
                return Response(f'<?xml version="1.0"?><opds><error>Config not found</error></opds>',
                              mimetype='application/xml')

            calibre_library_path = config.get('calibre_library_path', '')
            if not calibre_library_path:
                return Response('<?xml version="1.0"?><opds><error>Calibre path not set</error></opds>',
                              mimetype='application/xml')

            calibre_path = Path(calibre_library_path)
            metadata_db = calibre_path / 'metadata.db'

            if not metadata_db.exists():
                return Response(f'<?xml version="1.0"?><opds><error>metadata.db not found</error></opds>',
                              mimetype='application/xml')

            category = request.args.get('category', '').lower()
            series_id = request.args.get('series', '')

            # Use relative URLs for OPDS - Yomu app can't resolve external domains
            xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="https://tools.ietf.org/html/rfc4946">', '  <title>MediaHa Library</title>']

            if not category:
                xml_parts.append('  <link rel="start" href="/opds" />')
                xml_parts.append('  <entry><title>Books</title><link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=book" /></entry>')
                xml_parts.append('  <entry><title>Comics</title><link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=comic" /></entry>')

            elif category == 'comic':
                xml_parts.append('  <link rel="start" href="/opds" />')
                xml_parts.append('  <link rel="up" href="/opds" />')

                if not series_id:
                    # Show comic series - filter by Comics tag
                    cursor.execute("""
                        SELECT DISTINCT s.id, s.name
                        FROM series s
                        JOIN books_series_link bsl ON s.id = bsl.series
                        JOIN books_tags_link btl ON bsl.book = btl.book
                        JOIN tags t ON btl.tag = t.id
                        WHERE t.name = 'Comics'
                        ORDER BY s.name
                    """)
                    for row in cursor.fetchall():
                        xml_parts.append(f'  <entry><title>{escape_xml(row["name"])}</title><link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=comic&series={row["id"]}" /></entry>')
                else:
                    # Show comics in series - filter by Comics tag
                    xml_parts.append('  <link rel="up" href="/opds?category=comic" />')
                    cursor.execute("""
                        SELECT b.id, b.title, b.series_index, d.name as filename, d.format
                        FROM books b
                        JOIN books_series_link bsl ON b.id = bsl.book
                        JOIN books_tags_link btl ON b.id = btl.book
                        JOIN tags t ON btl.tag = t.id
                        JOIN data d ON b.id = d.book
                        WHERE bsl.series = ? AND t.name = 'Comics'
                        ORDER BY b.series_index
                    """, (series_id,))
                    for row in cursor.fetchall():
                        ext = row["format"].lower() if row["format"] else "pdf"
                        file_url = f'/fetch/{row["id"]}/{ext}'
                        title = escape_xml(row["title"])
                        xml_parts.append(f'  <entry><title>{title}</title><link rel="http://opds-spec.org/acquisition" type="application/{ext}+zip" href="{file_url}" /></entry>')

            elif category == 'book':
                xml_parts.append('  <link rel="start" href="/opds" />')
                xml_parts.append('  <link rel="up" href="/opds" />')

                if not series_id:
                    # Show book series
                    cursor.execute("""
                        SELECT DISTINCT s.id, s.name
                        FROM series s
                        JOIN books_series_link bsl ON s.id = bsl.series
                        JOIN data d ON bsl.book = d.book
                        WHERE d.format = 'EPUB'
                        ORDER BY s.name
                    """)
                    for row in cursor.fetchall():
                        xml_parts.append(f'  <entry><title>{escape_xml(row["name"])}</title><link type="application/atom+xml;profile=opds-catalog;kind=navigation" href="/opds?category=book&series={row["id"]}" /></entry>')

                    # Also show standalone books (no series) with EPUB format
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
                        file_url = f'/fetch/{row["id"]}/epub'
                        author = row["author"] if row["author"] else "Unknown"
                        title = escape_xml(row["title"])
                        xml_parts.append(f'  <entry><title>{title}</title><author><name>{escape_xml(author)}</name></author><link rel="http://opds-spec.org/acquisition" type="application/epub+zip" href="{file_url}" /></entry>')
                else:
                    # Show books in series
                    xml_parts.append('  <link rel="up" href="/opds?category=book" />')
                    cursor.execute("""
                        SELECT b.id, b.title, b.series_index, d.name as filename
                        FROM books b
                        JOIN books_series_link bsl ON b.id = bsl.book
                        JOIN data d ON b.id = d.book
                        WHERE bsl.series = ? AND d.format = 'EPUB'
                        ORDER BY b.series_index
                    """, (series_id,))
                    for row in cursor.fetchall():
                        file_url = f'/fetch/{row["id"]}/epub'
                        title = escape_xml(row["title"])
                        xml_parts.append(f'  <entry><title>{title}</title><link rel="http://opds-spec.org/acquisition" type="application/epub+zip" href="{file_url}" /></entry>')

            xml_parts.append('</feed>')
            conn.close()

            return Response('\n'.join(xml_parts), mimetype='application/atom+xml; charset=utf-8')

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(f'<?xml version="1.0"?><opds><error>{escape_xml(str(e))}</error></opds>',
                            mimetype='application/xml')
