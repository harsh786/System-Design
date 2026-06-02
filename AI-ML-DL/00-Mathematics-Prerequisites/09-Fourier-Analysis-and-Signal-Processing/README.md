# Fourier Analysis and Signal Processing for ML

## 1. Why Fourier Analysis for ML

Fourier analysis is not just signal processing theory — it's deeply embedded in modern ML:

| ML Application | Fourier Connection |
|---|---|
| CNNs | Convolution kernels ARE frequency filters |
| Transformers | Positional encoding uses Fourier basis (sinusoids) |
| Audio/Speech ML | Models operate on spectrograms (frequency representations) |
| Time Series | Spectral methods detect seasonality and trends |
| Neural Operators | Fourier Neural Operator learns in frequency domain |
| NeRF | Fourier features encode high-frequency spatial details |

**Key insight:** Convolution in spatial domain = multiplication in frequency domain.
This means every CNN layer is implicitly performing frequency-domain filtering.

---

## 2. Periodic Functions and Trigonometric Series

### Sine and Cosine Basics

A sinusoid is defined by three parameters:
```
f(t) = A * sin(2π * freq * t + φ)

A     = amplitude (height)
freq  = frequency (cycles per second, Hz)
φ     = phase (horizontal shift)
```

### Superposition Principle

Any complex periodic signal can be decomposed into a sum of sinusoids:

```
ASCII Visualization: Signal Decomposition

Original Signal:        Component 1:         Component 2:         Component 3:
  ╭─╮   ╭─╮              ╭───╮                 ╭╮  ╭╮               ╭╮╭╮╭╮
 ╱  ╲  ╱  ╲           ╱     ╲              ╱╲╱╲╱╲             ╱╲╱╲╱╲╱╲
╱    ╲╱    ╲         ╱       ╲            ╱      ╲           ╱        ╲
             ╲╱    ╲         ╲╱            ╲╱              ╲╱
                    ╲___╱
  f(t)        =    sin(t)      +    0.5*sin(3t)   +   0.3*sin(5t)
 (square-ish)     (fundamental)    (3rd harmonic)    (5th harmonic)
```

### Fourier Series

For a periodic function f(t) with period T:

```
f(t) = a₀/2 + Σ[aₙcos(2πnt/T) + bₙsin(2πnt/T)]    for n=1 to ∞
```

**Fourier coefficients:**
```
a₀ = (2/T) ∫₀ᵀ f(t) dt                    (DC component / mean)
aₙ = (2/T) ∫₀ᵀ f(t)cos(2πnt/T) dt         (cosine coefficients)
bₙ = (2/T) ∫₀ᵀ f(t)sin(2πnt/T) dt         (sine coefficients)
```

**Complex exponential form (more compact):**
```
f(t) = Σ cₙ * e^(j2πnt/T)    for n = -∞ to ∞

where cₙ = (1/T) ∫₀ᵀ f(t) * e^(-j2πnt/T) dt
```

```python
import numpy as np
import matplotlib.pyplot as plt

def fourier_series_square_wave(t, n_terms=10):
    """Approximate square wave using Fourier series."""
    result = np.zeros_like(t)
    for n in range(1, n_terms + 1, 2):  # Only odd harmonics
        result += (4 / (np.pi * n)) * np.sin(2 * np.pi * n * t)
    return result

# Demonstrate convergence
t = np.linspace(0, 2, 1000)
for n_terms in [1, 3, 5, 15, 51]:
    approx = fourier_series_square_wave(t, n_terms)
    print(f"Terms={n_terms:2d}, Max error from ideal: {np.max(np.abs(approx)) - 1:.4f}")
```

---

## 3. Discrete Fourier Transform (DFT)

### From Continuous to Discrete

Real signals are sampled at discrete time points. The DFT handles this:

```
DFT:  X[k] = Σ x[n] * e^(-j2πkn/N)     for k = 0, 1, ..., N-1
              n=0 to N-1

IDFT: x[n] = (1/N) Σ X[k] * e^(j2πkn/N)  for n = 0, 1, ..., N-1
                    k=0 to N-1
```

**What each frequency bin means:**
- `X[0]` = DC component (mean of signal × N)
- `X[k]` = amplitude and phase of frequency k/N cycles per sample
- `X[N/2]` = Nyquist frequency (highest representable)
- `|X[k]|` = magnitude (amplitude)
- `∠X[k]` = phase angle

### Nyquist Theorem

**Sampling rate must be ≥ 2× the highest frequency in the signal.**

```
fs ≥ 2 * fmax

If violated → aliasing (high frequencies masquerade as low frequencies)
```

### Python Implementation

```python
import numpy as np

def dft_naive(x):
    """Naive O(N²) DFT implementation."""
    N = len(x)
    X = np.zeros(N, dtype=complex)
    for k in range(N):
        for n in range(N):
            X[k] += x[n] * np.exp(-2j * np.pi * k * n / N)
    return X

def idft_naive(X):
    """Naive O(N²) inverse DFT."""
    N = len(X)
    x = np.zeros(N, dtype=complex)
    for n in range(N):
        for k in range(N):
            x[n] += X[k] * np.exp(2j * np.pi * k * n / N)
    return x / N

# Example: analyze a signal with two frequencies
N = 64
t = np.arange(N) / N
signal = 3 * np.sin(2 * np.pi * 5 * t) + 1.5 * np.sin(2 * np.pi * 12 * t)

X = dft_naive(signal)
magnitudes = np.abs(X[:N//2]) / (N/2)

print("Detected frequencies and amplitudes:")
for k in range(N//2):
    if magnitudes[k] > 0.1:
        print(f"  Frequency bin {k} (freq={k} cycles): amplitude = {magnitudes[k]:.2f}")
# Output: bin 5 → amp 3.0, bin 12 → amp 1.5
```

---

## 4. Fast Fourier Transform (FFT)

### Why FFT Matters

```
Naive DFT: O(N²)     — 1M samples → 10¹² operations
FFT:       O(N log N) — 1M samples → 2×10⁷ operations (50,000× faster!)
```

### Cooley-Tukey Algorithm (Divide and Conquer)

Split DFT into even-indexed and odd-indexed elements:
```
X[k] = Σ x[2m]*e^(-j2πk(2m)/N) + Σ x[2m+1]*e^(-j2πk(2m+1)/N)
     = DFT_even[k] + e^(-j2πk/N) * DFT_odd[k]
```

Recursively split N-point DFT into two N/2-point DFTs.

```python
def fft_recursive(x):
    """Recursive Cooley-Tukey FFT (radix-2). N must be power of 2."""
    N = len(x)
    if N <= 1:
        return x
    
    # Divide
    even = fft_recursive(x[0::2])
    odd = fft_recursive(x[1::2])
    
    # Conquer (butterfly operations)
    twiddle = np.exp(-2j * np.pi * np.arange(N//2) / N)
    return np.concatenate([
        even + twiddle * odd,
        even - twiddle * odd
    ])

# Performance comparison
import time

for N in [128, 512, 2048, 8192]:
    x = np.random.randn(N)
    
    start = time.time()
    X_naive = dft_naive(x)
    t_naive = time.time() - start
    
    start = time.time()
    X_fft = np.fft.fft(x)
    t_fft = time.time() - start
    
    print(f"N={N:5d}: Naive={t_naive:.4f}s, FFT={t_fft:.6f}s, "
          f"Speedup={t_naive/t_fft:.0f}x, "
          f"Max error={np.max(np.abs(X_naive - X_fft)):.2e}")
```

### 2D FFT for Image Analysis

```python
# 2D FFT reveals frequency content of images
image = np.random.randn(256, 256)  # placeholder for actual image

# Compute 2D FFT
F = np.fft.fft2(image)
F_shifted = np.fft.fftshift(F)  # Center zero-frequency
magnitude_spectrum = np.log(1 + np.abs(F_shifted))

# Low-pass filter (blur): keep only center frequencies
rows, cols = image.shape
crow, ccol = rows // 2, cols // 2
mask = np.zeros((rows, cols))
r = 30  # radius
y, x = np.ogrid[-crow:rows-crow, -ccol:cols-ccol]
mask[x*x + y*y <= r*r] = 1

# Apply filter in frequency domain
F_filtered = F_shifted * mask
img_filtered = np.real(np.fft.ifft2(np.fft.ifftshift(F_filtered)))
# Result: blurred image (low-pass filter removes high frequencies = edges)
```

---

## 5. Convolution Theorem

### The Fundamental Connection

```
Convolution Theorem:
    f * g  ←→  F · G

    Convolution in time/space  =  Multiplication in frequency domain
    
    f(t) * g(t) = IFFT( FFT(f) · FFT(g) )
```

### Why This Matters for CNNs

Every CNN convolution kernel is a frequency filter:

```
Kernel Type        | Frequency Behavior     | Effect
-------------------|------------------------|------------------
Large Gaussian     | Low-pass filter        | Blur (smooth)
Sobel/edge detect  | High-pass filter       | Edges (details)
Gabor filter       | Band-pass filter       | Texture at scale
Identity kernel    | All-pass               | No change
```

**CNN kernels learn which frequencies to keep/remove!**

### Fast Convolution via FFT

For large kernels, FFT-based convolution is faster:
```
Direct convolution: O(N * K)     where K = kernel size
FFT convolution:    O(N log N)   regardless of kernel size
```

```python
def convolve_direct(signal, kernel):
    """Direct convolution O(N*K)."""
    N, K = len(signal), len(kernel)
    output = np.zeros(N + K - 1)
    for i in range(N):
        for j in range(K):
            output[i + j] += signal[i] * kernel[j]
    return output

def convolve_fft(signal, kernel):
    """FFT-based convolution O(N log N)."""
    N = len(signal) + len(kernel) - 1
    # Pad to next power of 2 for efficiency
    N_padded = 2 ** int(np.ceil(np.log2(N)))
    
    F_signal = np.fft.fft(signal, N_padded)
    F_kernel = np.fft.fft(kernel, N_padded)
    
    # Multiply in frequency domain = convolve in time domain
    F_output = F_signal * F_kernel
    
    output = np.real(np.fft.ifft(F_output))[:N]
    return output

# Verify equivalence
signal = np.random.randn(1000)
kernel = np.random.randn(100)

result_direct = convolve_direct(signal, kernel)
result_fft = convolve_fft(signal, kernel)
print(f"Max difference: {np.max(np.abs(result_direct - result_fft)):.2e}")

# For large kernels, FFT wins
import time
signal_large = np.random.randn(10000)
for K in [10, 100, 500, 2000]:
    kernel_large = np.random.randn(K)
    
    start = time.time()
    _ = np.convolve(signal_large, kernel_large)
    t_direct = time.time() - start
    
    start = time.time()
    _ = convolve_fft(signal_large, kernel_large)
    t_fft = time.time() - start
    
    print(f"Kernel size={K:4d}: Direct={t_direct:.4f}s, FFT={t_fft:.4f}s")
```

---

## 6. Spectral Analysis for Time Series

### Power Spectral Density (PSD)

PSD shows how signal power is distributed across frequencies:

```python
def compute_psd(signal, fs=1.0):
    """Compute Power Spectral Density using periodogram."""
    N = len(signal)
    X = np.fft.fft(signal)
    psd = (np.abs(X[:N//2])**2) / (N * fs)
    freqs = np.fft.fftfreq(N, d=1/fs)[:N//2]
    return freqs, psd

# Detect seasonality in time series
np.random.seed(42)
days = 365 * 3  # 3 years of daily data
t = np.arange(days)

# Signal: weekly pattern + monthly pattern + noise
signal = (2.0 * np.sin(2 * np.pi * t / 7) +      # weekly (period=7 days)
          1.5 * np.sin(2 * np.pi * t / 30) +      # monthly (period=30 days)
          3.0 * np.sin(2 * np.pi * t / 365) +     # yearly (period=365 days)
          0.5 * np.random.randn(days))              # noise

freqs, psd = compute_psd(signal, fs=1.0)  # fs=1 sample/day

# Find dominant frequencies
top_indices = np.argsort(psd)[-5:]
print("Dominant periods detected:")
for idx in top_indices:
    if freqs[idx] > 0:
        period = 1.0 / freqs[idx]
        print(f"  Period = {period:.1f} days (power = {psd[idx]:.2f})")
```

### Short-Time Fourier Transform (STFT)

For non-stationary signals, use windowed FFT:

```python
def stft(signal, window_size=256, hop_size=128):
    """Compute Short-Time Fourier Transform."""
    n_windows = (len(signal) - window_size) // hop_size + 1
    window = np.hanning(window_size)
    
    spectrogram = np.zeros((window_size // 2 + 1, n_windows), dtype=complex)
    
    for i in range(n_windows):
        start = i * hop_size
        segment = signal[start:start + window_size] * window
        spectrogram[:, i] = np.fft.rfft(segment)
    
    return np.abs(spectrogram)  # magnitude spectrogram

# Example: chirp signal (increasing frequency)
fs = 1000
t = np.linspace(0, 2, 2 * fs)
chirp = np.sin(2 * np.pi * (50 * t + 100 * t**2))  # freq increases over time

spec = stft(chirp, window_size=256, hop_size=64)
print(f"Spectrogram shape: {spec.shape} (freq_bins x time_frames)")
# Spectrogram would show frequency increasing over time
```

### Filtering Noise

```python
def bandpass_filter(signal, fs, low_freq, high_freq):
    """Simple frequency-domain bandpass filter."""
    N = len(signal)
    X = np.fft.fft(signal)
    freqs = np.fft.fftfreq(N, d=1/fs)
    
    # Zero out frequencies outside band
    mask = (np.abs(freqs) >= low_freq) & (np.abs(freqs) <= high_freq)
    X_filtered = X * mask
    
    return np.real(np.fft.ifft(X_filtered))
```

---

## 7. Fourier Features in Modern ML

### Random Fourier Features (Kernel Approximation)

Bochner's theorem: any shift-invariant kernel can be approximated by random Fourier features.

```python
def random_fourier_features(X, n_features=100, sigma=1.0):
    """Approximate RBF kernel using Random Fourier Features.
    
    k(x, y) ≈ z(x)ᵀz(y) where z is the RFF mapping.
    """
    d = X.shape[1]
    # Sample frequencies from kernel's spectral density
    W = np.random.randn(d, n_features) / sigma  # For RBF kernel
    b = np.random.uniform(0, 2 * np.pi, n_features)
    
    # Map: z(x) = sqrt(2/D) * cos(Wx + b)
    Z = np.sqrt(2.0 / n_features) * np.cos(X @ W + b)
    return Z

# Linear model on RFF ≈ kernel SVM
X_train = np.random.randn(1000, 10)
Z_train = random_fourier_features(X_train, n_features=500)
# Now use linear regression/classification on Z_train
```

### Positional Encoding in Transformers

**This IS a Fourier basis!**

```python
def positional_encoding(max_len, d_model):
    """Transformer positional encoding — sinusoidal Fourier features.
    
    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    
    Each dimension corresponds to a different frequency sinusoid.
    Together they form a Fourier basis that uniquely encodes position.
    """
    pe = np.zeros((max_len, d_model))
    position = np.arange(max_len)[:, np.newaxis]  # (max_len, 1)
    
    # Frequencies: geometric series from high to low frequency
    div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
    
    pe[:, 0::2] = np.sin(position * div_term)  # Even dimensions
    pe[:, 1::2] = np.cos(position * div_term)  # Odd dimensions
    
    return pe

# Why sinusoidal? Relative position as linear transformation:
# PE(pos+k) can be expressed as a linear function of PE(pos)
# This is because sin(a+b) = sin(a)cos(b) + cos(a)sin(b)
# So the model can learn to attend to relative positions!

pe = positional_encoding(100, 64)
print(f"Positional encoding shape: {pe.shape}")
print(f"PE[0] (position 0): {pe[0, :8]}")
print(f"PE[1] (position 1): {pe[1, :8]}")

# Verify: dot product depends on relative distance
def pe_similarity(pe, pos1, pos2):
    return np.dot(pe[pos1], pe[pos2])

# Positions close together have higher similarity
print(f"\nSimilarity PE[10]·PE[11] = {pe_similarity(pe, 10, 11):.3f}")
print(f"Similarity PE[10]·PE[12] = {pe_similarity(pe, 10, 12):.3f}")
print(f"Similarity PE[10]·PE[50] = {pe_similarity(pe, 10, 50):.3f}")
```

### Fourier Neural Operator

```python
# Conceptual: Fourier layer in FNO
class FourierLayer:
    """Fourier Neural Operator layer (conceptual).
    
    1. FFT the input
    2. Multiply by learnable weights in frequency domain
    3. IFFT back to spatial domain
    4. Add residual connection
    """
    def __init__(self, modes, width):
        self.modes = modes  # Number of Fourier modes to keep
        # Learnable complex weights for frequency modes
        self.weights = np.random.randn(modes, width, width) + \
                      1j * np.random.randn(modes, width, width)
    
    def forward(self, x):
        # x shape: (batch, spatial_dim, channels)
        x_ft = np.fft.rfft(x, axis=1)  # To frequency domain
        
        # Multiply selected modes by learnable weights
        out_ft = np.zeros_like(x_ft)
        out_ft[:, :self.modes, :] = np.einsum(
            'bmi,mio->bmo', x_ft[:, :self.modes, :], self.weights
        )
        
        # Back to spatial domain
        return np.fft.irfft(out_ft, axis=1)
```

---

## 8. Audio/Speech ML Foundation

### The Audio ML Pipeline

```
Raw Waveform → Pre-emphasis → Framing → Windowing → FFT → Mel Filter Bank → Log → DCT → MFCC
     ↓              ↓            ↓          ↓         ↓          ↓             ↓          ↓
 Time domain   Boost high   Short segments  Smooth  Frequency  Perceptual   Compress    Decorrelate
               frequencies   (20-40ms)     edges    spectrum    scale       dynamics
```

```python
def audio_feature_pipeline(waveform, sr=16000):
    """Extract audio features for ML models."""
    
    # 1. Pre-emphasis (boost high frequencies)
    pre_emphasis = 0.97
    emphasized = np.append(waveform[0], waveform[1:] - pre_emphasis * waveform[:-1])
    
    # 2. Framing (split into overlapping windows)
    frame_size = int(0.025 * sr)   # 25ms frames
    frame_stride = int(0.010 * sr)  # 10ms hop
    num_frames = (len(emphasized) - frame_size) // frame_stride + 1
    
    frames = np.zeros((num_frames, frame_size))
    for i in range(num_frames):
        start = i * frame_stride
        frames[i] = emphasized[start:start + frame_size]
    
    # 3. Windowing (Hamming window to reduce spectral leakage)
    window = np.hamming(frame_size)
    frames *= window
    
    # 4. FFT → Power spectrum
    NFFT = 512
    mag_frames = np.abs(np.fft.rfft(frames, NFFT))
    pow_frames = mag_frames ** 2 / NFFT
    
    # 5. Mel filter bank
    n_mels = 40
    mel_filters = compute_mel_filterbank(n_mels, NFFT, sr)
    mel_spec = pow_frames @ mel_filters.T  # Apply filter bank
    
    # 6. Log compression
    log_mel_spec = np.log(mel_spec + 1e-8)
    
    # 7. DCT → MFCC (optional, take first 13 coefficients)
    from scipy.fft import dct
    mfcc = dct(log_mel_spec, type=2, axis=1, norm='ortho')[:, :13]
    
    return log_mel_spec, mfcc

def compute_mel_filterbank(n_mels, nfft, sr):
    """Compute Mel-scale triangular filter bank."""
    # Mel scale: mel = 2595 * log10(1 + f/700)
    def hz_to_mel(hz): return 2595 * np.log10(1 + hz / 700)
    def mel_to_hz(mel): return 700 * (10**(mel / 2595) - 1)
    
    mel_low = hz_to_mel(0)
    mel_high = hz_to_mel(sr / 2)
    mel_points = np.linspace(mel_low, mel_high, n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    
    bin_points = np.floor((nfft + 1) * hz_points / sr).astype(int)
    
    filters = np.zeros((n_mels, nfft // 2 + 1))
    for i in range(n_mels):
        for j in range(bin_points[i], bin_points[i+1]):
            filters[i, j] = (j - bin_points[i]) / (bin_points[i+1] - bin_points[i])
        for j in range(bin_points[i+1], bin_points[i+2]):
            filters[i, j] = (bin_points[i+2] - j) / (bin_points[i+2] - bin_points[i+1])
    
    return filters

# Why spectrograms, not raw waveforms?
# - Raw audio at 16kHz = 16000 samples/second (too long for attention)
# - Spectrogram: ~100 frames/second × 80 mel bins (much more compact)
# - Frequency representation matches human perception
# - Modern models: Whisper, Wav2Vec2, HuBERT all use spectrograms or learned equivalents
```

---

## Exercises

### Exercise 1: DFT by Hand
Compute the 4-point DFT of x = [1, 0, -1, 0].

**Solution:**
```python
x = np.array([1, 0, -1, 0])
N = 4
# X[k] = Σ x[n] * e^(-j2πkn/4)
# X[0] = 1 + 0 + (-1) + 0 = 0
# X[1] = 1*1 + 0*(-j) + (-1)*(-1) + 0*(j) = 1 + 1 = 2
# X[2] = 1*1 + 0*1 + (-1)*1 + 0*1 = 0
# X[3] = 1*1 + 0*(j) + (-1)*(-1) + 0*(-j) = 2
print(np.fft.fft(x))  # [0+0j, 2+0j, 0+0j, 2+0j]
```

### Exercise 2: Frequency Detection
Given a signal sampled at 1000 Hz containing frequencies 50 Hz and 120 Hz, write code to detect these.

**Solution:**
```python
fs = 1000
t = np.arange(0, 1, 1/fs)
signal = np.sin(2*np.pi*50*t) + 0.5*np.sin(2*np.pi*120*t)
X = np.fft.fft(signal)
freqs = np.fft.fftfreq(len(signal), 1/fs)
magnitudes = np.abs(X[:len(X)//2]) / (len(X)//2)
peaks = np.where(magnitudes > 0.3)[0]
print(f"Detected: {freqs[peaks]} Hz")  # [50, 120]
```

### Exercise 3: FFT-based Denoising
Remove noise from a signal containing a 10 Hz sine wave buried in noise.

**Solution:**
```python
fs, duration = 200, 2
t = np.arange(0, duration, 1/fs)
clean = np.sin(2*np.pi*10*t)
noisy = clean + 0.8*np.random.randn(len(t))

X = np.fft.fft(noisy)
freqs = np.fft.fftfreq(len(noisy), 1/fs)
X[np.abs(freqs) > 15] = 0  # Keep only frequencies below 15 Hz
denoised = np.real(np.fft.ifft(X))
print(f"MSE before: {np.mean((noisy-clean)**2):.3f}")
print(f"MSE after:  {np.mean((denoised-clean)**2):.3f}")
```

### Exercise 4: Verify Convolution Theorem
Show that convolution in time = multiplication in frequency.

**Solution:**
```python
a = np.random.randn(50)
b = np.random.randn(30)
N = len(a) + len(b) - 1

conv_direct = np.convolve(a, b)
conv_fft = np.real(np.fft.ifft(np.fft.fft(a, N) * np.fft.fft(b, N)))
print(f"Max error: {np.max(np.abs(conv_direct - conv_fft)):.2e}")  # ~1e-14
```

### Exercise 5: Image Frequency Analysis
Apply a high-pass filter to an image using 2D FFT.

**Solution:**
```python
image = np.random.randn(128, 128)  # Use real image in practice
F = np.fft.fftshift(np.fft.fft2(image))
rows, cols = image.shape
crow, ccol = rows//2, cols//2
# High-pass: remove low frequencies (center)
F[crow-10:crow+10, ccol-10:ccol+10] = 0
edges = np.real(np.fft.ifft2(np.fft.ifftshift(F)))
```

### Exercise 6: Positional Encoding Properties
Verify that PE similarity decreases with distance.

**Solution:**
```python
pe = positional_encoding(200, 128)
distances = [1, 5, 10, 50, 100]
for d in distances:
    sims = [np.dot(pe[i], pe[i+d]) for i in range(50)]
    print(f"Distance {d:3d}: avg similarity = {np.mean(sims):.3f}")
```

### Exercise 7: Spectral Seasonality Detection
Detect weekly and monthly patterns in synthetic sales data.

**Solution:**
```python
days = 365*2
t = np.arange(days)
sales = 100 + 20*np.sin(2*np.pi*t/7) + 10*np.sin(2*np.pi*t/30) + 5*np.random.randn(days)

X = np.fft.fft(sales - np.mean(sales))
freqs = np.fft.fftfreq(days, d=1)
power = np.abs(X[:days//2])**2
top5 = np.argsort(power)[-5:]
for idx in top5:
    if freqs[idx] > 0:
        print(f"Period: {1/freqs[idx]:.1f} days")
```

### Exercise 8: MFCC Feature Extraction
Implement and explain each step of MFCC extraction for a synthetic signal.

**Solution:**
```python
# Generate synthetic "vowel" (fundamental + harmonics)
sr = 16000
t = np.arange(0, 0.5, 1/sr)
vowel = np.sin(2*np.pi*150*t) + 0.5*np.sin(2*np.pi*300*t) + 0.3*np.sin(2*np.pi*450*t)
vowel += 0.1*np.random.randn(len(t))

log_mel, mfcc = audio_feature_pipeline(vowel, sr)
print(f"Log-mel spectrogram: {log_mel.shape}")  # (frames, 40)
print(f"MFCC: {mfcc.shape}")  # (frames, 13)
print(f"First frame MFCC: {mfcc[0]}")
```

---

## Interview Questions

**Q1: Why do CNNs work as frequency filters?**
A: Convolution theorem — spatial convolution equals frequency multiplication. Each learned kernel amplifies/suppresses specific frequency bands. Small kernels (3×3) act as high-pass filters (edges), large kernels as low-pass (smooth features).

**Q2: Why does the Transformer use sinusoidal positional encoding?**
A: Sinusoids form a Fourier basis where each dimension encodes position at a different frequency. Key property: PE(pos+k) is a linear transform of PE(pos), allowing the model to learn relative position attention. The geometric frequency spacing covers both fine and coarse positional information.

**Q3: When would you use FFT-based convolution instead of direct convolution in a neural network?**
A: When kernel size is large. Direct convolution is O(N×K), FFT-based is O(N log N). For typical CNN kernels (3×3, 5×5), direct is faster. For large kernels (>64) or global convolution (like in FNO), FFT wins.

**Q4: What is aliasing and why does it matter for ML on time series?**
A: Aliasing occurs when sampling rate < 2× highest frequency (violating Nyquist). High frequencies fold back as spurious low frequencies. For ML: if your data has high-frequency components you can't sample fast enough, you'll learn false patterns. Solution: anti-aliasing filter before downsampling.

**Q5: Explain Random Fourier Features and when you'd use them.**
A: RFF approximates shift-invariant kernels (like RBF) by mapping inputs to random sinusoidal features. Inner product in feature space ≈ kernel evaluation. Use when: kernel SVM is too expensive (O(N²) memory), you want kernel-like nonlinearity with linear model scalability, or in attention mechanisms for linear-time approximation.
