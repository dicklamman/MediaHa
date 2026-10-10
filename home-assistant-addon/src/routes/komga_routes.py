# -*- coding: utf-8 -*-
"""Komga-compatible API routes for comic readers like OpenComicVortex."""
import os
import re
import json
import base64
import sqlite3
import logging
import zipfile
import uuid
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from flask import request, Response, session, send_file, send_from_directory, jsonify, redirect

logger = logging.getLogger("komga")

CALIBRE_CONFIG_PATH = '/data/calibre_options.json' if os.path.exists('/data') else os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../config/calibre_options.json')
KOMGA_CONFIG_PATH = '/data/komga_options.json'
KOMGA_DB_PATH = '/media/comic/metadata.db'

def _get_komga_config():
    """Load Komga library config and return (komga_library_path, comic_folder) or defaults."""
    if os.path.exists(KOMGA_CONFIG_PATH):
        with open(KOMGA_CONFIG_PATH, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    komga_library_path = config.get('komga_library_path', '/media/comic/book')
    comic_folder = config.get('comic_folder', '/media/comic')
    return komga_library_path, comic_folder


def register_komga_routes(app, check_auth):
    """Register Komga-compatible API routes."""
    logger.warning("[Komga] register_komga_routes() called")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def escape_xml(text):
        if not text:
            return ''
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

    def _now_iso():
        return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    def _date_iso(val):
        if not val:
            return ""
        s = str(val)
        if 'T' in s:
            return s[:19] + 'Z'
        return s[:10]

    def _authenticate():
        """Check Basic Auth or session."""
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
        """Load Calibre/Komga config and return (calibre_path, metadata_db) or error tuple.
        
        Priority: Komga DB > Calibre config
        """
        # Check Komga database first (via komga_options.json)
        komga_lib, _ = _get_komga_config()
        komga_db = Path(komga_lib) / 'metadata.db'
        if komga_db.exists():
            komga_path = Path(komga_lib)
            if (komga_path / 'books').exists() and (komga_path / 'books').is_dir():
                komga_path = komga_path / 'books'
            return komga_path, komga_db, None

        # Fall back: Calibre config → /media/comic/metadata.db (Komga)
        if os.path.exists(CALIBRE_CONFIG_PATH):
            with open(CALIBRE_CONFIG_PATH, 'r') as f:
                config = json.load(f)
            calibre_library_path = config.get('calibre_library_path', '')
            if calibre_library_path:
                calibre_path = Path(calibre_library_path)
                if (calibre_path / 'books').exists() and (calibre_path / 'books').is_dir():
                    calibre_path = calibre_path / 'books'
                metadata_db = Path(calibre_library_path) / 'metadata.db'
                if metadata_db.exists():
                    return calibre_path, metadata_db, None

        # Final fallback: /media/comic/metadata.db
        default_path = Path('/media/comic') / 'metadata.db'
        if default_path.exists():
            books_path = Path('/media/comic') / 'books'
            if books_path.exists() and books_path.is_dir():
                return books_path, default_path, None
            return Path('/media/comic'), default_path, None

        return None, None, ({"error": "metadata.db not found"}, 404)

    def _get_db_conn(metadata_db):
        conn = sqlite3.connect(str(metadata_db), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _page_response(content, page=0, size=50, total=None):
        """Build a Komga-standard PageDto."""
        if total is None:
            total = len(content)
        total_pages = max(1, (total + size - 1) // size)
        return {
            "content": content,
            "empty": len(content) == 0,
            "first": page == 0,
            "last": page >= total_pages - 1,
            "number": page,
            "numberOfElements": len(content),
            "pageable": {
                "offset": page * size,
                "pageNumber": page,
                "pageSize": size,
                "paged": True,
                "sort": {"empty": True, "sorted": False, "unsorted": True},
                "unpaged": False,
            },
            "size": size,
            "sort": {"empty": True, "sorted": False, "unsorted": True},
            "totalElements": total,
            "totalPages": total_pages,
        }

    def _author_dto(name="", role="writer"):
        return {"name": name or "Unknown", "role": role}

    def _make_series_dto(row, comics_only=True):
        """Build a Komga-standard SeriesDto."""
        return {
            "id": str(row["id"]),
            "libraryId": "comics",
            "name": row["name"],
            "url": f"/api/v1/series/{row['id']}",
            "created": _date_iso(row.get("created", "")),
            "lastModified": _date_iso(row.get("last_modified", "")),
            "fileLastModified": _date_iso(row.get("file_last_modified", "")),
            "booksCount": row.get("books_count", 0),
            "booksReadCount": row.get("books_read_count", 0),
            "booksUnreadCount": row.get("books_count", 0),
            "booksInProgressCount": row.get("books_in_progress_count", 0),
            "oneshot": row.get("oneshot", False),
            "deleted": False,
            "metadata": {
                "title": row["name"],
                "titleLock": True,
                "titleSort": row.get("name_sort") or row["name"],
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
        """Count pages in CBZ/image directories."""
        try:
            ext = ext.lower().strip('.')
            db_path = None
            # Try to get stored path from DB
            if os.path.exists(KOMGA_CONFIG_PATH):
                with open(KOMGA_CONFIG_PATH, 'r') as f:
                    cfg = json.load(f)
                komga_lib = cfg.get('komga_library_path', '/media/comic/book')
                komga_db = Path(komga_lib) / 'metadata.db'
            else:
                komga_db = None
            if komga_db and komga_db.exists():
                conn2 = sqlite3.connect(str(komga_db))
                c2 = conn2.cursor()
                c2.execute("SELECT path FROM books WHERE id = ?", (book_id,))
                row2 = c2.fetchone()
                conn2.close()
                if row2 and row2[0]:
                    db_path = row2[0]

            library_roots = [calibre_path] + [Path(p) for p in [
                '/media/comic', '/media/comic/book'
            ] if Path(p) != calibre_path]

            if ext in ('cbz', 'zip'):
                book_path = _find_book_file(book_id, ext, calibre_path, db_path)
                if book_path and book_path.exists():
                    with zipfile.ZipFile(str(book_path), 'r') as zf:
                        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                        return sum(1 for n in zf.namelist()
                                  if os.path.splitext(n)[1].lower() in image_exts
                                  and not n.startswith('__MACOSX'))

            # Scan all subdirs in known roots for {book_id}.{ext}
            ext_suffix = f'.{ext}'
            for base in library_roots:
                if not base.is_dir():
                    continue
                try:
                    for sub in base.iterdir():
                        if not sub.is_dir():
                            continue
                        candidate = sub / f"{book_id}{ext_suffix}"
                        if candidate.is_file():
                            if ext == 'pdf':
                                return 1
                            image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                            return sum(1 for f in sub.iterdir()
                                      if f.suffix.lower() in image_exts)
                except PermissionError:
                    pass

        except Exception as e:
            logger.warning(f"[Komga] Error getting page count for {book_id}: {e}")
        return 0

    def _media_profile(media_type):
        mt = media_type.lower()
        if mt == "application/epub+zip":
            return "epub"
        if mt in ("application/pdf", "application/vnd.comicbook+zip",
                  "application/vnd.comicbook+xml"):
            return "pdf"
        if mt in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            return "image"
        return "unknown"

    def _make_book_dto(row, base_url="/api/v1"):
        """Build a Komga-standard BookDto."""
        book_id = str(row["id"])
        ext = row.get("format", "").lower()
        media_type = f"application/{ext}" if ext else "application/octet-stream"

        number_raw = row.get("series_index", 0) or 0
        try:
            number_int = int(float(number_raw))
        except (TypeError, ValueError):
            number_int = 0

        size_bytes = row.get("file_size") or 0
        # Page count is computed at call sites and passed as _pages_count
        pages_count = row.get("_pages_count") or 0

        return {
            "id": book_id,
            "seriesId": str(row["series_id"]) if row.get("series_id") else None,
            "seriesTitle": row.get("series_name"),
            "libraryId": "comics",
            "name": row.get("title") or f"Book {book_id}",
            "title": row.get("title") or f"Book {book_id}",
            "number": number_int,
            "oneshot": row.get("oneshot", False),
            "size": str(size_bytes),
            "sizeBytes": size_bytes,
            "fileHash": row.get("file_hash") or "",
            "fileLastModified": _date_iso(row.get("file_last_modified", "")),
            "created": _date_iso(row.get("created", "")),
            "lastModified": _date_iso(row.get("last_modified", "")),
            "deleted": False,
            "url": f"{base_url}/books/{book_id}",
            "thumbnailUrl": f"/api/v1/books/{book_id}/thumbnail",
            "readableAt": _date_iso(row.get("pubdate", "")),
            "readProgress": None,
            "media": {
                "mediaType": media_type,
                "status": "READY",
                "pagesCount": pages_count,
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

    def _find_book_file(book_id, ext, calibre_path, db_path=None):
        """Find a book file by ID and extension.

        If db_path is provided (e.g. 'books/女神のスプリンター'), use it directly.
        Otherwise fall back to book_id folder.

        Tries multiple library roots to handle legacy/alternate paths.
        """
        ext = ext.lower().lstrip('.')

        # Candidate library roots (most specific first)
        library_roots = [calibre_path] + [Path(p) for p in [
            '/media/comic',
            '/media/comic/book',
        ] if Path(p) != calibre_path]

        found = None

        # 1. Try the stored path first (most specific)
        if db_path:
            for root in library_roots:
                book_folder = root / db_path
                if book_folder.exists() and book_folder.is_dir():
                    for f in book_folder.iterdir():
                        if f.is_file() and f.suffix.lstrip('.').lower() == ext:
                            found = f
                            break
                    if found:
                        break
                    # Also check if db_path is already a file
                    file_path = root / db_path
                    if file_path.is_file() and file_path.suffix.lstrip('.').lower() == ext:
                        found = file_path
                        break
                # db_path might be a relative path under /media/comic directly
                # e.g. '女神のスプリンター/7.pdf' relative to /media/comic
                for base in ('/media/comic', '/media/comic/book'):
                    alt = Path(base) / db_path
                    if alt.is_file() and alt.suffix.lstrip('.').lower() == ext:
                        found = alt
                        break
                    alt_dir = Path(base) / db_path
                    if alt_dir.is_dir():
                        for f in alt_dir.iterdir():
                            if f.is_file() and f.suffix.lstrip('.').lower() == ext:
                                found = f
                                break
                        if found:
                            break
                if found:
                    break

        # 2. Fall back: scan ALL subdirectories of known roots for {book_id}.{ext}
        if not found:
            ext_suffix = f'.{ext}'
            for base in ('/media/comic', '/media/comic/book', str(calibre_path)):
                base_path = Path(base)
                if not base_path.is_dir():
                    continue
                try:
                    for sub in base_path.iterdir():
                        if not sub.is_dir():
                            continue
                        # Try {book_id}.{ext} inside subdirectory
                        candidate = sub / f"{book_id}{ext_suffix}"
                        if candidate.is_file():
                            found = candidate
                            break
                except PermissionError:
                    pass
                if found:
                    break

        return found

    def _build_book_page_url(book_id, page_num):
        """Build absolute URL for a book page."""
        base = request.host_url.rstrip('/')
        return f"{base}/api/v1/komga/books/{book_id}/pages/{page_num}"

    # Store calibre_path for use in helper functions
    calibre_path = None

    def _get_calibre_path():
        global calibre_path
        if calibre_path is None:
            _, _, err = _get_calibre_config()
            if err:
                return None
            calibre_path, _, _ = _get_calibre_config()
        return calibre_path

    # ── Auth check helper ────────────────────────────────────────────────────

    def _require_auth():
        if not _authenticate():
            return Response(json.dumps({"error": "Unauthorized"}), status=401,
                           mimetype='application/json',
                           headers={'WWW-Authenticate': 'Basic realm="MediaHa"'})
        return None

    # ── Root / System ────────────────────────────────────────────────────────

    @app.route('/api/v1')
    @app.route('/komga/api/v1')
    def komga_api_root():
        """Komga API root."""
        err = _require_auth()
        if err:
            return err
        return Response(json.dumps({"name": "MediaHa", "version": "1.0"}),
                       mimetype='application/json')

    @app.route('/api/v1/libraries')
    @app.route('/komga/api/v1/libraries')
    @app.route('/komga/libraries')
    def komga_libraries():
        """List libraries (always returns one 'Comics' library)."""
        err = _require_auth()
        if err:
            return err
        return Response(json.dumps([{
            "id": "comics",
            "name": "Comics",
            "type": "COMIC",
            "url": "/api/v1/libraries/comics",
            "created": _now_iso(),
            "lastModified": _now_iso(),
        }]), mimetype='application/json')

    @app.route('/api/v1/libraries/<library_id>')
    @app.route('/komga/api/v1/libraries/<library_id>')
    @app.route('/komga/libraries/<library_id>')
    def komga_library_detail(library_id):
        """Get library details."""
        err = _require_auth()
        if err:
            return err
        if library_id != "comics":
            return Response(json.dumps({"error": "Not found"}), status=404, mimetype='application/json')
        return Response(json.dumps({
            "id": "comics",
            "name": "Comics",
            "type": "COMIC",
            "url": "/api/v1/libraries/comics",
            "created": _now_iso(),
            "lastModified": _now_iso(),
        }), mimetype='application/json')

    # ── Series ────────────────────────────────────────────────────────────────

    def _derive_series_name(series_id, cursor):
        """Derive series name from first book's title, stripping volume/chapter prefixes."""
        cursor.execute("""
            SELECT b.title FROM books b
            JOIN books_series_link bsl ON b.id = bsl.book
            WHERE bsl.series = ?
            ORDER BY b.series_index
            LIMIT 1
        """, (series_id,))
        row = cursor.fetchone()
        if row and row["title"]:
            name = re.sub(r'^(第?\d+[卷話话章回集]|[VvOo]l?\.?\s*\d+|\d+\s*[-.]\s*)', '', row["title"])
            name = re.sub(r'\s+(第?\d+[卷話话章回集]|[VvOo]l?\.?\s*\d+|\d+)\s*$', '', name).strip()
            name = re.sub(r'\s*[-–—―_]+\s*$', '', name).strip()
            return name
        return None

    def _query_series(extra_where="", extra_params=(), order_by="s.name ASC"):
        """Reusable series query helper."""
        cpath, mdb, err = _get_calibre_config()
        if err:
            return [], 0
        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        where_comics = "JOIN books_tags_link btl ON b.id = btl.book JOIN tags t ON btl.tag = t.id AND t.name = 'Comics'"

        count_sql = f"""
            SELECT COUNT(DISTINCT s.id) as cnt
            FROM series s
            JOIN books_series_link bsl ON s.id = bsl.series
            JOIN books b ON bsl.book = b.id
            {where_comics}
            {'WHERE ' + extra_where if extra_where else ''}
        """
        cursor.execute(count_sql, extra_params)
        total = cursor.fetchone()["cnt"]

        data_sql = f"""
            SELECT s.id, s.name,
                   COUNT(DISTINCT b.id) as books_count,
                   MAX(b.pubdate) as latest_date
            FROM series s
            JOIN books_series_link bsl ON s.id = bsl.series
            JOIN books b ON bsl.book = b.id
            {where_comics}
            {'WHERE ' + extra_where if extra_where else ''}
            GROUP BY s.id, s.name
            ORDER BY {order_by}
        """
        cursor.execute(data_sql, extra_params)
        rows = [dict(row) for row in cursor.fetchall()]

        for r in rows:
            # Derive proper name from first book title using shared cursor
            derived = _derive_series_name(r["id"], cursor)
            if derived:
                r["name"] = derived
            r["books_read_count"] = 0
            r["books_in_progress_count"] = 0
            r["last_modified"] = r["latest_date"]
            r["created"] = r["latest_date"]
        conn.close()
        return rows, total

    @app.route('/api/v1/libraries/<library_id>/series')
    @app.route('/komga/api/v1/libraries/<library_id>/series')
    @app.route('/komga/libraries/<library_id>/series')
    def komga_library_series(library_id):
        """List all series in a library."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))
        sort = request.args.get('sort', 'name,asc')

        rows, total = _query_series()
        rows = rows[size * page: size * page + size]
        series_list = [_make_series_dto(r) for r in rows]
        return Response(json.dumps(_page_response(series_list, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/series')
    @app.route('/komga/api/v1/series')
    @app.route('/komga/series')
    def komga_series_list():
        """List all series (flat endpoint)."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))
        sort = request.args.get('sort', 'name,asc')

        rows, total = _query_series()
        rows = rows[size * page: size * page + size]
        series_list = [_make_series_dto(r) for r in rows]
        return Response(json.dumps(_page_response(series_list, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/series/new')
    @app.route('/komga/api/v1/series/new')
    @app.route('/komga/series/new')
    def komga_series_new():
        """New series - most recently added."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))

        rows, total = _query_series(order_by="latest_date DESC")
        rows = rows[size * page: size * page + size]
        series_list = [_make_series_dto(r) for r in rows]
        return Response(json.dumps(_page_response(series_list, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/series/updated')
    @app.route('/komga/api/v1/series/updated')
    @app.route('/komga/series/updated')
    def komga_series_updated():
        """Updated series - most recently modified."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))

        rows, total = _query_series(order_by="latest_date DESC")
        rows = rows[size * page: size * page + size]
        series_list = [_make_series_dto(r) for r in rows]
        return Response(json.dumps(_page_response(series_list, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/series/<series_id>')
    @app.route('/komga/api/v1/series/<series_id>')
    @app.route('/komga/series/<series_id>')
    def komga_series_detail(series_id):
        """Get single series details (bypass tag filter for direct lookups)."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps({"error": "Not found"}), status=404, mimetype='application/json')
        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        # Get series + first book title to derive proper series name
        cursor.execute("""
            SELECT s.id, s.name, s.name_sort,
                   b.id as first_book_id, b.title as first_book_title
            FROM series s
            LEFT JOIN books_series_link bsl ON s.id = bsl.series
            LEFT JOIN books b ON bsl.book = b.id
            WHERE s.id = ?
            LIMIT 1
        """, (series_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return Response(json.dumps({"error": "Not found"}), status=404, mimetype='application/json')
        rd = dict(row)

        # Derive series name from first book title (strip leading vol/chapter numbers)
        if rd.get("first_book_title"):
            series_name = re.sub(r'^(第?\d+[卷話话章回集]|[VvOo]ol?\.?\s*\d+|\d+\s*[-.]\s*)', '', rd["first_book_title"])
            series_name = re.sub(r'\s+(第?\d+[卷話话章回集]|[VvOo]ol?\.?\s*\d+|\d+)\s*$', '', series_name).strip()
            series_name = re.sub(r'\s*[-–—―_]+\s*$', '', series_name).strip()
        else:
            series_name = rd.get("name", "")

        cursor.execute("""
            SELECT COUNT(DISTINCT b.id) as books_count,
                   MAX(b.pubdate) as latest_date,
                   MAX(b.last_modified) as last_modified,
                   MIN(b.created) as created
            FROM series s
            LEFT JOIN books_series_link bsl ON s.id = bsl.series
            LEFT JOIN books b ON bsl.book = b.id
            WHERE s.id = ?
        """, (series_id,))
        meta = cursor.fetchone()
        conn.close()

        rd["name"] = series_name
        rd["books_count"] = meta["books_count"] if meta else 0
        rd["latest_date"] = meta["latest_date"] if meta else None
        rd["last_modified"] = meta["last_modified"] if meta else None
        rd["created"] = meta["created"] if meta else None
        rd["books_read_count"] = 0
        rd["books_in_progress_count"] = 0
        return Response(json.dumps(_make_series_dto(rd)), mimetype='application/json')

    @app.route('/api/v1/series/<series_id>/books')
    @app.route('/komga/api/v1/series/<series_id>/books')
    @app.route('/komga/series/<series_id>/books')
    def komga_series_books(series_id):
        """Get all books in a series."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 500))

        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps(_page_response([], page, size)), mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM books b
            JOIN books_series_link bsl ON b.id = bsl.book
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            WHERE bsl.series = ? AND t.name = 'Comics'
        """, (series_id,))
        total = cursor.fetchone()["cnt"]

        # Derive series name from first book title (before we iterate)
        derived_series_name = _derive_series_name(series_id, cursor)
        if not derived_series_name:
            cursor.execute("SELECT name FROM series WHERE id = ?", (series_id,))
            row = cursor.fetchone()
            derived_series_name = row["name"] if row else ""

        cursor.execute("""
            SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                   d.format, d.name as filename, d.uncompressed_size as file_size,
                   s.id as series_id
            FROM books b
            JOIN books_series_link bsl ON b.id = bsl.book
            JOIN series s ON bsl.series = s.id
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            LEFT JOIN data d ON b.id = d.book
            WHERE bsl.series = ? AND t.name = 'Comics'
            ORDER BY b.series_index
            LIMIT ? OFFSET ?
        """, (series_id, size, page * size))

        books = []
        for row in cursor.fetchall():
            rd = dict(row)
            rd["series_name"] = derived_series_name
            ext = rd.get("format", "").lower()
            if ext in ('cbz', 'zip'):
                rd["_pages_count"] = _get_book_page_count(rd["id"], ext, cpath)
            books.append(_make_book_dto(rd))
        conn.close()
        return Response(json.dumps(_page_response(books, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/series/<series_id>/thumbnail')
    @app.route('/komga/api/v1/series/<series_id>/thumbnail')
    @app.route('/komga/series/<series_id>/thumbnail')
    def komga_series_thumbnail(series_id):
        """Get series thumbnail (first book's cover)."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response("Not found", status=404)
        conn = _get_db_conn(mdb)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id FROM books b
            JOIN books_series_link bsl ON b.id = bsl.book
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            WHERE bsl.series = ? AND t.name = 'Comics'
            ORDER BY b.series_index LIMIT 1
        """, (series_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return Response("Not found", status=404)
        book_id = row["id"]
        # Redirect to the book's thumbnail
        return redirect(f"/api/v1/books/{book_id}/thumbnail", code=302)

    # ── Books ────────────────────────────────────────────────────────────────

    @app.route('/api/v1/books')
    @app.route('/komga/api/v1/books')
    @app.route('/komga/books')
    def komga_books_list():
        """List all books."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))

        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps(_page_response([], page, size)), mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM books b
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            WHERE t.name = 'Comics'
        """)
        total = cursor.fetchone()["cnt"]

        # Pre-load series names from book titles for all series in this page
        cursor.execute("""
            SELECT DISTINCT bsl.series as series_id
            FROM books b
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            LEFT JOIN books_series_link bsl ON b.id = bsl.book
            WHERE t.name = 'Comics' AND bsl.series IS NOT NULL
        """)
        series_ids = [row["series_id"] for row in cursor.fetchall()]
        series_name_map = {}
        for sid in series_ids:
            derived = _derive_series_name(sid, cursor)
            cursor.execute("SELECT name FROM series WHERE id = ?", (sid,))
            row = cursor.fetchone()
            fallback = row["name"] if row else ""
            series_name_map[sid] = derived or fallback

        cursor.execute("""
            SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                   d.format, d.name as filename, d.uncompressed_size as file_size,
                   s.id as series_id
            FROM books b
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            LEFT JOIN books_series_link bsl ON b.id = bsl.book
            LEFT JOIN series s ON bsl.series = s.id
            LEFT JOIN data d ON b.id = d.book
            WHERE t.name = 'Comics'
            ORDER BY b.series_index
            LIMIT ? OFFSET ?
        """, (size, page * size))

        books = []
        for row in cursor.fetchall():
            rd = dict(row)
            rd["series_name"] = series_name_map.get(rd["series_id"], "") if rd.get("series_id") else ""
            ext = rd.get("format", "").lower()
            if ext in ('cbz', 'zip'):
                rd["_pages_count"] = _get_book_page_count(rd["id"], ext, cpath)
            books.append(_make_book_dto(rd))
        conn.close()
        return Response(json.dumps(_page_response(books, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/books/ondeck')
    @app.route('/komga/api/v1/books/ondeck')
    @app.route('/komga/books/ondeck')
    def komga_books_ondeck():
        """Books on deck (recently read / next to read)."""
        err = _require_auth()
        if err:
            return err
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 20))

        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps(_page_response([], page, size)), mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        # Return recently added comics as "on deck"
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM books b
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            WHERE t.name = 'Comics'
        """)
        total = cursor.fetchone()["cnt"]

        cursor.execute("""
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
            ORDER BY b.last_modified DESC
            LIMIT ? OFFSET ?
        """, (size, page * size))

        books = []
        for row in cursor.fetchall():
            rd = dict(row)
            ext = rd.get("format", "").lower()
            if ext in ('cbz', 'zip'):
                rd["_pages_count"] = _get_book_page_count(rd["id"], ext, cpath)
            books.append(_make_book_dto(rd))
        conn.close()
        return Response(json.dumps(_page_response(books, page, size, total)), mimetype='application/json')

    @app.route('/api/v1/komga/books/<book_id>')
    @app.route('/api/v1/books/<book_id>')
    @app.route('/komga/api/v1/books/<book_id>')
    @app.route('/komga/books/<book_id>')
    def komga_book_detail(book_id):
        """Get single book details."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps({}), status=404, mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.title, b.series_index, b.pubdate, b.uuid,
                   d.format, d.name as filename, d.uncompressed_size as file_size,
                   s.id as series_id
            FROM books b
            LEFT JOIN books_series_link bsl ON b.id = bsl.book
            LEFT JOIN series s ON bsl.series = s.id
            LEFT JOIN data d ON b.id = d.book
            WHERE b.id = ?
        """, (book_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return Response(json.dumps({}), status=404, mimetype='application/json')
        rd = dict(row)
        # Derive series name from book title (s.name is unreliable)
        series_id = rd.get("series_id")
        if series_id and rd.get("title"):
            derived = re.sub(r'^(第?\d+[卷話话章回集]|[VvOo]l?\.?\s*\d+|\d+\s*[-.]\s*)', '', rd["title"])
            derived = re.sub(r'\s+(第?\d+[卷話话章回集]|[VvOo]l?\.?\s*\d+|\d+)\s*$', '', derived).strip()
            derived = re.sub(r'\s*[-–—―_]+\s*$', '', derived).strip()
            rd["series_name"] = derived
        else:
            rd["series_name"] = ""
        ext = rd.get("format", "").lower()
        if ext in ('cbz', 'zip'):
            rd["_pages_count"] = _get_book_page_count(book_id, ext, cpath)
        return Response(json.dumps(_make_book_dto(rd)), mimetype='application/json')

    @app.route('/api/v1/komga/books/<book_id>/thumbnail')
    @app.route('/api/v1/books/<book_id>/thumbnail')
    @app.route('/komga/api/v1/books/<book_id>/thumbnail')
    @app.route('/komga/books/<book_id>/thumbnail')
    def komga_book_thumbnail(book_id):
        """Serve book cover image."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response("Not found", status=404)

        # Always look in the book_id subfolder under cpath
        book_folder = cpath / str(book_id)
        if book_folder.exists() and book_folder.is_dir():
            # Prioritize cover.jpg / cover.png named files
            for f in book_folder.iterdir():
                if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                    name_lower = f.name.lower()
                    if 'cover' in name_lower or 'thumbnail' in name_lower or f.stem == 'cover':
                        return send_file(str(f))
            # Fall back to first image
            for f in book_folder.iterdir():
                if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                    return send_file(str(f))

        # Deep scan: search subdirectories of known roots for cover.jpg inside {book_id}/
        for base in ('/media/comic', '/media/comic/book'):
            try:
                base_path = Path(base)
                if not base_path.is_dir():
                    continue
                for sub in base_path.iterdir():
                    if not sub.is_dir() or sub.stem != str(book_id):
                        continue
                    for f in sub.iterdir():
                        if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp') and 'cover' in f.name.lower():
                            return send_file(str(f))
                    for f in sub.iterdir():
                        if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                            return send_file(str(f))
            except PermissionError:
                pass
        return Response("Not found", status=404)

    @app.route('/api/v1/komga/books/<book_id>/pages')
    @app.route('/api/v1/books/<book_id>/pages')
    @app.route('/komga/api/v1/books/<book_id>/pages')
    @app.route('/komga/books/<book_id>/pages')
    def komga_book_pages(book_id):
        """Get list of page URLs for a book."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps([]), status=404, mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()
        cursor.execute("SELECT b.id, b.path, d.format FROM books b LEFT JOIN data d ON b.id = d.book WHERE b.id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return Response(json.dumps([]), status=404, mimetype='application/json')

        ext = row["format"].lower() if row["format"] else ""
        db_path = row["path"]
        pages = []

        if ext in ('cbz', 'zip'):
            book_path = _find_book_file(book_id, ext, cpath, db_path)
            if book_path and book_path.exists():
                try:
                    with zipfile.ZipFile(str(book_path), 'r') as zf:
                        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                        names = sorted([n for n in zf.namelist()
                                      if os.path.splitext(n)[1].lower() in image_exts
                                      and not n.startswith('__MACOSX')],
                                      key=lambda x: x.lower())
                        for i, _ in enumerate(names, 1):
                            pages.append(_build_book_page_url(book_id, i))
                except Exception as e:
                    logger.warning(f"[Komga] Error reading CBZ: {e}")

        elif ext == 'pdf':
            pages.append(_build_book_page_url(book_id, 1))

        else:
            # Image folder: search broadly since db_path may be wrong
            image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            found_folder = None
            for base in ('/media/comic', '/media/comic/book'):
                try:
                    base_path = Path(base)
                    if not base_path.is_dir():
                        continue
                    for sub in base_path.iterdir():
                        if not sub.is_dir() or sub.stem != str(book_id):
                            continue
                        files = [f for f in sub.iterdir() if f.suffix.lower() in image_exts]
                        if files:
                            found_folder = sub
                            break
                except PermissionError:
                    pass
                if found_folder:
                    break
            if not found_folder:
                # Fall back to cpath
                found_folder = cpath / (db_path or str(book_id))
            if found_folder.exists() and found_folder.is_dir():
                files = sorted([f for f in found_folder.iterdir() if f.suffix.lower() in image_exts],
                              key=lambda x: x.name.lower())
                for i, _ in enumerate(files, 1):
                    pages.append(_build_book_page_url(book_id, i))

        logger.warning(f"[Komga] book_pages: book_id={book_id} format={ext} pages={len(pages)}")
        return Response(json.dumps(pages), mimetype='application/json')

    @app.route('/api/v1/komga/books/<book_id>/pages/<int:page_num>')
    @app.route('/api/v1/books/<book_id>/pages/<int:page_num>')
    @app.route('/komga/api/v1/books/<book_id>/pages/<int:page_num>')
    @app.route('/komga/books/<book_id>/pages/<int:page_num>')
    def komga_book_page(book_id, page_num):
        """Serve a specific page image."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response("Not found", status=404)

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()
        cursor.execute("SELECT b.id, b.path, d.format FROM books b LEFT JOIN data d ON b.id = d.book WHERE b.id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return Response("Not found", status=404)

        ext = row["format"].lower() if row["format"] else ""
        db_path = row["path"]
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                    '.gif': 'image/gif', '.webp': 'image/webp'}

        if ext in ('cbz', 'zip'):
            book_path = _find_book_file(book_id, ext, cpath, db_path)
            if book_path and book_path.exists():
                try:
                    with zipfile.ZipFile(str(book_path), 'r') as zf:
                        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                        names = sorted([n for n in zf.namelist()
                                      if os.path.splitext(n)[1].lower() in image_exts
                                      and not n.startswith('__MACOSX')],
                                      key=lambda x: x.lower())
                        if 1 <= page_num <= len(names):
                            data = zf.read(names[page_num - 1])
                            mime = mime_map.get(os.path.splitext(names[page_num - 1])[1].lower(), 'image/jpeg')
                            return Response(data, mimetype=mime)
                except Exception as e:
                    logger.warning(f"[Komga] Error extracting page: {e}")

        else:
            image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            found_folder = None
            for base in ('/media/comic', '/media/comic/book'):
                try:
                    base_path = Path(base)
                    if not base_path.is_dir():
                        continue
                    for sub in base_path.iterdir():
                        if not sub.is_dir() or sub.stem != str(book_id):
                            continue
                        files = [f for f in sub.iterdir() if f.suffix.lower() in image_exts]
                        if files:
                            found_folder = sub
                            break
                except PermissionError:
                    pass
                if found_folder:
                    break
            if not found_folder:
                found_folder = cpath / (db_path or str(book_id))
            if found_folder.exists() and found_folder.is_dir():
                files = sorted([f for f in found_folder.iterdir() if f.suffix.lower() in image_exts],
                              key=lambda x: x.name.lower())
                if 1 <= page_num <= len(files):
                    return send_file(str(files[page_num - 1]),
                                   mimetype=mime_map.get(files[page_num - 1].suffix.lower(), 'image/jpeg'))

        return Response("Page not found", status=404)

    @app.route('/api/v1/books/<book_id>/content')
    @app.route('/komga/api/v1/books/<book_id>/content')
    @app.route('/komga/books/<book_id>/content')
    def komga_book_content(book_id):
        """Download the book file."""
        err = _require_auth()
        if err:
            return err
        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response("Not found", status=404)

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()
        cursor.execute("SELECT b.id, b.path, d.format FROM books b LEFT JOIN data d ON b.id = d.book WHERE b.id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return Response("Not found", status=404)

        ext = row["format"].lower() if row["format"] else "cbz"
        db_path = row["path"]
        mime_map = {
            'epub': 'application/epub+zip', 'pdf': 'application/pdf',
            'cbz': 'application/vnd.comicbook+zip', 'cbr': 'application/vnd.comicbook-rar',
            'zip': 'application/zip',
        }
        book_path = _find_book_file(book_id, ext, cpath, db_path)
        if book_path and book_path.exists():
            return send_file(str(book_path), mimetype=mime_map.get(ext, 'application/octet-stream'),
                           as_attachment=True, download_name=book_path.name)
        return Response("File not found", status=404)

    # ── Search ──────────────────────────────────────────────────────────────

    @app.route('/api/v1/search')
    @app.route('/komga/api/v1/search')
    @app.route('/komga/search')
    def komga_search():
        """Search series and books."""
        err = _require_auth()
        if err:
            return err
        query = request.args.get('query', request.args.get('q', ''))
        if not query:
            return Response(json.dumps({"results": []}), mimetype='application/json')

        cpath, mdb, err = _get_calibre_config()
        if err:
            return Response(json.dumps({"results": []}), mimetype='application/json')

        conn = _get_db_conn(mdb)
        cursor = conn.cursor()

        results = []
        cursor.execute("""
            SELECT DISTINCT s.id, COUNT(DISTINCT b.id) as book_count
            FROM series s
            JOIN books_series_link bsl ON s.id = bsl.series
            JOIN books b ON bsl.book = b.id
            JOIN books_tags_link btl ON b.id = btl.book
            JOIN tags t ON btl.tag = t.id
            WHERE t.name = 'Comics' AND s.name LIKE ?
            GROUP BY s.id
            ORDER BY s.name LIMIT 20
        """, (f'%{query}%',))
        for row in cursor.fetchall():
            sid = row["id"]
            derived = _derive_series_name(sid, cursor)
            cursor.execute("SELECT name FROM series WHERE id = ?", (sid,))
            fallback_row = cursor.fetchone()
            fallback = fallback_row["name"] if fallback_row else ""
            results.append({"type": "series", "id": str(sid),
                          "name": derived or fallback, "bookCount": row["book_count"]})

        conn.close()
        return Response(json.dumps({"results": results}), mimetype='application/json')

    # ── Komga Sync ─────────────────────────────────────────────────────────────
    # NOTE: /api/komga/sync is now defined in calibre_routes.py
    # This avoids duplicate route conflicts

    @app.route('/komga/book/<book_id>')
    def komga_book_reader(book_id):
        """Serve the Komga book reader page."""
        if not session.get("authenticated"):
            return redirect('/login.html', code=302)
        return send_from_directory(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '../ui/pages'),
            'komga-book.html'
        )

    @app.route('/api/komga/settings', methods=['GET', 'POST'])
    def komga_settings():
        """Get or save Komga library settings."""
        if request.method == 'GET':
            if os.path.exists(KOMGA_CONFIG_PATH):
                with open(KOMGA_CONFIG_PATH, 'r') as f:
                    return jsonify(json.load(f))
            return jsonify({
                'komga_library_path': '/media/comic/book',
                'comic_folder': '/media/comic'
            })

        data = request.get_json()
        with open(KOMGA_CONFIG_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({'status': 'ok'})

    # ── Komga OPDS Catalog ─────────────────────────────────────────────────────
    # Sync is now in calibre_routes.py to avoid duplicate route conflicts

    logger.warning("[Komga] register_routes() complete")
