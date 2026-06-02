# Multimodal AI

## 1. What is Multimodal AI?

```
DEFINITION:
Models that can understand, process, and generate across multiple data types:
├── Text (natural language)
├── Images (photos, diagrams, screenshots)
├── Audio (speech, music, sound effects)
├── Video (sequences of frames + audio)
└── Other: 3D, sensor data, code, structured data

WHY IT MATTERS:
- The real world is multimodal — humans use all senses together
- Text-only AI misses 90% of information (charts, photos, tone of voice)
- Enables richer applications: describe images, generate from text, transcribe speech

THE KEY INSIGHT — SHARED EMBEDDING SPACE:
┌─────────┐     ┌──────────┐     ┌─────────────────────┐
│  Image  │────▶│ Encoder  │────▶│                     │
└─────────┘     └──────────┘     │                     │
┌─────────┐     ┌──────────┐     │  Shared Embedding   │
│  Text   │────▶│ Encoder  │────▶│       Space         │
└─────────┘     └──────────┘     │  (512-d or 768-d)   │
┌─────────┐     ┌──────────┐     │                     │
│  Audio  │────▶│ Encoder  │────▶│                     │
└─────────┘     └──────────┘     └─────────────────────┘

All modalities map to the SAME vector space:
- "a photo of a cat" is NEAR an actual cat image
- Enables cross-modal retrieval, zero-shot transfer, generation

EVOLUTION:
2020: CLIP (image + text alignment)
2021: DALL-E (text → image generation)
2022: Whisper (robust speech recognition)
      Stable Diffusion (open-source image generation)
2023: GPT-4V (vision-language reasoning)
      LLaVA (open-source VLM)
2024: GPT-4o (natively multimodal)
      Gemini 1.5 (million-token multimodal context)
      Sora (text → video)
```

---

## 2. CLIP (Contrastive Language-Image Pre-training)

```
ARCHITECTURE:
├── Image Encoder: ViT (Vision Transformer) or ResNet
│   Image → patches → transformer → image embedding (512-d)
├── Text Encoder: Transformer (GPT-style, 12 layers)
│   Text → BPE tokens → transformer → text embedding (512-d)
├── Training: Contrastive learning on 400M image-text pairs from internet
│   ├── Positive pairs: matching image-text (diagonal of matrix)
│   ├── Negative pairs: all other combinations in batch (off-diagonal)
│   └── Loss: InfoNCE (maximize cosine similarity for positives)
└── Inference: Encode image + encode text → cosine similarity score

CONTRASTIVE LEARNING VISUALIZED (batch size = 4):

                    Text₁   Text₂   Text₃   Text₄
        Image₁  [  ✓       ✗       ✗       ✗   ]
        Image₂  [  ✗       ✓       ✗       ✗   ]
        Image₃  [  ✗       ✗       ✓       ✗   ]
        Image₄  [  ✗       ✗       ✗       ✓   ]

    ✓ = maximize similarity (positive pair)
    ✗ = minimize similarity (negative pair)

    With batch size 32768: each positive has 32767 negatives!

LOSS FUNCTION (InfoNCE):
    L = -log( exp(sim(I_i, T_i)/τ) / Σⱼ exp(sim(I_i, T_j)/τ) )
    
    τ = temperature parameter (learned, starts at 0.07)
    sim = cosine similarity

WHY IT'S REVOLUTIONARY:
- Zero-shot image classification (no fine-tuning needed!)
  Just compare image embedding to text embeddings of class names
- Learned from NATURAL language supervision (not curated labels)
- Transfers to any visual concept expressible in language
- Foundation for DALL-E, Stable Diffusion, and all modern VLMs

ZERO-SHOT CLASSIFICATION:
┌──────────┐         ┌───────────────────────────┐
│  Image   │────────▶│ Image Embedding [512-d]   │──┐
└──────────┘         └───────────────────────────┘  │
                                                     │ cosine
"a photo of a cat"  ──▶ Text Embedding [512-d] ─────┤ similarity
"a photo of a dog"  ──▶ Text Embedding [512-d] ─────┤
"a photo of a car"  ──▶ Text Embedding [512-d] ─────┘
                                                     │
                                              argmax → "cat"
```

### CLIP Usage Example

```python
from transformers import CLIPModel, CLIPProcessor
from PIL import Image

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Zero-shot classification
image = Image.open("photo.jpg")
inputs = processor(
    text=["a photo of a cat", "a photo of a dog", "a photo of a bird"],
    images=image,
    return_tensors="pt",
    padding=True
)
outputs = model(**inputs)
similarity = outputs.logits_per_image.softmax(dim=1)
# → [0.92, 0.05, 0.03] → "cat"!

# Image search with natural language
query = "sunset over mountains"
query_embedding = model.get_text_features(**processor(text=[query], return_tensors="pt"))
# Compare against database of image embeddings → nearest neighbors
```

```
APPLICATIONS:
├── Image search engines (embed images + query with text)
├── Content moderation (is this image NSFW? violent?)
├── Product matching (photo → find similar products by description)
├── Zero-shot classification (no training data needed for new classes)
├── Image clustering and organization
├── Foundation for generative models (DALL-E, Stable Diffusion)
└── Recommendation systems (cross-modal similarity)

LIMITATIONS:
- Struggles with spatial relationships ("cat LEFT of dog")
- Poor at counting ("three cats")
- Biased by internet training data
- Not great at fine-grained distinctions (bird species)
```

---

## 3. Stable Diffusion / DALL-E (Image Generation)

```
ARCHITECTURE (Stable Diffusion):
┌────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  "A cat sitting on a rainbow"                                        │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                    │
│  │ CLIP Text    │ → text embeddings (77 × 768)                       │
│  │ Encoder      │   (frozen, from CLIP)                              │
│  └──────────────┘                                                    │
│         │                                                            │
│         │ cross-attention                                             │
│         ▼                                                            │
│  ┌──────────────┐     ┌──────────┐     ┌──────────────┐            │
│  │   Random     │────▶│  U-Net   │────▶│  Denoised    │            │
│  │   Noise      │     │(denoise) │     │  Latent      │            │
│  │  64×64×4     │     └──────────┘     │  64×64×4     │            │
│  └──────────────┘      ↑ repeat        └──────────────┘            │
│                         50 steps               │                     │
│                                                ▼                     │
│                                        ┌──────────────┐            │
│                                        │  VAE Decoder │            │
│                                        │ 64×64 → 512  │            │
│                                        └──────────────┘            │
│                                                │                     │
│                                                ▼                     │
│                                        Final Image 512×512           │
└────────────────────────────────────────────────────────────────────┘

KEY COMPONENTS:

1. VAE (Variational Autoencoder):
   - Encoder: 512×512×3 image → 64×64×4 latent (64× compression!)
   - Decoder: 64×64×4 latent → 512×512×3 image
   - WHY: Diffusion in latent space is 64× cheaper than pixel space

2. U-Net (Denoising Network):
   - Input: noisy latent + timestep + text condition
   - Output: predicted noise (ε)
   - Architecture: encoder-decoder with skip connections
   - Cross-attention layers inject text conditioning
   - ~860M parameters (the workhorse)

3. Text Encoder (CLIP):
   - Converts text prompt to embeddings
   - Frozen during training (pre-trained CLIP)
   - Cross-attention: U-Net attends to these text embeddings

4. Scheduler (Noise Schedule):
   - Defines how much noise at each timestep
   - DDPM, DDIM, Euler, DPM-Solver (different speed/quality tradeoffs)

TRAINING PROCESS:
1. Take clean image x₀, encode to latent z₀ with VAE
2. Sample random timestep t ∈ [1, 1000]
3. Add noise: z_t = √(ᾱ_t) * z₀ + √(1-ᾱ_t) * ε    (ε ~ N(0,1))
4. Train U-Net to predict ε given (z_t, t, text_embedding)
5. Loss = MSE(ε_predicted, ε_actual)

INFERENCE (e.g., 50 steps with DDIM):
z_T ~ N(0,1)          ← Start from pure random noise
for t = T, T-1, ..., 1:
    ε_pred = UNet(z_t, t, text_emb)    ← Predict noise
    z_{t-1} = scheduler.step(ε_pred)    ← Remove predicted noise
z_0 = VAE.decode(z_final)              ← Decode to pixel space

CLASSIFIER-FREE GUIDANCE (CFG):
- Key trick for quality vs. diversity tradeoff
- During training: randomly drop text condition (10% of time)
- During inference: run U-Net twice per step
    ε_uncond = UNet(z_t, t, "")           ← unconditional
    ε_cond   = UNet(z_t, t, text_emb)     ← conditional
    ε_guided = ε_uncond + scale * (ε_cond - ε_uncond)
- guidance_scale = 7.5 typical (higher = more faithful but less diverse)
```

### Key Concepts

```
NEGATIVE PROMPTS:
- Tell the model what NOT to generate
- "blurry, low quality, deformed hands, extra fingers"
- Works via CFG: pushes away from negative embedding

CONTROLNET:
- Additional conditioning beyond text
- Inputs: depth maps, edge detection, pose skeleton, segmentation
- Architecture: Copies of U-Net encoder (locked original + trainable copy)
- Enables precise spatial control while keeping text guidance

LoRA (Low-Rank Adaptation):
- Fine-tune for specific styles/characters with tiny models (4-64 MB)
- Injects low-rank matrices into attention layers
- Can combine multiple LoRAs (style + character + lighting)

img2img:
- Start from existing image (add noise to it), not pure noise
- strength parameter: 0.0 = no change, 1.0 = complete redraw
- Use for: style transfer, image enhancement, variations

INPAINTING:
- Mask part of image, regenerate only masked region
- Model sees: masked image + mask + text prompt
- Use for: object removal, background replacement, fixes

SDXL vs SD 1.5 vs SD 2.1:
├── SD 1.5: 512×512, most LoRAs available, community favorite
├── SD 2.1: 768×768, different text encoder, less community support
├── SDXL: 1024×1024, two-stage (base + refiner), best quality
└── SD 3/Flux: Latest, Flow Matching instead of DDPM, best text rendering
```

---

## 4. Whisper (Speech Recognition)

```
ARCHITECTURE:
┌────────────────────────────────────────────────────────────┐
│                                                              │
│  Audio Input (up to 30 seconds)                              │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────┐                                        │
│  │ Mel Spectrogram  │  80 channels, 25ms windows, 10ms hop   │
│  │ (preprocessing)  │  → 80 × 3000 (for 30s audio)          │
│  └──────────────────┘                                        │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────┐                                        │
│  │ Transformer      │  Conv1D (2 layers) → Transformer       │
│  │ Encoder          │  Sinusoidal positional encoding         │
│  │ (audio → features)│  Output: encoder hidden states        │
│  └──────────────────┘                                        │
│       │                                                      │
│       │ cross-attention                                       │
│       ▼                                                      │
│  ┌──────────────────┐                                        │
│  │ Transformer      │  Autoregressive text generation         │
│  │ Decoder          │  Learned positional encoding            │
│  │ (features → text)│  Output: text tokens                   │
│  └──────────────────┘                                        │
│       │                                                      │
│       ▼                                                      │
│  "Hello, how are you today?"                                 │
└────────────────────────────────────────────────────────────┘

MULTI-TASK FORMAT (special tokens):
<|startoftranscript|>
<|en|>                    ← language token (detected or specified)
<|transcribe|>            ← task: transcribe OR translate
<|notimestamps|>          ← or timestamp tokens <|0.00|><|2.50|>
Hello, how are you today?
<|endoftext|>

WHY WHISPER IS SPECIAL:
- Trained on 680,000 hours of labeled audio (web-scale supervision)
- Multilingual: 99 languages (auto-detects language)
- Multi-task: transcribe, translate to English, timestamp, detect language
- Robust to: noise, accents, background music, multiple speakers
- No fine-tuning needed for most use cases

MODEL SIZES:
┌─────────┬─────────┬────────────────┬─────────────┬────────────────┐
│  Model  │ Params  │ Relative Speed │ English WER │   VRAM Need    │
├─────────┼─────────┼────────────────┼─────────────┼────────────────┤
│  tiny   │   39M   │      32×       │    7.6%     │    ~1 GB       │
│  base   │   74M   │      16×       │    5.0%     │    ~1 GB       │
│  small  │  244M   │       6×       │    3.4%     │    ~2 GB       │
│  medium │  769M   │       2×       │    2.9%     │    ~5 GB       │
│  large  │ 1550M   │       1×       │    2.7%     │   ~10 GB       │
│large-v3 │ 1550M   │       1×       │    2.5%     │   ~10 GB       │
└─────────┴─────────┴────────────────┴─────────────┴────────────────┘

WER = Word Error Rate (lower is better)
```

### Whisper Usage

```python
import whisper

model = whisper.load_model("base")  # tiny/base/small/medium/large

# Simple transcription
result = model.transcribe("audio.mp3")
print(result["text"])

# With timestamps
result = model.transcribe("audio.mp3", word_timestamps=True)
for segment in result["segments"]:
    print(f"[{segment['start']:.1f}s - {segment['end']:.1f}s] {segment['text']}")

# Translation (any language → English)
result = model.transcribe("french_audio.mp3", task="translate")

# Language detection
audio = whisper.load_audio("unknown_language.mp3")
mel = whisper.log_mel_spectrogram(audio).to(model.device)
_, probs = model.detect_language(mel)
print(f"Detected: {max(probs, key=probs.get)}")  # → "fr"

# Faster inference with faster-whisper (CTranslate2)
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", compute_type="float16")
segments, info = model.transcribe("audio.mp3", beam_size=5)
for segment in segments:
    print(f"[{segment.start:.2f}s → {segment.end:.2f}s] {segment.text}")
```

---

## 5. Vision-Language Models (GPT-4V, LLaVA, Gemini)

```
HOW THEY WORK:
┌──────────────────────────────────────────────────────────────┐
│                                                                │
│  Image                    Text prompt                          │
│    │                         │                                 │
│    ▼                         │                                 │
│  ┌───────────────┐           │                                 │
│  │ Visual Encoder│           │                                 │
│  │ (CLIP ViT)    │           │                                 │
│  └───────────────┘           │                                 │
│    │                         │                                 │
│    ▼                         │                                 │
│  ┌───────────────┐           │                                 │
│  │  Projection   │           │                                 │
│  │  (MLP/Linear) │           │                                 │
│  └───────────────┘           │                                 │
│    │                         │                                 │
│    │  image tokens           │  text tokens                    │
│    ▼                         ▼                                 │
│  ┌────────────────────────────────────────┐                   │
│  │         Large Language Model            │                   │
│  │  [IMG][IMG][IMG]...[IMG] What is this? │                   │
│  │         (interleaved sequence)          │                   │
│  └────────────────────────────────────────┘                   │
│    │                                                           │
│    ▼                                                           │
│  "This is a photograph of a golden retriever playing fetch     │
│   in a park on a sunny day."                                   │
└──────────────────────────────────────────────────────────────┘

ARCHITECTURES COMPARED:

GPT-4V / GPT-4o (OpenAI):
├── Proprietary, best overall performance
├── Natively multimodal in GPT-4o (not bolted on)
├── Handles: text, images, audio, video (frames)
└── Excels at: reasoning, OCR, chart understanding, spatial

Gemini 1.5 (Google):
├── Natively multimodal from the ground up
├── 1M+ token context window (can process entire videos)
├── Handles: text, images, audio, video natively
└── Excels at: long-context, video understanding, multilingual

LLaVA (Open Source):
├── CLIP ViT-L/14 + Vicuna/LLaMA
├── Simple linear projection from vision to language space
├── 2-stage training: alignment → instruction tuning
└── Surprisingly competitive with proprietary models

Claude (Anthropic):
├── Strong vision understanding
├── Excels at: document analysis, chart reading, careful reasoning
└── Conservative on uncertain visual content

TRAINING (LLaVA Approach):
┌─────────────────────────────────────────────────────────┐
│ Stage 1: Feature Alignment (pre-training)                │
│ ├── Data: 558K image-caption pairs                       │
│ ├── Frozen: ViT encoder + LLM                           │
│ ├── Trainable: projection layer only                     │
│ └── Goal: align visual features to language token space  │
├─────────────────────────────────────────────────────────┤
│ Stage 2: Visual Instruction Tuning                       │
│ ├── Data: 150K visual instruction-following examples     │
│ ├── Frozen: ViT encoder                                 │
│ ├── Trainable: projection layer + LLM (full or LoRA)    │
│ └── Goal: follow complex instructions about images       │
└─────────────────────────────────────────────────────────┘

APPLICATIONS:
├── Document understanding (receipts, forms, contracts, charts)
├── Visual Q&A ("What color is the car in the background?")
├── Image captioning and detailed description
├── OCR replacement (just ask the model to read text in image)
├── Diagram and flowchart understanding
├── Code generation from UI screenshots
├── Accessibility (describe images for visually impaired users)
├── Medical image analysis (with appropriate fine-tuning)
└── Autonomous driving scene understanding
```

### VLM Usage

```python
# OpenAI GPT-4V
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image? Read any text."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]
    }]
)
print(response.choices[0].message.content)

# Open-source LLaVA with transformers
from transformers import LlavaForConditionalGeneration, AutoProcessor

model = LlavaForConditionalGeneration.from_pretrained("llava-hf/llava-1.5-7b-hf")
processor = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")

prompt = "USER: <image>\nDescribe this image in detail.\nASSISTANT:"
inputs = processor(text=prompt, images=image, return_tensors="pt")
output = model.generate(**inputs, max_new_tokens=200)
print(processor.decode(output[0], skip_special_tokens=True))
```

---

## 6. Text-to-Speech (TTS) and Speech Synthesis

```
MODERN APPROACHES:

┌─────────────────────────────────────────────────────────────┐
│ Traditional Pipeline:                                         │
│ Text → Phonemes → Acoustic Model → Vocoder → Waveform       │
│                                                               │
│ Modern End-to-End:                                            │
│ Text ──────────────────────────────────────→ Waveform        │
└─────────────────────────────────────────────────────────────┘

KEY MODELS:

1. VITS (Variational Inference TTS):
   ├── Text Encoder: Transformer → phoneme features
   ├── Stochastic Duration Predictor: phoneme → duration
   ├── Flow-based Decoder: generates mel-spectrogram
   └── HiFi-GAN: mel → waveform (neural vocoder)
   Quality: ★★★★☆  Speed: ★★★★★  Zero-shot: ✗

2. Bark (Suno AI):
   ├── GPT-style autoregressive generation
   ├── Text → semantic tokens → coarse acoustic → fine acoustic
   ├── Supports: speech, music, sound effects, laughter
   └── Can clone voices with short audio prompts
   Quality: ★★★★☆  Speed: ★★★☆☆  Zero-shot: ★★★☆☆

3. VALL-E (Microsoft):
   ├── Neural codec language model
   ├── 3-second voice sample → clone any voice
   ├── Treats TTS as language modeling on audio codec tokens
   └── Preserves emotion, speaking style, acoustic environment
   Quality: ★★★★★  Speed: ★★★☆☆  Zero-shot: ★★★★★

4. XTTS (Coqui TTS):
   ├── Open-source, multilingual voice cloning
   ├── 6-second reference audio for cloning
   └── 16 languages supported
   Quality: ★★★★☆  Speed: ★★★★☆  Zero-shot: ★★★★☆

5. Production APIs:
   ├── ElevenLabs: Best quality, voice cloning, emotion control
   ├── OpenAI TTS: Simple, good quality, 6 voices
   ├── Azure Neural TTS: Enterprise, SSML control, many voices
   └── Play.ht: Ultra-realistic, API-first

USAGE (OpenAI TTS):
```

```python
from openai import OpenAI
client = OpenAI()

response = client.audio.speech.create(
    model="tts-1-hd",      # tts-1 (fast) or tts-1-hd (quality)
    voice="alloy",          # alloy, echo, fable, onyx, nova, shimmer
    input="Hello! This is a test of text to speech."
)
response.stream_to_file("output.mp3")

# Coqui XTTS (open source, voice cloning)
from TTS.api import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
tts.tts_to_file(
    text="Hello world!",
    speaker_wav="reference_voice.wav",  # 6s sample to clone
    language="en",
    file_path="output.wav"
)
```

---

## 7. Video Understanding

```
APPROACHES:

1. Frame Sampling + Image Model (Simplest):
   Video → sample N frames → process each with VLM → aggregate
   ├── Pros: Simple, uses existing image models
   ├── Cons: Misses temporal relationships, motion
   └── Use when: You have GPT-4V/Gemini and short videos

2. TimeSformer (Meta):
   ├── Divided Space-Time Attention
   │   Each patch attends to: same-frame patches + same-position across time
   ├── Efficient: O(S + T) instead of O(S × T) attention
   └── Pre-trained on Kinetics-400/600

3. VideoMAE (Self-supervised):
   ├── Masked autoencoder for video (mask 90% of patches!)
   ├── Forces model to learn temporal dynamics
   └── State-of-art on action recognition after fine-tuning

4. LLM-based Video Understanding:
   ├── Gemini 1.5: Feed entire video (up to hours), natively
   ├── GPT-4o: Process sampled frames as images
   ├── Video-LLaVA: Open-source video + language model
   └── Best for: complex reasoning, Q&A about video content

TEMPORAL ATTENTION PATTERNS:
┌───────────────────────────────────────┐
│ Frame 1:  [P1] [P2] [P3] [P4]        │
│ Frame 2:  [P1] [P2] [P3] [P4]        │
│ Frame 3:  [P1] [P2] [P3] [P4]        │
│                                         │
│ Spatial attention: P1↔P2↔P3↔P4        │
│ Temporal attention: P1_f1↔P1_f2↔P1_f3 │
└───────────────────────────────────────┘

APPLICATIONS:
├── Action recognition ("person is playing tennis")
├── Video summarization (extract key moments)
├── Temporal grounding ("when does the goal happen?" → 2:34-2:37)
├── Video Q&A ("how many people are in the room at the end?")
├── Surveillance and anomaly detection
├── Sports analytics (player tracking, event detection)
├── Content moderation (detect harmful video content)
└── Video captioning and description

PRACTICAL VIDEO PROCESSING:
```

```python
# Gemini approach (best for long videos)
import google.generativeai as genai

model = genai.GenerativeModel("gemini-1.5-pro")
video = genai.upload_file("video.mp4")
response = model.generate_content([
    video,
    "Summarize this video. What are the key events and when do they happen?"
])

# Frame sampling approach (works with any VLM)
import cv2
from openai import OpenAI

def extract_frames(video_path, num_frames=10):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = [int(i * total / num_frames) for i in range(num_frames)]
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
    return frames
```

---

## 8. Building Multimodal Applications

```
PRACTICAL PATTERNS:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATTERN 1: EMBED EVERYTHING (Retrieval/Search)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use Case: Cross-modal search, similarity, clustering
Model: CLIP (or SigLIP, BLIP-2)

┌─────────┐     ┌──────┐     ┌────────────┐
│ Images  │────▶│ CLIP │────▶│            │
│ (1M)    │     │ ViT  │     │  Vector DB │  ← Index all embeddings
└─────────┘     └──────┘     │ (Pinecone, │
                              │  Qdrant)   │
"red sports car" ──▶ CLIP ──▶│            │  ← Query with text
                              └────────────┘
                                    │
                                    ▼
                              Top-K similar images

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATTERN 2: LLM AS REASONING ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use Case: Complex reasoning about visual/audio content
Model: GPT-4o, Gemini, LLaVA

┌─────────┐     ┌─────────┐
│  Image  │────▶│  VLM    │────▶ "The chart shows revenue grew 23%
│  Audio  │────▶│(GPT-4o) │      in Q3, mainly driven by the APAC
│  Video  │────▶│         │      region as shown in the blue bars"
└─────────┘     └─────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATTERN 3: GENERATION PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Direction         │ Model                    │ Use Case
──────────────────┼──────────────────────────┼─────────────────────
Text → Image      │ DALL-E 3, SD, Flux       │ Art, marketing, design
Text → Audio      │ Bark, ElevenLabs         │ Narration, podcasts
Text → Video      │ Sora, Runway, Kling      │ Ads, content creation
Text → 3D         │ Point-E, Shap-E          │ Game assets, products
Image → Text      │ GPT-4o, LLaVA            │ Captioning, OCR, Q&A
Audio → Text      │ Whisper                  │ Transcription
Image → Image     │ SD img2img, ControlNet   │ Style transfer, editing
Audio → Audio     │ AudioCraft               │ Music generation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATTERN 4: MULTIMODAL RAG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Documents with images/charts/tables:
1. Extract: text chunks + images + tables from PDFs
2. Embed: text with text embedder, images with CLIP
3. Store: both in vector DB with metadata
4. Query: embed query, retrieve relevant chunks AND images
5. Answer: send text + images to VLM for grounded response

CHOOSING AN APPROACH:
┌─────────────────────────────────────────────────────────────┐
│ Need understanding/reasoning? → VLM (GPT-4o, Gemini, LLaVA)│
│ Need image generation?        → Diffusion (DALL-E, SD, Flux)│
│ Need embeddings/search?       → CLIP or SigLIP              │
│ Need transcription?           → Whisper                     │
│ Need voice synthesis?         → TTS (ElevenLabs, XTTS)     │
│ Need video understanding?     → Gemini 1.5 or frame+VLM    │
│ Need real-time processing?    → Smaller models + streaming  │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Fine-tuning Multimodal Models

```
CLIP FINE-TUNING:
├── When: Domain-specific retrieval (medical, satellite, fashion)
├── Approach: Contrastive fine-tuning on domain image-text pairs
├── Data needed: 10K-100K domain pairs
├── Tips:
│   ├── Use low learning rate (1e-6 to 1e-5)
│   ├── Freeze early layers, fine-tune later layers
│   └── Use hard negatives for better discrimination
└── Libraries: open_clip, transformers

STABLE DIFFUSION LoRA:
├── When: Custom styles, characters, products, branding
├── Approach: Train low-rank adapters on 5-50 images
├── Data needed: 5-50 images of target concept
├── Training:
│   ├── Choose trigger word: "sks style", "ohwx person"
│   ├── Rank: 4-128 (higher = more capacity, larger file)
│   ├── Steps: 500-3000 (watch for overfitting)
│   └── Tools: kohya-ss, diffusers train_dreambooth_lora.py
├── Result: 4-64 MB file, composable with other LoRAs
└── DreamBooth: Alternative for subject-driven generation

WHISPER FINE-TUNING:
├── When: Domain-specific vocabulary (medical, legal, technical)
├── Approach: Fine-tune decoder on domain transcripts
├── Data needed: 10-100 hours of domain audio + transcripts
├── Tools: transformers Seq2SeqTrainer
├── Tips:
│   ├── Use whisper-large-v3 as base
│   ├── Low learning rate (1e-5)
│   └── Augment with noise, speed perturbation
└── Result: 5-50% WER reduction on domain-specific terms

VLM FINE-TUNING (LLaVA-style):
├── When: Custom visual tasks, domain Q&A, specific output formats
├── Approach: LoRA on LLM backbone, keep vision encoder frozen
├── Data needed: 1K-50K instruction-image-response triplets
├── Format: [{"image": "path.jpg", "conversations": [...]}]
├── Tools: LLaVA repo, transformers + PEFT
└── Tips: Start with high-quality data, not just quantity
```

---

## 10. Production Considerations

```
LATENCY BENCHMARKS:
┌────────────────────────┬──────────────┬─────────────────────┐
│ Task                   │ Typical Time │ Optimization         │
├────────────────────────┼──────────────┼─────────────────────┤
│ CLIP embedding         │ 10-50ms      │ ONNX, TensorRT      │
│ Whisper transcription  │ Real-time*   │ faster-whisper, int8 │
│ VLM inference (GPT-4o) │ 2-8s         │ Batching, caching    │
│ SD image generation    │ 2-30s        │ LCM (4 steps!), TRT │
│ TTS synthesis          │ 0.5-3s       │ Streaming, VITS      │
│ Video understanding    │ 5-30s        │ Frame sampling       │
└────────────────────────┴──────────────┴─────────────────────┘
* Whisper can run faster than real-time with optimizations

COST CONSIDERATIONS:
├── GPU-intensive: All multimodal models need GPUs for inference
├── Image generation: $0.02-0.12 per image (API) or ~$0.002 self-hosted
├── Transcription: $0.006/min (Whisper API) or free self-hosted
├── VLM: $0.01-0.03 per image + text tokens
├── Self-hosting: A100 ($2-3/hr), T4 ($0.50/hr) for smaller models
└── Optimization: Quantization (int8/int4) reduces cost 2-4×

SAFETY & MODERATION:
├── Generated content risks:
│   ├── NSFW content generation
│   ├── Deepfakes (face swapping, voice cloning)
│   ├── Misinformation (realistic fake images)
│   └── Copyright infringement (style mimicry)
├── Mitigations:
│   ├── NSFW classifiers on outputs (CLIP-based)
│   ├── Watermarking (invisible markers in generated content)
│   ├── Content policies and prompt filtering
│   ├── Rate limiting and user verification
│   └── C2PA metadata (content provenance)
└── Regulations: EU AI Act, state deepfake laws

EVALUATION METRICS:
├── Image Generation:
│   ├── FID (Fréchet Inception Distance) — lower = better distribution match
│   ├── CLIP Score — text-image alignment
│   └── Human preference (ELO ratings)
├── Speech Recognition:
│   ├── WER (Word Error Rate) — lower = better
│   └── CER (Character Error Rate)
├── Vision-Language:
│   ├── VQA accuracy (Visual Question Answering benchmarks)
│   ├── MMMU, MMBench (multimodal understanding benchmarks)
│   └── OCR accuracy on document benchmarks
└── TTS:
    ├── MOS (Mean Opinion Score) — human rating 1-5
    ├── Speaker similarity (for cloning)
    └── WER of transcription of generated speech

SCALING ARCHITECTURE:
┌─────────────────────────────────────────────────────────────┐
│                   Load Balancer                               │
│                       │                                       │
│         ┌─────────────┼─────────────┐                       │
│         ▼             ▼             ▼                        │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│   │  API GW  │ │  API GW  │ │  API GW  │                   │
│   └──────────┘ └──────────┘ └──────────┘                   │
│         │             │             │                        │
│         ▼             ▼             ▼                        │
│   ┌──────────────────────────────────────┐                  │
│   │         Task Queue (Redis/SQS)        │                  │
│   └──────────────────────────────────────┘                  │
│         │             │             │                        │
│         ▼             ▼             ▼                        │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│   │ GPU Worker│ │ GPU Worker│ │ GPU Worker│  (autoscale)     │
│   │ (SD/LLM) │ │ (Whisper)│ │ (CLIP)   │                   │
│   └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────┘

Key patterns:
- Async processing for generation tasks (webhook on completion)
- Streaming for real-time (Whisper, TTS)
- Caching embeddings (CLIP vectors don't change for same input)
- Model serving: vLLM, TGI, Triton Inference Server
- Batching: Group requests for GPU efficiency
```

---

## Summary: The Multimodal AI Landscape

```
┌──────────────────────────────────────────────────────────────────┐
│                    MULTIMODAL AI STACK                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  UNDERSTANDING          GENERATION           EMBEDDING            │
│  ─────────────          ──────────           ─────────            │
│  GPT-4o                 DALL-E 3             CLIP                 │
│  Gemini 1.5             Stable Diffusion     SigLIP               │
│  LLaVA                  Sora                 ImageBind            │
│  Whisper                Bark/XTTS                                 │
│                         Flux                                      │
│                                                                    │
│  TASK ROUTER:                                                     │
│  "What is this?" → VLM    "Make me a..." → Generation            │
│  "Find similar" → CLIP    "Transcribe" → Whisper                 │
│                                                                    │
├──────────────────────────────────────────────────────────────────┤
│  KEY TAKEAWAYS:                                                   │
│  1. Shared embedding spaces enable cross-modal understanding      │
│  2. Diffusion models dominate generation (images, video, audio)   │
│  3. LLMs are becoming the universal reasoning layer               │
│  4. Open-source is competitive (LLaVA, Whisper, SD)              │
│  5. The trend: natively multimodal > bolted-on multimodal         │
└──────────────────────────────────────────────────────────────────┘
```
