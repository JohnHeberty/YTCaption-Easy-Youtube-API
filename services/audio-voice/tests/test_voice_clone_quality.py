#!/usr/bin/env python3
"""
Test Suite - Voice Cloning Quality Analysis
Compara áudio original com áudio clonado e gera métricas de qualidade
"""
import sys
import os
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy import signal
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error, r2_score
import json

# Add app to path
sys.path.insert(0, '/app')

from app.openvoice_client import OpenVoiceClient
from app.models import VoiceProfile

# Configurações
TEST_AUDIO = Path('/app/tests/Teste.mp3')
OUTPUT_DIR = Path('/app/tests/output_clone_analysis')
SAMPLE_RATE = 24000

class VoiceCloneQualityTest:
    """Testa qualidade da clonagem de voz"""
    
    def __init__(self):
        self.client = OpenVoiceClient(device='cpu')
        # Força carregamento dos modelos
        self.client._load_models()
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_audio': str(TEST_AUDIO),
            'metrics': {},
            'spectral_analysis': {},
            'formant_analysis': {},
            'prosody_analysis': {}
        }
        
        # Cria diretório de saída
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
    def load_audio(self, path: Path) -> tuple:
        """Carrega áudio e converte para formato padrão"""
        print(f"📂 Loading audio: {path}")
        
        # Carrega com soundfile
        audio, sr = sf.read(str(path))
        
        # Converte para mono se necessário
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Resample se necessário
        if sr != SAMPLE_RATE:
            from scipy.signal import resample
            num_samples = int(len(audio) * SAMPLE_RATE / sr)
            audio = resample(audio, num_samples)
            sr = SAMPLE_RATE
        
        print(f"  Duration: {len(audio)/sr:.2f}s")
        print(f"  Sample rate: {sr} Hz")
        print(f"  Samples: {len(audio)}")
        print(f"  Range: [{audio.min():.3f}, {audio.max():.3f}]")
        
        return audio, sr
    
    def extract_spectral_features(self, audio: np.ndarray, sr: int, label: str) -> dict:
        """Extrai características espectrais do áudio"""
        print(f"\n🔬 Extracting spectral features: {label}")
        
        # FFT
        fft = np.fft.fft(audio)
        freqs = np.fft.fftfreq(len(audio), 1/sr)
        magnitudes = np.abs(fft)
        
        # Apenas frequências positivas
        positive_mask = freqs > 0
        freqs_pos = freqs[positive_mask]
        mags_pos = magnitudes[positive_mask]
        
        # Top 10 frequências
        top_indices = np.argsort(mags_pos)[-10:][::-1]
        top_freqs = freqs_pos[top_indices]
        top_mags = mags_pos[top_indices]
        
        # Spectral centroid (centro de massa do espectro)
        spectral_centroid = np.sum(freqs_pos * mags_pos) / np.sum(mags_pos)
        
        # Spectral rolloff (frequência abaixo da qual está 85% da energia)
        cumsum = np.cumsum(mags_pos)
        rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0][0]
        spectral_rolloff = freqs_pos[rolloff_idx]
        
        # Spectral flatness (quão "ruidoso" vs "tonal")
        geometric_mean = np.exp(np.mean(np.log(mags_pos + 1e-10)))
        arithmetic_mean = np.mean(mags_pos)
        spectral_flatness = geometric_mean / (arithmetic_mean + 1e-10)
        
        features = {
            'top_frequencies': [
                {'freq': float(f), 'magnitude': float(m)} 
                for f, m in zip(top_freqs, top_mags)
            ],
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'spectral_flatness': float(spectral_flatness)
        }
        
        print(f"  Spectral Centroid: {spectral_centroid:.1f} Hz")
        print(f"  Spectral Rolloff: {spectral_rolloff:.1f} Hz")
        print(f"  Spectral Flatness: {spectral_flatness:.3f}")
        print(f"  Top 3 frequencies:")
        for i in range(min(3, len(top_freqs))):
            print(f"    {top_freqs[i]:.1f} Hz (mag: {top_mags[i]:.0f})")
        
        return features
    
    def extract_formants(self, audio: np.ndarray, sr: int, label: str) -> dict:
        """Extrai formantes do áudio (ressonâncias vocais)"""
        print(f"\n🎵 Extracting formants: {label}")
        
        # Usa LPC (Linear Predictive Coding) para estimar formantes
        # Windowing
        frame_length = int(0.025 * sr)  # 25ms
        hop_length = int(0.010 * sr)    # 10ms
        
        formants_f1 = []
        formants_f2 = []
        formants_f3 = []
        
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i+frame_length]
            
            # Pre-emphasis (realça altas frequências)
            pre_emphasized = np.append(frame[0], frame[1:] - 0.97 * frame[:-1])
            
            # LPC
            try:
                # Autocorrelação
                autocorr = np.correlate(pre_emphasized, pre_emphasized, mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                
                # Coeficientes LPC (ordem 12 para capturar 3 formantes)
                lpc_order = 12
                lpc_coeffs = self._levinson_durbin(autocorr, lpc_order)
                
                # Encontra raízes do polinômio LPC
                roots = np.roots(lpc_coeffs)
                
                # Converte para frequências
                angles = np.angle(roots)
                freqs = angles * (sr / (2 * np.pi))
                
                # Filtra apenas frequências positivas e raízes dentro do círculo unitário
                mask = (freqs > 0) & (np.abs(roots) > 0.95)
                formant_freqs = sorted(freqs[mask])
                
                # Captura F1, F2, F3
                if len(formant_freqs) >= 3:
                    formants_f1.append(formant_freqs[0])
                    formants_f2.append(formant_freqs[1])
                    formants_f3.append(formant_freqs[2])
            except:
                pass
        
        # Médias dos formantes
        f1_mean = np.mean(formants_f1) if formants_f1 else 0
        f2_mean = np.mean(formants_f2) if formants_f2 else 0
        f3_mean = np.mean(formants_f3) if formants_f3 else 0
        
        formants = {
            'F1': {
                'mean': float(f1_mean),
                'std': float(np.std(formants_f1)) if formants_f1 else 0,
                'samples': len(formants_f1)
            },
            'F2': {
                'mean': float(f2_mean),
                'std': float(np.std(formants_f2)) if formants_f2 else 0,
                'samples': len(formants_f2)
            },
            'F3': {
                'mean': float(f3_mean),
                'std': float(np.std(formants_f3)) if formants_f3 else 0,
                'samples': len(formants_f3)
            }
        }
        
        print(f"  F1 (First Formant): {f1_mean:.1f} Hz ± {np.std(formants_f1) if formants_f1 else 0:.1f}")
        print(f"  F2 (Second Formant): {f2_mean:.1f} Hz ± {np.std(formants_f2) if formants_f2 else 0:.1f}")
        print(f"  F3 (Third Formant): {f3_mean:.1f} Hz ± {np.std(formants_f3) if formants_f3 else 0:.1f}")
        
        return formants
    
    def _levinson_durbin(self, r, order):
        """Algoritmo de Levinson-Durbin para LPC"""
        a = np.zeros(order + 1)
        a[0] = 1.0
        e = r[0]
        
        for i in range(1, order + 1):
            lambda_val = -np.sum(a[:i] * r[i:0:-1]) / e
            a[1:i+1] = a[1:i+1] + lambda_val * a[i-1::-1]
            a[i] = lambda_val
            e = e * (1 - lambda_val**2)
        
        return a
    
    def extract_prosody(self, audio: np.ndarray, sr: int, label: str) -> dict:
        """Extrai características prosódicas (pitch, energia, ritmo)"""
        print(f"\n🎼 Extracting prosody: {label}")
        
        # Pitch (F0) usando autocorrelação
        frame_length = int(0.025 * sr)
        hop_length = int(0.010 * sr)
        
        pitches = []
        energies = []
        
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i+frame_length]
            
            # Energia (RMS)
            energy = np.sqrt(np.mean(frame**2))
            energies.append(energy)
            
            # Pitch via autocorrelação
            autocorr = np.correlate(frame, frame, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            
            # Encontra primeiro pico após lag mínimo (exclui lag 0)
            min_lag = int(sr / 500)  # 500 Hz máximo
            max_lag = int(sr / 50)   # 50 Hz mínimo
            
            if max_lag < len(autocorr):
                search_region = autocorr[min_lag:max_lag]
                if len(search_region) > 0:
                    peak_lag = np.argmax(search_region) + min_lag
                    if autocorr[peak_lag] > 0.3 * autocorr[0]:  # Threshold
                        pitch = sr / peak_lag
                        if 50 <= pitch <= 500:  # Válido para voz humana
                            pitches.append(pitch)
        
        # Estatísticas
        pitch_mean = np.mean(pitches) if pitches else 0
        pitch_std = np.std(pitches) if pitches else 0
        energy_mean = np.mean(energies) if energies else 0
        energy_std = np.std(energies) if energies else 0
        
        # Zero crossing rate (indica conteúdo de alta frequência)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio)))) / len(audio)
        
        prosody = {
            'pitch': {
                'mean': float(pitch_mean),
                'std': float(pitch_std),
                'min': float(np.min(pitches)) if pitches else 0,
                'max': float(np.max(pitches)) if pitches else 0,
                'samples': len(pitches)
            },
            'energy': {
                'mean': float(energy_mean),
                'std': float(energy_std)
            },
            'zero_crossing_rate': float(zero_crossings)
        }
        
        print(f"  Pitch: {pitch_mean:.1f} Hz ± {pitch_std:.1f} (range: {np.min(pitches) if pitches else 0:.1f}-{np.max(pitches) if pitches else 0:.1f})")
        print(f"  Energy: {energy_mean:.4f} ± {energy_std:.4f}")
        print(f"  Zero Crossing Rate: {zero_crossings:.4f}")
        
        return prosody
    
    def compare_metrics(self, original_features: dict, cloned_features: dict) -> dict:
        """Compara métricas entre original e clonado"""
        print(f"\n📊 Computing similarity metrics...")
        
        metrics = {}
        
        # Spectral Centroid
        centroid_diff = abs(original_features['spectral_centroid'] - cloned_features['spectral_centroid'])
        centroid_error = centroid_diff / original_features['spectral_centroid'] * 100
        
        # Spectral Rolloff
        rolloff_diff = abs(original_features['spectral_rolloff'] - cloned_features['spectral_rolloff'])
        rolloff_error = rolloff_diff / original_features['spectral_rolloff'] * 100
        
        # Spectral Flatness
        flatness_diff = abs(original_features['spectral_flatness'] - cloned_features['spectral_flatness'])
        
        metrics['spectral_centroid_error_%'] = float(centroid_error)
        metrics['spectral_rolloff_error_%'] = float(rolloff_error)
        metrics['spectral_flatness_diff'] = float(flatness_diff)
        
        print(f"  Spectral Centroid Error: {centroid_error:.2f}%")
        print(f"  Spectral Rolloff Error: {rolloff_error:.2f}%")
        print(f"  Spectral Flatness Diff: {flatness_diff:.4f}")
        
        return metrics
    
    def run_test(self):
        """Executa teste completo"""
        print("="*80)
        print("🧪 VOICE CLONING QUALITY TEST")
        print("="*80)
        
        # 1. Carrega áudio original
        print("\n" + "="*80)
        print("STEP 1: Load Original Audio")
        print("="*80)
        original_audio, sr = self.load_audio(TEST_AUDIO)
        
        # 2. Clona voz
        print("\n" + "="*80)
        print("STEP 2: Clone Voice")
        print("="*80)
        print("🎤 Cloning voice from original audio...")
        
        voice_embedding = self.client._tts_model.extract_voice_embedding(str(TEST_AUDIO), 'pt')
        print(f"  Voice embedding extracted: shape {voice_embedding.shape}")
        
        # 3. Gera áudio clonado (mesmo texto: "Oi, tudo bem?")
        print("\n" + "="*80)
        print("STEP 3: Generate Cloned Audio")
        print("="*80)
        print("🔊 Generating: 'Oi, tudo bem?'")
        
        cloned_audio = self.client._tts_model.tts_with_voice(
            text="Oi, tudo bem?",
            voice_embedding=voice_embedding,
            speaker='pt-BR',
            language='pt'
        )
        
        # Salva áudio clonado
        cloned_path = OUTPUT_DIR / 'cloned_audio.wav'
        sf.write(str(cloned_path), cloned_audio, SAMPLE_RATE)
        print(f"  Saved: {cloned_path}")
        
        # 4. Extrai features do original
        print("\n" + "="*80)
        print("STEP 4: Analyze Original Audio")
        print("="*80)
        original_spectral = self.extract_spectral_features(original_audio, sr, "Original")
        original_formants = self.extract_formants(original_audio, sr, "Original")
        original_prosody = self.extract_prosody(original_audio, sr, "Original")
        
        # 5. Extrai features do clonado
        print("\n" + "="*80)
        print("STEP 5: Analyze Cloned Audio")
        print("="*80)
        cloned_spectral = self.extract_spectral_features(cloned_audio, SAMPLE_RATE, "Cloned")
        cloned_formants = self.extract_formants(cloned_audio, SAMPLE_RATE, "Cloned")
        cloned_prosody = self.extract_prosody(cloned_audio, SAMPLE_RATE, "Cloned")
        
        # 6. Compara métricas
        print("\n" + "="*80)
        print("STEP 6: Compare Metrics")
        print("="*80)
        comparison = self.compare_metrics(original_spectral, cloned_spectral)
        
        # 7. Salva resultados
        self.results['original'] = {
            'spectral': original_spectral,
            'formants': original_formants,
            'prosody': original_prosody
        }
        self.results['cloned'] = {
            'spectral': cloned_spectral,
            'formants': cloned_formants,
            'prosody': cloned_prosody
        }
        self.results['comparison'] = comparison
        
        # Salva JSON
        results_path = OUTPUT_DIR / f'analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Results saved: {results_path}")
        
        # 8. Gera visualizações
        self.generate_plots(original_audio, cloned_audio, sr)
        
        # 9. Gera relatório final
        self.print_final_report()
    
    def generate_plots(self, original: np.ndarray, cloned: np.ndarray, sr: int):
        """Gera gráficos de comparação"""
        print("\n" + "="*80)
        print("STEP 7: Generate Visualizations")
        print("="*80)
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        
        # Waveforms
        axes[0, 0].plot(original, linewidth=0.5)
        axes[0, 0].set_title('Original Waveform')
        axes[0, 0].set_xlabel('Samples')
        axes[0, 0].set_ylabel('Amplitude')
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].plot(cloned, linewidth=0.5)
        axes[0, 1].set_title('Cloned Waveform')
        axes[0, 1].set_xlabel('Samples')
        axes[0, 1].set_ylabel('Amplitude')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Spectrograms
        f1, t1, Sxx1 = signal.spectrogram(original, sr, nperseg=1024)
        axes[1, 0].pcolormesh(t1, f1, 10 * np.log10(Sxx1 + 1e-10), shading='gouraud', cmap='viridis')
        axes[1, 0].set_title('Original Spectrogram')
        axes[1, 0].set_ylabel('Frequency (Hz)')
        axes[1, 0].set_xlabel('Time (s)')
        axes[1, 0].set_ylim([0, 4000])
        
        f2, t2, Sxx2 = signal.spectrogram(cloned, SAMPLE_RATE, nperseg=1024)
        axes[1, 1].pcolormesh(t2, f2, 10 * np.log10(Sxx2 + 1e-10), shading='gouraud', cmap='viridis')
        axes[1, 1].set_title('Cloned Spectrogram')
        axes[1, 1].set_ylabel('Frequency (Hz)')
        axes[1, 1].set_xlabel('Time (s)')
        axes[1, 1].set_ylim([0, 4000])
        
        # Frequency spectra
        fft1 = np.fft.fft(original)
        freqs1 = np.fft.fftfreq(len(original), 1/sr)
        mask1 = (freqs1 > 0) & (freqs1 < 4000)
        
        fft2 = np.fft.fft(cloned)
        freqs2 = np.fft.fftfreq(len(cloned), 1/SAMPLE_RATE)
        mask2 = (freqs2 > 0) & (freqs2 < 4000)
        
        axes[2, 0].plot(freqs1[mask1], np.abs(fft1[mask1]), linewidth=0.5)
        axes[2, 0].set_title('Original Frequency Spectrum')
        axes[2, 0].set_xlabel('Frequency (Hz)')
        axes[2, 0].set_ylabel('Magnitude')
        axes[2, 0].grid(True, alpha=0.3)
        
        axes[2, 1].plot(freqs2[mask2], np.abs(fft2[mask2]), linewidth=0.5, color='orange')
        axes[2, 1].set_title('Cloned Frequency Spectrum')
        axes[2, 1].set_xlabel('Frequency (Hz)')
        axes[2, 1].set_ylabel('Magnitude')
        axes[2, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        plot_path = OUTPUT_DIR / f'comparison_plots_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"  Plots saved: {plot_path}")
        plt.close()
    
    def print_final_report(self):
        """Imprime relatório final"""
        print("\n" + "="*80)
        print("📋 FINAL REPORT")
        print("="*80)
        
        orig = self.results['original']
        clone = self.results['cloned']
        comp = self.results['comparison']
        
        print("\n🎯 SPECTRAL ANALYSIS")
        print("-" * 80)
        print(f"{'Metric':<30} {'Original':>15} {'Cloned':>15} {'Error':>15}")
        print("-" * 80)
        print(f"{'Spectral Centroid (Hz)':<30} {orig['spectral']['spectral_centroid']:>15.1f} {clone['spectral']['spectral_centroid']:>15.1f} {comp['spectral_centroid_error_%']:>14.2f}%")
        print(f"{'Spectral Rolloff (Hz)':<30} {orig['spectral']['spectral_rolloff']:>15.1f} {clone['spectral']['spectral_rolloff']:>15.1f} {comp['spectral_rolloff_error_%']:>14.2f}%")
        print(f"{'Spectral Flatness':<30} {orig['spectral']['spectral_flatness']:>15.3f} {clone['spectral']['spectral_flatness']:>15.3f} {comp['spectral_flatness_diff']:>15.3f}")
        
        print("\n🎵 FORMANT ANALYSIS")
        print("-" * 80)
        print(f"{'Formant':<30} {'Original (Hz)':>15} {'Cloned (Hz)':>15} {'Diff (Hz)':>15}")
        print("-" * 80)
        f1_diff = abs(orig['formants']['F1']['mean'] - clone['formants']['F1']['mean'])
        f2_diff = abs(orig['formants']['F2']['mean'] - clone['formants']['F2']['mean'])
        f3_diff = abs(orig['formants']['F3']['mean'] - clone['formants']['F3']['mean'])
        print(f"{'F1 (First Formant)':<30} {orig['formants']['F1']['mean']:>15.1f} {clone['formants']['F1']['mean']:>15.1f} {f1_diff:>15.1f}")
        print(f"{'F2 (Second Formant)':<30} {orig['formants']['F2']['mean']:>15.1f} {clone['formants']['F2']['mean']:>15.1f} {f2_diff:>15.1f}")
        print(f"{'F3 (Third Formant)':<30} {orig['formants']['F3']['mean']:>15.1f} {clone['formants']['F3']['mean']:>15.1f} {f3_diff:>15.1f}")
        
        print("\n🎼 PROSODY ANALYSIS")
        print("-" * 80)
        print(f"{'Metric':<30} {'Original':>15} {'Cloned':>15} {'Diff':>15}")
        print("-" * 80)
        pitch_diff = abs(orig['prosody']['pitch']['mean'] - clone['prosody']['pitch']['mean'])
        energy_diff = abs(orig['prosody']['energy']['mean'] - clone['prosody']['energy']['mean'])
        print(f"{'Pitch Mean (Hz)':<30} {orig['prosody']['pitch']['mean']:>15.1f} {clone['prosody']['pitch']['mean']:>15.1f} {pitch_diff:>15.1f}")
        print(f"{'Energy Mean':<30} {orig['prosody']['energy']['mean']:>15.4f} {clone['prosody']['energy']['mean']:>15.4f} {energy_diff:>15.4f}")
        
        print("\n" + "="*80)
        print("✅ TEST COMPLETE")
        print("="*80)


if __name__ == '__main__':
    test = VoiceCloneQualityTest()
    test.run_test()
