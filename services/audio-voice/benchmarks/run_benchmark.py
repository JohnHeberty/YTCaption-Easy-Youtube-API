"""
Benchmark Runner - XTTS vs F5-TTS PT-BR

Gera áudios com ambos engines usando dataset PT-BR e coleta métricas.

Usage:
    python run_benchmark.py --all
    python run_benchmark.py --engine xtts
    python run_benchmark.py --engine f5tts --device cuda:0
"""

import argparse
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import csv
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engines.xtts_engine import XttsEngine
from app.engines.f5tts_engine import F5TtsEngine
from app.models import VoiceProfile, QualityProfile

import psutil
import soundfile as sf


class BenchmarkRunner:
    """Executa benchmark comparativo entre engines"""
    
    def __init__(
        self,
        dataset_path: str = "dataset_ptbr.json",
        output_dir: str = "results",
        device: Optional[str] = None
    ):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.device = device
        
        # Criar diretórios
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "xtts_outputs").mkdir(exist_ok=True)
        (self.output_dir / "f5tts_outputs").mkdir(exist_ok=True)
        
        # Carregar dataset
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            self.dataset = json.load(f)
        
        # Engines (lazy loading)
        self._xtts_engine = None
        self._f5tts_engine = None
        
        # Métricas
        self.metrics: List[Dict] = []
        
        print(f"\n{'='*80}")
        print(f"🚀 BENCHMARK RUNNER - XTTS vs F5-TTS")
        print(f"{'='*80}\n")
        print(f"Dataset: {self.dataset_path}")
        print(f"Textos: {len(self.dataset['texts'])}")
        print(f"Vozes: {len(self.dataset['voices'])}")
        print(f"Output: {self.output_dir}")
        print(f"Device: {self.device or 'auto-detect'}")
        print()
    
    @property
    def xtts_engine(self):
        """Lazy load XTTS engine"""
        if self._xtts_engine is None:
            print("⏳ Carregando XTTS engine...")
            self._xtts_engine = XttsEngine(
                device=self.device,
                fallback_to_cpu=True
            )
            print("✅ XTTS engine carregado\n")
        return self._xtts_engine
    
    @property
    def f5tts_engine(self):
        """Lazy load F5-TTS engine"""
        if self._f5tts_engine is None:
            print("⏳ Carregando F5-TTS engine...")
            self._f5tts_engine = F5TtsEngine(
                device=self.device,
                fallback_to_cpu=True
            )
            print("✅ F5-TTS engine carregado\n")
        return self._f5tts_engine
    
    async def run_benchmark_xtts(
        self,
        texts: Optional[List[str]] = None,
        voices: Optional[List[str]] = None
    ):
        """Roda benchmark para XTTS"""
        print(f"\n{'='*80}")
        print("🔹 BENCHMARK XTTS")
        print(f"{'='*80}\n")
        
        texts = texts or [t['id'] for t in self.dataset['texts']]
        voices = voices or [v['id'] for v in self.dataset['voices']]
        
        # Se não tem vozes reais, usar apenas primeira combinação
        if not any((self.output_dir.parent / v['audio_path']).exists() 
                   for v in self.dataset['voices']):
            print("⚠️  Vozes de referência não encontradas, usando síntese básica")
            voices = [None]  # Síntese sem voice cloning
        
        total = len(texts) * len(voices) if voices[0] else len(texts)
        current = 0
        
        for text_id in texts:
            text_data = next(t for t in self.dataset['texts'] if t['id'] == text_id)
            
            for voice_id in voices:
                current += 1
                
                # Preparar voice profile (se disponível)
                voice_profile = None
                voice_name = "no_voice"
                
                if voice_id:
                    voice_data = next(v for v in self.dataset['voices'] if v['id'] == voice_id)
                    voice_path = self.output_dir.parent / voice_data['audio_path']
                    
                    if voice_path.exists():
                        voice_profile = await self.xtts_engine.clone_voice(
                            audio_path=str(voice_path),
                            language="pt-BR",
                            voice_name=voice_id
                        )
                        voice_name = voice_id
                
                # Gerar áudio
                print(f"[{current}/{total}] XTTS: {text_id} + {voice_name}")
                
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                try:
                    audio_bytes, duration = await self.xtts_engine.generate_dubbing(
                        text=text_data['text'],
                        language="pt-BR",
                        voice_profile=voice_profile,
                        quality_profile=QualityProfile.BALANCED
                    )
                    
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    
                    # Salvar áudio
                    output_filename = f"{text_id}_{voice_name}_xtts.wav"
                    output_path = self.output_dir / "xtts_outputs" / output_filename
                    
                    with open(output_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    # Métricas
                    processing_time = end_time - start_time
                    rtf = processing_time / duration if duration > 0 else 0
                    memory_delta = end_memory - start_memory
                    
                    self.metrics.append({
                        'engine': 'xtts',
                        'text_id': text_id,
                        'voice_id': voice_name,
                        'text_category': text_data['category'],
                        'text_length': len(text_data['text']),
                        'audio_duration': duration,
                        'processing_time': processing_time,
                        'rtf': rtf,
                        'memory_delta_mb': memory_delta,
                        'audio_size_kb': len(audio_bytes) / 1024,
                        'output_path': str(output_path),
                        'status': 'success'
                    })
                    
                    print(f"   ✅ Duration: {duration:.2f}s | RTF: {rtf:.2f}x | Memory: {memory_delta:.1f}MB")
                
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    self.metrics.append({
                        'engine': 'xtts',
                        'text_id': text_id,
                        'voice_id': voice_name,
                        'status': 'error',
                        'error': str(e)
                    })
        
        print(f"\n✅ XTTS benchmark completo: {len([m for m in self.metrics if m['engine']=='xtts' and m['status']=='success'])} sucessos\n")
    
    async def run_benchmark_f5tts(
        self,
        texts: Optional[List[str]] = None,
        voices: Optional[List[str]] = None
    ):
        """Roda benchmark para F5-TTS"""
        print(f"\n{'='*80}")
        print("🔹 BENCHMARK F5-TTS")
        print(f"{'='*80}\n")
        
        texts = texts or [t['id'] for t in self.dataset['texts']]
        voices = voices or [v['id'] for v in self.dataset['voices']]
        
        # Se não tem vozes reais, usar apenas primeira combinação
        if not any((self.output_dir.parent / v['audio_path']).exists() 
                   for v in self.dataset['voices']):
            print("⚠️  Vozes de referência não encontradas, usando síntese básica")
            voices = [None]
        
        total = len(texts) * len(voices) if voices[0] else len(texts)
        current = 0
        
        for text_id in texts:
            text_data = next(t for t in self.dataset['texts'] if t['id'] == text_id)
            
            for voice_id in voices:
                current += 1
                
                voice_profile = None
                voice_name = "no_voice"
                
                if voice_id:
                    voice_data = next(v for v in self.dataset['voices'] if v['id'] == voice_id)
                    voice_path = self.output_dir.parent / voice_data['audio_path']
                    
                    if voice_path.exists():
                        voice_profile = await self.f5tts_engine.clone_voice(
                            audio_path=str(voice_path),
                            language="pt-BR",
                            voice_name=voice_id,
                            ref_text=voice_data.get('ref_text')
                        )
                        voice_name = voice_id
                
                print(f"[{current}/{total}] F5-TTS: {text_id} + {voice_name}")
                
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                try:
                    audio_bytes, duration = await self.f5tts_engine.generate_dubbing(
                        text=text_data['text'],
                        language="pt-BR",
                        voice_profile=voice_profile,
                        quality_profile=QualityProfile.BALANCED
                    )
                    
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    
                    output_filename = f"{text_id}_{voice_name}_f5tts.wav"
                    output_path = self.output_dir / "f5tts_outputs" / output_filename
                    
                    with open(output_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    processing_time = end_time - start_time
                    rtf = processing_time / duration if duration > 0 else 0
                    memory_delta = end_memory - start_memory
                    
                    self.metrics.append({
                        'engine': 'f5tts',
                        'text_id': text_id,
                        'voice_id': voice_name,
                        'text_category': text_data['category'],
                        'text_length': len(text_data['text']),
                        'audio_duration': duration,
                        'processing_time': processing_time,
                        'rtf': rtf,
                        'memory_delta_mb': memory_delta,
                        'audio_size_kb': len(audio_bytes) / 1024,
                        'output_path': str(output_path),
                        'status': 'success'
                    })
                    
                    print(f"   ✅ Duration: {duration:.2f}s | RTF: {rtf:.2f}x | Memory: {memory_delta:.1f}MB")
                
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    self.metrics.append({
                        'engine': 'f5tts',
                        'text_id': text_id,
                        'voice_id': voice_name,
                        'status': 'error',
                        'error': str(e)
                    })
        
        print(f"\n✅ F5-TTS benchmark completo: {len([m for m in self.metrics if m['engine']=='f5tts' and m['status']=='success'])} sucessos\n")
    
    def save_metrics(self):
        """Salva métricas em CSV"""
        metrics_path = self.output_dir / "metrics.csv"
        
        if not self.metrics:
            print("⚠️  Nenhuma métrica para salvar")
            return
        
        # Filtrar apenas sucessos
        success_metrics = [m for m in self.metrics if m.get('status') == 'success']
        
        if not success_metrics:
            print("⚠️  Nenhuma métrica de sucesso para salvar")
            return
        
        with open(metrics_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=success_metrics[0].keys())
            writer.writeheader()
            writer.writerows(success_metrics)
        
        print(f"✅ Métricas salvas em: {metrics_path}")
        print(f"   Total de registros: {len(success_metrics)}")
    
    def print_summary(self):
        """Imprime resumo das métricas"""
        if not self.metrics:
            return
        
        success_metrics = [m for m in self.metrics if m.get('status') == 'success']
        
        xtts_metrics = [m for m in success_metrics if m['engine'] == 'xtts']
        f5tts_metrics = [m for m in success_metrics if m['engine'] == 'f5tts']
        
        print(f"\n{'='*80}")
        print("📊 RESUMO BENCHMARK")
        print(f"{'='*80}\n")
        
        if xtts_metrics:
            avg_rtf_xtts = sum(m['rtf'] for m in xtts_metrics) / len(xtts_metrics)
            avg_memory_xtts = sum(m['memory_delta_mb'] for m in xtts_metrics) / len(xtts_metrics)
            
            print(f"🔹 XTTS ({len(xtts_metrics)} amostras):")
            print(f"   RTF médio: {avg_rtf_xtts:.2f}x")
            print(f"   Memória média: {avg_memory_xtts:.1f}MB")
        
        if f5tts_metrics:
            avg_rtf_f5tts = sum(m['rtf'] for m in f5tts_metrics) / len(f5tts_metrics)
            avg_memory_f5tts = sum(m['memory_delta_mb'] for m in f5tts_metrics) / len(f5tts_metrics)
            
            print(f"\n🔹 F5-TTS ({len(f5tts_metrics)} amostras):")
            print(f"   RTF médio: {avg_rtf_f5tts:.2f}x")
            print(f"   Memória média: {avg_memory_f5tts:.1f}MB")
        
        if xtts_metrics and f5tts_metrics:
            print(f"\n📈 Comparação:")
            if avg_rtf_xtts < avg_rtf_f5tts:
                print(f"   ⚡ XTTS é {avg_rtf_f5tts/avg_rtf_xtts:.2f}x mais rápido")
            else:
                print(f"   ⚡ F5-TTS é {avg_rtf_xtts/avg_rtf_f5tts:.2f}x mais rápido")
        
        print(f"\n{'='*80}\n")


async def main():
    parser = argparse.ArgumentParser(description="Benchmark XTTS vs F5-TTS PT-BR")
    parser.add_argument(
        '--engine',
        choices=['xtts', 'f5tts', 'all'],
        default='all',
        help='Engine para benchmark (default: all)'
    )
    parser.add_argument(
        '--device',
        type=str,
        default=None,
        help='Device (cuda, cuda:0, cpu, etc.)'
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default='dataset_ptbr.json',
        help='Path para dataset JSON'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='results',
        help='Diretório de output'
    )
    parser.add_argument(
        '--minimal',
        action='store_true',
        help='Usar conjunto minimal de testes'
    )
    
    args = parser.parse_args()
    
    # Criar runner
    runner = BenchmarkRunner(
        dataset_path=args.dataset,
        output_dir=args.output,
        device=args.device
    )
    
    # Determinar textos/vozes para testar
    if args.minimal:
        texts = runner.dataset['test_combinations']['minimal_set']['texts']
        voices = runner.dataset['test_combinations']['minimal_set']['voices']
        print("ℹ️  Usando conjunto MINIMAL de testes\n")
    else:
        texts = None  # Usar todos
        voices = None
    
    # Executar benchmarks
    if args.engine in ['xtts', 'all']:
        await runner.run_benchmark_xtts(texts, voices)
    
    if args.engine in ['f5tts', 'all']:
        await runner.run_benchmark_f5tts(texts, voices)
    
    # Salvar e resumir
    runner.save_metrics()
    runner.print_summary()
    
    print("✅ Benchmark completo!")
    print(f"\nPróximos passos:")
    print("1. Revisar áudios em: results/xtts_outputs/ e results/f5tts_outputs/")
    print("2. Coletar MOS scores (usar mos_webapp.py ou editar results/mos_scores.csv)")
    print("3. Analisar resultados: python analyze_results.py")


if __name__ == '__main__':
    asyncio.run(main())
