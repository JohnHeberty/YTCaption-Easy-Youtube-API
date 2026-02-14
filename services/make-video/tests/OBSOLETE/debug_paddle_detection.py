#!/usr/bin/env python3
"""
Debug: Analisar detalhes da detecção do PaddleOCR
==================================================

Mostra frame-by-frame o que está acontecendo com a detecção.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
import json


def debug_detection(video_path: str, video_name: str):
    """Debug detalhado de um vídeo"""
    print(f"\n{'='*70}")
    print(f"🔍 DEBUG: {video_name}")
    print(f"{'='*70}")
    
    detector = SubtitleDetectorV2(roi_mode='multi')
    
    # Detectar com detalhes
    has_subs, confidence, text, metadata = detector.detect_in_video_with_multi_roi(video_path)
    
    print(f"\n📊 Resultado:")
    print(f"   Has subs: {has_subs}")
    print(f"   Confidence: {confidence:.2%}")
    print(f"   Text: {text[:100] if text else '(vazio)'}")
    
    print(f"\n🎯 Metadata:")
    print(f"   Resolution: {metadata.get('resolution')}")
    print(f"   Duration: {metadata.get('duration'):.1f}s")
    print(f"   Frames extracted: {metadata.get('frames_extracted')}")
    print(f"   ROI mode: {metadata.get('roi_mode')}")
    print(f"   ROI used: {metadata.get('roi_used')}")
    print(f"   ROIs checked: {metadata.get('rois_checked', [])}")
    
    # Se tem roi_metadata, mostrar detalhes
    roi_meta = metadata.get('roi_metadata', {})
    if roi_meta:
        print(f"\n📋 ROI Details:")
        print(f"   Frames analyzed: {roi_meta.get('frames_analyzed')}")
        print(f"   Frames with text: {roi_meta.get('frames_with_text')}")
        print(f"   Detection ratio: {roi_meta.get('detection_ratio', 0):.2%}")
        
        # Mostrar detecções por frame
        detections = roi_meta.get('detections', [])
        if detections:
            print(f"\n🎬 Frame-by-frame:")
            for det in detections:
                frame_idx = det.get('frame_idx', '?')
                has_text = det.get('has_text', False)
                conf = det.get('confidence', 0)
                texts = det.get('texts', [])
                
                status = "✅" if has_text else "❌"
                print(f"      Frame {frame_idx}: {status} ({conf:.1%}) - {len(texts)} texts")
                if texts:
                    for txt in texts[:2]:  # Mostrar primeiros 2 textos
                        print(f"         → {txt[:50]}")
    
    print(f"{'='*70}\n")
    return has_subs, confidence


if __name__ == "__main__":
    # Testar os 7 vídeos COM legendas
    storage = Path(__file__).parent.parent / "storage" / "validation" / "sample_OK"
    
    videos = [
        "5Bc-aOe4pC4.mp4",
        "IyZ-sdLQATM.mp4",
        "KWC32RL-wgc.mp4",
        "XGrMrVFuc-E.mp4",
        "bH1hczbzm9U.mp4",
        "fRf_Uh39hVQ.mp4",
        "kVTr1c9IL8w.mp4"
    ]
    
    print("\n" + "="*70)
    print("🔍 DEBUG DETALHADO - Vídeos COM Legendas")
    print("="*70)
    
    results = {}
    for video in videos:
        video_path = storage / video
        if video_path.exists():
            has_subs, conf = debug_detection(str(video_path), video)
            results[video] = {"has_subs": has_subs, "confidence": conf}
    
    print("\n" + "="*70)
    print("📊 RESUMO:")
    print("="*70)
    for video, res in results.items():
        status = "✅" if res['has_subs'] else "❌"
        print(f"{status} {video}: {res['has_subs']} ({res['confidence']:.1%})")
    
    detected = sum(1 for r in results.values() if r['has_subs'])
    print(f"\n📈 Detectados: {detected}/{len(results)} ({detected/len(results)*100:.1f}%)")
