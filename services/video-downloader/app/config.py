import os

def get_settings():
    return {
        'app_name': os.getenv('APP_NAME', 'Video Downloader Service'),
        'version': os.getenv('VERSION', '2.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8001')),
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'cache_ttl_hours': int(os.getenv('CACHE_TTL_HOURS', '24')),
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', '10240')),
        'cache_dir': os.getenv('CACHE_DIR', './cache'),
        'downloads_dir': os.getenv('DOWNLOADS_DIR', './downloads'),
        'temp_dir': os.getenv('TEMP_DIR', './temp'),
        'log_dir': os.getenv('LOG_DIR', './logs'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'max_concurrent_downloads': int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '2')),
        'default_quality': os.getenv('DEFAULT_QUALITY', 'best'),
        'job_processing_timeout_seconds': int(os.getenv('JOB_PROCESSING_TIMEOUT_SECONDS', '1800'))
    }
