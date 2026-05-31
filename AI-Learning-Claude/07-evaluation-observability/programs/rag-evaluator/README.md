# RAG Evaluator

## What This Does

A complete RAG evaluation system that measures the quality of your Retrieval-Augmented Generation pipeline. It takes a golden dataset (questions + ground truth answers + retrieved contexts) and computes:

- **Faithfulness**: Is the answer grounded in the retrieved context?
- **Answer Relevance**: Does the answer address the question?
- **Context Precision**: Are the retrieved documents relevant?
- **Context Recall**: Did we retrieve all necessary information?

## How It Works

1. Loads a golden dataset with questions, ground truths, contexts, and generated answers
2. Uses LLM-as-judge (GPT-4) to evaluate faithfulness and relevance
3. Uses semantic similarity for context precision and recall
4. Outputs a quality report with per-question and aggregate scores

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Output

```
=== RAG Evaluation Report ===
Questions evaluated: 10

Faithfulness:       0.92 (min: 0.80, max: 1.00)
Answer Relevance:   0.89 (min: 0.70, max: 1.00)
Context Precision:  0.85 (min: 0.60, max: 1.00)
Context Recall:     0.88 (min: 0.70, max: 1.00)

Overall Quality:    0.89 ✓ PASS (threshold: 0.85)
```

## Extending

- Add your own golden dataset in `golden_dataset.json`
- Adjust thresholds in `main.py`
- Add custom metrics by implementing new evaluation functions
