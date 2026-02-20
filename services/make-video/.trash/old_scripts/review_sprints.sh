#!/bin/bash
# Script de Revisão de Todas as Sprints

cd /root/YTCaption-Easy-Youtube-API/services/make-video
source .venv/bin/activate

echo "🔍 REVISÃO DE TODAS AS SPRINTS (0-9)"
echo "================================================"
echo ""

# Sprint 0-1: Setup & Models
echo "📦 Sprint 0-1: Setup & Models"
pytest tests/test_00_setup_validation.py tests/test_setup_validation.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 2: Exceptions + Circuit Breaker
echo "⚡ Sprint 2: Exceptions + Circuit Breaker"
pytest tests/unit/shared/test_exceptions.py tests/unit/infrastructure/test_circuit_breaker.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 3: Redis
echo "🔴 Sprint 3: Redis Store"
pytest tests/integration/infrastructure/test_redis_store.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 4: OCR/Detector
echo "👁️  Sprint 4: OCR/Detector"
pytest tests/unit/video_processing/test_ocr_detector.py tests/unit/video_processing/test_frame_extractor.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 5: Builder
echo "🏗️  Sprint 5: Builder"
pytest tests/unit/subtitle_processing/test_ass_generator.py tests/unit/subtitle_processing/test_classifier.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 6: Subtitle Processing
echo "📝 Sprint 6: Subtitle Processing"
pytest tests/integration/subtitle_processing/ -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 7: Services
echo "🔧 Sprint 7: Services"
pytest tests/unit/services/test_video_status_store.py tests/unit/utils/test_audio_utils.py tests/unit/utils/test_timeout_utils.py tests/unit/utils/test_vad.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 8: Pipeline
echo "🔄 Sprint 8: Pipeline"
pytest tests/integration/pipeline/test_video_pipeline.py -q --tb=no 2>&1 | tail -2
echo ""

# Sprint 9: Domain
echo "🏛️  Sprint 9: Domain"
pytest tests/unit/domain/ tests/integration/domain/ -q --tb=no 2>&1 | tail -2
echo ""

echo "================================================"
echo "✅ REVISÃO COMPLETA FINALIZADA"
