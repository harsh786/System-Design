"""
DATA PREPARATION FOR BERT/RoBERTa TEXT CLASSIFICATION
=====================================================
This script handles the messy reality of real-world text data.
Covers: loading, cleaning, encoding, splitting, validation.

MODIFY THIS for your own data:
- Change DATA_PATH to your CSV
- Change TEXT_COLUMN and LABEL_COLUMN
- Add domain-specific cleaning steps

Usage:
    python data_preparation.py                    # Use defaults or create demo data
    python data_preparation.py --data my.csv      # Use your own CSV
    python data_preparation.py --text-col review --label-col category
"""

import os
import re
import json
import argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# ============ CONFIGURATION (MODIFY THESE) ============
DATA_PATH = "data/reviews.csv"       # Your CSV file
TEXT_COLUMN = "text"                  # Column containing text data
LABEL_COLUMN = "label"               # Column containing labels
MAX_LENGTH = 256                     # Token limit for BERT (128-512)
TEST_SIZE = 0.2                      # 20% for test
VAL_SIZE = 0.1                       # 10% for validation (from remaining 80%)
RANDOM_SEED = 42
MIN_TEXT_LENGTH = 10                 # Skip texts shorter than this
OUTPUT_DIR = "data"


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare data for BERT classification")
    parser.add_argument("--data", type=str, default=DATA_PATH, help="Path to CSV file")
    parser.add_argument("--text-col", type=str, default=TEXT_COLUMN, help="Text column name")
    parser.add_argument("--label-col", type=str, default=LABEL_COLUMN, help="Label column name")
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--test-size", type=float, default=TEST_SIZE)
    parser.add_argument("--val-size", type=float, default=VAL_SIZE)
    parser.add_argument("--create-demo", action="store_true", help="Force create demo data")
    return parser.parse_args()


# ============ DATA LOADING ============

def load_data(path, text_col, label_col):
    """Load data from CSV/JSON/Excel with encoding fallbacks."""
    if not os.path.exists(path):
        print(f"[WARNING] File not found: {path}")
        print("          Creating synthetic demo data instead...")
        return None

    ext = os.path.splitext(path)[1].lower()

    # Try multiple encodings for CSV
    if ext == ".csv":
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                df = pd.read_csv(path, encoding=encoding)
                print(f"[OK] Loaded {len(df)} rows from {path} (encoding: {encoding})")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"[ERROR] Failed to load CSV: {e}")
                return None
    elif ext == ".json":
        df = pd.read_json(path)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    else:
        print(f"[ERROR] Unsupported file format: {ext}")
        return None

    # Validate required columns exist
    if text_col not in df.columns:
        print(f"[ERROR] Text column '{text_col}' not found. Available: {list(df.columns)}")
        return None
    if label_col not in df.columns:
        print(f"[ERROR] Label column '{label_col}' not found. Available: {list(df.columns)}")
        return None

    return df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})


# ============ TEXT CLEANING ============

def clean_text(text):
    """
    Clean text for BERT/RoBERTa.

    IMPORTANT: We do NOT lowercase or remove punctuation!
    BERT uses casing and punctuation as features.
    """
    if not isinstance(text, str):
        return ""

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Fix common encoding issues
    text = text.replace("\u2019", "'").replace("\u2018", "'")  # Smart quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", " - ").replace("\u2013", " - ")
    text = text.replace("\xa0", " ")  # Non-breaking space

    # Remove URLs
    text = re.sub(r"http[s]?://\S+", "[URL]", text)

    # Remove email addresses
    text = re.sub(r"\S+@\S+\.\S+", "[EMAIL]", text)

    # Remove @mentions (social media)
    text = re.sub(r"@\w+", "[USER]", text)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove very long repeated characters (e.g., "yessssssss")
    text = re.sub(r"(.)\1{4,}", r"\1\1\1", text)

    return text


def clean_dataframe(df):
    """Apply cleaning pipeline to dataframe."""
    print("\n[STEP] Cleaning text data...")
    original_len = len(df)

    # Clean text
    df["text"] = df["text"].apply(clean_text)

    # Remove empty texts
    df = df[df["text"].str.len() >= MIN_TEXT_LENGTH].copy()

    # Remove rows with missing labels
    df = df.dropna(subset=["label"]).copy()

    # Strip whitespace from labels
    df["label"] = df["label"].astype(str).str.strip()

    removed = original_len - len(df)
    if removed > 0:
        print(f"  Removed {removed} rows (empty/short text or missing labels)")
    print(f"  Remaining: {len(df)} rows")

    return df


# ============ LABEL PROCESSING ============

def process_labels(df):
    """Convert string labels to integers, create mappings."""
    print("\n[STEP] Processing labels...")

    # Get unique labels sorted for reproducibility
    unique_labels = sorted(df["label"].unique())
    num_classes = len(unique_labels)

    # Create mappings
    label2id = {label: idx for idx, label in enumerate(unique_labels)}
    id2label = {idx: label for label, idx in label2id.items()}

    # Encode labels
    df["label_id"] = df["label"].map(label2id)

    # Print class distribution
    print(f"  Number of classes: {num_classes}")
    print(f"  Classes: {unique_labels}")
    print("\n  Class distribution:")
    dist = df["label"].value_counts()
    for label in unique_labels:
        count = dist.get(label, 0)
        pct = count / len(df) * 100
        bar = "█" * int(pct / 2)
        print(f"    {label:20s}: {count:5d} ({pct:5.1f}%) {bar}")

    # Warn about class imbalance
    max_count = dist.max()
    min_count = dist.min()
    if max_count / min_count > 5:
        print("\n  [WARNING] Significant class imbalance detected!")
        print("  Consider: oversampling minority class, class weights, or focal loss")

    return df, label2id, id2label


# ============ TRAIN/VAL/TEST SPLIT ============

def split_data(df, test_size, val_size, seed):
    """Stratified split preserving class distribution."""
    print("\n[STEP] Splitting data...")

    # First split: train+val vs test
    train_val, test = train_test_split(
        df, test_size=test_size, random_state=seed,
        stratify=df["label_id"]
    )

    # Second split: train vs val
    val_ratio = val_size / (1 - test_size)  # Adjust ratio for remaining data
    train, val = train_test_split(
        train_val, test_size=val_ratio, random_state=seed,
        stratify=train_val["label_id"]
    )

    print(f"  Train: {len(train):5d} samples")
    print(f"  Val:   {len(val):5d} samples")
    print(f"  Test:  {len(test):5d} samples")

    return train, val, test


# ============ CREATE SYNTHETIC DEMO DATA ============

def create_demo_data(num_samples=2000):
    """
    Create synthetic multi-class dataset for demonstration.
    Categories: technology, sports, politics, entertainment
    """
    print("\n[STEP] Creating synthetic demo dataset...")
    np.random.seed(RANDOM_SEED)

    templates = {
        "technology": [
            "The new {product} features {feature} that improves {metric} significantly",
            "Apple announced {product} with revolutionary {feature} technology",
            "Google's latest AI model achieves {metric} on {benchmark} benchmarks",
            "Microsoft released an update to {product} adding {feature} support",
            "The {product} processor delivers {metric} better performance than last gen",
            "Samsung unveiled their new {product} with {feature} capabilities",
            "OpenAI's {product} can now {feature} with unprecedented {metric}",
            "The cybersecurity vulnerability in {product} affects {metric} users worldwide",
            "Tesla's {product} software update enables {feature} for all models",
            "Amazon Web Services launched {product} for enterprise {feature} workloads",
        ],
        "sports": [
            "The {team} defeated {opponent} {score} in yesterday's {league} match",
            "{player} scored {goals} goals to lead {team} to victory over {opponent}",
            "The {league} finals will feature {team} against {opponent} this weekend",
            "{player} broke the {record} record with an incredible performance",
            "Coach {coach} announced {player} will miss {weeks} weeks with injury",
            "The {team} signed {player} to a {years}-year contract worth millions",
            "{player} won the {tournament} defeating {opponent} in straight sets",
            "The Olympic {sport} team qualified for the finals after beating {opponent}",
            "{team} are now {position} in the {league} standings after tonight's win",
            "Transfer deadline: {team} complete signing of {player} from {opponent}",
        ],
        "politics": [
            "The Senate passed the {bill} bill with {votes} votes in favor",
            "President {leader} signed executive order on {policy} today",
            "The {party} party announced their position on {policy} reform",
            "Protests erupted over the government's {policy} decision affecting millions",
            "The election results show {party} winning {seats} seats in parliament",
            "Diplomatic tensions rise as {country} responds to {policy} sanctions",
            "The Supreme Court will hear arguments on {policy} next month",
            "Congress debates {bill} as deadline approaches for {policy} funding",
            "The governor vetoed the {bill} citing concerns about {policy}",
            "International summit focuses on {policy} cooperation between nations",
        ],
        "entertainment": [
            "The new {movie} movie grossed {amount} million in its opening weekend",
            "{actor} stars in the upcoming {movie} directed by {director}",
            "Netflix announced {show} will return for season {season} next year",
            "The {award} nominations include {movie} for best picture",
            "{artist} released their new album {album} to critical acclaim",
            "The {movie} sequel has been confirmed with {actor} returning",
            "Streaming numbers for {show} broke all previous records this week",
            "{actor} won the {award} for their role in {movie}",
            "The music festival lineup includes {artist} and {band} as headliners",
            "Box office: {movie} overtakes {other_movie} as highest grossing film",
        ],
    }

    fillers = {
        "product": ["iPhone 16", "Pixel 9", "Surface Pro", "Galaxy S25", "ChatGPT", "Vision Pro"],
        "feature": ["AI-powered", "quantum computing", "neural network", "edge computing", "5G"],
        "metric": ["30%", "50%", "2x", "10x", "record-breaking"],
        "benchmark": ["industry", "performance", "accuracy", "speed", "efficiency"],
        "team": ["Lakers", "Warriors", "Manchester United", "Barcelona", "Patriots", "Yankees"],
        "opponent": ["Celtics", "Rockets", "Liverpool", "Real Madrid", "Eagles", "Red Sox"],
        "player": ["Johnson", "Smith", "Rodriguez", "Williams", "Chen", "Martinez"],
        "score": ["3-1", "2-0", "105-98", "4-2", "28-21"],
        "league": ["NBA", "Premier League", "NFL", "MLB", "Champions League"],
        "goals": ["2", "3", "hat-trick of"],
        "record": ["scoring", "speed", "consecutive wins", "career"],
        "coach": ["Thompson", "Garcia", "Anderson", "Patel"],
        "weeks": ["2", "4", "6", "8"],
        "years": ["3", "4", "5"],
        "tournament": ["Grand Slam", "World Championship", "Open"],
        "sport": ["swimming", "athletics", "gymnastics", "basketball"],
        "position": ["first", "second", "third"],
        "bill": ["infrastructure", "healthcare", "education", "climate", "defense"],
        "votes": ["52-48", "60-40", "67-33", "55-45"],
        "leader": ["Biden", "the Prime Minister", "the Chancellor"],
        "policy": ["immigration", "climate", "healthcare", "economic", "trade"],
        "party": ["Democratic", "Republican", "Labour", "Conservative"],
        "seats": ["15", "23", "8", "31"],
        "country": ["China", "Russia", "the EU", "India"],
        "movie": ["Horizon", "Eclipse", "The Return", "Midnight", "Phoenix"],
        "actor": ["Tom Hanks", "Meryl Streep", "Denzel Washington", "Cate Blanchett"],
        "director": ["Nolan", "Spielberg", "Gerwig", "Villeneuve"],
        "show": ["The Crown", "Stranger Things", "Wednesday", "The Bear"],
        "season": ["4", "5", "6", "3"],
        "award": ["Oscar", "Emmy", "Golden Globe", "BAFTA"],
        "amount": ["150", "200", "95", "300", "180"],
        "artist": ["Taylor Swift", "Drake", "Beyonce", "Bad Bunny"],
        "album": ["Echoes", "Midnight", "Revolution", "Dreamscape"],
        "band": ["Coldplay", "Foo Fighters", "Arctic Monkeys"],
        "other_movie": ["Avatar", "Endgame", "Top Gun"],
    }

    rows = []
    samples_per_class = num_samples // len(templates)

    for label, tmpl_list in templates.items():
        for _ in range(samples_per_class):
            template = np.random.choice(tmpl_list)
            # Fill in placeholders
            text = template
            for key, values in fillers.items():
                if "{" + key + "}" in text:
                    text = text.replace("{" + key + "}", np.random.choice(values), 1)
            rows.append({"text": text, "label": label})

    df = pd.DataFrame(rows)
    # Shuffle
    df = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    print(f"  Created {len(df)} synthetic samples across {len(templates)} classes")
    return df


# ============ SAVE DATA ============

def save_splits(train, val, test, label2id, id2label, output_dir):
    """Save processed data splits and label mapping."""
    os.makedirs(output_dir, exist_ok=True)

    train.to_csv(os.path.join(output_dir, "train.csv"), index=False)
    val.to_csv(os.path.join(output_dir, "val.csv"), index=False)
    test.to_csv(os.path.join(output_dir, "test.csv"), index=False)

    mapping = {"label2id": label2id, "id2label": id2label}
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\n[DONE] Saved to {output_dir}/")
    print(f"  - train.csv ({len(train)} samples)")
    print(f"  - val.csv ({len(val)} samples)")
    print(f"  - test.csv ({len(test)} samples)")
    print(f"  - label_mapping.json")


# ============ MAIN ============

def main():
    args = parse_args()

    # Load or create data
    if args.create_demo:
        df = create_demo_data()
    else:
        df = load_data(args.data, args.text_col, args.label_col)
        if df is None:
            df = create_demo_data()

    # Clean
    df = clean_dataframe(df)

    # Process labels
    df, label2id, id2label = process_labels(df)

    # Split
    train, val, test = split_data(df, args.test_size, args.val_size, RANDOM_SEED)

    # Save
    save_splits(train, val, test, label2id, id2label, OUTPUT_DIR)

    print("\n[NEXT STEP] Run: python train.py")


if __name__ == "__main__":
    main()
