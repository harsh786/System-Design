# LoRA Fine-Tuning Simulator

Simulates the LoRA fine-tuning process to demonstrate the workflow, configuration, and monitoring without requiring GPU hardware.

## What It Does

1. Configures LoRA hyperparameters for different scenarios
2. Calculates trainable parameters for various model/rank combinations
3. Simulates training loop with realistic loss curves
4. Demonstrates early stopping logic
5. Generates text-based loss curve visualization
6. Produces training report with recommendations

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Note

Actual LoRA training requires GPU hardware and libraries like `peft`, `transformers`, `bitsandbytes`. This program simulates the workflow to teach the concepts.
