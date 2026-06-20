# -*- coding: utf-8 -*-
"""Calibre sync routes for EPUB and Comics."""
import os
import re
import json
import shutil
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from flask import jsonify


CALIBRE_CONFIG_PATH = '/data/calibre_options.json'


def register_calibre_routes(app):
    """Register Calibre sync routes."""

    def extract_epub_metadata(epub_path):
        """Extract metadata from EPUB file."""
        result = {
            'title': None, 'authors': [], 'cover_data': None, 'cover_name': None,
            'language': None, 'publisher': None, 'identifier': None,
            'description': None, 'tags': [], 'date': None
        }
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                container = zf.read('META-INF/container.xml').decode('utf-8')
                root = ET.fromstring(container)
                rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                if rootfile is not None:
                    opf_path = rootfile.get('full-path')
                    opf_content = zf.read(opf_path).decode('utf-8')
                    opf_root = ET.fromstring(opf_content)
                    ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}

                    title_el = opf_root.find('.//dc:title', ns)
                    if title_el is not None and title_el.text:
                        result['title'] = title_el.text.strip()

                    for creator in opf_root.findall('.//dc:creator', ns):
                        if creator.text:
                            result['authors'].append(creator.text.strip())

                    lang_el = opf_root.find('.//dc:language', ns)
                    if lang_el is not None and lang_el.text:
                        result['language'] = lang_el.text.strip()

                    pub_el = opf_root.find('.//dc:publisher', ns)
                    if pub_el is not None and pub_el.text:
                        result['publisher'] = pub_el.text.strip()

                    for id_el in opf_root.findall('.//dc:identifier', ns):
                        if id_el.text:
                            id_text = id_el.text.strip()
                            scheme = id_el.get('{http://purl.org/dc/elements/1.1/}scheme') or id_el.get('scheme') or ''
                            if 'isbn' in scheme.lower() or 'isbn' in id_text.lower():
                                result['identifier'] = id_text
                            elif not result['identifier']:
                                result['identifier'] = id_text

                    desc_el = opf_root.find('.//dc:description', ns)
                    if desc_el is not None and desc_el.text:
                        result['description'] = desc_el.text.strip()

                    for subj in opf_root.findall('.//dc:subject', ns):
                        if subj.text:
                            result['tags'].append(subj.text.strip())

                    date_el = opf_root.find('.//dc:date', ns)
                    if date_el is not None and date_el.text:
                        result['date'] = date_el.text.strip()

                    cover_id = None
                    meta_cover = opf_root.find('.//opf:meta[@name="cover"]', ns)
                    if meta_cover is not None:
                        cover_id = meta_cover.get('content')
                    if not cover_id:
                        for item in opf_root.findall('.//opf:item', ns):
                            props = item.get('properties', '')
                            if 'cover-image' in props:
                                cover_id = item.get('id')
                                break

                    if cover_id:
                        for item in opf_root.findall('.//opf:item', ns):
                            if item.get('id') == cover_id:
                                href = item.get('href')
                                if href:
                                    opf_dir = opf_path.rsplit('/', 1)[0] if '/' in opf_path else ''
                                    cover_path = f"{opf_dir}/{href}" if opf_dir else href
                                    cover_path = cover_path.lstrip('/')
                                    try:
                                        result['cover_data'] = zf.read(cover_path)
                                        result['cover_name'] = os.path.basename(href)
                                    except:
                                        pass
                                break
        except Exception as e:
            pass
        return result

    @app.route('/api/calibre/sync', methods=['POST'])
    def sync_calibre():
        """Sync EPUB files to Calibre library"""
        def generate():
            try:
                import sqlite3

                if os.path.exists(CALIBRE_CONFIG_PATH):
                    with open(CALIBRE_CONFIG_PATH, 'r') as f:
                        config = json.load(f)
                else:
                    yield json.dumps({'type': 'error', 'message': 'Please configure Calibre settings first'}) + '\n'
                    return

                epub_folder = config.get('epub_folder', '/media/eBook')
                calibre_library_path = config.get('calibre_library_path', '')

                if not epub_folder or not calibre_library_path:
                    yield json.dumps({'type': 'error', 'message': 'Please configure both EPUB folder and Calibre library path'}) + '\n'
                    return

                epub_path = Path(epub_folder)
                calibre_path = Path(calibre_library_path)

                if not epub_path.exists() or not calibre_path.exists():
                    yield json.dumps({'type': 'error', 'message': 'Folder not found'}) + '\n'
                    return

                epub_files = list(epub_path.rglob("*.epub"))
                total = len(epub_files)

                if total == 0:
                    yield json.dumps({'type': 'error', 'message': 'No EPUB files found'}) + '\n'
                    return

                yield json.dumps({'type': 'log', 'message': f'Found {total} EPUB files', 'level': 'info'}) + '\n'
                yield json.dumps({'type': 'log', 'message': f'Calibre library: {calibre_library_path}', 'level': 'info'}) + '\n'

                use_calibre = False
                try:
                    from calibre.library import db
                    from calibre.ebooks.metadata.book.base import Metadata
                    use_calibre = True
                    yield json.dumps({'type': 'log', 'message': 'Using Calibre library API', 'level': 'info'}) + '\n'
                except ImportError:
                    yield json.dumps({'type': 'log', 'message': 'Calibre library not available, using direct SQL', 'level': 'info'}) + '\n'

                if (calibre_path / 'books').exists() and (calibre_path / 'books').is_dir():
                    books_folder = calibre_path / 'books'
                else:
                    books_folder = calibre_path / 'books'

                metadata_db = Path(calibre_library_path) / 'metadata.db'
                books_folder.mkdir(parents=True, exist_ok=True)

                try:
                    conn = sqlite3.connect(str(metadata_db), timeout=30)
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA busy_timeout=30000")
                    cursor = conn.cursor()

                    cursor.execute("SELECT DISTINCT book FROM data WHERE format = 'EPUB'")
                    epub_book_ids = [b[0] for b in cursor.fetchall()]

                    if epub_book_ids:
                        yield json.dumps({'type': 'log', 'message': f'Cleaning up {len(epub_book_ids)} old EPUB entries...', 'level': 'info'}) + '\n'
                        cursor.execute("DELETE FROM books_authors_link WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                        cursor.execute("DELETE FROM books_series_link WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                        cursor.execute("DELETE FROM data WHERE book IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                        cursor.execute("DELETE FROM books WHERE id IN (%s)" % ','.join('?' * len(epub_book_ids)), epub_book_ids)
                        conn.commit()
                        for bid in epub_book_ids:
                            old_dir = books_folder / str(bid)
                            if old_dir.exists():
                                try:
                                    shutil.rmtree(old_dir)
                                except:
                                    pass

                    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                    for (trigger,) in cursor.fetchall():
                        try:
                            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                        except:
                            pass

                    schema = """
                        CREATE TABLE IF NOT EXISTS languages (id INTEGER PRIMARY KEY, lang_code TEXT UNIQUE NOT NULL);
                        CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                        CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
                        CREATE TABLE IF NOT EXISTS identifiers (id INTEGER PRIMARY KEY, type TEXT, val TEXT);
                        CREATE TABLE IF NOT EXISTS books_identifiers (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, type TEXT, val TEXT);
                        CREATE TABLE IF NOT EXISTS books_languages_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL);
                        CREATE TABLE IF NOT EXISTS books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL);
                        CREATE TABLE IF NOT EXISTS books_tags_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL);
                    """
                    for stmt in schema.strip().split(';'):
                        stmt = stmt.strip()
                        if stmt and not stmt.startswith('--'):
                            try:
                                cursor.execute(stmt)
                            except:
                                pass

                    conn.commit()
                    conn.close()

                    yield json.dumps({'type': 'log', 'message': 'Library cleared', 'level': 'info'}) + '\n'

                    yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
                    yield json.dumps({'type': 'log', 'message': '=' * 50, 'level': 'info'}) + '\n'
                    yield json.dumps({'type': 'log', 'message': 'STEP 2: Importing EPUB files', 'level': 'info'}) + '\n'
                    yield json.dumps({'type': 'log', 'message': '=' * 50, 'level': 'info'}) + '\n'

                    success_count = 0
                    error_count = 0
                    conn = None
                    cursor = None

                    if use_calibre:
                        cache = dbc.new_api
                    else:
                        conn = sqlite3.connect(str(metadata_db), timeout=30)
                        conn.execute("PRAGMA journal_mode=WAL")
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(books_authors_link)")
                        authors_link_cols = {row[1] for row in cursor.fetchall()}
                        yield json.dumps({'type': 'log', 'message': f'DEBUG: books_authors_link columns: {authors_link_cols}', 'level': 'info'}) + '\n'
                        cursor.execute("PRAGMA table_info(books_series_link)")
                        series_link_cols = {row[1] for row in cursor.fetchall()}
                        yield json.dumps({'type': 'log', 'message': f'DEBUG: books_series_link columns: {series_link_cols}', 'level': 'info'}) + '\n'

                    for idx, epub_file in enumerate(epub_files, 1):
                        yield json.dumps({'type': 'progress', 'current': idx, 'total': total, 'message': f'Importing: {epub_file.relative_to(epub_path)}'}) + '\n'

                        try:
                            rel_path = epub_file.relative_to(epub_path)
                            parts = rel_path.parts

                            if len(parts) >= 3:
                                series_name = parts[-2]
                            elif len(parts) == 2:
                                series_name = parts[0]
                            else:
                                series_name = ''

                            book_title = rel_path.stem

                            series_index = 1.0
                            match = re.search(r'(\d+(?:\.\d+)?)', book_title)
                            if match:
                                series_index = float(match.group(1))

                            if use_calibre:
                                meta = extract_epub_metadata(epub_file)
                                epub_title = meta['title'] or book_title
                                epub_authors = meta['authors'] if meta['authors'] else ['Unknown']
                                mi = Metadata(epub_title, authors=epub_authors)
                                if series_name:
                                    mi.series = series_name
                                    mi.series_index = series_index
                                if meta['cover_data']:
                                    import io
                                    mi.cover = io.BytesIO(meta['cover_data'])
                                format_map = {'EPUB': str(epub_file)}
                                ids, _ = cache.add_books([(mi, format_map)], add_duplicates=False)
                                if ids:
                                    success_count += 1
                                    series_info = f" [Series: {series_name} #{series_index}]" if series_name else ""
                                    author_info = f" by {', '.join(epub_authors[:2])}" if epub_authors and epub_authors[0] != 'Unknown' else ""
                                    yield json.dumps({'type': 'log', 'message': f'✓ {epub_title}{author_info}{series_info}', 'level': 'success'}) + '\n'
                                else:
                                    error_count += 1
                                    yield json.dumps({'type': 'log', 'message': f'✗ {epub_file.name}: Failed', 'level': 'error'}) + '\n'
                            else:
                                meta = extract_epub_metadata(epub_file)
                                epub_title = meta['title'] or book_title
                                epub_authors = meta['authors'] if meta['authors'] else ['Unknown']

                                cursor.execute("SELECT MAX(id) FROM books")
                                max_id = cursor.fetchone()[0] or 0
                                book_id = max_id + 1

                                book_dir = books_folder / str(book_id)
                                book_dir.mkdir(exist_ok=True)
                                safe_title = re.sub(r'[<>:"/\\|?*]', '_', epub_title)[:100]
                                shutil.copy2(epub_file, book_dir / f"{safe_title}.epub")

                                cover_filename = None
                                has_cover = 0
                                if meta['cover_data']:
                                    ext = os.path.splitext(meta['cover_name'] or 'cover.jpg')[1] or '.jpg'
                                    cover_filename = f"cover{ext}"
                                    with open(book_dir / cover_filename, 'wb') as f:
                                        f.write(meta['cover_data'])
                                    has_cover = 1

                                cursor.execute('''
                                    INSERT INTO books (id, title, sort, author_sort, series_index, path, uuid, has_cover, last_modified)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2000-01-01 00:00:00+00:00')
                                ''', (book_id, epub_title, epub_title, epub_authors[0], series_index, f"books/{book_id}", str(uuid.uuid4()), has_cover))

                                cursor.execute('''
                                    INSERT INTO data (book, format, name, uncompressed_size)
                                    VALUES (?, 'EPUB', ?, ?)
                                ''', (book_id, safe_title, epub_file.stat().st_size))

                                for author_name in epub_authors:
                                    cursor.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
                                    row = cursor.fetchone()
                                    author_id = row[0] if row else None
                                    if not author_id:
                                        cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", (author_name, author_name))
                                        author_id = cursor.lastrowid
                                    cols = ['book'] + [c for c in authors_link_cols if c != 'id']
                                    vals = [book_id] + [author_id if c in ('author', 'authors') else 0 for c in cols[1:]]
                                    placeholders = ', '.join(['?' for _ in cols])
                                    cursor.execute(f"INSERT INTO books_authors_link ({', '.join(cols)}) VALUES ({placeholders})", vals)

                                if meta['publisher']:
                                    cursor.execute("SELECT id FROM publishers WHERE name = ?", (meta['publisher'],))
                                    row = cursor.fetchone()
                                    pub_id = row[0] if row else None
                                    if not pub_id:
                                        cursor.execute("INSERT INTO publishers (name, sort) VALUES (?, ?)", (meta['publisher'], meta['publisher']))
                                        pub_id = cursor.lastrowid
                                    try:
                                        cursor.execute("INSERT OR IGNORE INTO books_publishers_link (book, publisher) VALUES (?, ?)", (book_id, pub_id))
                                    except:
                                        pass

                                for tag_name in meta['tags'][:20]:
                                    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                                    row = cursor.fetchone()
                                    tag_id = row[0] if row else None
                                    if not tag_id:
                                        cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                                        tag_id = cursor.lastrowid
                                    cursor.execute("INSERT OR IGNORE INTO books_tags_link (book, tag) VALUES (?, ?)", (book_id, tag_id))

                                if meta['identifier']:
                                    cursor.execute("SELECT 1 FROM books_identifiers WHERE book = ?", (book_id,))
                                    if not cursor.fetchone():
                                        cursor.execute("INSERT INTO books_identifiers (book, type, val) VALUES (?, 'ISBN', ?)", (book_id, meta['identifier']))

                                if meta['language']:
                                    lang_code = meta['language'][:10]
                                    cursor.execute("SELECT id FROM languages WHERE lang_code = ?", (lang_code,))
                                    row = cursor.fetchone()
                                    lang_id = row[0] if row else None
                                    if not lang_id:
                                        cursor.execute("INSERT INTO languages (lang_code) VALUES (?)", (lang_code,))
                                        lang_id = cursor.lastrowid
                                    try:
                                        cursor.execute("INSERT OR IGNORE INTO books_languages_link (book, lang_code) VALUES (?, ?)", (book_id, lang_id))
                                    except:
                                        pass

                                if meta['description']:
                                    cursor.execute("INSERT INTO comments (book, text) VALUES (?, ?)", (book_id, meta['description'][:10000]))

                                if series_name:
                                    cursor.execute("SELECT id FROM series WHERE name = ?", (series_name,))
                                    row = cursor.fetchone()
                                    if row:
                                        series_id = row[0]
                                    else:
                                        cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (series_name, series_name))
                                        series_id = cursor.lastrowid
                                    cols = ['book', 'series'] + [c for c in series_link_cols if c not in ('id', 'book', 'series')]
                                    vals = [book_id, series_id]
                                    for c in cols[2:]:
                                        if c == 'series_index':
                                            vals.append(series_index)
                                        else:
                                            vals.append(0)
                                    placeholders = ', '.join(['?' for _ in cols])
                                    cursor.execute(f"INSERT INTO books_series_link ({', '.join(cols)}) VALUES ({placeholders})", vals)

                                conn.commit()
                                success_count += 1
                                series_info = f" [{series_name} #{series_index}]" if series_name else ""
                                author_info = f" by {epub_authors[0]}" if epub_authors and epub_authors[0] != 'Unknown' else ""
                                yield json.dumps({'type': 'log', 'message': f'✓ {epub_title}{author_info}{series_info}', 'level': 'success'}) + '\n'

                        except Exception as e:
                            if not use_calibre:
                                conn.rollback()
                            error_count += 1
                            yield json.dumps({'type': 'log', 'message': f'✗ {epub_file.name}: {str(e)}', 'level': 'error'}) + '\n'

                    if not use_calibre:
                        conn.close()

                    yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
                    if error_count > 0:
                        yield json.dumps({'type': 'error', 'message': f'Completed with errors: {success_count} succeeded, {error_count} failed'}) + '\n'
                    else:
                        yield json.dumps({'type': 'success', 'message': f'Sync completed! {success_count} books imported'}) + '\n'

                except Exception as e:
                    import traceback
                    yield json.dumps({'type': 'error', 'message': f'Sync failed: {str(e)}\n{traceback.format_exc()}'}) + '\n'

            except Exception as e:
                import traceback
                yield json.dumps({'type': 'error', 'message': f'Sync error: {str(e)}\n{traceback.format_exc()}'}) + '\n'

        return app.response_class(generate(), mimetype='application/json')

    @app.route('/api/comic/sync', methods=['POST'])
    def sync_comics():
        """Sync comic files (PDF, CBZ) to Calibre library"""
        def generate():
            try:
                import sqlite3
                import fitz

                if os.path.exists(CALIBRE_CONFIG_PATH):
                    with open(CALIBRE_CONFIG_PATH, 'r') as f:
                        config = json.load(f)
                else:
                    yield json.dumps({'type': 'error', 'message': 'Please configure Calibre settings first'}) + '\n'
                    return

                comic_folder = config.get('comic_folder', '/media/comic')
                calibre_library_path = config.get('calibre_library_path', '')

                if not comic_folder or not calibre_library_path:
                    yield json.dumps({'type': 'error', 'message': 'Please configure both comic folder and Calibre library path'}) + '\n'
                    return

                comic_path = Path(comic_folder)
                calibre_path = Path(calibre_library_path)

                if not comic_path.exists():
                    yield json.dumps({'type': 'error', 'message': 'Comic folder not found'}) + '\n'
                    return

                comic_extensions = {'.pdf', '.cbz', '.cbr', '.cb7'}
                chapters = []
                for ext in comic_extensions:
                    chapters.extend(comic_path.rglob(f"*{ext}"))

                total = len(chapters)
                if total == 0:
                    yield json.dumps({'type': 'error', 'message': 'No comic files found'}) + '\n'
                    return

                yield json.dumps({'type': 'log', 'message': f'Found {total} comic chapters', 'level': 'info'}) + '\n'

                if (calibre_path / 'books').exists() and (calibre_path / 'books').is_dir():
                    calibre_path = calibre_path / 'books'

                metadata_db = Path(calibre_library_path) / 'metadata.db'
                books_folder = calibre_path
                books_folder.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(metadata_db))
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                for (trigger,) in cursor.fetchall():
                    try:
                        cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                    except:
                        pass

                schema = """
                    CREATE TABLE IF NOT EXISTS languages (id INTEGER PRIMARY KEY, lang_code TEXT UNIQUE NOT NULL);
                    CREATE TABLE IF NOT EXISTS publishers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                    CREATE TABLE IF NOT EXISTS series (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sort TEXT);
                    CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
                    CREATE TABLE IF NOT EXISTS identifiers (id INTEGER PRIMARY KEY, type TEXT, val TEXT);
                    CREATE TABLE IF NOT EXISTS books_identifiers (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, type TEXT, val TEXT);
                    CREATE TABLE IF NOT EXISTS books_languages_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS books_tags_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS books_series_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, series INTEGER NOT NULL);
                """
                for stmt in schema.strip().split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            cursor.execute(stmt)
                        except:
                            pass

                success_count = 0
                error_count = 0

                cursor.execute("SELECT id FROM tags WHERE name = 'Comics'")
                row = cursor.fetchone()
                if row:
                    comics_tag_id = row[0]
                    cursor.execute("SELECT book FROM books_tags_link WHERE tag = ?", (comics_tag_id,))
                    old_book_ids = [b[0] for b in cursor.fetchall()]
                    if old_book_ids:
                        yield json.dumps({'type': 'log', 'message': f'Cleaning up {len(old_book_ids)} old entries...', 'level': 'info'}) + '\n'
                        cursor.execute("DELETE FROM books_tags_link WHERE tag = ?", (comics_tag_id,))
                        cursor.execute("DELETE FROM books_authors_link WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                        cursor.execute("DELETE FROM books_series_link WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                        cursor.execute("DELETE FROM data WHERE book IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                        cursor.execute("DELETE FROM books WHERE id IN (%s)" % ','.join('?' * len(old_book_ids)), old_book_ids)
                        for bid in old_book_ids:
                            old_dir = books_folder / str(bid)
                            if old_dir.exists():
                                shutil.rmtree(old_dir)

                cursor.execute("SELECT MAX(id) FROM books")
                max_book_id = cursor.fetchone()[0] or 0

                comics = {}
                for chapter_file in chapters:
                    comic_name = chapter_file.parent.name
                    original_name = chapter_file.name
                    file_format = chapter_file.suffix[1:].upper()
                    if comic_name not in comics:
                        comics[comic_name] = []
                    comics[comic_name].append((original_name, str(chapter_file), file_format))

                yield json.dumps({'type': 'log', 'message': f'Found {len(comics)} comic series', 'level': 'info'}) + '\n'

                for comic_name, chapter_list in sorted(comics.items()):
                    try:
                        safe_comic = re.sub(r'[<>:"/\\|?*]', '_', comic_name)

                        cursor.execute("SELECT id FROM series WHERE name = ?", (comic_name,))
                        row = cursor.fetchone()
                        series_id = row[0] if row else None
                        if not series_id:
                            cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (comic_name, comic_name))
                            series_id = cursor.lastrowid

                        def natural_sort_key(s):
                            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

                        chapter_list.sort(key=lambda x: natural_sort_key(x[0]))

                        for idx, (original_name, file_path, file_format) in enumerate(chapter_list):
                            max_book_id += 1
                            book_id = max_book_id

                            book_dir = books_folder / str(book_id)
                            book_dir.mkdir(exist_ok=True)

                            uuid_str = str(uuid.uuid4())
                            chapter_idx = idx + 1

                            cursor.execute('''
                                INSERT INTO books (id, title, sort, author_sort, series_index, path, uuid, has_cover, last_modified)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 0, '2000-01-01 00:00:00+00:00')
                            ''', (book_id, f"{comic_name} - {Path(original_name).stem}", f"{comic_name} - {Path(original_name).stem}", 'Unknown', chapter_idx, f"books/{book_id}", uuid_str))

                            cursor.execute("INSERT OR IGNORE INTO books_series_link (book, series) VALUES (?, ?)", (book_id, series_id))

                            cursor.execute("SELECT id FROM tags WHERE name = 'Comics'")
                            row = cursor.fetchone()
                            tag_id = row[0] if row else None
                            if not tag_id:
                                cursor.execute("INSERT INTO tags (name) VALUES ('Comics')")
                                tag_id = cursor.lastrowid
                            cursor.execute("INSERT OR IGNORE INTO books_tags_link (book, tag) VALUES (?, ?)", (book_id, tag_id))

                            cursor.execute("SELECT id FROM authors WHERE name = 'Unknown'")
                            row = cursor.fetchone()
                            author_id = row[0] if row else None
                            if not author_id:
                                cursor.execute("INSERT INTO authors (name, sort) VALUES ('Unknown', 'Unknown')")
                                author_id = cursor.lastrowid
                            cursor.execute("INSERT OR IGNORE INTO books_authors_link (book, author) VALUES (?, ?)", (book_id, author_id))

                            dest_file = book_dir / original_name
                            shutil.copy2(Path(file_path), dest_file)

                            cover_extracted = False
                            if file_format == 'CBZ':
                                try:
                                    with zipfile.ZipFile(Path(file_path), 'r') as zf:
                                        images = [f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                                        if images:
                                            first_img = sorted(images)[0]
                                            img_data = zf.read(first_img)
                                            cover_path = book_dir / 'cover.jpg'
                                            with open(cover_path, 'wb') as cf:
                                                cf.write(img_data)
                                            cover_extracted = True
                                except:
                                    pass
                            elif file_format == 'PDF':
                                try:
                                    doc = fitz.open(Path(file_path))
                                    if len(doc) > 0:
                                        page = doc[0]
                                        mat = fitz.Matrix(2, 2)
                                        pix = page.get_pixmap(matrix=mat)
                                        cover_path = book_dir / 'cover.jpg'
                                        pix.save(str(cover_path))
                                        cover_extracted = True
                                    doc.close()
                                except:
                                    pass

                            if cover_extracted:
                                cursor.execute('UPDATE books SET has_cover = 1 WHERE id = ?', (book_id,))

                            chapter_file = Path(file_path)
                            file_size = chapter_file.stat().st_size
                            db_name = chapter_file.stem

                            cursor.execute('''
                                INSERT INTO data (book, format, name, uncompressed_size)
                                VALUES (?, ?, ?, ?)
                            ''', (book_id, file_format, db_name, file_size))

                        success_count += 1
                        yield json.dumps({'type': 'log', 'message': f'✓ {comic_name} ({len(chapter_list)} chapters)', 'level': 'success'}) + '\n'

                    except Exception as e:
                        error_count += 1
                        yield json.dumps({'type': 'log', 'message': f'✗ {comic_name}: {str(e)}', 'level': 'error'}) + '\n'

                conn.commit()
                conn.close()

                for item in books_folder.iterdir():
                    if item.is_dir() and not any(item.iterdir()):
                        shutil.rmtree(item)

                yield json.dumps({'type': 'log', 'message': '', 'level': 'info'}) + '\n'
                if error_count > 0:
                    yield json.dumps({'type': 'error', 'message': f'Completed: {success_count} comics, {error_count} errors'}) + '\n'
                else:
                    yield json.dumps({'type': 'success', 'message': f'Sync completed! {success_count} comics imported'}) + '\n'

            except Exception as e:
                import traceback
                yield json.dumps({'type': 'error', 'message': f'Sync failed: {str(e)}\n{traceback.format_exc()}'}) + '\n'

        return app.response_class(generate(), mimetype='application/json')
