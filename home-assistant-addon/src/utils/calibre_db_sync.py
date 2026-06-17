import sqlite3
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple, Generator
import json

class CalibreDBSync:
    """Direct Calibre metadata.db sync - replaces HTTP API approach"""
    
    def __init__(self, calibre_path: str, epub_folder: str):
        """
        Initialize Calibre DB sync
        
        Args:
            calibre_path: Path to Calibre library folder (contains metadata.db and books/ folder)
            epub_folder: Path to EPUB source folder
        """
        self.calibre_path = Path(calibre_path)
        self.metadata_db = self.calibre_path / 'metadata.db'
        self.books_folder = self.calibre_path / 'books'
        self.epub_folder = Path(epub_folder)
    
    def clear_library(self, yield_func) -> Generator[str, None, None]:
        """Clear all books from metadata.db and books folder"""
        
        # Step 1: Clear books folder
        yield from yield_func("Clearing books folder...")
        if self.books_folder.exists():
            try:
                # Remove all book directories (they are named by book ID)
                for item in self.books_folder.iterdir():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    except Exception as e:
                        yield from yield_func(f"Warning: Could not remove {item.name}: {e}")
                yield from yield_func(f"Cleared books folder")
            except Exception as e:
                yield from yield_func(f"Error clearing books folder: {e}")
        
        # Step 2: Clear metadata.db
        yield from yield_func("Clearing metadata.db...")
        if self.metadata_db.exists():
            try:
                conn = sqlite3.connect(str(self.metadata_db))
                cursor = conn.cursor()
                
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                yield from yield_func(f"Found tables: {tables}")
                
                # Delete all data from all tables (in correct order for foreign keys)
                # First delete from tables that reference others
                tables_to_clear = [
                    'comments',           # References books
                    'books_series_link',  # References books and series
                    'books_authors_link', # References books and authors
                    'books_languages_link',
                    'books_tags_link',
                    'books_publishers_link',
                    'books_identifiers',
                    'custom_columns_books',
                    'authors',            # Can clear after links
                    'series',
                    'tags',
                    'languages',
                    'publishers',
                    'custom_columns',
                    'data',               # References books
                    'books'               # Main table last
                ]
                
                for table in tables_to_clear:
                    if table in tables:
                        try:
                            cursor.execute(f"DELETE FROM {table}")
                            yield from yield_func(f"Cleared table: {table}")
                        except Exception as e:
                            yield from yield_func(f"Warning: Could not clear {table}: {e}")
                
                # Reset auto-increment counters
                try:
                    cursor.execute("DELETE FROM sqlite_sequence")
                except:
                    pass
                
                conn.commit()
                conn.close()
                
                # Vacuum to shrink the database
                yield from yield_func("Vacuuming database...")
                conn = sqlite3.connect(str(self.metadata_db))
                conn.execute("VACUUM")
                conn.close()
                
                yield from yield_func("metadata.db cleared and vacuumed")
                
            except Exception as e:
                yield from yield_func(f"Error clearing metadata.db: {e}")
        else:
            yield from yield_func("metadata.db not found, will create new one")
            # Create empty database with schema
            self._create_empty_db()
    
    def _create_empty_db(self):
        """Create an empty Calibre database with proper schema"""
        conn = sqlite3.connect(str(self.metadata_db))
        cursor = conn.cursor()
        
        # Create core tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                sort TEXT,
                author_sort TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pubdate DATETIME,
                series_index REAL DEFAULT 1.0,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                rating REAL,
                flags INTEGER DEFAULT 0,
                uuid TEXT,
                path TEXT,
                has_cover INTEGER DEFAULT 0,
                description TEXT,
                series TEXT,
                author DISPLAY_ENTITY
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                sort TEXT,
                link TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                sort TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publishers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                sort TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS languages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lang_code TEXT UNIQUE NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                text TEXT,
                order_index INTEGER DEFAULT 0,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                format TEXT,
                name TEXT,
                uncompressed_size INTEGER,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_authors_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                author INTEGER,
                ord INTEGER DEFAULT 0,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (author) REFERENCES authors(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_series_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                series INTEGER,
                series_index REAL DEFAULT 1.0,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (series) REFERENCES series(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_tags_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                tag INTEGER,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (tag) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_publishers_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                publisher INTEGER,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (publisher) REFERENCES publishers(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                type TEXT,
                val TEXT,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books_languages_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                lang_code INTEGER,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (lang_code) REFERENCES languages(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT UNIQUE NOT NULL,
                name TEXT,
                datatype TEXT,
                editable INTEGER DEFAULT 1,
                display TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_columns_books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book INTEGER,
                value TEXT,
                FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_books_title ON books(title)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_books_series ON books(series)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_authors_name ON authors(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_series_name ON series(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_tags_name ON tags(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_publishers_name ON publishers(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_data_book ON data(book)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_books_authors_link_book ON books_authors_link(book)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_books_series_link_book ON books_series_link(book)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_books_tags_link_book ON books_tags_link(book)')
        
        conn.commit()
        conn.close()
    
    def _ensure_books_folder(self):
        """Ensure books folder exists"""
        self.books_folder.mkdir(parents=True, exist_ok=True)
    
    def _get_next_book_id(self, conn: sqlite3.Connection) -> int:
        """Get next available book ID"""
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM books")
        max_id = cursor.fetchone()[0]
        return (max_id or 0) + 1
    
    def _get_or_create_author(self, conn: sqlite3.Connection, name: str) -> int:
        """Get author ID or create if not exists"""
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM authors WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", (name, name))
        return cursor.lastrowid
    
    def _get_or_create_series(self, conn: sqlite3.Connection, name: str) -> int:
        """Get series ID or create if not exists"""
        if not name:
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM series WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (name, name))
        return cursor.lastrowid
    
    def _extract_series_from_path(self, rel_path: Path) -> str:
        """Extract series name from EPUB file path"""
        parts = rel_path.parts
        if len(parts) >= 3:
            # category/series/book.epub -> series is 2nd to last
            return parts[-2]
        elif len(parts) == 2:
            # series/book.epub -> series is first
            return parts[0]
        return ''
    
    def _extract_title_from_path(self, rel_path: Path) -> str:
        """Extract book title from file path"""
        return rel_path.stem  # Remove extension
    
    def _extract_series_index(self, title: str) -> float:
        """Extract series index from book title (e.g., 'Book Name 01' -> 1)"""
        import re
        # Try to find volume/chapter number
        patterns = [
            r'[第卷]?\s*(\d+)',  # Chinese: 第01卷 or 卷01 or 01
            r'[vV]ol\.?\s*(\d+)',  # Vol. 1
            r'[Ee][Pp]?\s*\.?\s*(\d+)',  # Ep. 1 or E1
            r'\s+(\d+)$',  # Ends with number: Book Name 01
            r'[_\s-]+(\d+)',  # Separated by underscore/space/dash before extension
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return float(match.group(1))
        
        return 1.0  # Default
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        import re
        # Remove/replace invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Limit length
        if len(name) > 100:
            name = name[:100]
        return name
    
    def import_epubs(self, yield_func, progress_callback=None) -> Tuple[int, int, List[str]]:
        """
        Import all EPUB files from source folder into Calibre database
        
        Returns:
            Tuple of (success_count, error_count, error_messages)
        """
        # Get all EPUB files
        epub_files = list(self.epub_folder.rglob("*.epub"))
        total = len(epub_files)
        
        if total == 0:
            return 0, 0, ["No EPUB files found"]
        
        yield from yield_func(f"Found {total} EPUB files to import")
        
        # Ensure books folder exists
        self._ensure_books_folder()
        
        # Ensure database exists
        if not self.metadata_db.exists():
            yield from yield_func("Creating new metadata.db...")
            self._create_empty_db()
        
        # Connect to database
        conn = sqlite3.connect(str(self.metadata_db))
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        success_count = 0
        error_count = 0
        errors = []
        imported_books = []
        
        # Track authors and series for logging
        authors_cache = {}
        series_cache = {}
        
        for idx, epub_file in enumerate(epub_files, 1):
            try:
                # Calculate progress
                if progress_callback:
                    progress_callback(idx, total, str(epub_file.relative_to(self.epub_folder)))
                
                rel_path = epub_file.relative_to(self.epub_folder)
                book_title = self._extract_title_from_path(rel_path)
                series_name = self._extract_series_from_path(rel_path)
                series_index = self._extract_series_index(book_title)
                
                yield from yield_func(f"[{idx}/{total}] Importing: {book_title}")
                
                # Get next book ID
                book_id = self._get_next_book_id(conn)
                
                # Create book directory
                book_dir = self.books_folder / str(book_id)
                book_dir.mkdir(exist_ok=True)
                
                # Copy EPUB file
                safe_title = self._sanitize_filename(book_title)
                epub_dest = book_dir / f"{safe_title}.epub"
                shutil.copy2(epub_file, epub_dest)
                
                # Get file size
                file_size = epub_dest.stat().st_size
                
                # Generate UUID
                book_uuid = str(uuid.uuid4())
                
                # Insert book record
                cursor.execute('''
                    INSERT INTO books (
                        id, title, sort, author_sort, series, series_index,
                        timestamp, pubdate, last_modified, uuid, path,
                        has_cover, flags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book_id,
                    book_title,
                    book_title,  # sort
                    '',  # author_sort
                    series_name if series_name else None,
                    series_index,
                    'now',
                    None,
                    'now',
                    book_uuid,
                    str(book_id),  # path relative to books folder
                    0,  # has_cover
                    0   # flags
                ))
                
                # Insert data record (the actual file)
                cursor.execute('''
                    INSERT INTO data (book, format, name, uncompressed_size)
                    VALUES (?, ?, ?, ?)
                ''', (book_id, 'EPUB', f"{safe_title}.epub", file_size))
                
                # Create default author if not already created
                if 'Unknown' not in authors_cache:
                    cursor.execute("SELECT id FROM authors WHERE name = ?", ('Unknown',))
                    row = cursor.fetchone()
                    if row:
                        authors_cache['Unknown'] = row[0]
                    else:
                        cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", ('Unknown', 'Unknown'))
                        authors_cache['Unknown'] = cursor.lastrowid
                
                # Link to default author
                cursor.execute('''
                    INSERT INTO books_authors_link (book, author, ord)
                    VALUES (?, ?, ?)
                ''', (book_id, authors_cache['Unknown'], 0))
                
                # Link to series if exists
                if series_name:
                    if series_name not in series_cache:
                        cursor.execute("SELECT id FROM series WHERE name = ?", (series_name,))
                        row = cursor.fetchone()
                        if row:
                            series_cache[series_name] = row[0]
                        else:
                            cursor.execute("INSERT INTO series (name, sort) VALUES (?, ?)", (series_name, series_name))
                            series_cache[series_name] = cursor.lastrowid
                    
                    cursor.execute('''
                        INSERT INTO books_series_link (book, series, series_index)
                        VALUES (?, ?, ?)
                    ''', (book_id, series_cache[series_name], series_index))
                
                # Commit after each book
                conn.commit()
                
                success_count += 1
                imported_books.append({
                    'id': book_id,
                    'title': book_title,
                    'series': series_name,
                    'series_index': series_index
                })
                
                yield from yield_func(f"  ✓ {book_title}" + (f" [Series: {series_name} #{series_index}]" if series_name else ""))
                
            except Exception as e:
                error_count += 1
                error_msg = f"Error importing {epub_file.name}: {str(e)}"
                errors.append(error_msg)
                yield from yield_func(f"  ✗ {error_msg}")
        
        conn.close()
        
        yield from yield_func("")
        yield from yield_func(f"Import complete: {success_count} succeeded, {error_count} failed")
        
        if errors:
            yield from yield_func(f"Errors: {len(errors)}")
        
        return success_count, error_count, errors


def sync_calibre_library(calibre_path: str, epub_folder: str, yield_func, progress_callback=None) -> dict:
    """
    Main sync function
    
    Args:
        calibre_path: Path to Calibre library folder
        epub_folder: Path to EPUB source folder
        yield_func: Generator function to yield log messages
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with sync results
    """
    sync = CalibreDBSync(calibre_path, epub_folder)
    
    # Clear existing library
    yield from yield_func("=" * 50)
    yield from yield_func("STEP 1: Clearing existing library")
    yield from yield_func("=" * 50)
    
    for msg in sync.clear_library(yield_func):
        pass  # Already yielded
    
    # Import EPUBs
    yield from yield_func("")
    yield from yield_func("=" * 50)
    yield from yield_func("STEP 2: Importing EPUB files")
    yield from yield_func("=" * 50)
    
    success, errors_count, errors = sync.import_epubs(yield_func, progress_callback)
    
    return {
        'success': success,
        'errors': errors_count,
        'error_messages': errors
    }
