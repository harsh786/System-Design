# Latency Optimization for AI Systems (Questions 81-85)

## Q81: Systematic latency reduction from 3s p99 to 500ms for LLM-powered search

### Problem
Your LLM-powered search pipeline has: query understanding (200ms) → retrieval (300ms) → LLM generation (2500ms) = 3s p99. Reduce to 500ms without sacrificing quality.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Optimized Search Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Cache (p99 < 50ms for cache hits)               │   │
│  │  - Semantic cache (embedding similarity > 0.95)           │   │
│  │  - Exact query cache (Redis, TTL=5min)                    │   │
│  │  - Expected hit rate: 30-40%                              │   │
│  └───────────────────────────┬──────────────────────────────┘   │
│                              │ cache miss                         │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │ Layer 2: Speculative Execution (parallel, not serial)     │   │
│  │                                                           │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │   │
│  │  │ Query      │  │ Retrieval  │  │ Speculative LLM    │ │   │
│  │  │ Understand │  │ (sparse +  │  │ (start with query  │ │   │
│  │  │ (50ms)     │  │ dense)     │  │  alone, refine)    │ │   │
│  │  └─────┬──────┘  │ (100ms)   │  │ (starts at t=0)    │ │   │
│  │        │          └─────┬─────┘  └──────────┬─────────┘ │   │
│  │        └────────────────┼────────────────────┘           │   │
│  └─────────────────────────┼────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │ Layer 3: Fast Model (distilled, 100ms generation)         │   │
│  │  - 7B parameter model distilled from GPT-4                │   │
│  │  - Quantized INT8, served on optimized runtime            │   │
│  │  - Quality: 92% of GPT-4 on search-specific benchmarks   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Total: 50ms (cache) + 100ms (retrieval) + 100ms (fast LLM)    │
│       = 250ms p50, ~450ms p99                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import hashlib
import time
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class SearchResult:
    answer: str
    sources: list
    latency_ms: float
    cache_hit: bool
    model_used: str

class OptimizedSearchPipeline:
    def __init__(self):
        self.exact_cache = RedisCache(ttl_seconds=300)
        self.semantic_cache = SemanticCache(threshold=0.95, max_entries=1_000_000)
        self.fast_model = DistilledSearchModel("search-7b-int8")  
        self.full_model = LargeModel("gpt-4")
        self.retriever = HybridRetriever()
        
    async def search(self, query: str, max_latency_ms: float = 500) -> SearchResult:
        start = time.time()
        
        # Layer 1: Cache lookup (parallel exact + semantic)
        cache_result = await self._check_caches(query)
        if cache_result:
            return SearchResult(
                answer=cache_result, sources=[], 
                latency_ms=(time.time() - start) * 1000,
                cache_hit=True, model_used="cache"
            )
        
        # Layer 2: Parallel execution
        # Start retrieval AND speculative generation simultaneously
        retrieval_task = asyncio.create_task(self.retriever.search(query, top_k=5))
        
        # Speculative: generate with query alone (will be refined or discarded)
        speculative_task = asyncio.create_task(
            self.fast_model.generate(
                f"Answer concisely: {query}",
                max_tokens=150,
                timeout_ms=200
            )
        )
        
        # Wait for retrieval (critical path)
        docs = await retrieval_task
        retrieval_latency = (time.time() - start) * 1000
        
        # Remaining time budget
        remaining_ms = max_latency_ms - retrieval_latency - 50  # 50ms buffer
        
        if remaining_ms < 100:
            # Use speculative result if retrieval was slow
            speculative_answer = await speculative_task
            return SearchResult(
                answer=speculative_answer, sources=docs,
                latency_ms=(time.time() - start) * 1000,
                cache_hit=False, model_used="speculative"
            )
        
        # Cancel speculative, use grounded generation
        speculative_task.cancel()
        
        # Layer 3: Fast grounded generation
        context = "\n".join([d.text[:500] for d in docs[:3]])
        prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer concisely:"
        
        answer = await self.fast_model.generate(
            prompt, max_tokens=150, timeout_ms=int(remaining_ms)
        )
        
        total_latency = (time.time() - start) * 1000
        
        # Async: cache the result, don't block response
        asyncio.create_task(self._cache_result(query, answer))
        
        # Async: quality check with full model (for monitoring, not blocking)
        asyncio.create_task(self._async_quality_check(query, answer, docs))
        
        return SearchResult(
            answer=answer, sources=docs,
            latency_ms=total_latency,
            cache_hit=False, model_used="search-7b"
        )

    async def _check_caches(self, query: str) -> Optional[str]:
        """Parallel cache lookup."""
        exact_task = asyncio.create_task(self.exact_cache.get(query))
        semantic_task = asyncio.create_task(self.semantic_cache.get(query))
        
        exact, semantic = await asyncio.gather(exact_task, semantic_task)
        return exact or semantic

    async def _cache_result(self, query: str, answer: str):
        await asyncio.gather(
            self.exact_cache.set(query, answer),
            self.semantic_cache.set(query, answer)
        )

    async def _async_quality_check(self, query: str, fast_answer: str, docs: list):
        """Background quality monitoring - not in critical path."""
        full_answer = await self.full_model.generate(
            f"Rate this answer 1-5 for accuracy given the docs: {fast_answer}"
        )
        # Log quality score for model monitoring
        # Alert if quality drops below threshold


class SemanticCache:
    """Cache that matches semantically similar queries."""
    
    def __init__(self, threshold: float = 0.95, max_entries: int = 1_000_000):
        self.threshold = threshold
        self.embeddings = None  # FAISS index
        self.answers = {}
        
    async def get(self, query: str) -> Optional[str]:
        query_embedding = await embed(query)
        # FAISS search: O(log n) with IVF index
        distances, indices = self.embeddings.search(query_embedding, k=1)
        if distances[0][0] > self.threshold:
            return self.answers[indices[0][0]]
        return None
```

### Latency Breakdown Comparison

| Stage | Before | After | Technique |
|-------|--------|-------|-----------|
| Cache check | N/A | 5ms | Semantic + exact cache |
| Query understanding | 200ms | 0ms (removed) | Merged into retrieval |
| Retrieval | 300ms | 100ms | Pre-computed indexes, parallel sparse+dense |
| LLM generation | 2500ms | 100ms | Distilled 7B INT8 model |
| **Total (cache miss)** | **3000ms** | **250ms** | |
| **Total (cache hit)** | **3000ms** | **5ms** | |
| **Blended p99** | **3000ms** | **~450ms** | 35% cache hit rate |

### Production Considerations

- **Quality regression monitoring**: Continuously compare fast model output with full model. Alert if agreement drops below 90%.
- **Cache invalidation**: When source documents update, invalidate semantic cache entries that referenced them. Use document fingerprinting.
- **Adaptive timeout**: If p99 is well under 500ms, allow full model for complex queries. Dynamically route based on latency budget.
- **Model distillation pipeline**: Weekly distillation from GPT-4 on search-specific data. Automated quality gate before deployment.
- **Fallback chain**: fast_model → speculative → cached_similar → "I don't know" (never exceed SLA).

---

## Q82: Streaming architecture for time-to-first-token < 200ms with quality

### Problem
Users perceive responsiveness by time-to-first-token (TTFT). Standard LLM inference has 500ms-2s TTFT due to prefill. Design an architecture achieving <200ms TTFT while maintaining output quality.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│            Ultra-Low TTFT Streaming Architecture              │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Client Request                                               │
│       │                                                       │
│       ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Speculative Prefill Router                               │ │
│  │                                                          │ │
│  │  ┌───────────┐     ┌───────────────┐                   │ │
│  │  │ Draft     │────▶│ Speculative    │                   │ │
│  │  │ Model     │     │ Decoder        │                   │ │
│  │  │ (1B, 30ms│     │ (generates 5   │                   │ │
│  │  │  prefill) │     │  tokens ahead) │                   │ │
│  │  └───────────┘     └───────┬───────┘                   │ │
│  │                            │                             │ │
│  │                            ▼                             │ │
│  │  ┌───────────────────────────────────────────────────┐  │ │
│  │  │ Verification Model (70B)                           │  │ │
│  │  │ - Verifies draft tokens in parallel                │  │ │
│  │  │ - Accepts correct tokens, regenerates wrong ones   │  │ │
│  │  │ - Net: 3-4 tokens accepted per verification step   │  │ │
│  │  └───────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Streaming Output Buffer                                  │ │
│  │  - Sends tokens as soon as verified                      │ │
│  │  - Buffers 1 sentence for early stop evaluation          │ │
│  │  - SSE/WebSocket to client                               │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from typing import AsyncGenerator, List, Optional
from dataclasses import dataclass

@dataclass
class StreamConfig:
    max_ttft_ms: float = 200
    draft_model: str = "llama-1b"
    target_model: str = "llama-70b"
    speculation_length: int = 5    # tokens to speculate ahead
    max_output_tokens: int = 1024
    use_kv_cache_sharing: bool = True

class SpeculativeStreamingEngine:
    def __init__(self, config: StreamConfig):
        self.config = config
        self.draft = DraftModel(config.draft_model)       # 1B model, 30ms prefill
        self.target = TargetModel(config.target_model)    # 70B model, 400ms prefill
        
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens with speculative decoding for low TTFT."""
        start = time.time()
        
        # Phase 1: Start draft model immediately (low TTFT)
        # Draft model prefills in ~30ms vs ~400ms for target
        draft_kv = await self.draft.prefill(prompt)  # ~30ms
        
        # Start target model prefill in background
        target_prefill_task = asyncio.create_task(
            self.target.prefill(prompt)
        )
        
        # Generate first tokens from draft model immediately
        draft_tokens = []
        async for token in self.draft.generate(draft_kv, max_tokens=self.config.speculation_length):
            draft_tokens.append(token)
            # Yield first token ASAP from draft
            if len(draft_tokens) == 1:
                ttft = (time.time() - start) * 1000
                # First token from draft model: ~50ms total
                yield token
        
        # Phase 2: Target model verifies draft tokens
        target_kv = await target_prefill_task  # Should be ready by now (~400ms)
        
        # Verify draft tokens in one forward pass (parallel verification)
        verified_count = await self.target.verify_tokens(
            target_kv, draft_tokens
        )
        
        # If draft was wrong, regenerate from target
        if verified_count < len(draft_tokens):
            # Send correction signal (optional: for rewrite-capable clients)
            yield f"\x00REWIND:{len(draft_tokens) - verified_count}"
            
            # Continue from verified position with target model
            async for token in self._target_decode_loop(target_kv, verified_count):
                yield token
        else:
            # Draft was correct, continue with speculative decoding loop
            async for token in self._speculative_decode_loop(draft_kv, target_kv):
                yield token

    async def _speculative_decode_loop(self, draft_kv, target_kv) -> AsyncGenerator[str, None]:
        """Main speculative decoding loop after initial tokens."""
        tokens_generated = 0
        
        while tokens_generated < self.config.max_output_tokens:
            # Draft generates K tokens speculatively
            draft_tokens = []
            async for token in self.draft.generate(draft_kv, max_tokens=self.config.speculation_length):
                draft_tokens.append(token)
            
            # Target verifies all K tokens in one forward pass
            verified_count = await self.target.verify_tokens(target_kv, draft_tokens)
            
            # Yield verified tokens
            for i in range(verified_count):
                yield draft_tokens[i]
                tokens_generated += 1
            
            # Target generates one corrected token if needed
            if verified_count < len(draft_tokens):
                correct_token = await self.target.generate_one(target_kv)
                yield correct_token
                tokens_generated += 1
            
            # Check for EOS
            if draft_tokens and draft_tokens[verified_count - 1] == "<EOS>":
                break
            
            # Update KV caches
            self.draft.update_kv(draft_kv, draft_tokens[:verified_count])
            self.target.update_kv(target_kv, draft_tokens[:verified_count])

    async def _target_decode_loop(self, target_kv, start_pos: int) -> AsyncGenerator[str, None]:
        """Fallback: standard autoregressive from target model."""
        tokens = 0
        async for token in self.target.generate(target_kv, max_tokens=self.config.max_output_tokens):
            yield token
            tokens += 1


class StreamingResponseHandler:
    """Handles client-facing streaming with buffering strategies."""
    
    def __init__(self):
        self.buffer = []
        self.flush_strategies = {
            "immediate": self._flush_immediate,      # Every token
            "word": self._flush_on_word_boundary,    # Every word
            "sentence": self._flush_on_sentence,     # Every sentence
        }
    
    async def stream_to_client(self, token_stream: AsyncGenerator, 
                                strategy: str = "word") -> AsyncGenerator[str, None]:
        """Buffer and flush tokens based on strategy."""
        flush_fn = self.flush_strategies[strategy]
        
        async for token in token_stream:
            self.buffer.append(token)
            flush_text = flush_fn()
            if flush_text:
                yield flush_text
        
        # Flush remaining buffer
        if self.buffer:
            yield "".join(self.buffer)
            self.buffer.clear()
    
    def _flush_immediate(self) -> Optional[str]:
        text = "".join(self.buffer)
        self.buffer.clear()
        return text
    
    def _flush_on_word_boundary(self) -> Optional[str]:
        text = "".join(self.buffer)
        if " " in text or "\n" in text:
            # Flush up to last space
            last_space = max(text.rfind(" "), text.rfind("\n"))
            flush = text[:last_space + 1]
            self.buffer = [text[last_space + 1:]] if last_space + 1 < len(text) else []
            return flush
        return None
    
    def _flush_on_sentence(self) -> Optional[str]:
        text = "".join(self.buffer)
        for delim in [".", "!", "?", "\n"]:
            if delim in text:
                idx = text.index(delim) + 1
                flush = text[:idx]
                self.buffer = [text[idx:]] if idx < len(text) else []
                return flush
        return None
```

### Performance Metrics

| Metric | Standard Decoding | Speculative Decoding | Improvement |
|--------|------------------|---------------------|-------------|
| TTFT | 400-500ms | 50-80ms | 5-8x |
| Tokens/second | 30-50 | 80-120 | 2-3x |
| Quality | 100% (baseline) | 100% (verified) | No loss |
| GPU cost | 1x | 1.3x (draft overhead) | Slightly higher |
| Total latency (500 tokens) | 10-15s | 4-6s | 2-3x |

### Production Considerations

- **Draft model selection**: Draft must share vocabulary with target. Smaller models from same family work best (Llama-1B → Llama-70B).
- **KV cache memory**: Both models need KV cache simultaneously. Plan for 2x memory per request.
- **Acceptance rate monitoring**: Track draft acceptance rate. If <60%, draft model needs fine-tuning on target's distribution.
- **Client reconnection**: Token position tracking for seamless reconnection mid-stream.
- **Early stopping**: Monitor token probability entropy. If model is "uncertain," stop early rather than hallucinate.

---

## Q83: Request coalescing and batching for embedding generation

### Problem
You serve 100K embedding requests per minute. Each request has 1-10 texts. GPU batch inference is most efficient at batch sizes of 64-256. Design a system that maximizes throughput while keeping individual request p99 < 50ms.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│             Embedding Batching System                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Request 1  │  │ Request 2  │  │ Request N  │            │
│  │ [3 texts]  │  │ [1 text]   │  │ [5 texts]  │            │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘            │
│        │                │                │                    │
│        ▼                ▼                ▼                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Micro-Batcher                            │   │
│  │  - Collects items for up to 5ms OR 128 items         │   │
│  │  - Groups by sequence length (reduces padding)        │   │
│  │  - Assigns batch IDs, tracks per-request futures      │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Length-Sorted Batch Queue                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐       │   │
│  │  │ Short    │  │ Medium   │  │ Long         │       │   │
│  │  │ <128 tok │  │ <512 tok │  │ <2048 tok    │       │   │
│  │  │ batch=256│  │ batch=128│  │ batch=32     │       │   │
│  │  └──────────┘  └──────────┘  └──────────────┘       │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         GPU Worker Pool (N GPUs)                      │   │
│  │  - Continuous batching                                │   │
│  │  - Batch dispatched when full OR timeout              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np
from concurrent.futures import Future

@dataclass
class EmbeddingItem:
    text: str
    token_count: int
    request_id: str
    item_index: int  # Position within original request
    future: asyncio.Future
    arrival_time: float = field(default_factory=time.time)

@dataclass
class BatchConfig:
    max_batch_size: int = 128
    max_wait_ms: float = 5.0          # Max time to wait for batch to fill
    length_buckets: List[int] = field(default_factory=lambda: [128, 512, 2048])
    batch_sizes_per_bucket: List[int] = field(default_factory=lambda: [256, 128, 32])
    sla_deadline_ms: float = 50.0     # p99 target

class MicroBatcher:
    """Collects individual embedding items into optimal batches."""
    
    def __init__(self, config: BatchConfig, num_gpus: int = 4):
        self.config = config
        self.num_gpus = num_gpus
        self.buckets: Dict[int, List[EmbeddingItem]] = {
            b: [] for b in config.length_buckets
        }
        self.lock = asyncio.Lock()
        self._batch_event = asyncio.Event()
        
        # Start batch dispatch loop
        asyncio.create_task(self._dispatch_loop())
    
    async def submit(self, texts: List[str], request_id: str) -> List[np.ndarray]:
        """Submit texts for embedding, returns when all are done."""
        futures = []
        
        async with self.lock:
            for i, text in enumerate(texts):
                token_count = len(text.split()) * 1.3  # Rough estimate
                future = asyncio.get_event_loop().create_future()
                
                item = EmbeddingItem(
                    text=text, token_count=int(token_count),
                    request_id=request_id, item_index=i,
                    future=future
                )
                
                # Route to appropriate length bucket
                bucket = self._get_bucket(item.token_count)
                self.buckets[bucket].append(item)
                futures.append(future)
                
                # Signal if any bucket is full
                bucket_idx = self.config.length_buckets.index(bucket)
                if len(self.buckets[bucket]) >= self.config.batch_sizes_per_bucket[bucket_idx]:
                    self._batch_event.set()
        
        # Wait for all embeddings to complete
        results = await asyncio.gather(*futures)
        return results
    
    def _get_bucket(self, token_count: int) -> int:
        for bucket in self.config.length_buckets:
            if token_count <= bucket:
                return bucket
        return self.config.length_buckets[-1]
    
    async def _dispatch_loop(self):
        """Continuously dispatch batches."""
        while True:
            # Wait for either: bucket full OR timeout
            try:
                await asyncio.wait_for(
                    self._batch_event.wait(),
                    timeout=self.config.max_wait_ms / 1000
                )
            except asyncio.TimeoutError:
                pass
            
            self._batch_event.clear()
            
            # Dispatch ready batches
            async with self.lock:
                for bucket_size in self.config.length_buckets:
                    bucket_idx = self.config.length_buckets.index(bucket_size)
                    max_batch = self.config.batch_sizes_per_bucket[bucket_idx]
                    
                    while len(self.buckets[bucket_size]) > 0:
                        # Take up to max_batch items
                        batch_items = self.buckets[bucket_size][:max_batch]
                        self.buckets[bucket_size] = self.buckets[bucket_size][max_batch:]
                        
                        # Check SLA: any item close to deadline?
                        oldest = min(item.arrival_time for item in batch_items)
                        age_ms = (time.time() - oldest) * 1000
                        
                        if len(batch_items) >= max_batch * 0.5 or age_ms > self.config.max_wait_ms:
                            # Dispatch this batch
                            asyncio.create_task(
                                self._execute_batch(batch_items, bucket_size)
                            )
                        else:
                            # Put back, wait for more items
                            self.buckets[bucket_size] = batch_items + self.buckets[bucket_size]
                            break

    async def _execute_batch(self, items: List[EmbeddingItem], max_length: int):
        """Execute batch on GPU."""
        texts = [item.text for item in items]
        
        try:
            # Pad to uniform length within bucket, run inference
            embeddings = await gpu_embed_batch(
                texts, 
                max_length=max_length,
                batch_size=len(texts)
            )
            
            # Resolve futures
            for item, embedding in zip(items, embeddings):
                if not item.future.done():
                    item.future.set_result(embedding)
                    
        except Exception as e:
            for item in items:
                if not item.future.done():
                    item.future.set_exception(e)


class RequestCoalescer:
    """Deduplicates identical texts across concurrent requests."""
    
    def __init__(self):
        self.pending: Dict[str, asyncio.Future] = {}  # text_hash → future
        self.lock = asyncio.Lock()
    
    async def get_or_compute(self, text: str, compute_fn) -> np.ndarray:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        async with self.lock:
            if text_hash in self.pending:
                # Another request is already computing this embedding
                return await self.pending[text_hash]
            
            future = asyncio.get_event_loop().create_future()
            self.pending[text_hash] = future
        
        try:
            result = await compute_fn(text)
            future.set_result(result)
            return result
        finally:
            async with self.lock:
                del self.pending[text_hash]
```

### Performance Analysis

| Batch Strategy | Throughput (emb/s) | p50 Latency | p99 Latency | GPU Util |
|---------------|-------------------|-------------|-------------|----------|
| No batching (1 at a time) | 500 | 8ms | 15ms | 5% |
| Fixed batch (64) | 15,000 | 20ms | 45ms | 70% |
| Adaptive (this) | 25,000 | 12ms | 35ms | 90% |
| Max batch (256) | 30,000 | 30ms | 80ms | 95% |

### Production Considerations

- **Padding waste**: Length bucketing reduces padding from 40% to <10% of compute.
- **Deduplication**: In RAG workloads, 10-20% of texts are repeated across concurrent requests. Coalescing saves significant GPU time.
- **Timeout enforcement**: If a batch hasn't completed within 40ms, it's likely stuck. Cancel and retry on different GPU.
- **Warmup**: First batch after cold start is 2-3x slower. Pre-warm with dummy batch.
- **Monitoring**: Track batch fill rate, padding percentage, coalescing hit rate, and per-bucket latency.

---

## Q84: Predictive pre-computation for near-zero perceived latency

### Problem
For common interactions (search suggestions, chat follow-ups, dashboard queries), pre-generate likely responses before the user asks. Reduce perceived latency to near-zero for 60%+ of interactions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Predictive Pre-computation System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Prediction Layer                                          │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Session     │  │ Population   │  │ Temporal      │   │   │
│  │  │ Predictor   │  │ Predictor    │  │ Predictor     │   │   │
│  │  │ (user's     │  │ (trending    │  │ (time-of-day  │   │   │
│  │  │  next query)│  │  queries)    │  │  patterns)    │   │   │
│  │  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘   │   │
│  │         │                 │                  │            │   │
│  │         ▼                 ▼                  ▼            │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ Prediction Ranker (top-K likely queries)          │   │   │
│  │  │ Score = P(query|session) × value × freshness      │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────┬───────────────────────┘   │
│                                     │                            │
│                                     ▼                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Pre-computation Engine                                    │   │
│  │  - Generates responses for top-5 predicted queries        │   │
│  │  - Uses spare GPU capacity (off-peak) or cheap models     │   │
│  │  - Stores in per-user pre-computation cache (TTL=5min)    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Serving Layer                                             │   │
│  │  User Query → Check pre-computation cache → Hit? Instant! │   │
│  │                                         → Miss? Normal path│   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

@dataclass
class PredictedQuery:
    query: str
    confidence: float       # 0-1, probability user will ask this
    value: float           # Business value of pre-computing (cost × frequency)
    freshness_weight: float  # How time-sensitive is this answer

@dataclass
class PrecomputedResponse:
    query: str
    response: str
    generated_at: float
    model_used: str
    ttl_seconds: float
    confidence_at_generation: float

class SessionPredictor:
    """Predicts next query based on current session context."""
    
    def __init__(self):
        self.session_model = load_model("next-query-predictor")  # Fine-tuned on session logs
        # Markov chain of query transitions (computed offline)
        self.transition_matrix: Dict[str, List[Tuple[str, float]]] = {}
    
    async def predict_next(self, session_history: List[str], 
                           user_profile: dict, k: int = 5) -> List[PredictedQuery]:
        """Predict top-K likely next queries for this session."""
        predictions = []
        
        # 1. ML model prediction (most accurate)
        ml_predictions = await self.session_model.predict(
            session_history=session_history,
            user_context=user_profile,
            top_k=k * 2
        )
        
        # 2. Markov chain (fast, covers common patterns)
        if session_history:
            last_query = session_history[-1]
            markov_predictions = self.transition_matrix.get(last_query, [])[:k]
        else:
            markov_predictions = []
        
        # 3. Merge and deduplicate
        seen = set()
        for query, confidence in ml_predictions + markov_predictions:
            if query not in seen:
                seen.add(query)
                predictions.append(PredictedQuery(
                    query=query,
                    confidence=confidence,
                    value=self._estimate_value(query),
                    freshness_weight=self._freshness_requirement(query)
                ))
        
        # Sort by expected value (confidence × value)
        predictions.sort(key=lambda p: p.confidence * p.value, reverse=True)
        return predictions[:k]
    
    def _estimate_value(self, query: str) -> float:
        """Value = generation_cost × frequency. High-value = expensive to compute."""
        # Queries requiring RAG or long generation are more valuable to pre-compute
        estimated_tokens = len(query.split()) * 50  # Rough output estimate
        return min(estimated_tokens / 500, 1.0)
    
    def _freshness_requirement(self, query: str) -> float:
        """How quickly does this answer become stale?"""
        # "What's the stock price" → very fresh needed (low TTL)
        # "How does X work" → stable (high TTL)
        return 0.5  # Default: moderate freshness


class PrecomputationEngine:
    """Manages pre-computation budget and execution."""
    
    def __init__(self, gpu_budget_fraction: float = 0.2):
        self.gpu_budget = gpu_budget_fraction  # Use 20% of spare GPU capacity
        self.cache: Dict[str, Dict[str, PrecomputedResponse]] = defaultdict(dict)
        self.stats = {"hits": 0, "misses": 0, "precomputed": 0, "wasted": 0}
    
    async def precompute_for_user(self, user_id: str, 
                                   predictions: List[PredictedQuery]):
        """Pre-generate responses for predicted queries."""
        # Budget: only precompute if confidence > threshold
        threshold = 0.3  # Pre-compute if >30% likely
        
        tasks = []
        for pred in predictions:
            if pred.confidence < threshold:
                continue
            
            # Skip if already cached and fresh
            existing = self.cache[user_id].get(pred.query)
            if existing and time.time() - existing.generated_at < existing.ttl_seconds:
                continue
            
            tasks.append(self._generate_and_cache(user_id, pred))
        
        # Run pre-computations with limited concurrency
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent per user
        async def limited(task):
            async with semaphore:
                return await task
        
        await asyncio.gather(*[limited(t) for t in tasks])
    
    async def _generate_and_cache(self, user_id: str, pred: PredictedQuery):
        """Generate and cache a predicted response."""
        # Use cheaper model for pre-computation (cost-conscious)
        response = await generate_response(
            query=pred.query,
            model="gpt-3.5-turbo",  # Cheaper for speculative generation
            max_tokens=300
        )
        
        ttl = 300 / pred.freshness_weight  # Less fresh = longer TTL
        
        self.cache[user_id][pred.query] = PrecomputedResponse(
            query=pred.query,
            response=response,
            generated_at=time.time(),
            model_used="gpt-3.5-turbo",
            ttl_seconds=ttl,
            confidence_at_generation=pred.confidence
        )
        self.stats["precomputed"] += 1
    
    async def serve(self, user_id: str, query: str) -> Optional[str]:
        """Check if we have a pre-computed response."""
        # Exact match
        cached = self.cache[user_id].get(query)
        if cached and time.time() - cached.generated_at < cached.ttl_seconds:
            self.stats["hits"] += 1
            return cached.response
        
        # Semantic similarity match (fuzzy)
        for cached_query, cached_response in self.cache[user_id].items():
            if self._semantic_match(query, cached_query) > 0.92:
                if time.time() - cached_response.generated_at < cached_response.ttl_seconds:
                    self.stats["hits"] += 1
                    return cached_response.response
        
        self.stats["misses"] += 1
        return None
    
    def _semantic_match(self, q1: str, q2: str) -> float:
        """Fast semantic similarity (cached embeddings)."""
        # Use pre-computed embeddings
        return 0.0  # Placeholder
    
    def get_efficiency_metrics(self) -> dict:
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        waste_rate = 1 - (self.stats["hits"] / self.stats["precomputed"]) if self.stats["precomputed"] > 0 else 0
        return {
            "hit_rate": hit_rate,
            "waste_rate": waste_rate,  # Pre-computed but never used
            "gpu_roi": hit_rate / self.gpu_budget,  # Effectiveness per GPU spent
        }
```

### Trade-offs

| Strategy | Hit Rate | GPU Waste | Latency Saving | Complexity |
|----------|----------|-----------|----------------|------------|
| No pre-computation | 0% | 0% | 0ms | None |
| Popular queries only | 20-30% | Low | High for hits | Low |
| Session-aware (this) | 40-60% | 20-30% | Near-zero for hits | High |
| Full pre-computation | 80%+ | 60-70% | Near-zero | Very High |

### Production Considerations

- **GPU budget management**: Pre-computation uses spare capacity. During peak, reduce pre-computation aggressively. Never starve real-time requests.
- **Cache invalidation**: When underlying data changes, invalidate pre-computed responses that depend on it.
- **Quality bridge**: Pre-computed with cheap model. If user actually asks, start streaming pre-computed AND generate with full model in background. Replace if quality differs.
- **Privacy**: Per-user prediction models see session data. Ensure predictions are never leaked across users.
- **Measurement**: A/B test pre-computation. Measure perceived latency improvement and user engagement lift.

---

## Q85: Tiered inference with routing logic and quality guarantees

### Problem
80% of queries are simple (factual lookups, reformatting) and can be handled by a fast 7B model. 20% need GPT-4 class reasoning. Design a router that correctly identifies complexity and guarantees quality across tiers.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              Tiered Inference Architecture                     │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  User Query                                                   │
│       │                                                       │
│       ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Complexity Router (lightweight classifier, <10ms)        │ │
│  │                                                          │ │
│  │  Features:                                               │ │
│  │  - Query length, question type                           │ │
│  │  - Entity count, reasoning keywords                      │ │
│  │  - Historical difficulty of similar queries              │ │
│  │  - User tier (enterprise gets premium default)           │ │
│  │                                                          │ │
│  │  Output: {tier: "fast"|"medium"|"premium",               │ │
│  │           confidence: 0.0-1.0}                           │ │
│  └────────────────┬──────────────┬───────────────┬─────────┘ │
│                   │              │               │            │
│     confidence>0.8│   0.5-0.8   │     <0.5      │            │
│                   ▼              ▼               ▼            │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────────┐  │
│  │ Fast Tier│  │ Medium   │  │ Premium Tier              │  │
│  │ Llama-7B │  │ Llama-70B│  │ GPT-4 / Claude           │  │
│  │ INT8     │  │ FP16     │  │ Full capability           │  │
│  │ 50ms     │  │ 200ms    │  │ 1-3s                     │  │
│  │ $0.001/q │  │ $0.01/q  │  │ $0.05/q                  │  │
│  └────┬─────┘  └────┬─────┘  └─────────────┬─────────────┘  │
│       │              │                       │                │
│       ▼              ▼                       ▼                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Quality Verifier (async, samples 10%)                     ││
│  │ - Compares fast tier output with premium model            ││
│  │ - Detects quality regressions                             ││
│  │ - Feeds back to router training                           ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import random

class InferenceTier(Enum):
    FAST = "fast"       # 7B INT8 - simple queries
    MEDIUM = "medium"   # 70B FP16 - moderate complexity
    PREMIUM = "premium" # GPT-4 - complex reasoning

@dataclass
class TierSpec:
    model: str
    max_tokens: int
    timeout_ms: float
    cost_per_query: float
    expected_latency_ms: float

TIER_SPECS = {
    InferenceTier.FAST: TierSpec("llama-7b-int8", 256, 200, 0.001, 50),
    InferenceTier.MEDIUM: TierSpec("llama-70b", 512, 1000, 0.01, 200),
    InferenceTier.PREMIUM: TierSpec("gpt-4", 1024, 5000, 0.05, 1500),
}

class ComplexityRouter:
    """Classifies query complexity to select inference tier."""
    
    def __init__(self):
        self.classifier = load_model("query-complexity-classifier")  # Fine-tuned BERT-tiny
        self.feature_extractor = QueryFeatureExtractor()
        # Thresholds (tuned on labeled data)
        self.fast_threshold = 0.7    # Route to fast if P(simple) > 0.7
        self.premium_threshold = 0.6  # Route to premium if P(complex) > 0.6
    
    async def route(self, query: str, context: dict = None) -> Tuple[InferenceTier, float]:
        """Classify query complexity. Returns (tier, confidence)."""
        features = self.feature_extractor.extract(query)
        
        # Rule-based fast path (near-zero latency)
        rule_result = self._rule_based_check(query, features)
        if rule_result:
            return rule_result
        
        # ML classifier
        probs = await self.classifier.predict(features)
        # probs = [P(simple), P(moderate), P(complex)]
        
        if probs[0] > self.fast_threshold:
            return InferenceTier.FAST, probs[0]
        elif probs[2] > self.premium_threshold:
            return InferenceTier.PREMIUM, probs[2]
        else:
            return InferenceTier.MEDIUM, max(probs)
    
    def _rule_based_check(self, query: str, features: dict) -> Optional[Tuple[InferenceTier, float]]:
        """Fast heuristic rules for obvious cases."""
        # Very short, factual queries → fast
        if features["word_count"] < 10 and features["question_type"] in ["what_is", "define"]:
            return InferenceTier.FAST, 0.95
        
        # Multi-step reasoning keywords → premium
        complex_indicators = ["compare", "analyze", "trade-offs", "design", "explain why",
                             "step by step", "pros and cons"]
        if any(ind in query.lower() for ind in complex_indicators):
            return InferenceTier.PREMIUM, 0.85
        
        # Code generation with complexity → premium
        if features["has_code_request"] and features["word_count"] > 50:
            return InferenceTier.PREMIUM, 0.8
        
        return None


class TieredInferenceEngine:
    """Orchestrates tiered inference with quality guarantees."""
    
    def __init__(self):
        self.router = ComplexityRouter()
        self.models = {
            InferenceTier.FAST: FastModel("llama-7b-int8"),
            InferenceTier.MEDIUM: MediumModel("llama-70b"),
            InferenceTier.PREMIUM: PremiumModel("gpt-4"),
        }
        self.quality_monitor = QualityMonitor()
        self.escalation_rate = 0.0  # Track how often fast tier escalates
    
    async def infer(self, query: str, user_tier: str = "pro") -> dict:
        """Route and execute inference with quality fallback."""
        # Route
        tier, confidence = await self.router.route(query)
        
        # Enterprise users: minimum medium tier
        if user_tier == "enterprise" and tier == InferenceTier.FAST:
            tier = InferenceTier.MEDIUM
            confidence = 0.9
        
        spec = TIER_SPECS[tier]
        
        # Execute on selected tier
        response = await self.models[tier].generate(
            query, max_tokens=spec.max_tokens, timeout_ms=spec.timeout_ms
        )
        
        # Quality gate: check if response seems adequate
        if tier != InferenceTier.PREMIUM:
            quality_ok = await self._quick_quality_check(query, response, tier)
            if not quality_ok:
                # Escalate to next tier
                tier = InferenceTier(tier.value)  # Next tier
                next_tier = self._get_next_tier(tier)
                if next_tier:
                    response = await self.models[next_tier].generate(
                        query, max_tokens=TIER_SPECS[next_tier].max_tokens
                    )
                    tier = next_tier
                    self.escalation_rate = self.escalation_rate * 0.99 + 0.01
        
        # Async quality sampling (doesn't block response)
        if random.random() < 0.1:  # Sample 10%
            asyncio.create_task(
                self.quality_monitor.evaluate(query, response, tier)
            )
        
        return {
            "response": response,
            "tier_used": tier.value,
            "confidence": confidence,
            "latency_ms": spec.expected_latency_ms,
        }
    
    async def _quick_quality_check(self, query: str, response: str, 
                                    tier: InferenceTier) -> bool:
        """Lightweight quality check (<5ms)."""
        # Heuristic checks
        if len(response.strip()) < 10:
            return False  # Too short, likely failed
        if "I don't know" in response and len(query.split()) > 5:
            return False  # Likely needs more capable model
        if response.count("...") > 3:
            return False  # Hedging, uncertain
        
        # Check response confidence (if model provides logprobs)
        # Low avg logprob → model is uncertain → escalate
        return True
    
    def _get_next_tier(self, current: InferenceTier) -> Optional[InferenceTier]:
        order = [InferenceTier.FAST, InferenceTier.MEDIUM, InferenceTier.PREMIUM]
        idx = order.index(current)
        return order[idx + 1] if idx + 1 < len(order) else None


class QualityMonitor:
    """Continuously monitors tier routing quality."""
    
    def __init__(self):
        self.scores: dict = defaultdict(list)
    
    async def evaluate(self, query: str, response: str, tier: InferenceTier):
        """Compare tier response with premium model (ground truth)."""
        if tier == InferenceTier.PREMIUM:
            return  # Nothing to compare against
        
        # Generate premium response
        premium_response = await PremiumModel("gpt-4").generate(query)
        
        # Score agreement (using another LLM as judge)
        score = await self._judge_agreement(response, premium_response, query)
        self.scores[tier.value].append(score)
        
        # Alert if quality drops
        recent_scores = self.scores[tier.value][-100:]
        avg_quality = np.mean(recent_scores)
        
        if avg_quality < 0.85:
            await self._alert_quality_drop(tier, avg_quality)
    
    async def _judge_agreement(self, response_a: str, response_b: str, query: str) -> float:
        """Quick agreement score 0-1."""
        # Simplified: use embedding similarity as proxy
        emb_a = await embed(response_a)
        emb_b = await embed(response_b)
        return float(np.dot(emb_a, emb_b))
    
    async def _alert_quality_drop(self, tier: InferenceTier, score: float):
        """Alert when tier quality drops below threshold."""
        pass  # Send to PagerDuty/Slack
```

### Cost-Quality Analysis

| Traffic Mix | Avg Cost/Query | Avg Latency | Quality Score |
|-------------|---------------|-------------|---------------|
| All Premium | $0.050 | 1500ms | 1.00 (baseline) |
| All Fast | $0.001 | 50ms | 0.72 |
| Tiered (80/15/5) | $0.005 | 120ms | 0.94 |
| Tiered + escalation | $0.008 | 150ms | 0.97 |

### Production Considerations

- **Router accuracy is everything**: 5% misrouting of complex queries to fast tier = visible quality degradation. Invest heavily in router training data.
- **Feedback loop**: Log every escalation. Use escalated queries as training data for the router (they were misclassified).
- **A/B testing**: Run 5% of fast-tier traffic through premium tier to measure quality gap. Adjust thresholds based on results.
- **Cost ceiling**: Even with tiered inference, set per-user cost ceilings. A user sending only complex queries shouldn't bankrupt the system.
- **Model refresh**: When fast model is retrained/upgraded, re-evaluate routing thresholds. Better fast model → more queries can go to fast tier.
