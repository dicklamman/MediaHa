"""OPDS catalog routes for ebook readers"""
import os
import re
import base64
import sqlite3
import logging
import zipfile
import io
from flask import request, Response, session, send_file
from pathlib import Path
import json
import datetime

logger = logging.getLogger("opds")

CALIBRE_CONFIG_PATH = '/data/calibre_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(__file__), '../config/calibre_options.json')

def escape_xml(text):
    """Escape XML special characters"""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def slugify(text):
    """Convert text to URL-safe slug."""
    if not text:
        return ''
    text = str(text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w\-_]', '', text)
    return text

def register_routes(app, check_auth):
    """Register OPDS routes with the Flask app"""
    logger.warning("[OPDS STARTUP] register_routes() called — starting route registration")

    # ── Komga-standard DTO helpers ──────────────────────────────────────────

    def _now_iso():
        return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    def _date_iso(val):
        """Return ISO date string from a Calibre date value, or empty string."""
        if not val:
            return ""
        s = str(val)
        # Calibre stores as 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS'
        if 'T' in s:
            return s[:19] + 'Z'
        return s[:10]

    def _author_dto(name="", role="writer"):
        return {"name": name or "Unknown", "role": role}

    def _make_series_dto(row):
        """Build a Komga-standard SeriesDto from a query row dict."""
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "booksCount": row.get("books_count", 0),
            "booksReadCount": row.get("books_read_count", 0),
            "booksUnreadCount": row.get("books_unread_count", row.get("books_count", 0)),
            "booksInProgressCount": row.get("books_in_progress_count", 0),
            "created": _date_iso(row.get("created", "")),
            "lastModified": _date_iso(row.get("last_modified", "")),
            "fileLastModified": _date_iso(row.get("file_last_modified", "")),
            "deleted": False,
            "oneshot": row.get("oneshot", False),
            "libraryId": "comics",
            "url": f"/api/v1/series/{row['id']}",
            "metadata": {
                "title": row["name"],
                "titleLock": True,
                "titleSort": row["name"],
                "titleSortLock": True,
                "summary": row.get("summary", ""),
                "summaryLock": True,
                "ageRating": row.get("age_rating"),
                "ageRatingLock": True,
                "alternateTitles": [],
                "alternateTitlesLock": True,
                "publisher": row.get("publisher", ""),
                "publisherLock": True,
                "language": row.get("language", ""),
                "languageLock": True,
                "genres": [],
                "genresLock": True,
                "tags": [],
                "tagsLock": True,
                "readingDirection": "",
                "readingDirectionLock": True,
                "status": row.get("status", "ONGOING"),
                "statusLock": True,
                "sharingLabels": [],
                "sharingLabelsLock": True,
                "totalBookCount": row.get("books_count", 0),
                "totalBookCountLock": True,
                "created": _date_iso(row.get("metadata_created", "")),
                "lastModified": _date_iso(row.get("metadata_last_modified", "")),
                "links": [],
                "linksLock": True,
            },
            "booksMetadata": {
                "authors": [_author_dto(row.get("author_name", ""))] if row.get("author_name") else [],
                "releaseDate": row.get("release_date", ""),
                "summary": row.get("summary", ""),
                "summaryNumber": "",
                "tags": [],
                "created": _date_iso(row.get("metadata_created", "")),
                "lastModified": _date_iso(row.get("metadata_last_modified", "")),
            },
        }

    def _get_book_page_count(book_id, ext, calibre_path):
        """Get the page count for a book by examining its file.
        
        Returns the number of pages in the book, or 0 if unknown.
        """
        try:
            ext = ext.lower().strip('.')
            
            # Handle CBZ (ZIP) files
            if ext in ('cbz', 'zip'):
                book_path, _ = _get_book_file(book_id, ext, calibre_path)
                if book_path and book_path.exists():
                    with zipfile.ZipFile(str(book_path), 'r') as zf:
                        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                        count = 0
                        for name in zf.namelist():
                            ext_lower = os.path.splitext(name)[1].lower()
                            if ext_lower in image_extensions and not name.startswith('__MACOSX'):
                                count += 1
                        return count
            
            # Handle image directories
            book_folder = calibre_path / str(book_id)
            if book_folder.exists() and book_folder.is_dir():
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                count = 0
                for f in book_folder.iterdir():
                    if f.suffix.lower() in image_extensions:
                        count += 1
                return count
            
            # PDF - return 1 as placeholder (actual count requires parsing PDF)
            if ext == 'pdf':
                return 1
                
        except Exception as e:
            logger.warning(f"[OPDS] Error getting page count for book {book_id}: {e}")
        
        return 0

    def _make_book_dto(row, base_url="/api/v1"):
        """Build a Komga-standard BookDto from a query row dict."""
        book_id = str(row["id"])
        media_type = f"application/{row['format'].lower()}" if row.get("format") else "application/octet-stream"
        series_id = str(row["series_id"]) if row.get("series_id") else None
        series_name = row.get("series_name") or None
        series_slug = slugify(series_name) if series_name else ""
        series_book_count = row.get("series_book_count", 0)

        # Number fields: series_index is float in Calibre, Komga uses int
        number_raw = row.get("series_index", 0) or 0
        try:
            number_int = int(float(number_raw))
        except (TypeError, ValueError):
            number_int = 0

        # size: Komga requires size as string AND sizeBytes as int
        size_bytes = row.get("file_size") or 0
        size_str = str(size_bytes)

        # Determine page count - use dynamic count when available
        pages_count = row.get("pages_count")
        if not pages_count:
            # Try to compute from file if we have the path hint
            pages_count = row.get("_computed_pages", 0)

        return {
            "id": book_id,
            "seriesId": series_id,
            "seriesTitle": series_name,
            "number": number_int,
            "oneshot": row.get("oneshot", False),
            "deleted": False,
            "libraryId": "comics",
            "name": row.get("title") or f"Book {book_id}",
            "title": row.get("title") or f"Book {book_id}",
            "size": size_str,
            "sizeBytes": size_bytes,
            "fileHash": row.get("file_hash") or "",
            "fileLastModified": _date_iso(row.get("file_last_modified", "")),
            "created": _date_iso(row.get("created", "")),
            "lastModified": _date_iso(row.get("last_modified", "")),
            "url": f"{base_url}/books/{book_id}",
            "thumbnailUrl": f"/opds/cover/{book_id}",
            "readableAt": _date_iso(row.get("pubdate", "")),
            "readProgress": None,
            "media": {
                "mediaType": media_type,
                "status": "Ready",
                "pagesCount": pages_count or 0,
                "mediaProfile": _media_profile(media_type),
                "epubIsKepub": False,
                "epubDivinaCompatible": False,
                "comment": "",
            },
            "metadata": {
                "title": row.get("title") or f"Book {book_id}",
                "titleLock": True,
                "number": str(number_int),
                "numberLock": True,
                "numberSort": float(number_int),
                "numberSortLock": True,
                "authors": [_author_dto(row.get("author_name", ""))] if row.get("author_name") else [],
                "authorsLock": True,
                "releaseDate": _date_iso(row.get("pubdate", "")),
                "releaseDateLock": True,
                "summary": row.get("summary", ""),
                "summaryLock": True,
                "isbn": "",
                "isbnLock": True,
                "tags": [],
                "tagsLock": True,
                "links": [],
                "linksLock": True,
                "created": _date_iso(row.get("metadata_created", "")),
                "lastModified": _date_iso(row.get("metadata_last_modified", "")),
            },
        }

    def _media_profile(media_type):
        mt = media_type.lower()
        if mt == "application/epub+zip":
            return "epub"
        if mt in ("application/pdf", "application/x-cbz", "application/vnd.comicbook+zip",
                  "application/vnd.comicbook+xml"):
            return "pdf"
        if mt in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            return "image"
        return "unknown"

    def _page_response(content, total_elements, page=0, size=20, sort_empty=True):
        """Build a Komga-standard PageDto wrapper."""
        total_pages = max(1, (total_elements + size - 1) // size)
        return {
            "content": content,
            "empty": len(content) == 0,
            "first": True,
            "last": page >= total_pages - 1,
            "number": page,
            "numberOfElements": len(content),
            "pageable": {
                "offset": page * size,
                "pageNumber": page,
                "pageSize": size,
                "paged": True,
                "sort": {"empty": sort_empty, "sorted": False, "unsorted": True},
                "unpaged": False,
            },
            "size": size,
            "sort": {"empty": sort_empty, "sorted": False, "unsorted": True},
            "totalElements": total_elements,
            "totalPages": total_pages,
        }

    # ── DB helpers ────────────────────────────────────────────────────────────

    # Log all registered routes at startup for debugging
    rules = [(r.rule, list(r.methods - {'OPTIONS', 'HEAD'})) for r in app.url_map.iter_rules()]
    logger.warning(f"[OPDS STARTUP] Pre-registration routes: {rules}")

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
            '    <content type="text">Book ' + str(int(series_index)) + ' of ' + escape_xml(series_name) + '</content>',
            '    <link href="/opds/cover/' + str(book_id) + '" type="image/jpeg" rel="http://opds-spec.org/image"/>',
            '    <link href="/opds/cover/' + str(book_id) + '" type="image/jpeg" rel="http://opds-spec.org/image/thumbnail"/>'
        ]
        
        # Map extension to MIME type (used in both feed entries and download)
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

        # Add acquisition link with correct MIME type and file size
        acq_link = '    <link href="' + file_url + '" type="' + mime + '" rel="http://opds-spec.org/acquisition"'
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

    def _authenticate():
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

    def _get_calibre_config():
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

    def _get_db_connection(metadata_db):
        """Create a SQLite connection with row factory"""
        conn = sqlite3.connect(str(metadata_db), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_book_file(book_id, ext, calibre_path):
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
        logger.warning(f"[OPDS DEBUG] path={request.path} method={request.method} auth={request.headers.get('Authorization','')[:30]}...")
        authenticated = _authenticate()
        if not authenticated:
            logger.warning(f"[OPDS DEBUG] opds_root: returning 401")
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return error

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

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
            cursor = conn.cursor()

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
            cursor = conn.cursor()

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
            cursor = conn.cursor()

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

    # Paperback-compatible routes (no /opds prefix)
    @app.route('/api/v1/series/new')
    def paperback_api_series_new():
        """Paperback API - new series (no /opds prefix)."""
        return _komga_series_response(prefix="/api/v1/series/", order_by_date=True)

    @app.route('/api/v1/series/updated')
    def paperback_api_series_updated():
        """Paperback API - updated series (no /opds prefix)."""
        return _komga_series_response(prefix="/api/v1/series/", order_by_date=True)

    @app.route('/opds/api/v1/series/new')
    def opds_api_series_new():
        """OPDS Feed Update Protocol - return new series since a given time."""
        return _komga_series_response(prefix="/opds/api/v1/series/", order_by_date=True)

    @app.route('/opds/api/v1/series/updated')
    def opds_api_series_updated():
        """OPDS Feed Update Protocol - return updated series since a given time."""
        return _komga_series_response(prefix="/opds/api/v1/series/", order_by_date=True)

    def _komga_series_response(prefix, order_by_date=False):
        """Shared logic for series list endpoints (used by both OPDS and Paperback routes).
        
        Args:
            prefix: URL prefix for series links
            order_by_date: If True, order by latest book date descending (for /new and /updated)
        """
        authenticated = _authenticate()
        if not authenticated:
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            order_clause = "ORDER BY s.name" if not order_by_date else "ORDER BY latest_date DESC"
            cursor.execute(f"""
                SELECT s.id, s.name,
                       COUNT(DISTINCT b.id) as book_count,
                       MAX(b.pubdate) as latest_date
                FROM series s
                JOIN books_series_link bsl ON s.id = bsl.series
                JOIN books b ON bsl.book = b.id
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                WHERE t.name = 'Comics'
                GROUP BY s.id, s.name
                {order_clause}
            """)
            rows = cursor.fetchall()
            conn.close()

            series_list = []
            for row in rows:
                row_dict = dict(row)
                row_dict["books_count"] = row_dict["book_count"]
                row_dict["books_read_count"] = 0
                row_dict["oneshot"] = False
                row_dict["last_modified"] = row_dict["latest_date"]
                row_dict["created"] = row_dict["latest_date"]
                series_list.append(_make_series_dto(row_dict))

            resp = _page_response(series_list, len(series_list))
            return Response(json.dumps(resp), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] _komga_series_response error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

    @app.route('/api/v1/series/<series_id>/books')
    def paperback_api_series_books(series_id):
        """Paperback API - books in a series."""
        return _komga_series_books(series_id, base_url="/api/v1")

    @app.route('/opds/api/v1/series/<series_id>/books')
    def opds_api_series_books(series_id):
        """Komga API - return all books in a series."""
        return _komga_series_books(series_id, base_url="/api/v1")

    def _komga_series_books(series_id, base_url="/api/v1"):
        """Shared logic for series books endpoints."""
        authenticated = _authenticate()
        if not authenticated:
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                       d.format, d.name as filename, d.uncompressed_size as file_size,
                       s.id as series_id, s.name as series_name
                FROM books b
                JOIN books_series_link bsl ON b.id = bsl.book
                JOIN series s ON bsl.series = s.id
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                LEFT JOIN data d ON b.id = d.book
                WHERE bsl.series = ? AND t.name = 'Comics'
                ORDER BY b.series_index
            """, (series_id,))
            rows = cursor.fetchall()
            conn.close()

            books = []
            for row in rows:
                row_dict = dict(row)
                # Compute page count dynamically for CBZ/image directories
                ext = row_dict.get("format", "").lower()
                if ext in ('cbz', 'zip'):
                    row_dict["_computed_pages"] = _get_book_page_count(row_dict["id"], ext, calibre_path)
                elif ext in ('cbr', 'rar'):
                    row_dict["_computed_pages"] = 0  # Can't determine without rarfile
                elif ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                    row_dict["_computed_pages"] = _get_book_page_count(row_dict["id"], ext, calibre_path)
                books.append(_make_book_dto(row_dict, base_url=base_url))
            
            resp = _page_response(books, len(books))
            return Response(json.dumps(resp), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] _komga_series_books error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

    @app.route('/opds/api/v1/search')
    def opds_api_search():
        """OPDS API - search for series/books."""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        query = request.args.get('q', request.args.get('query', ''))
        accept = request.headers.get('Accept', '')
        logger.warning(f"[OPDS DEBUG] search query='{query}' Accept={accept}")

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response('{"results":[]}', mimetype='application/json')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            results = []
            if query:
                # Search for series matching query
                cursor.execute("""
                    SELECT DISTINCT s.id, s.name,
                           COUNT(DISTINCT b.id) as book_count
                    FROM series s
                    JOIN books_series_link bsl ON s.id = bsl.series
                    JOIN books b ON bsl.book = b.id
                    JOIN books_tags_link btl ON b.id = btl.book
                    JOIN tags t ON btl.tag = t.id
                    WHERE t.name = 'Comics' AND s.name LIKE ?
                    GROUP BY s.id, s.name
                    ORDER BY s.name
                    LIMIT 20
                """, (f'%{query}%',))
                for row in cursor.fetchall():
                    results.append({
                        "type": "series",
                        "id": str(row["id"]),
                        "name": row["name"],
                        "bookCount": row["book_count"]
                    })

            conn.close()
            logger.warning(f"[OPDS DEBUG] search returning {len(results)} results for '{query}'")
            return Response(json.dumps({"results": results}), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS DEBUG] search error: {e}\n{traceback.format_exc()}")
            return Response('{"results":[]}', mimetype='application/json')

    # ─── Komga-compatible API endpoints ───────────────────────────────────────

    @app.route('/opds/api/v1/series')
    @app.route('/api/v1/series')
    def komga_api_series():
        """Komga API - list all series (PageSeriesDto)."""
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT s.id, s.name,
                       COUNT(DISTINCT b.id) as book_count,
                       MAX(b.pubdate) as latest_date
                FROM series s
                JOIN books_series_link bsl ON s.id = bsl.series
                JOIN books b ON bsl.book = b.id
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                WHERE t.name = 'Comics'
                GROUP BY s.id, s.name
                ORDER BY s.name
            """)
            rows = cursor.fetchall()
            conn.close()

            content = []
            for row in rows:
                row_dict = dict(row)
                row_dict["books_count"] = row_dict["book_count"]
                row_dict["books_read_count"] = 0
                row_dict["oneshot"] = False
                row_dict["last_modified"] = row_dict["latest_date"]
                row_dict["created"] = row_dict["latest_date"]
                content.append(_make_series_dto(row_dict))

            resp = _page_response(content, len(content))
            return Response(json.dumps(resp), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_series error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

    @app.route('/opds/api/v1/libraries')
    def komga_api_libraries():
        """Komga API - list libraries (returns one "Comics" library)."""
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})
        logger.warning(f"[OPDS DEBUG] komga /api/v1/libraries")
        resp = json.dumps([{
            "id": "comics",
            "name": "Comics",
            "url": "/opds/api/v1/series"
        }])
        logger.warning(f"[OPDS DEBUG] komga /api/v1/libraries returning: {resp}")
        return Response(resp, mimetype='application/json')

    @app.route('/opds/api/v1/series/<series_id>')
    @app.route('/api/v1/series/<series_id>')
    def komga_api_series_detail(series_id):
        """Komga API - single series detail (SeriesDto)."""
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps({}), mimetype='application/json', status=404)

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT s.id, s.name,
                       COUNT(DISTINCT b.id) as book_count,
                       MAX(b.pubdate) as latest_date
                FROM series s
                JOIN books_series_link bsl ON s.id = bsl.series
                JOIN books b ON bsl.book = b.id
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                WHERE t.name = 'Comics' AND s.id = ?
                GROUP BY s.id, s.name
            """, (series_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response(json.dumps({}), mimetype='application/json', status=404)

            row_dict = dict(row)
            row_dict["books_count"] = row_dict["book_count"]
            row_dict["books_read_count"] = 0
            row_dict["oneshot"] = False
            row_dict["last_modified"] = row_dict["latest_date"]
            row_dict["created"] = row_dict["latest_date"]
            return Response(json.dumps(_make_series_dto(row_dict)), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_series_detail error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps({}), mimetype='application/json', status=500)

    # Paperback-compatible book routes (no /opds prefix)
    @app.route('/api/v1/books')
    @app.route('/api/v1/books/ondeck')
    def paperback_api_books():
        """Paperback API - list all books / ondeck (flat)."""
        return _komga_books_response(ondeck=request.path.endswith('/ondeck'))

    @app.route('/opds/api/v1/books')
    @app.route('/opds/api/v1/books/ondeck')
    def komga_api_books():
        """Komga API - list all books / ondeck (flat)."""
        return _komga_books_response(ondeck=request.path.endswith('/ondeck'))

    def _komga_books_response(ondeck=False):
        """Shared logic for books/ondeck list endpoints (PageBookDto)."""
        authenticated = _authenticate()
        if not authenticated:
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            query = """
                SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                       d.format, d.name as filename, d.uncompressed_size as file_size,
                       s.id as series_id, s.name as series_name
                FROM books b
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                LEFT JOIN books_series_link bsl ON b.id = bsl.book
                LEFT JOIN series s ON bsl.series = s.id
                LEFT JOIN data d ON b.id = d.book
                WHERE t.name = 'Comics'
            """
            if ondeck:
                query += " ORDER BY b.pubdate DESC, b.id DESC LIMIT 20"
            else:
                query += " ORDER BY b.series_index"

            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            books = []
            for row in rows:
                row_dict = dict(row)
                ext = row_dict.get("format", "").lower()
                if ext in ('cbz', 'zip'):
                    row_dict["_computed_pages"] = _get_book_page_count(row_dict["id"], ext, calibre_path)
                elif ext in ('cbr', 'rar'):
                    row_dict["_computed_pages"] = 0
                books.append(_make_book_dto(row_dict))
            
            resp = _page_response(books, len(books))
            return Response(json.dumps(resp), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] _komga_books_response error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps(_page_response([], 0)), mimetype='application/json')

    @app.route('/opds/api/v1/books/<book_id>')
    @app.route('/api/v1/books/<book_id>')
    def komga_api_book_detail(book_id):
        """Komga API - single book detail (BookDto)."""
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps({}), mimetype='application/json', status=404)

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                       d.format, d.name as filename, d.uncompressed_size as file_size,
                       s.id as series_id, s.name as series_name
                FROM books b
                LEFT JOIN books_series_link bsl ON b.id = bsl.book
                LEFT JOIN series s ON bsl.series = s.id
                LEFT JOIN data d ON b.id = d.book
                WHERE b.id = ?
            """, (book_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response(json.dumps({}), mimetype='application/json', status=404)

            row_dict = dict(row)
            # Compute page count dynamically for CBZ/image directories
            ext = row_dict.get("format", "").lower()
            if ext in ('cbz', 'zip'):
                row_dict["_computed_pages"] = _get_book_page_count(book_id, ext, calibre_path)
            elif ext in ('cbr', 'rar'):
                row_dict["_computed_pages"] = 0

            return Response(json.dumps(_make_book_dto(row_dict)), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_book_detail error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps({}), mimetype='application/json', status=500)

    def _get_book_page_url(book_id, page_num):
        """Build the absolute URL for a book page using request.host_url."""
        base = request.host_url.rstrip('/')
        return f"{base}/opds/api/v1/books/{book_id}/pages/{page_num}"

    @app.route('/opds/api/v1/books/<book_id>/pages')
    @app.route('/api/v1/books/<book_id>/pages')
    def komga_api_book_pages(book_id):
        """Komga API - get all page URLs for a book.
        
        Returns a list of page URLs in format:
        ["http://host:port/opds/api/v1/books/<id>/pages/1", ...]
        
        Paperback expects absolute URLs (including scheme/host).
        """
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response(json.dumps([]), mimetype='application/json', status=404)

            # Get book info from database
            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT b.id, d.format, d.name as filename
                FROM books b
                LEFT JOIN data d ON b.id = d.book
                WHERE b.id = ?
            """, (book_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response(json.dumps([]), mimetype='application/json', status=404)

            book_id = row["id"]
            ext = row["format"].lower() if row["format"] else ""
            
            pages = []
            
            # Handle CBZ (ZIP) files
            if ext in ('cbz', 'zip'):
                book_path, _ = _get_book_file(book_id, ext, calibre_path)
                if book_path and book_path.exists():
                    try:
                        with zipfile.ZipFile(str(book_path), 'r') as zf:
                            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                            all_names = sorted(zf.namelist(), key=lambda x: x.lower())
                            for name in all_names:
                                ext_lower = os.path.splitext(name)[1].lower()
                                if ext_lower in image_extensions and not name.startswith('__MACOSX'):
                                    pages.append(_get_book_page_url(book_id, len(pages) + 1))
                    except Exception as e:
                        logger.warning(f"[OPDS] Error reading CBZ {book_path}: {e}")
            
            # Handle CBR (RAR) files
            elif ext in ('cbr', 'rar'):
                logger.warning(f"[OPDS] CBR/RAR files not supported for page listing: {book_id}")
            
            # Handle PDF files
            elif ext == 'pdf':
                pages.append(_get_book_page_url(book_id, 1))
            
            # Handle image directories (comics stored as folders of images)
            else:
                book_folder = calibre_path / str(book_id)
                if book_folder.exists() and book_folder.is_dir():
                    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                    image_files = sorted(
                        [f for f in book_folder.iterdir() if f.suffix.lower() in image_extensions],
                        key=lambda x: x.name.lower()
                    )
                    for f in image_files:
                        pages.append(_get_book_page_url(book_id, len(pages) + 1))

            logger.warning(f"[OPDS] book_pages: book_id={book_id} format={ext} pages_count={len(pages)}")
            return Response(json.dumps(pages), mimetype='application/json')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_book_pages error: {e}\n{traceback.format_exc()}")
            return Response(json.dumps([]), mimetype='application/json', status=500)

    @app.route('/opds/api/v1/books/<book_id>/pages/<int:page_num>')
    @app.route('/api/v1/books/<book_id>/pages/<int:page_num>')
    def komga_api_book_page(book_id, page_num):
        """Komga API - serve a specific page of a book.
        
        Extracts and serves the image from CBZ files by page number.
        """
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response('Not found', status=404, mimetype='text/plain')

            # Get book format from database
            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT b.id, d.format
                FROM books b
                LEFT JOIN data d ON b.id = d.book
                WHERE b.id = ?
            """, (book_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response('Not found', status=404, mimetype='text/plain')

            ext = row["format"].lower() if row["format"] else ""
            
            # Handle CBZ (ZIP) files
            if ext in ('cbz', 'zip'):
                book_path, _ = _get_book_file(book_id, ext, calibre_path)
                if book_path and book_path.exists():
                    try:
                        with zipfile.ZipFile(str(book_path), 'r') as zf:
                            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                            all_names = sorted(zf.namelist(), key=lambda x: x.lower())
                            image_names = [n for n in all_names 
                                          if os.path.splitext(n)[1].lower() in image_extensions
                                          and not n.startswith('__MACOSX')]
                            
                            if 1 <= page_num <= len(image_names):
                                page_name = image_names[page_num - 1]
                                data = zf.read(page_name)
                                
                                # Determine MIME type
                                mime_types = {
                                    '.jpg': 'image/jpeg',
                                    '.jpeg': 'image/jpeg',
                                    '.png': 'image/png',
                                    '.gif': 'image/gif',
                                    '.webp': 'image/webp'
                                }
                                mime = mime_types.get(os.path.splitext(page_name)[1].lower(), 'image/jpeg')
                                
                                return Response(data, mimetype=mime)
                    except Exception as e:
                        logger.warning(f"[OPDS] Error extracting page from CBZ: {e}")
            
            # Handle image directories
            book_folder = calibre_path / str(book_id)
            if book_folder.exists() and book_folder.is_dir():
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                image_files = []
                for f in book_folder.iterdir():
                    if f.suffix.lower() in image_extensions:
                        image_files.append(f)
                image_files.sort(key=lambda x: x.name.lower())
                
                if 1 <= page_num <= len(image_files):
                    page_file = image_files[page_num - 1]
                    mime_types = {
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp'
                    }
                    mime = mime_types.get(page_file.suffix.lower(), 'image/jpeg')
                    return send_file(str(page_file), mimetype=mime)
            
            return Response('Page not found', status=404, mimetype='text/plain')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_book_page error: {e}\n{traceback.format_exc()}")
            return Response('Error', status=500, mimetype='text/plain')

    @app.route('/opds/api/v1/series/<series_id>/thumbnail')
    @app.route('/api/v1/series/<series_id>/thumbnail')
    def komga_api_series_thumbnail(series_id):
        """Komga API - get thumbnail image for a series.

        Returns the cover of the first book in the series.
        """
        authenticated = _authenticate()
        if not authenticated:
            return Response('{"error":"Unauthorized"}', status=401, mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})

        try:
            calibre_path, metadata_db, error = _get_calibre_config()
            if error:
                return Response('Not found', status=404, mimetype='text/plain')

            conn = _get_db_connection(metadata_db)
            cursor = conn.cursor()

            # Get the first book in the series
            cursor.execute("""
                SELECT b.id
                FROM books b
                JOIN books_series_link bsl ON b.id = bsl.book
                JOIN books_tags_link btl ON b.id = btl.book
                JOIN tags t ON btl.tag = t.id
                WHERE bsl.series = ? AND t.name = 'Comics'
                ORDER BY b.series_index
                LIMIT 1
            """, (series_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return Response('Not found', status=404, mimetype='text/plain')

            # Redirect to the book cover
            book_id = row["id"]
            logger.warning(f"[OPDS] series_thumbnail: series_id={series_id} -> book_id={book_id}")
            return send_file(str(calibre_path / str(book_id)), mimetype='image/jpeg')

        except Exception as e:
            import traceback
            logger.warning(f"[OPDS] komga_api_series_thumbnail error: {e}\n{traceback.format_exc()}")
            return Response('Error: ' + str(e), status=500)

    @app.route('/opds/<path:unknown>')
    def opds_catchall(unknown):
        """Catch-all for unexpected OPDS paths."""
        logger.warning(f"[OPDS DEBUG] catchall hit: /opds/{unknown}")
        authenticated = _authenticate()
        if not authenticated:
            return Response('Authentication required', status=401, mimetype='text/plain',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa OPDS"'})
        return Response(
            '<?xml version="1.0"?><opds><error>Unknown OPDS path</error></opds>',
            mimetype='application/xml',
            status=404
        )

    # Log all registered routes after full registration
    rules = [(r.rule, list(r.methods - {'OPTIONS', 'HEAD'})) for r in app.url_map.iter_rules()]
    logger.warning(f"[OPDS STARTUP] Post-registration routes: {rules}")
    logger.warning("[OPDS STARTUP] register_routes() complete")
