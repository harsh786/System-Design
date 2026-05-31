"""
Chain-of-Thought Prompting Demo
================================
Compares standard prompting vs CoT on reasoning tasks.
Shows how "thinking step by step" dramatically improves accuracy.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    """Call the LLM and return the response."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()


# =============================================================================
# Test Problems with Known Answers
# =============================================================================

PROBLEMS = [
    {
        "question": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?",
        "answer": "$0.05",
        "category": "math",
    },
    {
        "question": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
        "answer": "5 minutes",
        "category": "logic",
    },
    {
        "question": "In a lake, there is a patch of lily pads. Every day, the patch doubles in size. If it takes 48 days for the patch to cover the entire lake, how long would it take for the patch to cover half of the lake?",
        "answer": "47 days",
        "category": "logic",
    },
    {
        "question": "A farmer has 17 sheep. All but 9 die. How many sheep does the farmer have left?",
        "answer": "9",
        "category": "trick",
    },
    {
        "question": "If you have a 3-gallon jug and a 5-gallon jug, how do you measure exactly 4 gallons of water?",
        "answer": "Fill 5-gallon, pour into 3-gallon (leaving 2 in the 5), empty 3-gallon, pour 2 into 3-gallon, fill 5-gallon again. Now you have 5 + 2 that was in 3 = but actually: fill 5, pour into 3 leaving 2, empty 3, pour 2 into 3, fill 5, pour from 5 into 3 (which has 2, needs 1 more), leaving 4 in the 5-gallon jug.",
        "category": "reasoning",
    },
    {
        "question": "Three people check into a hotel room that costs $30. They each pay $10. The manager realizes the room should only cost $25 and gives $5 to the bellboy to return. The bellboy keeps $2 and gives $1 back to each person. So each person paid $9 (total $27), the bellboy has $2. That's $29. Where's the missing dollar?",
        "answer": "There is no missing dollar. The $27 paid includes the $25 for the room + $2 the bellboy kept. You shouldn't add the $2 to $27; you should subtract it.",
        "category": "logic",
    },
]


# =============================================================================
# Standard Prompting (No CoT)
# =============================================================================

def solve_standard(question: str) -> str:
    """Solve with standard prompting — just ask for the answer."""
    prompt = f"""Answer this question. Give only your final answer, be concise.

Question: {question}

Answer:"""
    return call_llm(prompt)


# =============================================================================
# Zero-Shot CoT
# =============================================================================

def solve_zero_shot_cot(question: str) -> str:
    """Solve with zero-shot CoT — just add 'Let's think step by step'."""
    prompt = f"""Question: {question}

Let's think step by step, then give the final answer."""
    return call_llm(prompt)


# =============================================================================
# Few-Shot CoT
# =============================================================================

FEW_SHOT_COT_EXAMPLES = """
Question: If John has 3 apples and gives away 1, then buys 5 more, and eats 2, how many does he have?
Let's think step by step:
- Starts with 3 apples
- Gives away 1: 3 - 1 = 2
- Buys 5 more: 2 + 5 = 7
- Eats 2: 7 - 2 = 5
Final answer: 5 apples

Question: A train leaves Station A at 9:00 AM traveling at 60 mph. Another train leaves Station B (300 miles away) at 10:00 AM traveling toward Station A at 40 mph. When do they meet?
Let's think step by step:
- Train A starts at 9:00 at 60 mph
- By 10:00 AM, Train A has traveled 60 miles, so they're now 240 miles apart
- After 10:00, they approach each other at 60 + 40 = 100 mph combined
- Time to meet: 240 / 100 = 2.4 hours after 10:00 AM
- 2.4 hours = 2 hours 24 minutes
- They meet at 12:24 PM
Final answer: 12:24 PM
"""


def solve_few_shot_cot(question: str) -> str:
    """Solve with few-shot CoT — provide reasoning examples."""
    prompt = f"""{FEW_SHOT_COT_EXAMPLES}

Question: {question}
Let's think step by step:"""
    return call_llm(prompt)


# =============================================================================
# Run Comparison
# =============================================================================

def main():
    print("=" * 70)
    print("CHAIN-OF-THOUGHT PROMPTING COMPARISON")
    print("=" * 70)
    print(f"Model: {MODEL}\n")

    results = {"standard": 0, "zero_shot_cot": 0, "few_shot_cot": 0}

    for i, problem in enumerate(PROBLEMS, 1):
        print(f"\n{'─' * 70}")
        print(f"Problem {i} [{problem['category']}]:")
        print(f"  {problem['question']}")
        print(f"  Expected: {problem['answer'][:80]}...")
        print()

        # Standard
        standard_answer = solve_standard(problem["question"])
        print(f"  📋 Standard:      {standard_answer[:100]}")

        # Zero-shot CoT
        cot_answer = solve_zero_shot_cot(problem["question"])
        # Extract just the final line for display
        cot_final = cot_answer.split("\n")[-1] if "\n" in cot_answer else cot_answer
        print(f"  🧠 Zero-shot CoT: {cot_final[:100]}")

        # Few-shot CoT
        few_shot_answer = solve_few_shot_cot(problem["question"])
        few_shot_final = few_shot_answer.split("\n")[-1] if "\n" in few_shot_answer else few_shot_answer
        print(f"  📚 Few-shot CoT:  {few_shot_final[:100]}")

    print(f"\n{'=' * 70}")
    print("OBSERVATIONS:")
    print("─" * 70)
    print("""
    1. Standard prompting often gives the 'intuitive but wrong' answer
       (e.g., $0.10 for the bat-and-ball problem)
    
    2. Zero-shot CoT ('Let's think step by step') catches many errors
       by forcing the model to show intermediate reasoning
    
    3. Few-shot CoT with examples of reasoning patterns is most reliable
       for complex multi-step problems
    
    4. CoT adds tokens (cost + latency) — use it when accuracy matters
    """)

    # Bonus: Show the FULL reasoning for one problem
    print("=" * 70)
    print("FULL REASONING TRACE (Zero-shot CoT on bat-and-ball problem):")
    print("─" * 70)
    full_reasoning = solve_zero_shot_cot(PROBLEMS[0]["question"])
    print(full_reasoning)


if __name__ == "__main__":
    main()
