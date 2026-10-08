# Routes package
from .auth_routes import register_auth_routes
from .web_routes import register_web_routes
from .file_routes import register_file_routes
from .audio_routes import register_audio_routes
from .config_routes import register_config_routes
from .special_routes import register_special_routes
from .subtitle_routes import register_subtitle_routes
from .calibre_routes import register_calibre_routes

__all__ = [
    'register_auth_routes',
    'register_web_routes',
    'register_file_routes',
    'register_audio_routes',
    'register_config_routes',
    'register_special_routes',
    'register_subtitle_routes',
    'register_calibre_routes',
]
