# 🧪 Voice Clone Quality Test Suite

Automated testing framework to validate voice cloning quality by comparing original audio with AI-generated clones.

## 📋 Overview

This test suite analyzes voice cloning output using multiple acoustic metrics:

- **Spectral Analysis**: Frequency distribution, centroid, rolloff, flatness
- **Formant Detection**: F1, F2, F3 resonances (vowel quality)
- **Prosody Analysis**: Pitch, energy, rhythm
- **Visual Comparison**: Waveforms, spectrograms, frequency spectra

## 🚀 Quick Start

### Prerequisites

- Docker installed
- Your voice sample: `tests/Teste.mp3` (saying "Oi, tudo bem?" or any text)

### Run Test

```bash
cd services/audio-voice
./run_clone_test.sh
```

The script will:
1. ✅ Stop any running containers
2. 🔨 Build test image with analysis dependencies
3. 🎤 Extract voice embedding from your audio
4. 🔊 Generate cloned audio with same text
5. 📊 Compare metrics (spectral, formants, prosody)
6. 📈 Create visualization plots
7. 💾 Save results to `tests/output_clone_analysis/`

### Expected Output

```
🧪 VOICE CLONING QUALITY TEST
================================================================================

STEP 1: Load Original Audio
  Duration: 2.44s
  Sample rate: 24000 Hz
  Samples: 58508

STEP 2: Clone Voice
  Voice embedding extracted: shape (256,)

STEP 3: Generate Cloned Audio
  Saved: cloned_audio.wav

STEP 4-5: Analyze Original & Cloned Audio
  [Spectral features, formants, prosody]

STEP 6: Compare Metrics
  Spectral Centroid Error: X%
  Spectral Rolloff Error: Y%

STEP 7: Generate Visualizations
  Plots saved: comparison_plots_YYYYMMDD_HHMMSS.png

📋 FINAL REPORT
  [Detailed comparison tables]

✅ TEST COMPLETE
```

## 📁 Output Files

All results saved in `tests/output_clone_analysis/`:

| File | Description |
|------|-------------|
| `analysis_results_<timestamp>.json` | Complete metrics (JSON format) |
| `cloned_audio.wav` | Generated audio (24kHz, mono) |
| `comparison_plots_<timestamp>.png` | Visual comparison (waveforms, spectrograms, spectra) |
| `TEST-RESULTS-ANALYSIS.md` | Human-readable analysis report |

## 📊 Metrics Explained

### Spectral Analysis

**Spectral Centroid**
- "Center of mass" of frequency spectrum
- Perceptual correlate: Brightness
- **Target**: < 20% error between original and clone

**Spectral Rolloff**
- Frequency below which 85% of energy is concentrated
- Indicates frequency range usage
- **Target**: < 25% error

**Spectral Flatness**
- 0.0 = Pure tone, 1.0 = White noise
- Speech typically 0.02 - 0.15
- **Target**: Difference < 0.10

### Formant Analysis

**Formants (F1, F2, F3)**
- Resonant frequencies of vocal tract
- Define vowel identity
- F1: 300-1000 Hz (mouth openness)
- F2: 800-2500 Hz (tongue position)
- F3: 2000-4000 Hz (lip rounding)
- **Target**: All 3 detected, mean differences < 100 Hz

### Prosody Analysis

**Pitch (F0)**
- Fundamental frequency
- Male: ~100-150 Hz, Female: ~180-250 Hz
- **Target**: Mean difference < 30 Hz

**Energy (RMS)**
- Signal amplitude/loudness
- **Target**: Ratio 0.8 - 1.2 (clone vs original)

**Zero Crossing Rate**
- Frequency of signal sign changes
- High = more high-frequency content
- **Target**: Difference < 0.05

## 🔬 Test Methodology

### Process Flow

```
┌─────────────────┐
│ Input:          │
│ Teste.mp3       │
│ "Oi, tudo bem?" │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract Voice   │
│ Embedding       │
│ (256-dim vector)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ TTS Synthesis   │
│ with Embedding  │
│ → cloned_audio  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Parallel Analysis:              │
│ ┌──────────┐  ┌──────────┐     │
│ │ Original │  │  Cloned  │     │
│ └────┬─────┘  └────┬─────┘     │
│      │             │            │
│      ▼             ▼            │
│   ┌─────────────────────┐      │
│   │ FFT Analysis        │      │
│   │ Formant Extraction  │      │
│   │ Pitch Tracking      │      │
│   │ Energy Calculation  │      │
│   └──────────┬──────────┘      │
└──────────────┼──────────────────┘
               │
               ▼
      ┌────────────────┐
      │ Comparison     │
      │ Metrics        │
      │ • Errors       │
      │ • Differences  │
      │ • Scores       │
      └────────┬───────┘
               │
               ▼
      ┌────────────────┐
      │ Output:        │
      │ • JSON data    │
      │ • Plots        │
      │ • Report       │
      └────────────────┘
```

### Analysis Algorithms

**FFT (Fast Fourier Transform)**
```python
fft = np.fft.fft(audio)
freqs = np.fft.fftfreq(len(audio), 1/sample_rate)
magnitudes = np.abs(fft)
```

**LPC Formant Extraction**
```python
# Linear Predictive Coding (12th order)
autocorr = np.correlate(frame, frame, mode='full')
lpc_coeffs = levinson_durbin(autocorr, order=12)
roots = np.roots(lpc_coeffs)
formants = angles_to_frequencies(roots, sample_rate)
```

**Pitch Tracking (Autocorrelation)**
```python
autocorr = np.correlate(frame, frame, mode='full')
peak_lag = find_first_peak(autocorr[len//2:])
pitch = sample_rate / peak_lag
```

## 🎯 Quality Criteria

For a voice clone to pass quality validation:

| Metric | Threshold | Weight |
|--------|-----------|--------|
| Spectral Centroid Error | < 20% | 25% |
| Formants Detected | 3/3 | 25% |
| Formant Mean Error | < 100 Hz | 20% |
| Pitch Error | < 30 Hz | 15% |
| Energy Ratio | 0.8 - 1.2 | 10% |
| Spectral Flatness Diff | < 0.10 | 5% |

**Pass Grade**: ≥ 70% (weighted score)

## 🐛 Troubleshooting

### Test fails to run

**Error**: `tests/Teste.mp3 not found`
```bash
# Record your voice saying "Oi, tudo bem?" and save as:
cp /path/to/your/audio.mp3 tests/Teste.mp3
```

**Error**: `Permission denied`
```bash
chmod +x run_clone_test.sh
```

**Error**: `Docker not found`
```bash
# Install Docker first
curl -fsSL https://get.docker.com | sh
```

### Unexpected metrics

**Energy too high** (> 5× original)
- Check audio normalization in synthesis
- Verify soft clipping is working

**Formants not detected**
- Signal may be too pure (sine wave)
- Need more spectral complexity

**Spectral centroid error > 100%**
- Frequency distribution completely wrong
- Check amplitude balance (fundamental vs formants)

## 📚 Dependencies

Test container includes:

```
soundfile==0.12.1      # Audio I/O
matplotlib==3.8.2      # Plotting
scipy==1.11.4          # Signal processing
scikit-learn==1.3.2    # Metrics
numpy                  # Array operations
```

## 🔧 Customization

### Change test text

Edit `test_voice_clone_quality.py`:
```python
cloned_audio = self.client._tts_model.tts_with_voice(
    text="Seu texto aqui",  # ← Change this
    voice_embedding=voice_embedding,
    speaker='pt-BR',
    language='pt'
)
```

### Add custom metrics

Example - Add spectral entropy:
```python
def spectral_entropy(magnitudes):
    """Shannon entropy of frequency distribution"""
    probs = magnitudes / np.sum(magnitudes)
    entropy = -np.sum(probs * np.log2(probs + 1e-10))
    return entropy
```

### Adjust quality thresholds

Edit `compare_metrics()` method:
```python
# Example: Stricter spectral centroid
if centroid_error > 10:  # Was 20%
    logger.warning("Spectral centroid error too high!")
```

## 📖 Further Reading

- [Speech Signal Processing](https://www.dspguide.com/)
- [Formant Analysis](https://home.cc.umanitoba.ca/~krussll/phonetics/acoustic/formants.html)
- [LPC Tutorial](https://ccrma.stanford.edu/~hskim08/lpc/)
- [Spectral Audio Features](https://www.coursera.org/learn/audio-signal-processing)

## 🤝 Contributing

Improvements welcome:
- Add perceptual metrics (PESQ, STOI)
- Mel-frequency cepstral coefficients (MFCC)
- Speaker verification metrics
- Subjective quality scores (MOS)

## 📄 License

Part of YTCaption-Easy-Youtube-API project.

---

**Last Updated**: 2025-11-25  
**Version**: 1.0  
**Maintainer**: audio-voice team
