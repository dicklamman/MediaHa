# -*- coding: utf-8 -*-
"""Special API routes for conversion and text processing."""
import os
from flask import request, jsonify
from utils.epub_converter import convert_to_hk_traditional_chinese


def register_special_routes(app):
    """Register special route handlers."""

    @app.route('/convert', methods=['POST'])
    def convert():
        """Convert EPUB to HK Traditional Chinese"""
        file_name = request.json.get('file_name')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        media_dir = '/media'
        input_path = os.path.join(media_dir, file_name)
        if not os.path.exists(input_path):
            return jsonify({'error': 'File not found'}), 404

        output_path = convert_to_hk_traditional_chinese(input_path)
        return jsonify({'message': 'Conversion successful', 'output_file': output_path})

    @app.route('/api/o3ics/ruby', methods=['POST'])
    def o3ics_ruby():
        """Convert Japanese text to furigana ruby format"""
        text = request.json.get('text', '')
        if not text:
            return jsonify({'result': ''})
        try:
            import pykakasi
            import re

            text = re.sub(r'([?-?]+)([\u3040-\u309F\u30A0-\u30FF]+)\)', r'\1', text)

            print(f"After removing parens: {text[:100]}")

            if not re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
                 print(f"No Japanese chars found in text, returning original")
                 return jsonify({'result': text})

            print(f"Japanese text detected, processing with pykakasi")
            kks = pykakasi.kakasi()
            kks.setMode('H', 'H')
            kks.setMode('K', 'H')
            kks.setMode('J', 'H')
            result = []

            print(f"Processing text with pykakasi (first 100 chars): {text[:100]}")
            for line in text.split('\n'):
                line_res = []
                if not line.strip():
                    result.append(line)
                    continue
                try:
                    items = kks.convert(line)
                    print(f"Converted line '{line[:30]}...' got {len(items)} items")
                    for item in items:
                        orig = item['orig']
                        hira = item['hira']
                        if hira and orig != hira:
                            line_res.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
                        else:
                            line_res.append(orig)
                    print(f"Result for line: {''.join(line_res)[:50]}...")
                except Exception as e:
                    print(f"pykakasi conversion error for line: {line}, error: {e}")
                    line_res.append(line)
                result.append("".join(line_res))
            final_result = "\n".join(result)
            print(f"Final result (first 100 chars): {final_result[:100]}")
            return jsonify({'result': final_result})
        except ImportError:
            return jsonify({'result': text})
        except Exception as e:
            print(f"o3ics_ruby error: {e}")
            return jsonify({'result': text})
