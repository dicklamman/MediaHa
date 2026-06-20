# -*- coding: utf-8 -*-
"""EPUB operation routes."""
import os
import json
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
            from bs4 import BeautifulSoup

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
                'subjects': []
            }

            # Get Dublin Core metadata
            for item in book.get_metadata('DC'):
                key = item[0].lower()
                value = item[1]
                if key in metadata and value:
                    if key == 'subjects':
                        if isinstance(value, list):
                            metadata[key] = value
                        else:
                            metadata[key].append(value) if isinstance(metadata[key], list) else value
                    else:
                        metadata[key] = str(value) if value else ''

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
