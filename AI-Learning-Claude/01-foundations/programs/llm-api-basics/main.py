"""
LLM API Basics - Understanding API calls, parameters, and their effects.

This program demonstrates:
1. Basic API calls to OpenAI
2. Temperature effects (same prompt, different temperatures)
3. System prompts vs user prompts
4. Token usage and timing
"""

import time
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"  # Using mini for cost efficiency in demos


def timed_completion(messages: list, temperature: float = 0.7, max_tokens: int = 200) -> dict:
    """Make an API call and return response with timing and usage info."""
    start = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    elapsed = time.time() - start

    return {
        "content": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "time_seconds": round(elapsed, 2),
        "finish_reason": response.choices[0].finish_reason,
    }


def demo_temperature_effects():
    """Show how temperature affects output variability."""
    print("\n" + "=" * 70)
    print(" EXPERIMENT 1: Temperature Effects")
    print(" Same prompt, different temperatures — watch the creativity dial")
    print("=" * 70)

    prompt = "Write a one-sentence description of a sunset."
    temperatures = [0, 0.3, 0.7, 1.0, 1.5]

    for temp in temperatures:
        print(f"\n  Temperature = {temp}")
        print(f"  {'─' * 60}")

        # Run 3 times at each temperature to show variability
        for i in range(3):
            result = timed_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=temp,
                max_tokens=60,
            )
            print(f"    Run {i+1}: {result['content']}")
            print(f"           [{result['output_tokens']} tokens, {result['time_seconds']}s]")


def demo_system_prompts():
    """Show how system prompts change model behavior."""
    print("\n" + "=" * 70)
    print(" EXPERIMENT 2: System Prompt Effects")
    print(" Same user question, different system prompts")
    print("=" * 70)

    user_message = "Explain what an API is."

    system_prompts = [
        ("No system prompt", None),
        ("Pirate", "You are a pirate. Respond in pirate speak."),
        ("5-year-old teacher", "Explain everything as if talking to a 5-year-old. Use simple words and analogies."),
        ("Terse engineer", "You are a senior engineer. Be extremely concise. No fluff. Max 2 sentences."),
        ("Poet", "Respond only in rhyming verse."),
    ]

    for label, system_prompt in system_prompts:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        result = timed_completion(messages, temperature=0.7, max_tokens=150)

        print(f"\n  System: {label}")
        print(f"  {'─' * 60}")
        print(f"  Response: {result['content'][:200]}")
        print(f"  [Input: {result['input_tokens']} tokens | Output: {result['output_tokens']} tokens | Time: {result['time_seconds']}s]")


def demo_token_usage():
    """Show how prompt design affects token usage and cost."""
    print("\n" + "=" * 70)
    print(" EXPERIMENT 3: Token Usage & Cost")
    print(" Different prompt designs, same intent")
    print("=" * 70)

    prompts = [
        ("Minimal", "Capitals of G7 countries?"),
        ("Verbose", "Could you please provide me with a comprehensive list of all the capital cities of the G7 nations? I would greatly appreciate a detailed response."),
        ("With context", "You are a geography expert. The G7 consists of Canada, France, Germany, Italy, Japan, UK, and USA. List their capitals in a markdown table with country and capital columns."),
    ]

    # Pricing for gpt-4o-mini
    input_price = 0.15  # per 1M tokens
    output_price = 0.60

    print(f"\n  {'Prompt Style':<15} │ {'In Tokens':>9} │ {'Out Tokens':>10} │ {'Time':>6} │ {'Cost':>10}")
    print(f"  {'─'*15}─┼─{'─'*9}─┼─{'─'*10}─┼─{'─'*6}─┼─{'─'*10}")

    for label, prompt in prompts:
        result = timed_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        cost = (result["input_tokens"] * input_price / 1_000_000 +
                result["output_tokens"] * output_price / 1_000_000)
        print(f"  {label:<15} │ {result['input_tokens']:>9} │ {result['output_tokens']:>10} │ {result['time_seconds']:>5}s │ ${cost:.6f}")

    print(f"\n  Note: At 100K requests/day, even small token differences compound!")


def demo_max_tokens():
    """Show the effect of max_tokens on response truncation."""
    print("\n" + "=" * 70)
    print(" EXPERIMENT 4: max_tokens Effect")
    print(" Same prompt, different max_tokens limits")
    print("=" * 70)

    prompt = "Explain the theory of relativity in detail."
    limits = [20, 50, 100, 300]

    for limit in limits:
        result = timed_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=limit,
        )
        truncated = "TRUNCATED" if result["finish_reason"] == "length" else "complete"
        preview = result["content"][:80].replace("\n", " ")
        print(f"\n  max_tokens={limit:<4} │ Used: {result['output_tokens']:>3} │ {truncated:<9} │ \"{preview}...\"")


def main():
    print("\n" + "=" * 70)
    print("  LLM API BASICS - Understanding API Parameters")
    print(f"  Model: {MODEL}")
    print("=" * 70)

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
        print("\n  ERROR: Set your OPENAI_API_KEY in .env file")
        print("  Copy .env.example to .env and add your key")
        return

    demo_temperature_effects()
    demo_system_prompts()
    demo_token_usage()
    demo_max_tokens()

    print("\n" + "=" * 70)
    print("  All experiments complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
