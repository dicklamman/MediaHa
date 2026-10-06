# -*- coding: utf-8 -*-
"""Photo/image routes with resizing and random selection."""
import os
import random
import base64
from io import BytesIO
from flask import send_file, request, session, jsonify

MEDIA_DIR = '/media'

# Password for photo endpoints
PHOTO_PASSWORD = 'lamleunghome'

# Image extensions to look for
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def _verify_photo_password():
    """
    Verify the photo password from query param or Basic Auth.
    Returns (authorized: bool, error_response: tuple or None)
    """
    # Check session
    if session.get('photo_authenticated'):
        return True, None
    
    # Check query parameter: ?password=lamleunghome
    provided_password = request.args.get('password', '')
    if provided_password == PHOTO_PASSWORD:
        session['photo_authenticated'] = True
        return True, None
    
    # Check Basic Auth header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Basic '):
        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode('utf-8')
            if ':' in decoded:
                _, password = decoded.split(':', 1)
                if password == PHOTO_PASSWORD:
                    session['photo_authenticated'] = True
                    return True, None
        except Exception:
            pass
    
    return False, (jsonify({'error': 'Unauthorized - password required'}), 401)


def register_photo_routes(app):
    """Register photo-related routes."""

    @app.route('/photo/<path:filename>', methods=['GET'])
    def serve_photo(filename):
        """
        Serve a photo from media/photo with optional resizing.
        
        URL format: /photo/photo.jpg&w=480&h=320&quality=85
        Query params: w (width), h (height), quality (1-100)
        Password: ?password=lamleunghome
        
        The filename can optionally include query-like params after & for convenience.
        """
        # Verify password
        authorized, error = _verify_photo_password()
        if not authorized:
            return error
        # Parse optional parameters from the path (filename may contain &params)
        path_parts = filename.split('&')
        actual_filename = path_parts[0]
        
        # Also check for query parameters
        width = request.args.get('w', type=int)
        height = request.args.get('h', type=int)
        quality = request.args.get('quality', default=85, type=int)
        
        # Parse params from path if present (format: filename.jpg&w=480&h=320&quality=85)
        for part in path_parts[1:]:
            if part.startswith('w='):
                try:
                    width = int(part[2:])
                except ValueError:
                    pass
            elif part.startswith('h='):
                try:
                    height = int(part[2:])
                except ValueError:
                    pass
            elif part.startswith('quality='):
                try:
                    quality = int(part[8:])
                except ValueError:
                    pass
        
        # Sanitize quality
        quality = max(1, min(100, quality))
        
        file_path = os.path.abspath(os.path.join(MEDIA_DIR, actual_filename))
        
        # Security check - prevent directory traversal
        if not file_path.startswith(os.path.abspath(MEDIA_DIR)):
            return {'error': 'Access denied'}, 403
        
        if not os.path.exists(file_path):
            return {'error': 'File not found'}, 404
        
        if not os.path.isfile(file_path):
            return {'error': 'Not a file'}, 400
        
        # Return resized image if dimensions specified
        if width or height:
            return _resize_image(file_path, width, height, quality)
        
        # Return original file
        return send_file(file_path)

    @app.route('/photo/random', methods=['GET'])
    @app.route('/photo/random.jpg', methods=['GET'])
    def random_photo():
        """
        Randomly select and serve a photo from media/photo folder.
        
        Optional query params:
        - w: width for resizing
        - h: height for resizing  
        - quality: JPEG quality (1-100, default 85)
        - password: photo access password
        
        Examples:
        - /photo/random?w=480&h=320&password=lamleunghome
        - /photo/random.jpg?quality=75&password=lamleunghome
        """
        # Verify password
        authorized, error = _verify_photo_password()
        if not authorized:
            return error
        
        # First try media/photo folder
        photo_folder = os.path.join(MEDIA_DIR, 'photo')
        
        if not os.path.isdir(photo_folder):
            # Fall back to media root
            photo_folder = MEDIA_DIR
        
        width = request.args.get('w', type=int)
        height = request.args.get('h', type=int)
        quality = request.args.get('quality', default=85, type=int)
        quality = max(1, min(100, quality))
        
        # Collect all image files recursively
        images = []
        for root, dirs, files in os.walk(photo_folder):
            for f in files:
                if f.lower().endswith(IMAGE_EXTENSIONS):
                    images.append(os.path.join(root, f))
        
        if not images:
            return {'error': 'No images found'}, 404
        
        # Pick a random image
        selected = random.choice(images)
        
        # Return resized if dimensions specified
        if width or height:
            return _resize_image(selected, width, height, quality)
        
        return send_file(selected)


def _resize_image(file_path, width, height, quality=85):
    """
    Resize an image and return it.
    
    Uses Pillow (PIL) for image processing.
    """
    try:
        from PIL import Image
        
        with Image.open(file_path) as img:
            # Convert RGBA to RGB if needed for JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Calculate new dimensions
            original_width, original_height = img.size
            
            if width and height:
                # Both dimensions specified - resize to fit
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            elif width:
                # Only width specified
                ratio = width / original_width
                new_height = int(original_height * ratio)
                img = img.resize((width, new_height), Image.Resampling.LANCZOS)
            elif height:
                # Only height specified
                ratio = height / original_height
                new_width = int(original_width * ratio)
                img = img.resize((new_width, height), Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='image/jpeg',
                as_attachment=False,
                download_name=None
            )
    
    except ImportError:
        # Pillow not installed - return original
        return send_file(file_path)
    except Exception:
        # On error, return original file
        return send_file(file_path)
