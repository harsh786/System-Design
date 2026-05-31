"""
Memory Compression Strategies Demo
Demonstrates: sliding window, progressive summarization, entity extraction,
hierarchical compression with information retention checks.
"""

import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

try:
    client = OpenAI()
    USE_LLM = True
except Exception:
    USE_LLM = False
    print("[Note: OpenAI not configured. Using mock compression.]\n")


# =============================================================================
# SAMPLE CONVERSATION (50 messages simulating a real session)
# =============================================================================

def generate_sample_conversation():
    """Generate a realistic 50-message conversation."""
    messages = [
        {"role": "user", "content": "Hi, I'm starting a new project. It's a RAG system for legal documents."},
        {"role": "assistant", "content": "Great! Legal document RAG systems have unique challenges. What's your tech stack?"},
        {"role": "user", "content": "We're using Python with FastAPI for the backend. Team of 5 engineers."},
        {"role": "assistant", "content": "Solid choice. FastAPI gives you async capabilities which helps with concurrent embedding requests."},
        {"role": "user", "content": "Exactly. We need to handle about 10,000 documents initially."},
        {"role": "assistant", "content": "10K docs is manageable. What's the average document length?"},
        {"role": "user", "content": "Most are 20-50 pages. Some contracts are over 100 pages."},
        {"role": "assistant", "content": "For long documents, chunking strategy is critical. Have you decided on an approach?"},
        {"role": "user", "content": "Not yet. We're considering recursive character splitting."},
        {"role": "assistant", "content": "Recursive splitting works well for legal docs. I'd suggest 512 tokens with overlap."},
        {"role": "user", "content": "What overlap would you recommend?"},
        {"role": "assistant", "content": "For legal text, 50-100 tokens overlap preserves clause boundaries. 10-20% of chunk size."},
        {"role": "user", "content": "Let's go with 512 chunks, 64 token overlap. Now for embeddings..."},
        {"role": "assistant", "content": "For embeddings, you have several options: OpenAI ada-002, E5-large, or BGE."},
        {"role": "user", "content": "We need something we can self-host. Budget is tight."},
        {"role": "assistant", "content": "Then E5-large or BGE-large are your best bets. Both run well on a single GPU."},
        {"role": "user", "content": "We have an A100 available. Which performs better on legal text?"},
        {"role": "assistant", "content": "BGE-large-en-v1.5 edges out on legal benchmarks. E5 is more general-purpose."},
        {"role": "user", "content": "OK let's go with BGE-large. Now for the vector database..."},
        {"role": "assistant", "content": "Popular options: Qdrant, Weaviate, Pinecone, Milvus. What are your priorities?"},
        {"role": "user", "content": "Self-hosted, good filtering support, and production-ready."},
        {"role": "assistant", "content": "Qdrant or Milvus then. Qdrant has better filtering and simpler operations."},
        {"role": "user", "content": "I've heard good things about Qdrant. Let's use that."},
        {"role": "assistant", "content": "Good choice. Qdrant supports payload filtering which is perfect for legal metadata."},
        {"role": "user", "content": "What metadata should we store with each chunk?"},
        {"role": "assistant", "content": "For legal docs: document_id, page_number, section_title, document_type, date, parties."},
        {"role": "user", "content": "Makes sense. We also need to track document versions."},
        {"role": "assistant", "content": "Add version_id and effective_date to metadata. Allows querying 'as of' a specific date."},
        {"role": "user", "content": "Perfect. Now the retrieval pipeline..."},
        {"role": "assistant", "content": "Basic flow: query → embed → vector search → rerank → return. Want to add hybrid search?"},
        {"role": "user", "content": "What's hybrid search in this context?"},
        {"role": "assistant", "content": "Combine dense (vector) search with sparse (BM25/keyword) search. Catches exact terms vectors miss."},
        {"role": "user", "content": "Legal terms are very specific. Yes, we need hybrid."},
        {"role": "assistant", "content": "Qdrant supports hybrid search natively. You can weight dense vs sparse results."},
        {"role": "user", "content": "What weights do you suggest?"},
        {"role": "assistant", "content": "Start with 0.7 dense / 0.3 sparse for legal. Tune based on evaluation results."},
        {"role": "user", "content": "Got it. Now for reranking after retrieval..."},
        {"role": "assistant", "content": "Cross-encoder reranking significantly improves precision. BGE-reranker or Cohere rerank API."},
        {"role": "user", "content": "We want self-hosted. BGE-reranker it is."},
        {"role": "assistant", "content": "BGE-reranker-large works well. Retrieve top-50, rerank to top-5 for the LLM."},
        {"role": "user", "content": "What about the generation side? Which LLM?"},
        {"role": "assistant", "content": "For legal: GPT-4o for accuracy, or Llama-3-70B for self-hosted. Legal needs high accuracy."},
        {"role": "user", "content": "We'll start with GPT-4o and evaluate open-source later."},
        {"role": "assistant", "content": "Smart approach. Use GPT-4o as baseline, measure quality, then compare with fine-tuned open models."},
        {"role": "user", "content": "What about hallucination prevention? Critical for legal."},
        {"role": "assistant", "content": "Key strategies: cite sources in response, use retrieval-grounded generation, add verification step."},
        {"role": "user", "content": "Can you elaborate on the verification step?"},
        {"role": "assistant", "content": "After generation, check each claim against retrieved docs. Flag unsupported statements. Some teams use a second LLM call for this."},
        {"role": "user", "content": "That's smart. We'll add claim verification. What about evaluation?"},
        {"role": "assistant", "content": "Evaluate with: RAGAS framework (faithfulness, relevance), human eval on 100 samples, and A/B testing."},
        {"role": "user", "content": "When's the deadline for all this?"},
        {"role": "assistant", "content": "When are you targeting launch?"},
        {"role": "user", "content": "March 15th. About 8 weeks from now."},
        {"role": "assistant", "content": "Tight but doable with 5 engineers. I'd suggest: weeks 1-2 indexing, weeks 3-4 retrieval, weeks 5-6 generation, weeks 7-8 eval and polish."},
    ]
    return messages


# =============================================================================
# COMPRESSION STRATEGY 1: Sliding Window
# =============================================================================

class SlidingWindowCompressor:
    """Keep recent messages in full, summarize older ones."""

    def __init__(self, window_size=10):
        self.window_size = window_size

    def compress(self, messages):
        if len(messages) <= self.window_size:
            return {"summary": "", "recent": messages, "compressed": False}

        old = messages[:-self.window_size]
        recent = messages[-self.window_size:]

        summary = self._summarize(old)
        return {
            "summary": summary,
            "recent": recent,
            "compressed": True,
            "original_count": len(messages),
            "kept_in_full": self.window_size,
            "summarized_count": len(old)
        }

    def _summarize(self, messages):
        if USE_LLM:
            text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Summarize this conversation concisely. Preserve all decisions, facts, and preferences. Use bullet points."
                }, {
                    "role": "user",
                    "content": text
                }],
                max_tokens=300
            )
            return response.choices[0].message.content
        else:
            # Mock summarization
            topics = set()
            decisions = []
            for m in messages:
                content = m["content"].lower()
                if "let's" in content or "go with" in content or "decided" in content:
                    decisions.append(m["content"][:80])
                for keyword in ["rag", "legal", "python", "fastapi", "qdrant", "bge", "chunk"]:
                    if keyword in content:
                        topics.add(keyword)

            summary = f"Topics discussed: {', '.join(topics)}.\n"
            if decisions:
                summary += "Decisions:\n" + "\n".join(f"- {d}" for d in decisions[:5])
            return summary


# =============================================================================
# COMPRESSION STRATEGY 2: Progressive Summarization
# =============================================================================

class ProgressiveSummarizer:
    """Multi-level summarization: raw → detailed → concise → facts."""

    def compress(self, messages):
        # Level 1: Detailed summary (keeps most info)
        level1 = self._summarize_level1(messages)

        # Level 2: Concise summary (key points only)
        level2 = self._summarize_level2(level1)

        # Level 3: Facts only (maximum compression)
        level3 = self._extract_facts(level1)

        return {
            "level1_detailed": level1,
            "level2_concise": level2,
            "level3_facts": level3,
            "compression_ratios": {
                "original_chars": sum(len(m["content"]) for m in messages),
                "level1_chars": len(level1),
                "level2_chars": len(level2),
                "level3_chars": len(level3),
            }
        }

    def _summarize_level1(self, messages):
        if USE_LLM:
            text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Create a detailed summary preserving ALL decisions, technical choices, facts, and preferences. Max 500 tokens."
                }, {"role": "user", "content": text}],
                max_tokens=500
            )
            return response.choices[0].message.content
        else:
            return (
                "Project: RAG system for legal documents. Team: 5 engineers, deadline March 15.\n"
                "Tech stack: Python/FastAPI backend, BGE-large embeddings (self-hosted on A100), "
                "Qdrant vector DB (self-hosted), GPT-4o for generation.\n"
                "Chunking: 512 tokens, 64 overlap, recursive character splitting.\n"
                "Retrieval: Hybrid search (0.7 dense / 0.3 sparse), BGE-reranker (top-50 → top-5).\n"
                "Features: Claim verification, source citations, metadata filtering.\n"
                "Metadata: document_id, page_number, section_title, doc_type, date, parties, version_id.\n"
                "Evaluation: RAGAS framework + human eval on 100 samples + A/B testing.\n"
                "Timeline: Weeks 1-2 indexing, 3-4 retrieval, 5-6 generation, 7-8 eval."
            )

    def _summarize_level2(self, level1_text):
        if USE_LLM:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Condense to key points only. Max 100 tokens."
                }, {"role": "user", "content": level1_text}],
                max_tokens=100
            )
            return response.choices[0].message.content
        else:
            return (
                "Legal RAG project: Python/FastAPI, BGE embeddings, Qdrant, GPT-4o. "
                "512-token chunks. Hybrid search with reranking. "
                "Deadline March 15, team of 5. Self-hosted where possible."
            )

    def _extract_facts(self, level1_text):
        if USE_LLM:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Extract only entity facts as 'entity: attribute' pairs. One per line. Max 10 facts."
                }, {"role": "user", "content": level1_text}],
                max_tokens=150
            )
            return response.choices[0].message.content
        else:
            return (
                "Project: legal RAG system\n"
                "Stack: Python, FastAPI, Qdrant, BGE-large, GPT-4o\n"
                "Chunks: 512 tokens, 64 overlap\n"
                "Search: hybrid (0.7/0.3), reranked\n"
                "Team: 5 engineers\n"
                "Deadline: March 15\n"
                "Hardware: A100 GPU"
            )


# =============================================================================
# COMPRESSION STRATEGY 3: Entity Extraction
# =============================================================================

class EntityExtractor:
    """Extract structured entity knowledge from conversations."""

    def extract(self, messages):
        if USE_LLM:
            text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": """Extract all entities and their attributes from this conversation.
Format as JSON: {"entities": {"name": {"attribute": "value", ...}, ...}}
Include: technologies, people, projects, decisions, configurations."""
                }, {"role": "user", "content": text}],
                max_tokens=400
            )
            try:
                return json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                return {"raw": response.choices[0].message.content}
        else:
            return {
                "entities": {
                    "Project": {"type": "RAG", "domain": "legal", "deadline": "March 15", "team_size": 5},
                    "Backend": {"framework": "FastAPI", "language": "Python"},
                    "Embeddings": {"model": "BGE-large-en-v1.5", "hosting": "self-hosted", "hardware": "A100"},
                    "VectorDB": {"name": "Qdrant", "hosting": "self-hosted", "features": "hybrid search, filtering"},
                    "Chunking": {"size": 512, "overlap": 64, "method": "recursive character"},
                    "Retrieval": {"type": "hybrid", "dense_weight": 0.7, "sparse_weight": 0.3, "reranker": "BGE-reranker-large"},
                    "Generation": {"model": "GPT-4o", "verification": "claim checking"},
                    "Documents": {"count": 10000, "length": "20-100 pages", "type": "legal/contracts"},
                }
            }


# =============================================================================
# INFORMATION RETENTION CHECK
# =============================================================================

def check_retention(original_messages, compressed_output):
    """Check what key facts survived compression."""
    # Define ground truth facts from the conversation
    ground_truth = [
        "RAG system for legal documents",
        "Python with FastAPI",
        "Team of 5 engineers",
        "10,000 documents",
        "512 token chunks",
        "64 token overlap",
        "BGE-large embeddings",
        "Self-hosted on A100",
        "Qdrant vector database",
        "Hybrid search 0.7 dense / 0.3 sparse",
        "BGE-reranker",
        "GPT-4o for generation",
        "Claim verification",
        "March 15 deadline",
        "8 week timeline",
    ]

    compressed_text = str(compressed_output).lower()
    retained = []
    lost = []

    for fact in ground_truth:
        # Check if key terms from the fact appear in compressed output
        key_terms = [t for t in fact.lower().split() if len(t) > 3]
        matches = sum(1 for t in key_terms if t in compressed_text)
        if matches >= len(key_terms) * 0.5:  # At least half the key terms present
            retained.append(fact)
        else:
            lost.append(fact)

    return {
        "total_facts": len(ground_truth),
        "retained": len(retained),
        "lost": len(lost),
        "retention_rate": len(retained) / len(ground_truth),
        "retained_facts": retained,
        "lost_facts": lost
    }


# =============================================================================
# MAIN DEMONSTRATION
# =============================================================================

def count_tokens_approx(text):
    """Approximate token count."""
    return len(str(text)) // 4


def main():
    print("=" * 60)
    print("  MEMORY COMPRESSION STRATEGIES DEMO")
    print("=" * 60)

    # Generate sample conversation
    messages = generate_sample_conversation()
    original_size = sum(len(m["content"]) for m in messages)
    original_tokens = count_tokens_approx(original_size)

    print(f"\n  Original conversation:")
    print(f"    Messages: {len(messages)}")
    print(f"    Characters: {original_size:,}")
    print(f"    Tokens (approx): {original_tokens:,}")

    # Strategy 1: Sliding Window
    print(f"\n{'─' * 60}")
    print("  STRATEGY 1: Sliding Window (keep last 10 messages)")
    print(f"{'─' * 60}")

    sw = SlidingWindowCompressor(window_size=10)
    sw_result = sw.compress(messages)

    summary_tokens = count_tokens_approx(sw_result["summary"])
    recent_tokens = count_tokens_approx(" ".join(m["content"] for m in sw_result["recent"]))
    total_compressed = summary_tokens + recent_tokens

    print(f"\n  Summary of messages 1-40: {summary_tokens} tokens")
    print(f"  Recent messages 41-50 (full): {recent_tokens} tokens")
    print(f"  Total after compression: {total_compressed} tokens")
    print(f"  Compression ratio: {original_tokens/max(total_compressed,1):.1f}x")
    print(f"\n  Summary preview:")
    print(f"    {sw_result['summary'][:200]}...")

    # Strategy 2: Progressive Summarization
    print(f"\n{'─' * 60}")
    print("  STRATEGY 2: Progressive Summarization (3 levels)")
    print(f"{'─' * 60}")

    ps = ProgressiveSummarizer()
    ps_result = ps.compress(messages)

    ratios = ps_result["compression_ratios"]
    print(f"\n  Original: {ratios['original_chars']:,} chars")
    print(f"  Level 1 (detailed): {ratios['level1_chars']:,} chars ({ratios['original_chars']/max(ratios['level1_chars'],1):.1f}x compression)")
    print(f"  Level 2 (concise):  {ratios['level2_chars']:,} chars ({ratios['original_chars']/max(ratios['level2_chars'],1):.1f}x compression)")
    print(f"  Level 3 (facts):    {ratios['level3_chars']:,} chars ({ratios['original_chars']/max(ratios['level3_chars'],1):.1f}x compression)")

    print(f"\n  Level 1 (detailed summary):")
    print(f"    {ps_result['level1_detailed'][:200]}...")
    print(f"\n  Level 2 (concise):")
    print(f"    {ps_result['level2_concise']}")
    print(f"\n  Level 3 (facts only):")
    print(f"    {ps_result['level3_facts']}")

    # Strategy 3: Entity Extraction
    print(f"\n{'─' * 60}")
    print("  STRATEGY 3: Entity Extraction")
    print(f"{'─' * 60}")

    ee = EntityExtractor()
    entities = ee.extract(messages)
    entity_text = json.dumps(entities, indent=2)
    entity_tokens = count_tokens_approx(entity_text)

    print(f"\n  Entities extracted: {len(entities.get('entities', {}))}")
    print(f"  Compressed size: {entity_tokens} tokens ({original_tokens/max(entity_tokens,1):.1f}x compression)")
    print(f"\n  Entity knowledge:")
    for name, attrs in entities.get("entities", {}).items():
        attrs_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
        print(f"    {name}: {attrs_str}")

    # Information Retention Check
    print(f"\n{'─' * 60}")
    print("  INFORMATION RETENTION CHECK")
    print(f"{'─' * 60}")

    # Check retention for each strategy
    strategies = {
        "Sliding Window": sw_result,
        "Progressive L1": ps_result["level1_detailed"],
        "Progressive L2": ps_result["level2_concise"],
        "Progressive L3 (facts)": ps_result["level3_facts"],
        "Entity Extraction": entities,
    }

    print(f"\n  {'Strategy':<25} {'Retained':<12} {'Lost':<8} {'Rate':<8}")
    print(f"  {'─'*25} {'─'*12} {'─'*8} {'─'*8}")

    for name, output in strategies.items():
        retention = check_retention(messages, output)
        rate_str = f"{retention['retention_rate']:.0%}"
        print(f"  {name:<25} {retention['retained']:<12} {retention['lost']:<8} {rate_str:<8}")

    # Final comparison
    print(f"\n{'─' * 60}")
    print("  COMPRESSION SUMMARY")
    print(f"{'─' * 60}")

    print(f"\n  {'Method':<25} {'Size (tokens)':<15} {'Compression':<12}")
    print(f"  {'─'*25} {'─'*15} {'─'*12}")
    print(f"  {'Original':<25} {original_tokens:<15} {'1x':<12}")
    sw_ratio = f"{original_tokens/max(total_compressed,1):.1f}x"
    print(f"  {'Sliding Window':<25} {total_compressed:<15} {sw_ratio:<12}")
    l1_tokens = count_tokens_approx(ps_result['level1_detailed'])
    l2_tokens = count_tokens_approx(ps_result['level2_concise'])
    l1_ratio = f"{original_tokens/max(l1_tokens,1):.1f}x"
    l2_ratio = f"{original_tokens/max(l2_tokens,1):.1f}x"
    print(f"  {'Progressive L1':<25} {l1_tokens:<15} {l1_ratio:<12}")
    print(f"  {'Progressive L2':<25} {l2_tokens:<15} {l2_ratio:<12}")
    ef_ratio = f"{original_tokens/max(entity_tokens,1):.1f}x"
    print(f"  {'Entity Facts':<25} {entity_tokens:<15} {ef_ratio:<12}")

    print(f"\n  Key Insight: 50 messages (~{original_tokens} tokens) can be compressed to")
    print(f"  ~{entity_tokens} tokens of entity facts with {check_retention(messages, entities)['retention_rate']:.0%} information retention.")
    print(f"\n  This means memory budget of 4000 tokens can hold the equivalent")
    print(f"  of {4000 // max(entity_tokens // len(entities.get('entities', {1:1})), 1)} sessions worth of knowledge!")


if __name__ == "__main__":
    main()
