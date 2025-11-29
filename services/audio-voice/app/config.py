import os

def get_settings():
    """
    Retorna todas as configurações do serviço a partir de variáveis de ambiente.
    Configurações organizadas por categoria para fácil manutenção.
    """
    return {
        # ===== APLICAÇÃO =====
        'app_name': os.getenv('APP_NAME', 'Audio Voice Service'),
        'version': os.getenv('VERSION', '1.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8004')),
        
        # ===== REDIS =====
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/4'),
        
        # ===== CELERY =====
        'celery': {
            'broker_url': os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/4')),
            'result_backend': os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/4')),
            'task_serializer': os.getenv('CELERY_TASK_SERIALIZER', 'json'),
            'result_serializer': os.getenv('CELERY_RESULT_SERIALIZER', 'json'),
            'accept_content': os.getenv('CELERY_ACCEPT_CONTENT', 'json').split(','),
            'timezone': os.getenv('CELERY_TIMEZONE', 'UTC'),
            'enable_utc': os.getenv('CELERY_ENABLE_UTC', 'true').lower() == 'true',
            'task_track_started': os.getenv('CELERY_TASK_TRACK_STARTED', 'true').lower() == 'true',
            'task_time_limit': int(os.getenv('CELERY_TASK_TIME_LIMIT', '900')),  # 15 min
            'task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '840')),  # 14 min
            'worker_prefetch_multiplier': int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1')),
            'worker_max_tasks_per_child': int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', '50')),
        },
        
        # ===== CACHE =====
        'cache_ttl_hours': int(os.getenv('CACHE_TTL_HOURS', '24')),
        'cache_cleanup_interval_minutes': int(os.getenv('CACHE_CLEANUP_INTERVAL_MINUTES', '30')),
        'cache_max_size_mb': int(os.getenv('CACHE_MAX_SIZE_MB', '2048')),
        'voice_profile_ttl_days': int(os.getenv('VOICE_PROFILE_TTL_DAYS', '30')),
        
        # ===== PROCESSAMENTO - LIMITES =====
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', '100')),
        'max_duration_minutes': int(os.getenv('MAX_DURATION_MINUTES', '10')),
        'max_text_length': int(os.getenv('MAX_TEXT_LENGTH', '10000')),
        'max_concurrent_jobs': int(os.getenv('MAX_CONCURRENT_JOBS', '3')),
        'job_timeout_minutes': int(os.getenv('JOB_TIMEOUT_MINUTES', '15')),
        
        # ===== LOW VRAM MODE =====
        # Quando ativo, carrega/descarrega modelos automaticamente para economizar VRAM
        'low_vram_mode': os.getenv('LOW_VRAM', 'false').lower() == 'true',
        
        # ===== TTS ENGINES (SPRINT 4: Multi-Engine Support) =====
        'tts_engine_default': os.getenv('TTS_ENGINE_DEFAULT', 'xtts'),  # Default engine
        'tts_engines': {
            # XTTS Configuration (default/stable)
            'xtts': {
                'enabled': os.getenv('XTTS_ENABLED', 'true').lower() == 'true',
                'device': os.getenv('XTTS_DEVICE', None),  # None = auto-detect
                'fallback_to_cpu': os.getenv('XTTS_FALLBACK_CPU', 'true').lower() == 'true',
                'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
            },
            # F5-TTS / E2-TTS Configuration (experimental/high-quality)
            'f5tts': {
                'enabled': os.getenv('F5TTS_ENABLED', 'true').lower() == 'true',
                'device': os.getenv('F5TTS_DEVICE', 'cuda'),  # cuda ou cpu
                'fallback_to_cpu': os.getenv('F5TTS_FALLBACK_CPU', 'true').lower() == 'true',
                'model_name': os.getenv('F5TTS_MODEL', 'firstpixel/F5-TTS-pt-br'),  # PT-BR otimizado por padrão
                
                # Whisper (auto-transcription)
                'whisper_model': os.getenv('F5TTS_WHISPER_MODEL', 'base'),
                'whisper_device': os.getenv('F5TTS_WHISPER_DEVICE', 'cpu'),
                
                # Quality Profiles (NFE Steps)
                'nfe_step_fast': int(os.getenv('F5TTS_NFE_STEP_FAST', '24')),
                'nfe_step_balanced': int(os.getenv('F5TTS_NFE_STEP_BALANCED', '40')),
                'nfe_step_ultra': int(os.getenv('F5TTS_NFE_STEP_ULTRA', '64')),
                
                # Synthesis Parameters
                'cfg_strength': float(os.getenv('F5TTS_CFG_STRENGTH', '2.2')),
                'sway_sampling_coef': float(os.getenv('F5TTS_SWAY_SAMPLING_COEF', '0.3')),
                'speed': float(os.getenv('F5TTS_SPEED', '0.80')),
                
                # Text Processing - Chunking inteligente
                'chunk_by_punctuation': os.getenv('F5TTS_CHUNK_BY_PUNCTUATION', 'true').lower() == 'true',
                'max_chunk_chars': int(os.getenv('F5TTS_MAX_CHUNK_CHARS', '200')),
                'cross_fade_duration': float(os.getenv('F5TTS_CROSS_FADE_DURATION', '0.05')),
                
                # DSP Post-Processing
                'denoise_strength': float(os.getenv('F5TTS_DENOISE_STRENGTH', '0.85')),
                'deessing_freq': int(os.getenv('F5TTS_DEESSING_FREQ', '7000')),
                'highpass_freq': int(os.getenv('F5TTS_HIGHPASS_FREQ', '50')),
                'lowpass_freq': int(os.getenv('F5TTS_LOWPASS_FREQ', '12000')),
                
                # Audio Constraints
                'sample_rate': int(os.getenv('F5TTS_SAMPLE_RATE', '24000')),
                'min_ref_duration': int(os.getenv('F5TTS_MIN_REF_DURATION', '3')),
                'max_ref_duration': int(os.getenv('F5TTS_MAX_REF_DURATION', '30')),
                'max_text_length': int(os.getenv('F5TTS_MAX_TEXT_LENGTH', '10000')),
            }
        },
        
        # ===== XTTS (Coqui TTS - NEW DEFAULT) =====
        'xtts': {
            # Modelo padrão
            'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
            
            # Device (auto, cuda, cpu)
            'device': os.getenv('XTTS_DEVICE', None),  # None = auto-detect
            
            # Fallback para CPU se CUDA não disponível
            'fallback_to_cpu': os.getenv('XTTS_FALLBACK_CPU', 'true').lower() == 'true',
            
            # Parâmetros de síntese
            'temperature': float(os.getenv('XTTS_TEMPERATURE', '0.8')),
            'repetition_penalty': float(os.getenv('XTTS_REPETITION_PENALTY', '1.3')),
            'length_penalty': float(os.getenv('XTTS_LENGTH_PENALTY', '1.2')),
            'top_k': int(os.getenv('XTTS_TOP_K', '70')),
            'top_p': float(os.getenv('XTTS_TOP_P', '0.93')),
            'speed': float(os.getenv('XTTS_SPEED', '1.0')),
            
            # Text splitting para textos longos
            'enable_text_splitting': os.getenv('XTTS_TEXT_SPLITTING', 'true').lower() == 'true',
            
            # Sample rate (XTTS v2 = 24kHz)
            'sample_rate': int(os.getenv('XTTS_SAMPLE_RATE', '24000')),
            
            # Limites
            'max_text_length': int(os.getenv('XTTS_MAX_TEXT_LENGTH', '5000')),
            'min_ref_duration': int(os.getenv('XTTS_MIN_REF_DURATION', '3')),  # segundos
            'max_ref_duration': int(os.getenv('XTTS_MAX_REF_DURATION', '30')),  # segundos
        },
        
        # ===== RVC (Voice Conversion) =====
        'rvc': {
            # Device (auto, cuda, cpu)
            'device': os.getenv('RVC_DEVICE', 'cpu'),  # Default CPU (economiza VRAM)
            
            # Fallback para CPU se CUDA não disponível
            'fallback_to_cpu': os.getenv('RVC_FALLBACK_TO_CPU', 'true').lower() == 'true',
            
            # Diretório dos modelos RVC
            'models_dir': os.getenv('RVC_MODELS_DIR', './models/rvc'),
            
            # Parâmetros padrão de conversão
            'pitch': int(os.getenv('RVC_PITCH', '0')),  # -12 a +12 semitons
            'filter_radius': int(os.getenv('RVC_FILTER_RADIUS', '3')),
            'index_rate': float(os.getenv('RVC_INDEX_RATE', '0.75')),
            'rms_mix_rate': float(os.getenv('RVC_RMS_MIX_RATE', '0.25')),
            'protect': float(os.getenv('RVC_PROTECT', '0.33')),
        },
        
        # ===== RESILIÊNCIA =====
        'resilience': {
            'max_retries': int(os.getenv('MAX_RETRIES', '3')),
            'retry_delay_seconds': int(os.getenv('RETRY_DELAY_SECONDS', '5')),
            'circuit_breaker_threshold': int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', '5')),
            'circuit_breaker_timeout': int(os.getenv('CIRCUIT_BREAKER_TIMEOUT', '60')),
            'task_timeout_seconds': int(os.getenv('TASK_TIMEOUT_SECONDS', '300')),  # 5min
        },
        
        # ===== VOICE PRESETS =====
        'voice_presets': {
            'female_generic': {
                'speaker': 'default_female',
                'description': 'Voz feminina genérica',
                'languages': ['en', 'pt', 'pt-BR', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh']
            },
            'male_generic': {
                'speaker': 'default_male',
                'description': 'Voz masculina genérica',
                'languages': ['en', 'pt', 'pt-BR', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh']
            },
            'female_young': {
                'speaker': 'young_female',
                'description': 'Voz feminina jovem',
                'languages': ['en', 'pt', 'pt-BR', 'es', 'fr']
            },
            'male_deep': {
                'speaker': 'deep_male',
                'description': 'Voz masculina grave',
                'languages': ['en', 'pt', 'pt-BR', 'es']
            },
            'female_warm': {
                'speaker': 'warm_female',
                'description': 'Voz feminina mais natural, calorosa',
                'languages': ['pt', 'pt-BR', 'en']
            },
            'male_warm': {
                'speaker': 'warm_male',
                'description': 'Voz masculina mais natural, calorosa',
                'languages': ['pt', 'pt-BR', 'en']
            },
            'female_soft': {
                'speaker': 'soft_female',
                'description': 'Voz feminina suave, naturalidade máxima',
                'languages': ['pt', 'pt-BR', 'en']
            },
            'male_soft': {
                'speaker': 'soft_male',
                'description': 'Voz masculina suave, naturalidade máxima',
                'languages': ['pt', 'pt-BR', 'en']
            }
        },
        
        # ===== IDIOMAS SUPORTADOS =====
        'supported_languages': [
            'en', 'en-US', 'en-GB',  # Inglês
            'pt', 'pt-BR', 'pt-PT',  # Português
            'es', 'es-ES', 'es-MX',  # Espanhol
            'fr', 'fr-FR',           # Francês
            'de', 'de-DE',           # Alemão
            'it', 'it-IT',           # Italiano
            'ja', 'ja-JP',           # Japonês
            'ko', 'ko-KR',           # Coreano
            'zh', 'zh-CN', 'zh-TW',  # Chinês
            'ru', 'ru-RU',           # Russo
            'ar', 'ar-SA',           # Árabe
            'hi', 'hi-IN',           # Hindi
        ],
        
        # ===== AUDIO PROCESSING =====
        'audio': {
            'output_format': os.getenv('AUDIO_OUTPUT_FORMAT', 'wav'),
            'output_sample_rate': int(os.getenv('AUDIO_OUTPUT_SAMPLE_RATE', '24000')),
            'output_bitrate': os.getenv('AUDIO_OUTPUT_BITRATE', '128k'),
            'normalize_audio': os.getenv('AUDIO_NORMALIZE', 'true').lower() == 'true',
        },
        
        # ===== FFMPEG =====
        'ffmpeg': {
            'threads': int(os.getenv('FFMPEG_THREADS', '0')),
            'preset': os.getenv('FFMPEG_PRESET', 'medium'),
            'audio_codec': os.getenv('FFMPEG_AUDIO_CODEC', 'pcm_s16le'),
        },
        
        # ===== DIRETÓRIOS =====
        'upload_dir': os.getenv('UPLOAD_DIR', './uploads'),
        'processed_dir': os.getenv('PROCESSED_DIR', './processed'),
        'temp_dir': os.getenv('TEMP_DIR', './temp'),
        'voice_profiles_dir': os.getenv('VOICE_PROFILES_DIR', './voice_profiles'),
        'models_dir': os.getenv('MODELS_DIR', './models'),
        'log_dir': os.getenv('LOG_DIR', './logs'),
        
        # ===== LOGGING =====
        'log_level': os.getenv('LOG_LEVEL', 'DEBUG'),  # DEBUG para auditoria detalhada
        'log_format': os.getenv('LOG_FORMAT', 'json'),
        'log_rotation': os.getenv('LOG_ROTATION', '1 day'),
        'log_retention': os.getenv('LOG_RETENTION', '30 days')
    }


def get_supported_languages():
    """Retorna lista de idiomas suportados"""
    settings = get_settings()
    return settings['supported_languages']


def is_language_supported(language: str) -> bool:
    """Verifica se idioma é suportado"""
    supported = get_supported_languages()
    
    # Normaliza código de idioma (aceita 'en' e 'en-US')
    lang_code = language.lower().split('-')[0] if '-' in language else language.lower()
    
    # Verifica se código completo ou base está na lista
    return language.lower() in [l.lower() for l in supported] or \
           lang_code in [l.lower().split('-')[0] for l in supported]


def get_voice_presets():
    """Retorna vozes genéricas pré-configuradas"""
    settings = get_settings()
    return settings['voice_presets']


def is_voice_preset_valid(preset: str) -> bool:
    """Verifica se preset de voz existe"""
    presets = get_voice_presets()
    return preset in presets
