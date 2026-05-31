"""
RAG Evaluator - Evaluates Retrieval-Augmented Generation quality.

Computes: Faithfulness, Answer Relevance, Context Precision, Context Recall
Uses LLM-as-judge for subjective metrics, semantic similarity for objective ones.
"""

import json
import os
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# --- LLM-as-Judge Prompts ---

FAITHFULNESS_PROMPT = """You are evaluating whether an AI-generated answer is faithful to the provided context.

Context:
{context}

Answer:
{answer}

Task: Identify each factual claim in the answer. For each claim, determine if it is supported by the context.

Output a JSON object:
{{
  "claims": [
    {{"claim": "...", "supported": true/false, "evidence": "quote from context or 'no support'"}}
  ],
  "faithfulness_score": <float between 0 and 1 = supported_claims / total_claims>
}}

Only output valid JSON."""

RELEVANCE_PROMPT = """You are evaluating whether an AI-generated answer is relevant to the question asked.

Question: {question}
Answer: {answer}

Evaluate:
1. Does the answer directly address the question?
2. Is the information provided useful for answering the question?
3. Is there unnecessary off-topic information?

Output a JSON object:
{{
  "reasoning": "your analysis",
  "relevance_score": <float between 0 and 1>
}}

Only output valid JSON."""

CONTEXT_PRECISION_PROMPT = """You are evaluating whether retrieved contexts are relevant to the question.

Question: {question}

Retrieved contexts:
{contexts}

For each context, determine if it contains information useful for answering the question.

Output a JSON object:
{{
  "context_assessments": [
    {{"context_index": 0, "relevant": true/false, "reason": "..."}}
  ],
  "precision_score": <float between 0 and 1 = relevant_contexts / total_contexts>
}}

Only output valid JSON."""


def evaluate_faithfulness(answer: str, contexts: list[str]) -> float:
    """Use LLM-as-judge to evaluate if answer is grounded in context."""
    context_text = "\n---\n".join(contexts)
    prompt = FAITHFULNESS_PROMPT.format(context=context_text, answer=answer)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("faithfulness_score", 0))
    except Exception as e:
        print(f"  [faithfulness error: {e}]")
        return 0.0


def evaluate_relevance(question: str, answer: str) -> float:
    """Use LLM-as-judge to evaluate if answer addresses the question."""
    prompt = RELEVANCE_PROMPT.format(question=question, answer=answer)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("relevance_score", 0))
    except Exception as e:
        print(f"  [relevance error: {e}]")
        return 0.0


def evaluate_context_precision(question: str, contexts: list[str]) -> float:
    """Use LLM-as-judge to evaluate if retrieved contexts are relevant."""
    contexts_text = "\n".join(
        f"[Context {i}]: {c}" for i, c in enumerate(contexts)
    )
    prompt = CONTEXT_PRECISION_PROMPT.format(
        question=question, contexts=contexts_text
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("precision_score", 0))
    except Exception as e:
        print(f"  [precision error: {e}]")
        return 0.0


def evaluate_context_recall(
    ground_truth: str, contexts: list[str]
) -> float:
    """Evaluate how much of the ground truth is covered by retrieved contexts.

    Uses embedding similarity between ground truth sentences and contexts.
    """
    # Split ground truth into sentences
    gt_sentences = [s.strip() for s in ground_truth.split(".") if s.strip()]
    if not gt_sentences:
        return 0.0

    context_text = " ".join(contexts).lower()
    covered = 0

    for sentence in gt_sentences:
        # Simple keyword overlap check (in production, use embeddings)
        words = sentence.lower().split()
        key_words = [w for w in words if len(w) > 3]
        if key_words:
            overlap = sum(1 for w in key_words if w in context_text)
            if overlap / len(key_words) > 0.5:
                covered += 1

    return covered / len(gt_sentences)


def run_evaluation(dataset_path: str = "golden_dataset.json") -> pd.DataFrame:
    """Run full evaluation on golden dataset."""
    with open(dataset_path) as f:
        dataset = json.load(f)

    results = []
    print(f"Evaluating {len(dataset)} examples...\n")

    for i, example in enumerate(dataset):
        print(f"  [{i+1}/{len(dataset)}] {example['question'][:50]}...")

        faithfulness = evaluate_faithfulness(
            example["generated_answer"], example["contexts"]
        )
        relevance = evaluate_relevance(
            example["question"], example["generated_answer"]
        )
        precision = evaluate_context_precision(
            example["question"], example["contexts"]
        )
        recall = evaluate_context_recall(
            example["ground_truth"], example["contexts"]
        )

        results.append(
            {
                "question": example["question"],
                "faithfulness": faithfulness,
                "relevance": relevance,
                "context_precision": precision,
                "context_recall": recall,
            }
        )

    return pd.DataFrame(results)


def print_report(df: pd.DataFrame, threshold: float = 0.85):
    """Print evaluation report."""
    print("\n" + "=" * 50)
    print("        RAG EVALUATION REPORT")
    print("=" * 50)
    print(f"\nQuestions evaluated: {len(df)}\n")

    metrics = ["faithfulness", "relevance", "context_precision", "context_recall"]

    for metric in metrics:
        mean = df[metric].mean()
        min_val = df[metric].min()
        max_val = df[metric].max()
        status = "PASS" if mean >= threshold else "FAIL"
        symbol = "\u2713" if mean >= threshold else "\u2717"
        print(
            f"  {metric:<20} {mean:.3f}  "
            f"(min: {min_val:.2f}, max: {max_val:.2f})  {symbol} {status}"
        )

    overall = df[metrics].mean().mean()
    status = "PASS" if overall >= threshold else "FAIL"
    symbol = "\u2713" if overall >= threshold else "\u2717"
    print(f"\n  {'Overall Quality':<20} {overall:.3f}  {symbol} {status}")
    print(f"  {'Threshold':<20} {threshold:.3f}")
    print("=" * 50)

    # Show worst performers
    print("\nLowest scoring questions:")
    df["avg_score"] = df[metrics].mean(axis=1)
    worst = df.nsmallest(3, "avg_score")
    for _, row in worst.iterrows():
        print(f"  - {row['question'][:60]}... (avg: {row['avg_score']:.2f})")


if __name__ == "__main__":
    df = run_evaluation()
    print_report(df)
