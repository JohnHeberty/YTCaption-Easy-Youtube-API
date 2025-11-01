import os

def get_settings():
    return {
        'app_name': os.getenv('APP_NAME', 'Audio Normalization Service'),
        'version': os.getenv('VERSION', '2.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8001')),
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'cache_ttl_hours': int(os.getenv('CACHE__TTL_HOURS', '24')),
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', '100')),
        'upload_dir': os.getenv('UPLOAD_DIR', './uploads'),
        'processed_dir': os.getenv('PROCESSED_DIR', './processed'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'security': {
            'rate_limit_requests': int(os.getenv('SECURITY__RATE_LIMIT_REQUESTS', '5000')),
            'rate_limit_window': int(os.getenv('SECURITY__RATE_LIMIT_WINDOW', '60')),
            'enable_file_validation': os.getenv('SECURITY__ENABLE_FILE_CONTENT_VALIDATION', 'true').lower() == 'true',
            'validate_audio_headers': os.getenv('SECURITY__VALIDATE_AUDIO_HEADERS', 'true').lower() == 'true'
        }
    }
