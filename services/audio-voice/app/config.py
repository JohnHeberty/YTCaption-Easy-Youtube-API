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
        
        # ===== OPENVOICE =====
        'openvoice': {
            'model_path': os.getenv('OPENVOICE_MODEL_PATH', './models'),
            'device': os.getenv('OPENVOICE_DEVICE', 'cpu'),  # cpu ou cuda
            'default_model': os.getenv('OPENVOICE_DEFAULT_MODEL', 'base'),
            'preload_models': os.getenv('OPENVOICE_PRELOAD_MODELS', 'false').lower() == 'true',
            
            # Modelos
            'base_speaker_model': os.getenv('OPENVOICE_BASE_SPEAKER_MODEL', 'checkpoints/base_speakers/EN'),
            'converter_model': os.getenv('OPENVOICE_CONVERTER_MODEL', 'checkpoints/converter'),
            
            # Parâmetros de síntese
            'default_speed': float(os.getenv('OPENVOICE_DEFAULT_SPEED', '1.0')),
            'default_pitch': float(os.getenv('OPENVOICE_DEFAULT_PITCH', '1.0')),
            'sample_rate': int(os.getenv('OPENVOICE_SAMPLE_RATE', '24000')),
            
            # Voice cloning
            'min_clone_duration_sec': int(os.getenv('OPENVOICE_MIN_CLONE_DURATION_SEC', '5')),
            'max_clone_duration_sec': int(os.getenv('OPENVOICE_MAX_CLONE_DURATION_SEC', '60')),
            'clone_sample_rate': int(os.getenv('OPENVOICE_CLONE_SAMPLE_RATE', '24000')),
        },
        
        # ===== F5-TTS (pt-BR OPTIMIZED for GTX 1050 Ti) =====
        'f5tts': {
            # Modelo padrão
            'model': os.getenv('F5TTS_MODEL', 'F5-TTS'),
            
            # Device (cuda para GTX 1050 Ti)
            'device': os.getenv('F5TTS_DEVICE', 'cuda'),
            
            # Paths - MODELO PT-BR CUSTOMIZADO
            'hf_cache_dir': os.getenv('F5TTS_CACHE', '/app/models/f5tts'),
            'custom_model_dir': os.getenv('F5TTS_CUSTOM_MODEL_DIR', '/app/models/f5tts/pt-br'),
            'custom_model_file': os.getenv('F5TTS_CUSTOM_MODEL_FILE', 'model_last.safetensors'),
            
            # Otimizações VRAM (GTX 1050 Ti = 4GB)
            'nfe_step': int(os.getenv('F5TTS_NFE_STEP', '16')),  # REDUZIDO: 32->16 (economia VRAM)
            'target_rms': float(os.getenv('F5TTS_TARGET_RMS', '0.1')),
            'use_fp16': os.getenv('F5TTS_USE_FP16', 'true').lower() == 'true',  # FP16 ativa
            'max_batch_size': int(os.getenv('F5TTS_MAX_BATCH_SIZE', '1')),  # Batch=1 para VRAM baixa
            
            # Limites de texto/áudio (evitar OOM)
            'max_gen_length': int(os.getenv('F5TTS_MAX_GEN_LENGTH', '5000')),  # chars
            'max_ref_duration': int(os.getenv('F5TTS_MAX_REF_DURATION', '12')),  # segundos
            
            # Whisper para transcrição (SEMPRE CPU para economizar VRAM)
            'whisper_model': os.getenv('F5TTS_WHISPER_MODEL', 'openai/whisper-base'),  # base (mais leve)
            'whisper_device': os.getenv('F5TTS_WHISPER_DEVICE', 'cpu'),  # CPU por padrão
        },
        
        # ===== F5TTS PT-BR MODEL PATH =====
        'F5TTS_MODEL_PATH': os.path.join(
            os.getenv('F5TTS_CUSTOM_MODEL_DIR', '/app/models/f5tts/pt-br'),
            os.getenv('F5TTS_CUSTOM_MODEL_FILE', 'model_last.safetensors')
        ),
        
        # ===== XTTS (Coqui TTS - NEW DEFAULT) =====
        'xtts': {
            # Modelo padrão
            'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
            
            # Device (auto, cuda, cpu)
            'device': os.getenv('XTTS_DEVICE', None),  # None = auto-detect
            
            # Fallback para CPU se CUDA não disponível
            'fallback_to_cpu': os.getenv('XTTS_FALLBACK_CPU', 'true').lower() == 'true',
            
            # Parâmetros de síntese
            'temperature': float(os.getenv('XTTS_TEMPERATURE', '0.7')),
            'repetition_penalty': float(os.getenv('XTTS_REPETITION_PENALTY', '5.0')),
            'length_penalty': float(os.getenv('XTTS_LENGTH_PENALTY', '1.0')),
            'top_k': int(os.getenv('XTTS_TOP_K', '50')),
            'top_p': float(os.getenv('XTTS_TOP_P', '0.85')),
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
        
        # ===== TTS ENGINE SELECTION =====
        'use_xtts': os.getenv('USE_XTTS', 'true').lower() == 'true',  # True = XTTS (padrão), False = TTS_ENGINE var
        
        # ===== VOICE PRESETS =====
        'voice_presets': {
            'female_generic': {
                'speaker': 'default_female',
                'description': 'Voz feminina genérica',
                'languages': ['en', 'pt', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh']
            },
            'male_generic': {
                'speaker': 'default_male',
                'description': 'Voz masculina genérica',
                'languages': ['en', 'pt', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh']
            },
            'female_young': {
                'speaker': 'young_female',
                'description': 'Voz feminina jovem',
                'languages': ['en', 'pt', 'es', 'fr']
            },
            'male_deep': {
                'speaker': 'deep_male',
                'description': 'Voz masculina grave',
                'languages': ['en', 'pt', 'es']
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
