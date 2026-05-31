"""
Prompt Chaining Demo
=====================
Shows how chaining multiple focused prompts produces better results
than a single complex prompt for multi-step tasks.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def call_llm(prompt: str, system: str = "", temperature: float = 0.0) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=temperature, max_tokens=1500
    )
    return response.choices[0].message.content.strip()


# =============================================================================
# Sample Document for Analysis
# =============================================================================

SAMPLE_DOCUMENT = """
QUARTERLY BUSINESS REVIEW - Q3 2024

Revenue grew 23% YoY to $45.2M, exceeding our target of $42M. The growth was primarily 
driven by our enterprise segment which saw 34% growth, while SMB grew 12%. Customer 
acquisition cost (CAC) increased 15% to $1,200 per customer due to increased competition 
in the market.

Churn rate improved from 4.2% to 3.8%, saving an estimated $2.1M in annual recurring 
revenue. The product team shipped 3 major features: AI-powered search (adopted by 67% 
of enterprise users within 30 days), bulk import tool, and the new dashboard.

Engineering headcount grew from 45 to 58 (+29%). We opened a new office in Austin, TX. 
Two senior engineers departed for competitors, creating a gap in the infrastructure team. 
Mean time to resolution (MTTR) for P1 incidents increased from 23 minutes to 41 minutes.

The board approved a $10M Series C extension at a $250M valuation. Cash runway is 
18 months at current burn rate. We plan to invest $3M in AI capabilities in Q4.

Key risks: (1) Infrastructure team understaffing may impact reliability SLAs, 
(2) Rising CAC suggests market saturation in current segments, 
(3) Dependency on single cloud provider creates concentration risk.
"""


# =============================================================================
# Approach 1: Single Prompt (Monolithic)
# =============================================================================

def single_prompt_analysis(document: str) -> str:
    """Try to do everything in one prompt."""
    prompt = f"""Analyze this business document completely. Extract all key metrics, 
classify each point as positive/negative/neutral, identify risks and opportunities, 
provide strategic recommendations, and format as a structured executive brief with 
sections for: Financial Summary, Product & Engineering, Risks, and Recommendations.

Document:
{document}"""
    return call_llm(prompt)


# =============================================================================
# Approach 2: Chained Prompts (Pipeline)
# =============================================================================

def step1_extract_facts(document: str) -> str:
    """Step 1: Extract raw facts and metrics."""
    prompt = f"""Extract ALL quantitative facts and key statements from this document.
Return as a JSON list of objects with fields: "fact", "category" (financial/product/team/risk), "value" (if numeric).

Document:
{document}

JSON:"""
    return call_llm(prompt)


def step2_classify_sentiment(facts_json: str) -> str:
    """Step 2: Classify each fact as positive, negative, or neutral."""
    prompt = f"""For each fact below, add a "sentiment" field (positive/negative/neutral) 
and a "impact" field (high/medium/low) based on business impact.

Facts:
{facts_json}

Return the updated JSON with sentiment and impact added to each entry:"""
    return call_llm(prompt)


def step3_analyze(classified_json: str) -> str:
    """Step 3: Analyze patterns and generate insights."""
    prompt = f"""Based on these classified business facts, provide strategic analysis:

1. What are the 3 most important positive signals?
2. What are the 3 most concerning negative signals?
3. What connections or patterns exist between the facts?
4. What questions should leadership be asking?

Facts:
{classified_json}

Analysis:"""
    return call_llm(prompt)


def step4_format_report(analysis: str, facts: str) -> str:
    """Step 4: Format into executive brief."""
    prompt = f"""Format the following analysis into a concise executive brief.
Use this exact structure:

## Executive Summary (2 sentences max)
## Key Wins
- (bullet points)
## Concerns
- (bullet points)  
## Strategic Recommendations
1. (numbered, actionable)
## Key Metrics Table
| Metric | Value | Trend |

Analysis: {analysis}

Raw facts for the metrics table: {facts}

Executive Brief:"""
    return call_llm(prompt)


def chained_analysis(document: str) -> dict:
    """Run the full chain with intermediate results."""
    results = {}

    print("  Step 1: Extracting facts...")
    results["step1_facts"] = step1_extract_facts(document)

    print("  Step 2: Classifying sentiment...")
    results["step2_classified"] = step2_classify_sentiment(results["step1_facts"])

    print("  Step 3: Analyzing patterns...")
    results["step3_analysis"] = step3_analyze(results["step2_classified"])

    print("  Step 4: Formatting report...")
    results["step4_report"] = step4_format_report(
        results["step3_analysis"], results["step1_facts"]
    )

    return results


# =============================================================================
# Error Handling Between Chains
# =============================================================================

def safe_chain_step(step_fn, input_data: str, step_name: str, fallback: str = "") -> str:
    """Execute a chain step with error handling."""
    try:
        result = step_fn(input_data)
        # Validate result isn't empty
        if not result or len(result) < 10:
            print(f"  ⚠️  {step_name}: Empty result, using fallback")
            return fallback or input_data
        return result
    except Exception as e:
        print(f"  ❌ {step_name} failed: {e}")
        return fallback or input_data


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 70)
    print("PROMPT CHAINING COMPARISON")
    print("=" * 70)
    print(f"Model: {MODEL}")
    print(f"Document: Q3 2024 Business Review ({len(SAMPLE_DOCUMENT)} chars)\n")

    # --- Single Prompt ---
    print("─" * 70)
    print("APPROACH 1: Single Monolithic Prompt")
    print("─" * 70)
    single_result = single_prompt_analysis(SAMPLE_DOCUMENT)
    print(single_result[:500])
    print("..." if len(single_result) > 500 else "")

    # --- Chained Prompts ---
    print(f"\n\n{'─' * 70}")
    print("APPROACH 2: Chained Prompts (4 steps)")
    print("─" * 70)
    chain_results = chained_analysis(SAMPLE_DOCUMENT)

    print("\n--- Intermediate: Extracted Facts (Step 1) ---")
    print(chain_results["step1_facts"][:300] + "...")

    print("\n--- Intermediate: Classified (Step 2) ---")
    print(chain_results["step2_classified"][:300] + "...")

    print("\n--- Final Report (Step 4) ---")
    print(chain_results["step4_report"])

    # --- Comparison ---
    print(f"\n\n{'=' * 70}")
    print("COMPARISON")
    print("─" * 70)
    print(f"""
    Single Prompt:
      - Output length: {len(single_result)} chars
      - API calls: 1
      - Debuggability: Low (black box)
    
    Chained Prompts:
      - Output length: {len(chain_results['step4_report'])} chars
      - API calls: 4
      - Debuggability: High (inspect each step)
    
    Key Differences:
      - Chained approach produces more structured, complete output
      - Each step is focused and verifiable
      - Errors are catchable at each stage
      - Single prompt may miss details or mix concerns
      - Chained approach costs more (4x API calls) but higher quality
    """)

    # --- Error Handling Demo ---
    print("─" * 70)
    print("BONUS: Error Handling Between Chains")
    print("─" * 70)
    print("  Using safe_chain_step() wrapper for production resilience...")

    safe_facts = safe_chain_step(step1_extract_facts, SAMPLE_DOCUMENT, "Extract")
    safe_classified = safe_chain_step(step2_classify_sentiment, safe_facts, "Classify")
    print("  ✓ Chain completed with error handling\n")


if __name__ == "__main__":
    main()
