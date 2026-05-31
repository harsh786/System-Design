# Fine-Tuning Data Preparation Pipeline
# Demonstrates: collection, cleaning, formatting, validation, splitting, analysis

import json
import os
import re
import random
import hashlib
from collections import Counter
from datetime import datetime

random.seed(42)

# =============================================================================
# STEP 1: Simulate Raw Production Data
# =============================================================================

CATEGORIES = ["billing", "technical", "general", "complaints", "feature_request"]
SYSTEM_PROMPT = "You are a helpful customer support agent for TechCorp. Be professional, concise, and empathetic."

# Simulated production logs (as if from a real system)
RAW_QUERIES = [
    # Billing
    ("How do I cancel my subscription?", "billing"),
    ("I was charged twice this month", "billing"),
    ("Can I get a refund for last month?", "billing"),
    ("How do I upgrade to the pro plan?", "billing"),
    ("What payment methods do you accept?", "billing"),
    ("My invoice shows the wrong amount", "billing"),
    ("When is my next billing date?", "billing"),
    ("Can I pause my subscription instead of canceling?", "billing"),
    ("Do you offer annual billing discounts?", "billing"),
    ("I need a receipt for tax purposes", "billing"),
    # Technical
    ("The app crashes when I upload large files", "technical"),
    ("How do I reset my password?", "technical"),
    ("API returns 500 error on POST requests", "technical"),
    ("Integration with Slack isn't working", "technical"),
    ("How do I export my data as CSV?", "technical"),
    ("The dashboard loads very slowly", "technical"),
    ("Two-factor authentication isn't sending codes", "technical"),
    ("Can I use the API with Python?", "technical"),
    ("My webhook endpoint isn't receiving events", "technical"),
    ("How do I set up SSO for my team?", "technical"),
    # General
    ("What are your business hours?", "general"),
    ("Do you have a mobile app?", "general"),
    ("How many users can I add to my team?", "general"),
    ("What's the difference between Pro and Enterprise?", "general"),
    ("Do you offer educational discounts?", "general"),
    ("Is my data stored in the EU?", "general"),
    ("What's your uptime SLA?", "general"),
    ("Can I white-label the product?", "general"),
    # Complaints
    ("Your service has been down 3 times this week!", "complaints"),
    ("I've been waiting 2 days for a response", "complaints"),
    ("The new UI update is terrible", "complaints"),
    ("Your pricing is way too high compared to competitors", "complaints"),
    ("I lost data because of your bug", "complaints"),
    # Feature requests
    ("Can you add dark mode?", "feature_request"),
    ("We need better reporting/analytics", "feature_request"),
    ("Please add bulk import from Excel", "feature_request"),
    ("Can you integrate with Jira?", "feature_request"),
    ("We need role-based access control", "feature_request"),
]

RESPONSE_TEMPLATES = {
    "billing": [
        "I'd be happy to help with your billing question. {detail} Is there anything else I can assist you with?",
        "Thank you for reaching out about your billing concern. {detail} Let me know if you need further assistance.",
    ],
    "technical": [
        "I understand you're experiencing a technical issue. {detail} If this doesn't resolve the problem, I can escalate to our engineering team.",
        "Thanks for reporting this. {detail} Please let me know if you continue to experience issues.",
    ],
    "general": [
        "Great question! {detail} Feel free to ask if you have any other questions.",
        "Thanks for your interest. {detail} Would you like more details about any specific aspect?",
    ],
    "complaints": [
        "I sincerely apologize for the inconvenience. {detail} We take this feedback seriously and are working to improve.",
        "I'm sorry to hear about your experience. {detail} Your feedback helps us do better.",
    ],
    "feature_request": [
        "Thank you for the suggestion! {detail} I've passed this along to our product team.",
        "That's a great idea. {detail} We're always looking to improve based on user feedback.",
    ],
}

DETAILS = {
    "billing": [
        "You can cancel anytime from Settings > Subscription > Cancel Plan.",
        "I've checked your account and issued a refund for the duplicate charge.",
        "Refunds are processed within 5-7 business days back to your original payment method.",
        "You can upgrade directly from your dashboard - the price difference will be prorated.",
        "We accept Visa, Mastercard, American Express, and PayPal.",
    ],
    "technical": [
        "This is a known issue with files over 100MB. We've deployed a fix - please try again.",
        "You can reset your password at app.techcorp.com/reset-password.",
        "The 500 error was caused by a malformed JSON body. Please ensure Content-Type is set to application/json.",
        "Please reconnect the Slack integration from Settings > Integrations > Slack > Reconnect.",
        "Go to Reports > Export and select CSV format. The file will be emailed to you within 5 minutes.",
    ],
    "general": [
        "Our support team is available Monday-Friday, 9am-6pm EST.",
        "Yes! Our mobile app is available on both iOS and Android.",
        "The Pro plan supports up to 50 team members. Enterprise is unlimited.",
        "Pro includes basic analytics and 5 integrations. Enterprise adds advanced reporting, SSO, and dedicated support.",
        "Yes, we offer 50% off for educational institutions. Please email edu@techcorp.com with your .edu address.",
    ],
    "complaints": [
        "We had unexpected infrastructure issues this week. We're migrating to a more reliable provider and expect 99.99% uptime going forward.",
        "I apologize for the delay. I'm prioritizing your case now and will have an answer within the hour.",
        "We hear you. We're rolling out an option to use the classic UI while we refine the new design based on feedback.",
        "I understand the concern. Let me connect you with our sales team to discuss a custom plan that fits your budget.",
        "I'm escalating this immediately. We'll work to recover your data and provide a post-mortem within 24 hours.",
    ],
    "feature_request": [
        "Dark mode is actually on our Q1 roadmap! You'll see it in the next 2-3 months.",
        "Better analytics is our #1 requested feature. We're actively developing an advanced reporting dashboard.",
        "Bulk import from Excel is available in our Enterprise plan. I can help you set it up.",
        "Jira integration is in beta! Would you like early access?",
        "RBAC is available on Enterprise. I can walk you through the setup if you'd like.",
    ],
}


def generate_raw_data(n=200):
    """Generate simulated production logs."""
    data = []
    for i in range(n):
        query, category = random.choice(RAW_QUERIES)
        template = random.choice(RESPONSE_TEMPLATES[category])
        detail = random.choice(DETAILS[category])
        response = template.format(detail=detail)

        # Add some noise (realistic production issues)
        record = {
            "id": f"log_{i:04d}",
            "timestamp": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00Z",
            "query": query,
            "response": response,
            "category": category,
            "user_rating": random.choices([1, 2, 3, 4, 5], weights=[5, 5, 15, 35, 40])[0],
        }

        # Inject some PII (to demonstrate cleaning)
        if random.random() < 0.15:
            emails = ["john.doe@email.com", "sarah.k@company.org", "user123@gmail.com"]
            record["query"] += f" My email is {random.choice(emails)}"

        if random.random() < 0.1:
            phones = ["555-0123", "(555) 867-5309", "+1-555-444-3333"]
            record["query"] += f" Call me at {random.choice(phones)}"

        # Some duplicates (to demonstrate dedup)
        if random.random() < 0.05:
            data.append(record)  # Exact duplicate

        data.append(record)

    return data


# =============================================================================
# STEP 2: Clean Data
# =============================================================================

def remove_pii(text):
    """Remove personally identifiable information."""
    # Email
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    # Phone numbers
    text = re.sub(r'(\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}', '[PHONE]', text)
    # Names after common patterns
    text = re.sub(r'My name is [\w]+', 'My name is [NAME]', text)
    return text


def clean_text(text):
    """Clean text: normalize whitespace, fix encoding."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)  # Collapse multiple spaces
    text = text.replace('\u200b', '')  # Remove zero-width spaces
    text = text.replace('\xa0', ' ')   # Non-breaking space → regular space
    return text


def deduplicate(records):
    """Remove exact duplicates based on query+response hash."""
    seen = set()
    unique = []
    for record in records:
        key = hashlib.md5((record["query"] + record["response"]).encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


def clean_dataset(raw_data):
    """Full cleaning pipeline."""
    print(f"\n{'='*60}")
    print("STEP 2: CLEANING DATA")
    print(f"{'='*60}")
    print(f"  Records before cleaning: {len(raw_data)}")

    # Remove PII
    pii_count = 0
    for record in raw_data:
        original = record["query"]
        record["query"] = remove_pii(record["query"])
        record["response"] = remove_pii(record["response"])
        if record["query"] != original:
            pii_count += 1
    print(f"  PII removed from: {pii_count} records")

    # Clean text
    for record in raw_data:
        record["query"] = clean_text(record["query"])
        record["response"] = clean_text(record["response"])

    # Deduplicate
    before_dedup = len(raw_data)
    cleaned = deduplicate(raw_data)
    print(f"  Duplicates removed: {before_dedup - len(cleaned)}")

    # Filter by rating (only keep rating >= 4 for training)
    high_quality = [r for r in cleaned if r["user_rating"] >= 4]
    print(f"  After quality filter (rating >= 4): {len(high_quality)}")

    # Filter by length
    valid_length = [r for r in high_quality if 10 < len(r["response"]) < 2000]
    print(f"  After length filter: {len(valid_length)}")

    print(f"  Final clean records: {len(valid_length)}")
    return valid_length


# =============================================================================
# STEP 3: Format Data
# =============================================================================

def format_to_chat(records, system_prompt):
    """Convert to OpenAI chat format."""
    formatted = []
    for record in records:
        example = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": record["query"]},
                {"role": "assistant", "content": record["response"]},
            ],
            "metadata": {
                "category": record["category"],
                "original_id": record["id"],
            },
        }
        formatted.append(example)
    return formatted


# =============================================================================
# STEP 4: Validate Data
# =============================================================================

def validate_example(example):
    """Validate a single training example."""
    errors = []

    # Schema check
    if "messages" not in example:
        errors.append("missing 'messages' field")
        return errors

    messages = example["messages"]

    # Must have at least user + assistant
    if len(messages) < 2:
        errors.append("need at least 2 messages")

    # Roles check
    roles = [m["role"] for m in messages]
    if roles[-1] != "assistant":
        errors.append("last message must be assistant")

    # Content not empty
    for msg in messages:
        if not msg.get("content", "").strip():
            errors.append(f"empty content for role: {msg['role']}")

    # Token length estimate (rough: 1 token ≈ 4 chars)
    total_chars = sum(len(m["content"]) for m in messages)
    estimated_tokens = total_chars / 4
    if estimated_tokens > 4096:
        errors.append(f"too long: ~{estimated_tokens:.0f} tokens")
    if estimated_tokens < 10:
        errors.append(f"too short: ~{estimated_tokens:.0f} tokens")

    return errors


def validate_dataset(data):
    """Validate entire dataset."""
    print(f"\n{'='*60}")
    print("STEP 4: VALIDATING DATA")
    print(f"{'='*60}")

    valid = []
    invalid = []
    for example in data:
        errors = validate_example(example)
        if errors:
            invalid.append({"example": example, "errors": errors})
        else:
            valid.append(example)

    print(f"  Valid examples: {len(valid)}")
    print(f"  Invalid examples: {len(invalid)}")
    if invalid:
        print(f"  Sample errors: {invalid[0]['errors']}")

    return valid


# =============================================================================
# STEP 5: Split Data
# =============================================================================

def stratified_split(data, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1):
    """Split data maintaining category balance."""
    print(f"\n{'='*60}")
    print("STEP 5: SPLITTING DATA")
    print(f"{'='*60}")

    # Group by category
    by_category = {}
    for example in data:
        cat = example["metadata"]["category"]
        by_category.setdefault(cat, []).append(example)

    train, val, test = [], [], []

    for cat, examples in by_category.items():
        random.shuffle(examples)
        n = len(examples)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train.extend(examples[:n_train])
        val.extend(examples[n_train:n_train + n_val])
        test.extend(examples[n_train + n_val:])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    print(f"  Train: {len(train)} examples")
    print(f"  Val:   {len(val)} examples")
    print(f"  Test:  {len(test)} examples")

    return train, val, test


# =============================================================================
# STEP 6: Analyze Data
# =============================================================================

def analyze_dataset(data, name):
    """Comprehensive dataset analysis."""
    categories = Counter(ex["metadata"]["category"] for ex in data)
    lengths = [sum(len(m["content"]) for m in ex["messages"]) / 4 for ex in data]

    report = []
    report.append(f"\n--- {name} Analysis ---")
    report.append(f"  Total examples: {len(data)}")
    report.append(f"  Estimated tokens: min={min(lengths):.0f}, max={max(lengths):.0f}, "
                  f"mean={sum(lengths)/len(lengths):.0f}, median={sorted(lengths)[len(lengths)//2]:.0f}")
    report.append(f"  Category distribution:")
    for cat, count in sorted(categories.items()):
        pct = count / len(data) * 100
        bar = "█" * int(pct / 2)
        report.append(f"    {cat:20s}: {count:3d} ({pct:5.1f}%) {bar}")

    # Imbalance check
    max_count = max(categories.values())
    min_count = min(categories.values())
    imbalance = max_count / min_count if min_count > 0 else float('inf')
    if imbalance > 3:
        report.append(f"  ⚠️  IMBALANCE WARNING: {imbalance:.1f}x ratio between largest/smallest class")
    else:
        report.append(f"  ✓ Balance OK: {imbalance:.1f}x ratio")

    return "\n".join(report)


def compute_quality_score(data):
    """Compute overall dataset quality score."""
    scores = {
        "format_valid": 1.0,  # All passed validation
        "length_appropriate": 0.0,
        "category_balance": 0.0,
        "diversity": 0.0,
    }

    # Length score (penalize if too many very short or very long)
    lengths = [sum(len(m["content"]) for m in ex["messages"]) for ex in data]
    good_length = sum(1 for l in lengths if 100 < l < 2000) / len(lengths)
    scores["length_appropriate"] = good_length

    # Balance score
    categories = Counter(ex["metadata"]["category"] for ex in data)
    if categories:
        max_c = max(categories.values())
        min_c = min(categories.values())
        scores["category_balance"] = min_c / max_c if max_c > 0 else 0

    # Diversity score (unique queries / total)
    unique_queries = len(set(ex["messages"][1]["content"] for ex in data))
    scores["diversity"] = unique_queries / len(data)

    overall = sum(scores.values()) / len(scores)
    return scores, overall


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def save_jsonl(data, filepath):
    """Save data as JSONL (without metadata for training)."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for example in data:
            # Remove metadata for training file
            training_example = {"messages": example["messages"]}
            f.write(json.dumps(training_example) + "\n")


def main():
    print("=" * 60)
    print("  FINE-TUNING DATA PREPARATION PIPELINE")
    print("=" * 60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Generate raw data
    print(f"\n{'='*60}")
    print("STEP 1: COLLECTING RAW DATA")
    print(f"{'='*60}")
    raw_data = generate_raw_data(n=200)
    print(f"  Generated {len(raw_data)} raw production log entries")
    print(f"  Sample entry:")
    print(f"    Query: {raw_data[0]['query'][:80]}...")
    print(f"    Category: {raw_data[0]['category']}")
    print(f"    Rating: {raw_data[0]['user_rating']}/5")

    # Step 2: Clean
    cleaned = clean_dataset(raw_data)

    # Step 3: Format
    print(f"\n{'='*60}")
    print("STEP 3: FORMATTING DATA")
    print(f"{'='*60}")
    formatted = format_to_chat(cleaned, SYSTEM_PROMPT)
    print(f"  Converted {len(formatted)} records to OpenAI chat format")
    print(f"  Sample formatted example:")
    sample = formatted[0]
    for msg in sample["messages"]:
        print(f"    [{msg['role']}]: {msg['content'][:60]}...")

    # Step 4: Validate
    valid = validate_dataset(formatted)

    # Step 5: Split
    train, val, test = stratified_split(valid)

    # Step 6: Analyze
    print(f"\n{'='*60}")
    print("STEP 6: ANALYZING DATA")
    print(f"{'='*60}")

    train_analysis = analyze_dataset(train, "Training Set")
    val_analysis = analyze_dataset(val, "Validation Set")
    test_analysis = analyze_dataset(test, "Test Set")

    print(train_analysis)
    print(val_analysis)
    print(test_analysis)

    # Quality score
    scores, overall = compute_quality_score(train)
    print(f"\n--- Quality Score ---")
    for metric, score in scores.items():
        bar = "█" * int(score * 20)
        print(f"  {metric:25s}: {score:.2f} {bar}")
    print(f"  {'OVERALL':25s}: {overall:.2f} {'█' * int(overall * 20)}")
    print(f"\n  Recommendation: {'✓ READY FOR TRAINING' if overall > 0.7 else '⚠️ NEEDS IMPROVEMENT'}")

    # Save outputs
    output_dir = "output"
    save_jsonl(train, f"{output_dir}/train.jsonl")
    save_jsonl(val, f"{output_dir}/val.jsonl")
    save_jsonl(test, f"{output_dir}/test.jsonl")

    # Save quality report
    report = [
        "FINE-TUNING DATA QUALITY REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\nPipeline Summary:",
        f"  Raw records: {len(raw_data)}",
        f"  After cleaning: {len(cleaned)}",
        f"  After validation: {len(valid)}",
        f"  Train/Val/Test: {len(train)}/{len(val)}/{len(test)}",
        train_analysis,
        val_analysis,
        test_analysis,
        f"\nQuality Scores:",
    ]
    for metric, score in scores.items():
        report.append(f"  {metric}: {score:.3f}")
    report.append(f"  OVERALL: {overall:.3f}")

    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/quality_report.txt", "w") as f:
        f.write("\n".join(report))

    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Output files:")
    print(f"    {output_dir}/train.jsonl ({len(train)} examples)")
    print(f"    {output_dir}/val.jsonl ({len(val)} examples)")
    print(f"    {output_dir}/test.jsonl ({len(test)} examples)")
    print(f"    {output_dir}/quality_report.txt")


if __name__ == "__main__":
    main()
