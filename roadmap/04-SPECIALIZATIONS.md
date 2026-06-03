# Stage 4: Specializations (NLP + Computer Vision + Generative AI)

> Duration: 3-4 months per specialization | You must go deep in at least ONE, broad in both

---

## How to Approach This Stage

```
The Three Paths:
                              
         ┌─────────────────────────────────────────────┐
         │           YOUR DEEP LEARNING BASE            │
         │            (Stage 3 complete)                │
         └──────────────────┬──────────────────────────┘
                            │
              ┌─────────────┼─────────────────┐
              ▼             ▼                 ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │     NLP      │ │  Computer    │ │  Generative  │
     │   + LLMs     │ │   Vision     │ │     AI       │
     │              │ │              │ │              │
     │ If you want: │ │ If you want: │ │ If you want: │
     │ - Chatbots   │ │ - Robotics   │ │ - Image gen  │
     │ - Search     │ │ - Autonomous │ │ - Video gen  │
     │ - Agents     │ │ - Medical    │ │ - Music gen  │
     │ - Knowledge  │ │ - Satellite  │ │ - Multimodal │
     │   systems    │ │ - Retail/mfg │ │ - Creative   │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                 │
            │    PICK ONE PRIMARY              │
            │    Learn the other at 60%        │
            │                                  │
            └─────────────────┬────────────────┘
                              ▼
                    ┌──────────────────┐
                    │  MULTIMODAL      │
                    │  (The future is  │
                    │   combining all) │
                    └──────────────────┘

My honest recommendation for 2024-2026:
─────────────────────────────────────────
Primary: NLP + LLMs (market demand is insane, pays the most)
Secondary: Generative AI (overlaps heavily with NLP now)
Tertiary: Computer Vision (still critical, especially multimodal)
```

---

## PART A: NLP + Large Language Models

### The NLP Evolution (What You Need to Know)

```
ERA 1 (2013-2017): Word Embeddings
├── Word2Vec (Skip-gram, CBOW)
├── GloVe
├── FastText
└── Status: Still useful for lightweight applications

ERA 2 (2018-2019): Pretrained Transformers  
├── BERT (bidirectional, masked language modeling)
├── GPT-2 (autoregressive, left-to-right)
├── RoBERTa, ALBERT, DistilBERT
└── Status: BERT still used for classification/NER

ERA 3 (2020-2022): Scale Era
├── GPT-3 (175B params, few-shot learning)
├── T5 (text-to-text framework)
├── PaLM, Chinchilla (scaling laws)
└── Status: Defined the paradigm

ERA 4 (2023-present): The LLM Era
├── ChatGPT / GPT-4 (instruction following, RLHF)
├── LLaMA / Mistral / Mixtral (open-weight models)
├── Claude, Gemini (multimodal)
├── RAG (Retrieval Augmented Generation)
├── Agents (tool use, planning, code execution)
├── Fine-tuning: LoRA, QLoRA, PEFT
└── Status: THIS IS WHERE THE JOBS ARE
```

### Month 1: NLP Fundamentals + Hugging Face

**Week 1-2: Text Processing + Classical NLP**

```
Learn:
├── Tokenization (BPE, WordPiece, SentencePiece, Unigram)
│   └── This is NOT trivial. Tokenization affects EVERYTHING.
├── Text preprocessing (cleaning, normalization, when NOT to clean)
├── TF-IDF + BM25 (still powers most production search)
├── Named Entity Recognition (rule-based, then ML-based)
├── Sentiment analysis (lexicon-based, then learned)
├── Text classification pipeline (end to end)
└── Evaluation: accuracy, F1, confusion matrix for text tasks

Build:
├── Custom tokenizer (BPE from scratch -- Karpathy has a video)
├── Search engine using BM25 + TF-IDF on Wikipedia subset
└── Text classifier using TF-IDF + LogReg (surprisingly strong baseline!)
```

**Week 3-4: Hugging Face Ecosystem + Transformers**

```
Master the HF ecosystem (this is your daily toolkit):
├── transformers library
│   ├── AutoModel, AutoTokenizer, AutoConfig
│   ├── Pipeline API (quick inference)
│   ├── Fine-tuning with Trainer / native PyTorch
│   ├── Model Hub (find, download, upload models)
│   └── Tokenizer internals (special tokens, padding, truncation)
├── datasets library (load, process, stream any dataset)
├── evaluate library (metrics computation)
├── accelerate (multi-GPU, mixed precision)
├── peft library (LoRA, prefix tuning, adapters)
└── gradio (build demos in 10 lines)

Build:
├── Fine-tune BERT on custom text classification dataset
├── Fine-tune for NER (token classification)
├── Fine-tune for question answering (SQuAD-style)
├── Train a sentence embeddings model (sentence-transformers)
└── Deploy a model with Gradio and share publicly
```

**Resources:**

| Resource | Link |
|----------|------|
| Hugging Face NLP Course (free) | https://huggingface.co/learn/nlp-course |
| Stanford CS224n (2023) | https://web.stanford.edu/class/cs224n/ |
| "NLP with Transformers" (O'Reilly) | Book by HF founders |
| Karpathy: "Let's build the GPT tokenizer" | https://youtube.com/watch?v=zduSFxRajkE |
| Jay Alammar's blog (all illustrated guides) | https://jalammar.github.io/ |

### Month 2: LLMs, Fine-Tuning, and RAG

**Week 5-6: Working with LLMs**

```
Understand:
├── How GPT works (autoregressive, next-token prediction)
├── Scaling laws (Chinchilla: tokens vs parameters tradeoff)
├── Emergent abilities (in-context learning, chain-of-thought)
├── RLHF pipeline (SFT → Reward Model → PPO/DPO)
├── Constitutional AI / RLAIF
├── Tokenizer effects on multilingual / code performance
└── Context windows (how attention scales, RoPE, ALiBi)

Prompt Engineering (yes, this is a real skill):
├── Zero-shot, few-shot, chain-of-thought
├── System prompts, role prompting
├── Output formatting (JSON mode, structured output)
├── Self-consistency (sample multiple, take majority)
├── ReAct (Reason + Act -- for tool use)
└── Meta-prompting and prompt chaining

Fine-tuning LLMs:
├── When to fine-tune vs when to prompt
├── LoRA / QLoRA (fine-tune with 1% of parameters)
├── Full fine-tuning (when you have the compute)
├── Data preparation for instruction tuning
├── Evaluation of fine-tuned models (perplexity, downstream tasks)
├── Merging adapters (LoRA merge, TIES merging)
└── Quantization (GPTQ, AWQ, GGUF -- run models locally)
```

**Week 7-8: RAG (Retrieval Augmented Generation)**

```
RAG is the most practically useful LLM pattern. It lets you:
- Ground LLMs in your own data (no hallucination)
- Keep knowledge up-to-date (no retraining)
- Provide citations (verifiable answers)
- Work with private data (no training on sensitive docs)

Build a production RAG system:
├── Document Processing
│   ├── Chunking strategies (fixed size, semantic, recursive)
│   ├── Metadata extraction
│   ├── Document parsing (PDF, HTML, code, tables)
│   └── Cleaning and deduplication
├── Embedding & Indexing
│   ├── Embedding models (OpenAI, sentence-transformers, Cohere)
│   ├── Vector databases (Pinecone, Weaviate, Qdrant, ChromaDB, pgvector)
│   ├── Hybrid search (dense + sparse/BM25)
│   └── Re-ranking (cross-encoders, Cohere rerank)
├── Retrieval
│   ├── Similarity search (cosine, dot product)
│   ├── MMR (Maximal Marginal Relevance) for diversity
│   ├── Query expansion / HyDE
│   └── Multi-step retrieval (retrieve → refine → retrieve again)
├── Generation
│   ├── Context stuffing (simple but effective)
│   ├── Map-reduce (for long documents)
│   ├── Citation generation
│   └── Hallucination detection
└── Evaluation
    ├── Retrieval metrics (recall@k, MRR, NDCG)
    ├── Generation quality (faithfulness, relevance, coherence)
    ├── RAGAS framework
    └── Human evaluation protocols
```

**Resources:**

| Resource | Link |
|----------|------|
| LangChain docs (learn concepts, not necessarily the library) | https://python.langchain.com/docs/ |
| LlamaIndex docs | https://docs.llamaindex.ai/ |
| "Building LLM Powered Applications" (Valentino) | Book (2024) |
| Pinecone Learning Center | https://www.pinecone.io/learn/ |
| Lilian Weng: "LLM Powered Autonomous Agents" | https://lilianweng.github.io/posts/2023-06-23-agent/ |

### Month 3: Agents, Tool Use, and Production NLP

**Week 9-10: LLM Agents**

```
The frontier of NLP in 2024-2025:

Agent Architecture:
├── Planning (decompose complex task into steps)
├── Tool Use (call APIs, run code, search the web)
├── Memory (short-term: context, long-term: vector store)
├── Reflection (self-evaluate, retry on failure)
└── Multi-agent systems (debate, collaboration)

Build:
├── Simple ReAct agent (reasoning + tool calling)
├── Code execution agent (write + run Python)
├── Research agent (search + summarize + cite)
├── Multi-agent debate system
└── Agent with persistent memory

Frameworks to know:
├── LangChain / LangGraph (most popular, batteries-included)
├── LlamaIndex (data-focused, great for RAG)
├── CrewAI (multi-agent)
├── Autogen (Microsoft, multi-agent)
├── Raw API calls (sometimes better than frameworks!)
└── Function calling (OpenAI, Anthropic native tool use)
```

**Week 11-12: Production NLP Systems**

```
Taking NLP to production:
├── Serving LLMs
│   ├── vLLM (fast inference, paged attention)
│   ├── Text Generation Inference (TGI by HF)
│   ├── Ollama (local models)
│   ├── API providers (OpenAI, Anthropic, Together, Groq)
│   └── Cost optimization (caching, routing, model cascading)
├── Evaluation at Scale
│   ├── LLM-as-judge (using GPT-4 to evaluate)
│   ├── Human evaluation protocols
│   ├── Benchmark suites (MMLU, HumanEval, etc.)
│   └── Red teaming and safety testing
├── Guardrails
│   ├── Input validation (prompt injection detection)
│   ├── Output filtering (toxicity, PII, off-topic)
│   ├── Rate limiting and cost controls
│   └── Fallback strategies
└── Monitoring
    ├── Latency tracking (TTFT, tokens/sec)
    ├── Quality monitoring (user feedback, LLM-eval)
    ├── Cost tracking (per-request, per-user)
    └── Drift detection (prompt performance degradation)
```

### NLP Capstone Project

```
PROJECT: Production RAG + Agent System
────────────────────────────────────────

Build a system that can:
1. Ingest a large document corpus (company docs, codebase, research papers)
2. Answer questions with citations (RAG)
3. Perform multi-step research (Agent)
4. Execute code to answer analytical questions
5. Handle follow-up questions (conversation memory)

Technical requirements:
├── FastAPI backend with streaming responses
├── Vector store (Qdrant or pgvector)
├── Hybrid retrieval (BM25 + dense embeddings)
├── Re-ranking with cross-encoder
├── Fine-tuned embedding model for your domain
├── LLM serving (vLLM for open model, or API for GPT-4)
├── Evaluation pipeline (automated quality checks)
├── Guardrails (input/output filtering)
├── Observability (LangSmith or custom tracing)
├── Frontend (Streamlit or Next.js)
└── Docker + docker-compose for deployment
```

---

## PART B: Computer Vision

### Month 1: Core CV Tasks

**Week 1-2: Image Classification + Transfer Learning**

```
Master:
├── Data augmentation (THE most important CV technique)
│   ├── Basic: flip, rotate, crop, color jitter
│   ├── Advanced: MixUp, CutMix, CutOut, Mosaic
│   ├── Albumentations library (use this, not torchvision.transforms)
│   └── Test-time augmentation (TTA)
├── Transfer learning workflow
│   ├── Feature extraction (freeze backbone, train head)
│   ├── Fine-tuning (unfreeze gradually, discriminative LR)
│   ├── Which pretrained model to choose (ImageNet-21k > ImageNet-1k)
│   └── Modern backbones: EfficientNet, ConvNeXt, ViT, Swin
├── Training tricks
│   ├── Progressive resizing (train small → fine-tune large)
│   ├── Label smoothing
│   ├── Mixup/CutMix regularization
│   ├── Knowledge distillation (big model → small model)
│   └── Stochastic depth
└── Evaluation
    ├── Top-1, Top-5 accuracy
    ├── Confusion matrix analysis
    ├── GradCAM visualization (where is model looking?)
    └── Calibration (are probabilities meaningful?)

Build:
├── Fine-tune ViT on custom dataset (your own photos)
├── Compare CNN vs Transformer on same task
├── Implement GradCAM from scratch
└── Build a production image classifier with confidence scores
```

**Week 3-4: Object Detection**

```
Evolution:
├── Two-stage detectors
│   ├── R-CNN → Fast R-CNN → Faster R-CNN
│   ├── Region Proposal Network (RPN)
│   └── Feature Pyramid Network (FPN)
├── One-stage detectors
│   ├── YOLO (v5, v8, v9, v10 -- use ultralytics)
│   ├── SSD
│   └── RetinaNet (focal loss for class imbalance)
├── Anchor-free detectors
│   ├── CenterNet (detect centers, not boxes)
│   ├── FCOS
│   └── DETR (detection transformer -- end-to-end, no NMS!)
└── Modern (2024)
    ├── YOLOv9/v10 (real-time king)
    ├── RT-DETR (real-time transformer detector)
    └── Grounding DINO (open-vocabulary detection)

Concepts to master:
├── IoU (Intersection over Union)
├── NMS (Non-Maximum Suppression)
├── Anchor boxes (ratios, scales)
├── Feature Pyramid Networks (multi-scale features)
├── Focal Loss (handle easy negatives)
└── mAP calculation (mean Average Precision at different IoU thresholds)

Build:
├── Fine-tune YOLOv8 on custom dataset (annotate yourself using LabelStudio)
├── Build real-time object detection with webcam
├── Implement NMS from scratch
└── Compare YOLO vs DETR on same dataset (speed vs accuracy)
```

### Month 2: Advanced CV

**Week 5-6: Segmentation**

```
Types:
├── Semantic segmentation (pixel-level class labels)
│   └── Every pixel gets a class, no instance distinction
├── Instance segmentation (separate each object)
│   └── Distinguish between "car 1" and "car 2"
├── Panoptic segmentation (semantic + instance combined)
│   └── Stuff (sky, road) + Things (people, cars)
└── Interactive segmentation (user-guided)
    └── SAM (Segment Anything Model)

Architectures:
├── U-Net (encoder-decoder with skip connections)
├── DeepLab (atrous/dilated convolutions, ASPP)
├── Mask R-CNN (detection + segmentation)
├── SegFormer (transformer-based, lightweight)
└── SAM (foundation model for segmentation)

Build:
├── U-Net from scratch for medical image segmentation
├── Fine-tune SAM on custom objects
├── Panoptic segmentation on COCO subset
└── Interactive segmentation app (click to segment)
```

**Week 7-8: Video + 3D + Multimodal**

```
Video:
├── Action recognition (I3D, SlowFast, VideoMAE)
├── Object tracking (DeepSORT, ByteTrack, BoT-SORT)
├── Video segmentation (tracking + segmentation)
├── Temporal understanding
└── Efficient video models (sample frames, not all frames)

3D Vision:
├── Point clouds (PointNet, PointNet++)
├── Depth estimation (monocular: MiDaS, DPT)
├── NeRF (Neural Radiance Fields) -- 3D from 2D images
├── 3D Gaussian Splatting (faster alternative to NeRF)
└── Multi-view geometry basics

Multimodal Vision-Language:
├── CLIP (learn visual concepts from text supervision)
├── BLIP-2 (visual question answering)
├── LLaVA (visual chat, multimodal LLM)
├── Grounding DINO + SAM = auto-labeling pipeline!
└── Florence-2 (unified vision model)

Build:
├── Real-time multi-object tracker (YOLOv8 + ByteTrack)
├── Depth estimation from single image (MiDaS)
├── Image captioning system (BLIP-2)
└── Visual search engine (CLIP embeddings + vector DB)
```

### CV Capstone Project

```
PROJECT: End-to-End Visual Intelligence System
───────────────────────────────────────────────

Build a system that combines detection + segmentation + tracking + understanding:

Option A: Smart Retail (count people, track movement, detect products)
Option B: Document Intelligence (OCR + layout + table extraction)  
Option C: Medical Imaging (segmentation + classification + report generation)
Option D: Autonomous Navigation (detection + depth + tracking)

Requirements:
├── Real-time inference (30+ FPS for video tasks)
├── Multiple models working together (detection → segmentation → classification)
├── API with image/video upload
├── Results visualization (bounding boxes, masks, tracks)
├── Batch processing for large datasets
├── Model optimization (ONNX/TensorRT for speed)
├── Confidence calibration
├── Active learning loop (flag uncertain predictions for human review)
└── Deployed and accessible via web
```

---

## PART C: Generative AI (Overlaps with NLP)

### Key Areas

```
Text Generation:
├── (Covered in NLP section above)
└── Fine-tuning, RLHF, deployment

Image Generation:
├── Stable Diffusion (latent diffusion models)
├── ControlNet (conditional generation)
├── IP-Adapter (style transfer)
├── SDXL, SD3 (latest architectures)
├── DreamBooth, Textual Inversion (personalization)
└── ComfyUI (node-based generation pipeline)

Video Generation:
├── Stable Video Diffusion
├── Sora-like architectures (DiT -- Diffusion Transformer)
└── AnimateDiff

Audio Generation:
├── Text-to-Speech (Bark, XTTS, StyleTTS2)
├── Music (MusicGen, Stable Audio)
└── Voice cloning

Multimodal:
├── GPT-4V, Gemini, Claude (vision + language)
├── DALL-E 3, Midjourney (text → image)
└── Video understanding (GPT-4V on video frames)
```

---

## Stage 4 Completion Criteria

**For your PRIMARY specialization (must hit ALL):**
- [ ] Can build production systems end-to-end in this domain
- [ ] Have read 20+ papers in this area
- [ ] Can explain the state-of-the-art and its limitations
- [ ] Have 2-3 substantial projects deployed
- [ ] Could give a 1-hour talk on the topic

**For your SECONDARY specialization (must hit 3/5):**
- [ ] Understand the major architectures and when to use them
- [ ] Can fine-tune pretrained models for new tasks
- [ ] Have at least 1 project
- [ ] Can read papers in this area and understand them
- [ ] Know the production considerations
