# -*- coding: utf-8 -*-
"""EPUB operation routes."""
import os
import json
import base64
from flask import jsonify, request, send_from_directory

MEDIA_DIR = '/media'


def register_epub_routes(app):
    """Register EPUB operation routes."""

    @app.route('/api/epub/metadata', methods=['GET'])
    def get_epub_metadata():
        """Get EPUB metadata."""
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        try:
            from ebooklib import epub

            book = epub.read_epub(file_path)
            metadata = {
                'title': '',
                'creator': '',
                'publisher': '',
                'language': '',
                'description': '',
                'identifier': '',
                'date': '',
                'rights': '',
                'subjects': [],
                'cover': None
            }

            # Get metadata - try multiple approaches for compatibility
            metadata_items = {}
            
            # Try book.get_metadata() with namespace first (most compatible)
            try:
                dc_metadata = book.get_metadata('http://purl.org/dc/elements/1.1/')
                for item in dc_metadata:
                    if len(item) >= 2:
                        name = item[0].lower()
                        values = item[1]
                        metadata_items[name] = values
            except:
                pass
            
            # Also try book.metadata dict
            if hasattr(book, 'metadata') and book.metadata:
                try:
                    dc_items = book.metadata.get('DC', {})
                    for key, values in dc_items.items():
                        lower_key = key.lower()
                        if lower_key not in metadata_items:
                            metadata_items[lower_key] = values
                except:
                    pass
            
            # Map to our metadata dict (case-insensitive)
            for key, value in metadata_items.items():
                lower_key = key.lower()
                if lower_key in ['title', 'creator', 'publisher', 'language', 'description', 'identifier', 'date', 'rights']:
                    if isinstance(value, list):
                        metadata[lower_key] = str(value[0]) if value else ''
                    else:
                        metadata[lower_key] = str(value)
                elif lower_key == 'subjects':
                    if isinstance(value, list):
                        for v in value:
                            metadata['subjects'].append(str(v))
                    else:
                        metadata['subjects'].append(str(value))

            # Get cover image - use item ID/name check instead of ITEM_TYPE
            for item in book.get_items():
                item_name = item.get_name().lower()
                # Look for cover images by name pattern
                if 'cover' in item_name and (item_name.endswith('.jpg') or item_name.endswith('.jpeg') or item_name.endswith('.png')):
                    metadata['cover'] = base64.b64encode(item.get_content()).decode('utf-8')
                    break

            return jsonify(metadata)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/epub/metadata', methods=['POST'])
    def update_epub_metadata():
        """Update EPUB metadata."""
        data = request.json
        file_name = data.get('file_name')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return jsonify({'error': 'Access denied'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        try:
            from ebooklib import epub
            from ebooklib.epub import Namespace

            book = epub.read_epub(file_path)

            # Update metadata
            title = data.get('title')
            creator = data.get('creator')
            publisher = data.get('publisher')
            language = data.get('language')
            description = data.get('description')
            identifier = data.get('identifier')
            date = data.get('date')
            rights = data.get('rights')
            subjects = data.get('subjects', [])

            if title is not None:
                book.set_metadata('DC', 'title', title)
            if creator is not None:
                book.set_metadata('DC', 'creator', creator)
            if publisher is not None:
                book.set_metadata('DC', 'publisher', publisher)
            if language is not None:
                book.set_metadata('DC', 'language', language)
            if description is not None:
                book.set_metadata('DC', 'description', description)
            if identifier is not None:
                book.set_metadata('DC', 'identifier', identifier)
            if date is not None:
                book.set_metadata('DC', 'date', date)
            if rights is not None:
                book.set_metadata('DC', 'rights', rights)
            if subjects is not None:
                # Clear existing subjects and add new ones
                book.set_metadata('DC', 'subject', '')
                for subject in subjects:
                    if subject:
                        book.set_metadata('DC', 'subject', subject)

            # Write back to file
            epub.write_epub(file_path, book)

            return jsonify({'message': 'Metadata updated successfully'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
