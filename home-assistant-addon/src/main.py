from flask import Flask, request, jsonify, send_from_directory
import os
from utils.epub_converter import convert_to_hk_traditional_chinese

app = Flask(__name__)

MEDIA_DIR = '/media/eBook'

@app.route('/')
def index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), 'index.html')

@app.route('/<path:filename>')
def serve_ui(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), filename)

@app.route('/convert', methods=['POST'])
def convert():
    file_name = request.json.get('file_name')
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    input_path = os.path.join(MEDIA_DIR, file_name)
    if not os.path.exists(input_path):
        return jsonify({'error': 'File not found'}), 404

    output_path = convert_to_hk_traditional_chinese(input_path)
    return jsonify({'message': 'Conversion successful', 'output_file': output_path})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)