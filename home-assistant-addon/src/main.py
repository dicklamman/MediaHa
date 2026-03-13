from flask import Flask, request, jsonify, send_from_directory
import os
from utils.epub_converter import convert_to_hk_traditional_chinese

app = Flask(__name__)

MEDIA_DIR = '/media'

@app.route('/')
def index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), 'index.html')

@app.route('/<path:filename>')
def serve_ui(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'ui'), filename)

@app.route('/api/files', methods=['GET'])
def list_files():
    sub_dir = request.args.get('dir', '')
    target_dir = os.path.abspath(os.path.join(MEDIA_DIR, sub_dir))

    # Security: Ensure we don't traverse outside MEDIA_DIR
    if not target_dir.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(target_dir):
        return jsonify([])

    items = []
    for item in os.listdir(target_dir):
        full_path = os.path.join(target_dir, item)
        rel_path = os.path.relpath(full_path, MEDIA_DIR)

        # Windows compatibility for rel_path
        rel_path = rel_path.replace('\\\\', '/')

        if os.path.isdir(full_path):
            items.append({'name': item, 'type': 'folder', 'path': rel_path})
        elif item.lower().endswith(('.epub', '.mp3', '.lrc', '.jpg', '.jpeg', '.png')):
            items.append({'name': item, 'type': 'file', 'path': rel_path})

    # Sort folders first, then files
    items.sort(key=lambda x: (0 if x['type'] == 'folder' else 1, x['name'].lower()))
    return jsonify(items)

@app.route('/api/download', methods=['GET'])
def download_file():
    file_name = request.args.get('file_name')
    if not file_name:
        return jsonify({'error': 'No file name provided'}), 400

    file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))
    if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename)

@app.route('/api/rename', methods=['POST'])
def rename_item():
    data = request.json
    old_rel_path = data.get('old_path')
    new_name = data.get('new_name')

    if not old_rel_path or not new_name:
        return jsonify({'error': 'Missing parameters'}), 400

    old_abs_path = os.path.abspath(os.path.join(MEDIA_DIR, old_rel_path))
    if not old_abs_path.startswith(os.path.abspath(MEDIA_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(old_abs_path):
        return jsonify({'error': 'File or folder not found'}), 404

    # Calculate new absolute path
    parent_dir = os.path.dirname(old_abs_path)
    new_abs_path = os.path.join(parent_dir, new_name)

    try:
        os.rename(old_abs_path, new_abs_path)
        return jsonify({'message': 'Renamed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
