# Structured Output

A program demonstrating how to get reliable, typed, validated data from LLMs using structured output and function calling.

## What You'll Learn

- How to define Pydantic models for structured LLM output
- Using OpenAI's function calling to extract structured data
- Parsing unstructured text (movie reviews, articles) into typed objects
- Validation and error handling for AI-generated structured data

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## Run It

```bash
python main.py
```

## Key Insight

LLMs generate text. But production systems need structured data — JSON, typed objects, database records.
Structured output bridges this gap: you define the schema, the LLM fills it in, and you get validated data.
