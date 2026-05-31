"""
Token Counter - Understand how LLMs see your text.

This program demonstrates tokenization: how text is broken into tokens,
how different models tokenize differently, and what it costs.
"""

import tiktoken

# Pricing per 1M tokens (input, output) in USD
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "encoding": "o200k_base"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "encoding": "o200k_base"},
    "gpt-4": {"input": 30.00, "output": 60.00, "encoding": "cl100k_base"},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "encoding": "cl100k_base"},
}

COLORS = [
    "\033[42m", "\033[43m", "\033[44m", "\033[45m",
    "\033[46m", "\033[41m", "\033[47m\033[30m",
]
RESET = "\033[0m"


def count_tokens(text: str, encoding_name: str) -> tuple[list[int], list[str]]:
    """Tokenize text and return token IDs and decoded strings."""
    enc = tiktoken.get_encoding(encoding_name)
    token_ids = enc.encode(text)
    token_strings = [enc.decode([tid]) for tid in token_ids]
    return token_ids, token_strings


def visualize_tokens(token_strings: list[str]) -> str:
    """Create a colorized visualization of tokens."""
    parts = []
    for i, token in enumerate(token_strings):
        color = COLORS[i % len(COLORS)]
        display = token.replace("\n", "\\n").replace("\t", "\\t")
        parts.append(f"{color} {display} {RESET}")
    return "".join(parts)


def calculate_cost(num_tokens: int, price_per_million: float) -> float:
    """Calculate cost for a given number of tokens."""
    return num_tokens * price_per_million / 1_000_000


def analyze_text(text: str):
    """Full analysis of text across all models."""
    print(f"\n{'='*60}")
    print(f"INPUT TEXT ({len(text)} characters):")
    print(f"  \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
    print(f"{'='*60}\n")

    for model, info in MODEL_PRICING.items():
        token_ids, token_strings = count_tokens(text, info["encoding"])
        num_tokens = len(token_ids)
        input_cost = calculate_cost(num_tokens, info["input"])
        output_cost = calculate_cost(num_tokens, info["output"])

        print(f"  {model:<18} │ {num_tokens:>6} tokens │ "
              f"Input: ${input_cost:.6f} │ Output: ${output_cost:.6f}")

    # Visual tokenization using gpt-4o encoding
    print(f"\n  Token visualization (gpt-4o encoding):")
    _, token_strings = count_tokens(text, "o200k_base")
    print(f"  {visualize_tokens(token_strings[:30])}")
    if len(token_strings) > 30:
        print(f"  ... and {len(token_strings) - 30} more tokens")
    print()


def compare_texts():
    """Compare different types of text to show tokenization differences."""
    samples = [
        ("Simple English", "Hello world, how are you today?"),
        ("Technical", "The HTTP/2 protocol uses HPACK header compression."),
        ("Code", "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"),
        ("JSON", '{"name": "Alice", "age": 30, "city": "New York"}'),
        ("Non-English (Spanish)", "Buenos días, ¿cómo estás hoy?"),
        ("Non-English (Japanese)", "こんにちは、今日はどうですか？"),
        ("Numbers", "The year 2024 had 366 days and GDP was $28,781,083,000,000"),
        ("Repetitive", "the the the the the the the the the the"),
    ]

    print("\n" + "=" * 70)
    print(" TOKEN COUNT COMPARISON ACROSS TEXT TYPES")
    print("=" * 70)
    print(f"\n  {'Text Type':<20} │ {'Chars':>5} │ {'Tokens':>6} │ {'Chars/Token':>11} │ Cost (GPT-4o input)")
    print(f"  {'─'*20}─┼─{'─'*5}─┼─{'─'*6}─┼─{'─'*11}─┼─{'─'*20}")

    enc = tiktoken.get_encoding("o200k_base")
    for label, text in samples:
        tokens = enc.encode(text)
        num_tokens = len(tokens)
        ratio = len(text) / num_tokens
        cost = calculate_cost(num_tokens, MODEL_PRICING["gpt-4o"]["input"])
        print(f"  {label:<20} │ {len(text):>5} │ {num_tokens:>6} │ {ratio:>8.1f}    │ ${cost:.6f}")

    print()


def cost_calculator():
    """Interactive cost calculator for real-world scenarios."""
    print("\n" + "=" * 70)
    print(" REAL-WORLD COST SCENARIOS")
    print("=" * 70)

    scenarios = [
        ("Single chat message", 100, 300),
        ("RAG query (with context)", 5000, 500),
        ("Document summary (10 pages)", 4000, 800),
        ("Code generation request", 2000, 1000),
        ("Full conversation (20 turns)", 15000, 3000),
    ]

    print(f"\n  {'Scenario':<35} │ {'In Tokens':>9} │ {'Out Tokens':>10} │ {'GPT-4o':>10} │ {'GPT-4o-mini':>11}")
    print(f"  {'─'*35}─┼─{'─'*9}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*11}")

    for scenario, input_tokens, output_tokens in scenarios:
        cost_4o = (calculate_cost(input_tokens, MODEL_PRICING["gpt-4o"]["input"]) +
                   calculate_cost(output_tokens, MODEL_PRICING["gpt-4o"]["output"]))
        cost_mini = (calculate_cost(input_tokens, MODEL_PRICING["gpt-4o-mini"]["input"]) +
                     calculate_cost(output_tokens, MODEL_PRICING["gpt-4o-mini"]["output"]))
        print(f"  {scenario:<35} │ {input_tokens:>9,} │ {output_tokens:>10,} │ ${cost_4o:>8.4f} │ ${cost_mini:>9.4f}")

    # Scale calculation
    print(f"\n  At 100,000 requests/day (RAG query scenario):")
    daily_4o = 100_000 * (calculate_cost(5000, 2.50) + calculate_cost(500, 10.00))
    daily_mini = 100_000 * (calculate_cost(5000, 0.15) + calculate_cost(500, 0.60))
    print(f"    GPT-4o:      ${daily_4o:,.0f}/day = ${daily_4o*30:,.0f}/month")
    print(f"    GPT-4o-mini: ${daily_mini:,.0f}/day = ${daily_mini*30:,.0f}/month")
    print(f"    Savings:     {daily_4o/daily_mini:.0f}x cheaper with mini")


def main():
    print("\n" + "=" * 70)
    print("  TOKEN COUNTER - Understanding How LLMs See Your Text")
    print("=" * 70)

    # Analyze specific texts
    analyze_text("Hello world")
    analyze_text("Artificial intelligence is transforming how we build software systems.")
    analyze_text("def hello():\n    print('Hello, World!')\n\nhello()")

    # Compare different text types
    compare_texts()

    # Cost scenarios
    cost_calculator()

    # Interactive mode
    print("\n" + "=" * 70)
    print(" INTERACTIVE MODE - Enter text to tokenize (or 'quit' to exit)")
    print("=" * 70)

    while True:
        try:
            text = input("\n  Enter text: ").strip()
            if text.lower() in ("quit", "exit", "q"):
                break
            if text:
                analyze_text(text)
        except (KeyboardInterrupt, EOFError):
            break

    print("\n  Done! 👋\n")


if __name__ == "__main__":
    main()
