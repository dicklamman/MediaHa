import sqlite3
import os
import shutil
import uuid
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Generator, Optional, Callable
from xml.etree import ElementTree
import json

class CalibreDBSync:
    """Sync EPUB files to Calibre library using calibredb or direct database access"""
    
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
        
        # Try to find calibredb
        self.calibredb_path = None
        for path in ['/usr/bin/calibredb', '/usr/local/bin/calibredb', 
                     '/opt/calibre/bin/calibredb', '/Applications/calibre.app/Contents/MacOS/calibredb']:
            if os.path.exists(path):
                self.calibredb_path = path
                break
        
        if not self.calibredb_path:
            import shutil as sh
            self.calibredb_path = sh.which('calibredb')
    
    def clear_library(self, log_func: Callable[[str], None]) -> None:
        """Clear all books from metadata.db and books folder"""
        
        # Step 1: Clear books folder
        log_func("Clearing books folder...")
        if self.books_folder.exists():
            try:
                for item in self.books_folder.iterdir():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    except Exception as e:
                        log_func(f"Warning: Could not remove {item.name}: {e}")
                log_func("Cleared books folder")
            except Exception as e:
                log_func(f"Error clearing books folder: {e}")
        
        # Step 2: Clear metadata.db
        log_func("Clearing metadata.db...")
        if self.metadata_db.exists():
            try:
                conn = sqlite3.connect(str(self.metadata_db))
                cursor = conn.cursor()
                
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                log_func(f"Found tables: {tables}")
                
                # Delete all data from tables in correct order (respecting foreign keys)
                tables_to_clear = [
                    'comments',
                    'books_series_link',
                    'books_authors_link',
                    'books_languages_link',
                    'books_tags_link',
                    'books_publishers_link',
                    'books_identifiers',
                    'custom_columns_books',
                    'data',
                    'authors',
                    'series',
                    'tags',
                    'languages',
                    'publishers',
                    'custom_columns',
                    'books'
                ]
                
                for table in tables_to_clear:
                    if table in tables:
                        try:
                            cursor.execute(f"DELETE FROM {table}")
                            log_func(f"Cleared table: {table}")
                        except Exception as e:
                            log_func(f"Warning: Could not clear {table}: {e}")
                
                try:
                    cursor.execute("DELETE FROM sqlite_sequence")
                except:
                    pass
                
                conn.commit()
                conn.close()
                
                # Vacuum to shrink the database
                log_func("Vacuuming database...")
                conn = sqlite3.connect(str(self.metadata_db))
                conn.execute("VACUUM")
                conn.close()
                
                log_func("metadata.db cleared and vacuumed")
                
            except Exception as e:
                log_func(f"Error clearing metadata.db: {e}")
        else:
            log_func("metadata.db not found, will create new one")
            self._create_empty_db()
    
    def _create_empty_db(self):
        """Create an empty Calibre database with proper schema"""
        conn = sqlite3.connect(str(self.metadata_db))
        cursor = conn.cursor()
        
        # Create tables matching Calibre's schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                sort TEXT,
                author_sort TEXT,
                series_index REAL DEFAULT 1.0,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                series TEXT,
                author_sort_alias TEXT GENERATED ALWAYS AS (
                    CASE 
                        WHEN INSTR(name, ',') > 0 THEN 
                            TRIM(SUBSTR(name, INSTR(name, ',') + 1)) || ' ' || TRIM(SUBSTR(name, 1, INSTR(name, ',') - 1))
                        ELSE name
                    END
                ) VIRTUAL
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
        if not name or name.strip() == '':
            name = 'Unknown'
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM authors WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        # Create author sort: "Last, First" format
        author_sort = name
        if ',' not in name:
            parts = name.split()
            if len(parts) > 1:
                author_sort = f"{parts[-1]}, {' '.join(parts[:-1])}"
        cursor.execute("INSERT INTO authors (name, sort) VALUES (?, ?)", (name, author_sort))
        return cursor.lastrowid
    
    def _get_or_create_series(self, conn: sqlite3.Connection, name: str) -> Optional[int]:
        """Get series ID or create if not exists"""
        if not name or name.strip() == '':
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
            return parts[-2]
        elif len(parts) == 2:
            return parts[0]
        return ''
    
    def _extract_title_from_path(self, rel_path: Path) -> str:
        """Extract book title from file path"""
        return rel_path.stem
    
    def _extract_series_index(self, title: str) -> float:
        """Extract series index from book title"""
        # Try to find volume/chapter number
        patterns = [
            r'[第卷]?\s*(\d+)',  # Chinese: 第01卷 or 卷01 or 01
            r'[vV]ol\.?\s*(\d+)',  # Vol. 1
            r'[Ee][Pp]?\s*\.?\s*(\d+)',  # Ep. 1 or E1
            r'\s+(\d+)$',  # Ends with number
            r'[_\s-]+(\d+)',  # Separated
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return float(match.group(1))
        
        return 1.0
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        if len(name) > 100:
            name = name[:100]
        return name
    
    def import_with_calibredb(self, log_func: Callable[[str], None], 
                             progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[int, int, List[str]]:
        """Import using calibredb command-line tool"""
        if not self.calibredb_path:
            return 0, 0, ["calibredb not found in PATH"]
        
        epub_files = list(self.epub_folder.rglob("*.epub"))
        total = len(epub_files)
        
        if total == 0:
            return 0, 0, ["No EPUB files found"]
        
        log_func(f"Using calibredb: {self.calibredb_path}")
        log_func(f"Found {total} EPUB files to import")
        
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, epub_file in enumerate(epub_files, 1):
            try:
                if progress_callback:
                    progress_callback(idx, total, str(epub_file.relative_to(self.epub_folder)))
                
                rel_path = epub_file.relative_to(self.epub_folder)
                series_name = self._extract_series_from_path(rel_path)
                
                log_func(f"[{idx}/{total}] Importing: {rel_path}")
                
                # Build calibredb command
                cmd = [
                    self.calibredb_path,
                    'add',
                    str(epub_file),
                    '--library-path', str(self.calibre_path)
                ]
                
                if series_name:
                    cmd.extend(['--series', series_name])
                    series_index = self._extract_series_index(rel_path.stem)
                    cmd.extend(['--series-index', str(series_index)])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    success_count += 1
                    log_func(f"  ✓ {rel_path}" + (f" [Series: {series_name}]" if series_name else ""))
                else:
                    error_count += 1
                    error_msg = f"Error importing {rel_path}: {result.stderr}"
                    errors.append(error_msg)
                    log_func(f"  ✗ {error_msg}")
                    
            except subprocess.TimeoutExpired:
                error_count += 1
                error_msg = f"Timeout: {epub_file.name}"
                errors.append(error_msg)
                log_func(f"  ✗ {error_msg}")
            except Exception as e:
                error_count += 1
                error_msg = f"Error: {epub_file.name}: {str(e)}"
                errors.append(error_msg)
                log_func(f"  ✗ {error_msg}")
        
        log_func("")
        log_func(f"Import complete: {success_count} succeeded, {error_count} failed")
        
        return success_count, error_count, errors
    
    def import_epubs_direct(self, log_func: Callable[[str], None],
                          progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[int, int, List[str]]:
        """Import EPUBs directly into database without calibredb"""
        epub_files = list(self.epub_folder.rglob("*.epub"))
        total = len(epub_files)
        
        if total == 0:
            return 0, 0, ["No EPUB files found"]
        
        log_func(f"Using direct database import")
        log_func(f"Found {total} EPUB files to import")
        
        self._ensure_books_folder()
        
        if not self.metadata_db.exists():
            log_func("Creating new metadata.db...")
            self._create_empty_db()
        
        conn = sqlite3.connect(str(self.metadata_db))
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, epub_file in enumerate(epub_files, 1):
            try:
                if progress_callback:
                    progress_callback(idx, total, str(epub_file.relative_to(self.epub_folder)))
                
                rel_path = epub_file.relative_to(self.epub_folder)
                book_title = self._extract_title_from_path(rel_path)
                series_name = self._extract_series_from_path(rel_path)
                series_index = self._extract_series_index(book_title)
                
                log_func(f"[{idx}/{total}] Importing: {book_title}")
                
                book_id = self._get_next_book_id(conn)
                
                book_dir = self.books_folder / str(book_id)
                book_dir.mkdir(exist_ok=True)
                
                safe_title = self._sanitize_filename(book_title)
                epub_dest = book_dir / f"{safe_title}.epub"
                shutil.copy2(epub_file, epub_dest)
                
                file_size = epub_dest.stat().st_size
                book_uuid = str(uuid.uuid4())
                
                # Insert book
                cursor.execute('''
                    INSERT INTO books (id, title, sort, series, series_index, last_modified)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    book_id,
                    book_title,
                    book_title,
                    series_name if series_name else None,
                    series_index
                ))
                
                # Insert data record
                cursor.execute('''
                    INSERT INTO data (book, format, name, uncompressed_size)
                    VALUES (?, ?, ?, ?)
                ''', (book_id, 'EPUB', f"{safe_title}.epub", file_size))
                
                # Create default author
                author_id = self._get_or_create_author(conn, 'Unknown')
                cursor.execute('''
                    INSERT INTO books_authors_link (book, author, ord)
                    VALUES (?, ?, ?)
                ''', (book_id, author_id, 0))
                
                # Link to series if exists
                if series_name:
                    series_id = self._get_or_create_series(conn, series_name)
                    if series_id:
                        cursor.execute('''
                            INSERT INTO books_series_link (book, series, series_index)
                            VALUES (?, ?, ?)
                        ''', (book_id, series_id, series_index))
                
                conn.commit()
                
                success_count += 1
                log_func(f"  ✓ {book_title}" + (f" [Series: {series_name} #{series_index}]" if series_name else ""))
                
            except Exception as e:
                error_count += 1
                error_msg = f"Error importing {epub_file.name}: {str(e)}"
                errors.append(error_msg)
                log_func(f"  ✗ {error_msg}")
                conn.rollback()
        
        conn.close()
        
        log_func("")
        log_func(f"Import complete: {success_count} succeeded, {error_count} failed")
        
        return success_count, error_count, errors


def sync_calibre_library(calibre_path: str, epub_folder: str, 
                       log_func: Callable[[str], None],
                       progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Generator[str, None, dict]:
    """
    Main sync function - tries calibredb first, falls back to direct DB
    
    Args:
        calibre_path: Path to Calibre library folder
        epub_folder: Path to EPUB source folder
        log_func: Function to call for logging messages
        progress_callback: Optional callback for progress updates (current, total, filename)
    
    Yields:
        Log messages as JSON strings
    
    Returns:
        Dict with sync results
    """
    sync = CalibreDBSync(calibre_path, epub_folder)
    
    # Clear existing library
    log_func("=" * 50)
    log_func("STEP 1: Clearing existing library")
    log_func("=" * 50)
    
    sync.clear_library(log_func)
    
    # Try calibredb first, fall back to direct DB
    log_func("")
    log_func("=" * 50)
    log_func("STEP 2: Importing EPUB files")
    log_func("=" * 50)
    
    if sync.calibredb_path:
        log_func(f"Found calibredb at: {sync.calibredb_path}")
        success, errors_count, error_list = sync.import_with_calibredb(log_func, progress_callback)
    else:
        log_func("calibredb not found, using direct database import")
        success, errors_count, error_list = sync.import_epubs_direct(log_func, progress_callback)
    
    return {
        'success': success,
        'errors': errors_count,
        'error_messages': error_list
    }
