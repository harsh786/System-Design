# LoRA Fine-Tuning Simulator
# Demonstrates: configuration, parameter calculation, training loop, early stopping

import math
import random
from dataclasses import dataclass

random.seed(42)


# =============================================================================
# MODEL CONFIGURATIONS
# =============================================================================

@dataclass
class ModelConfig:
    name: str
    params_billions: float
    hidden_dim: int
    num_layers: int
    num_attention_heads: int
    intermediate_dim: int  # FFN intermediate size
    model_size_gb_fp16: float


MODELS = {
    "llama-7b": ModelConfig("Llama 2 7B", 6.7, 4096, 32, 32, 11008, 13.5),
    "llama-13b": ModelConfig("Llama 2 13B", 13.0, 5120, 40, 40, 13824, 26.0),
    "llama-70b": ModelConfig("Llama 2 70B", 65.0, 8192, 80, 64, 28672, 131.0),
    "mistral-7b": ModelConfig("Mistral 7B", 7.2, 4096, 32, 32, 14336, 14.5),
}


@dataclass
class LoRAConfig:
    rank: int
    alpha: int
    target_modules: list
    dropout: float
    learning_rate: float
    epochs: int
    batch_size: int
    gradient_accumulation: int


# =============================================================================
# PARAMETER CALCULATION
# =============================================================================

def calculate_lora_params(model: ModelConfig, lora: LoRAConfig):
    """Calculate number of trainable LoRA parameters."""

    params_per_module = {
        "q_proj": 2 * model.hidden_dim * lora.rank,  # A (r×d) + B (d×r)
        "k_proj": 2 * model.hidden_dim * lora.rank,
        "v_proj": 2 * model.hidden_dim * lora.rank,
        "o_proj": 2 * model.hidden_dim * lora.rank,
        "gate_proj": model.hidden_dim * lora.rank + model.intermediate_dim * lora.rank,
        "up_proj": model.hidden_dim * lora.rank + model.intermediate_dim * lora.rank,
        "down_proj": model.intermediate_dim * lora.rank + model.hidden_dim * lora.rank,
    }

    total_params = 0
    breakdown = {}
    for module in lora.target_modules:
        if module in params_per_module:
            module_params = params_per_module[module] * model.num_layers
            breakdown[module] = module_params
            total_params += module_params

    return total_params, breakdown


def estimate_vram(model: ModelConfig, lora: LoRAConfig, quantization="none"):
    """Estimate VRAM requirements."""
    # Base model
    if quantization == "4bit":
        model_vram = model.model_size_gb_fp16 / 4  # 4-bit = 1/4 of fp16
    elif quantization == "8bit":
        model_vram = model.model_size_gb_fp16 / 2
    else:
        model_vram = model.model_size_gb_fp16

    # LoRA adapters (always fp16)
    lora_params, _ = calculate_lora_params(model, lora)
    adapter_vram = lora_params * 2 / (1024**3)  # 2 bytes per param (fp16)

    # Gradients for adapters
    gradient_vram = adapter_vram

    # Optimizer states (Adam: 2× adapter size)
    optimizer_vram = adapter_vram * 2

    # Activations (rough estimate based on batch size)
    activation_vram = model.num_layers * model.hidden_dim * lora.batch_size * 2048 * 2 / (1024**3) * 0.01

    total = model_vram + adapter_vram + gradient_vram + optimizer_vram + activation_vram
    return {
        "model": model_vram,
        "adapters": adapter_vram,
        "gradients": gradient_vram,
        "optimizer": optimizer_vram,
        "activations": activation_vram,
        "total": total,
    }


# =============================================================================
# TRAINING SIMULATION
# =============================================================================

def simulate_loss_curve(num_steps, initial_loss=2.5, final_loss=0.8, noise=0.05):
    """Simulate a realistic training loss curve."""
    losses = []
    for step in range(num_steps):
        progress = step / num_steps
        # Exponential decay with noise
        expected = initial_loss * math.exp(-3 * progress) + final_loss * (1 - math.exp(-3 * progress))
        actual = expected + random.gauss(0, noise * (1 - progress * 0.5))
        losses.append(max(0.1, actual))
    return losses


def simulate_val_loss(train_losses, overfit_start=0.7):
    """Simulate validation loss (diverges from train if overfitting)."""
    val_losses = []
    num_steps = len(train_losses)
    for i, train_loss in enumerate(train_losses):
        progress = i / num_steps
        if progress < overfit_start:
            # Val tracks train closely
            val_loss = train_loss + random.gauss(0.05, 0.02)
        else:
            # Val starts increasing (overfitting)
            overfit_amount = (progress - overfit_start) * 2
            val_loss = train_loss + 0.05 + overfit_amount + random.gauss(0, 0.03)
        val_losses.append(max(0.1, val_loss))
    return val_losses


def plot_loss_ascii(train_losses, val_losses, width=60, height=20):
    """Plot loss curves in ASCII."""
    all_losses = train_losses + val_losses
    min_loss = min(all_losses)
    max_loss = max(all_losses)
    loss_range = max_loss - min_loss

    # Sample to fit width
    step = max(1, len(train_losses) // width)
    sampled_train = train_losses[::step][:width]
    sampled_val = val_losses[::step][:width]

    # Create grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Plot points
    for x, (tl, vl) in enumerate(zip(sampled_train, sampled_val)):
        if x >= width:
            break
        # Train loss
        ty = height - 1 - int((tl - min_loss) / loss_range * (height - 1))
        ty = max(0, min(height - 1, ty))
        grid[ty][x] = '●'

        # Val loss
        vy = height - 1 - int((vl - min_loss) / loss_range * (height - 1))
        vy = max(0, min(height - 1, vy))
        if grid[vy][x] == ' ':
            grid[vy][x] = '○'

    # Render
    lines = []
    lines.append(f"  Loss Curve (● = train, ○ = validation)")
    lines.append(f"  {'─' * (width + 4)}")
    for i, row in enumerate(grid):
        loss_val = max_loss - (i / (height - 1)) * loss_range
        lines.append(f"  {loss_val:5.2f} │{''.join(row)}│")
    lines.append(f"        └{'─' * width}┘")
    lines.append(f"         Step 0{' ' * (width - 10)}Step {len(train_losses)}")

    return "\n".join(lines)


class EarlyStopping:
    def __init__(self, patience=3, min_delta=0.01):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float('inf')
        self.counter = 0
        self.stopped_step = None

    def check(self, val_loss, step):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            return False
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.stopped_step = step
                return True
            return False


def run_training_simulation(model_name, lora_config, num_training_examples):
    """Simulate a complete training run."""
    model = MODELS[model_name]

    # Calculate steps
    effective_batch = lora_config.batch_size * lora_config.gradient_accumulation
    steps_per_epoch = math.ceil(num_training_examples / effective_batch)
    total_steps = steps_per_epoch * lora_config.epochs
    eval_every = max(1, total_steps // 20)  # Evaluate 20 times during training

    print(f"\n{'='*60}")
    print(f"  TRAINING SIMULATION: {model.name} + LoRA (rank={lora_config.rank})")
    print(f"{'='*60}")

    # Parameter calculation
    lora_params, breakdown = calculate_lora_params(model, lora_config)
    total_model_params = model.params_billions * 1e9
    trainable_pct = lora_params / total_model_params * 100

    print(f"\n  Model: {model.name} ({model.params_billions}B parameters)")
    print(f"  LoRA rank: {lora_config.rank}, alpha: {lora_config.alpha}")
    print(f"  Target modules: {', '.join(lora_config.target_modules)}")
    print(f"\n  Parameter Breakdown:")
    for module, params in breakdown.items():
        print(f"    {module:12s}: {params:>12,} params")
    print(f"    {'─'*30}")
    print(f"    {'TOTAL':12s}: {lora_params:>12,} params ({trainable_pct:.4f}% of model)")

    # VRAM estimation
    vram_fp16 = estimate_vram(model, lora_config, "none")
    vram_4bit = estimate_vram(model, lora_config, "4bit")

    print(f"\n  VRAM Estimation:")
    print(f"    {'Component':<15} {'FP16':>10} {'QLoRA (4-bit)':>14}")
    print(f"    {'─'*42}")
    for key in ["model", "adapters", "gradients", "optimizer", "activations"]:
        print(f"    {key:<15} {vram_fp16[key]:>8.1f} GB  {vram_4bit[key]:>8.1f} GB")
    print(f"    {'─'*42}")
    print(f"    {'TOTAL':<15} {vram_fp16['total']:>8.1f} GB  {vram_4bit['total']:>8.1f} GB")

    # Training config
    print(f"\n  Training Configuration:")
    print(f"    Training examples: {num_training_examples}")
    print(f"    Batch size: {lora_config.batch_size} × {lora_config.gradient_accumulation} = {effective_batch} effective")
    print(f"    Steps per epoch: {steps_per_epoch}")
    print(f"    Total steps: {total_steps}")
    print(f"    Epochs: {lora_config.epochs}")
    print(f"    Learning rate: {lora_config.learning_rate}")
    print(f"    Evaluate every: {eval_every} steps")

    # Simulate training
    print(f"\n  Simulating training...")
    train_losses = simulate_loss_curve(total_steps)
    val_losses = simulate_val_loss(train_losses, overfit_start=0.75)

    # Apply early stopping
    early_stop = EarlyStopping(patience=3)
    stopped = False
    for i in range(0, total_steps, eval_every):
        if i < len(val_losses):
            if early_stop.check(val_losses[i], i):
                stopped = True
                break

    if stopped:
        print(f"  ⚠️  Early stopping triggered at step {early_stop.stopped_step}")
        print(f"      Best validation loss: {early_stop.best_loss:.4f}")
        # Truncate losses at early stop point
        train_losses = train_losses[:early_stop.stopped_step]
        val_losses = val_losses[:early_stop.stopped_step]
    else:
        print(f"  ✓ Training completed all {total_steps} steps")
        print(f"      Final training loss: {train_losses[-1]:.4f}")
        print(f"      Final validation loss: {val_losses[-1]:.4f}")

    # Plot
    print(f"\n{plot_loss_ascii(train_losses, val_losses)}")

    # Training time estimate
    # Rough: ~1 second per step for 7B on A100, scales with model size
    seconds_per_step = model.params_billions / 7 * 1.0
    total_time_min = len(train_losses) * seconds_per_step / 60
    print(f"\n  Estimated training time (A100 80GB): {total_time_min:.0f} minutes ({total_time_min/60:.1f} hours)")

    return {
        "model": model.name,
        "lora_params": lora_params,
        "trainable_pct": trainable_pct,
        "final_train_loss": train_losses[-1],
        "final_val_loss": val_losses[-1],
        "best_val_loss": early_stop.best_loss,
        "steps_trained": len(train_losses),
        "early_stopped": stopped,
    }


# =============================================================================
# COMPARISON ACROSS CONFIGURATIONS
# =============================================================================

def compare_configurations():
    """Compare LoRA parameters across different model/rank combinations."""
    print(f"\n{'='*60}")
    print("  PARAMETER COMPARISON: Model Size × LoRA Rank")
    print(f"{'='*60}")

    ranks = [8, 16, 32, 64]
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]

    print(f"\n  {'Model':<15} {'Rank':>5} {'LoRA Params':>14} {'% of Model':>12} {'Adapter Size':>14}")
    print(f"  {'─'*65}")

    for model_name, model in MODELS.items():
        for rank in ranks:
            config = LoRAConfig(
                rank=rank, alpha=rank*2, target_modules=target_modules,
                dropout=0.05, learning_rate=2e-4, epochs=3,
                batch_size=4, gradient_accumulation=8
            )
            params, _ = calculate_lora_params(model, config)
            pct = params / (model.params_billions * 1e9) * 100
            size_mb = params * 2 / (1024**2)  # fp16
            print(f"  {model.name:<15} {rank:>5} {params:>14,} {pct:>10.4f}% {size_mb:>10.1f} MB")
        print(f"  {'─'*65}")


# =============================================================================
# RECOMMENDATIONS
# =============================================================================

def generate_recommendations(results):
    """Generate training recommendations based on results."""
    print(f"\n{'='*60}")
    print("  RECOMMENDATIONS")
    print(f"{'='*60}")

    if results["early_stopped"]:
        print(f"\n  1. Early stopping was triggered → model was starting to overfit")
        print(f"     Actions:")
        print(f"     - Use the checkpoint at best validation loss ({results['best_val_loss']:.4f})")
        print(f"     - Consider adding more training data")
        print(f"     - Consider increasing dropout")
    else:
        print(f"\n  1. Training completed without overfitting ✓")
        if results["final_val_loss"] > results["final_train_loss"] * 1.5:
            print(f"     Note: gap between train/val loss suggests mild overfitting")
            print(f"     Consider reducing epochs or adding regularization")

    print(f"\n  2. Parameter efficiency:")
    print(f"     Training {results['trainable_pct']:.4f}% of model parameters")
    if results["trainable_pct"] < 0.1:
        print(f"     This is very efficient. If quality is insufficient, try increasing rank.")
    elif results["trainable_pct"] > 1.0:
        print(f"     This is relatively high. Consider reducing rank if quality is sufficient.")

    print(f"\n  3. Next steps:")
    print(f"     - Evaluate on held-out test set")
    print(f"     - Compare generations against base model qualitatively")
    print(f"     - Check for catastrophic forgetting on general benchmarks")
    print(f"     - If satisfactory, merge adapter and deploy")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  LoRA FINE-TUNING SIMULATOR")
    print("=" * 60)

    # Show parameter comparison
    compare_configurations()

    # Run simulation for a typical scenario
    lora_config = LoRAConfig(
        rank=16,
        alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        dropout=0.05,
        learning_rate=2e-4,
        epochs=3,
        batch_size=4,
        gradient_accumulation=8,
    )

    results = run_training_simulation("llama-7b", lora_config, num_training_examples=2000)
    generate_recommendations(results)

    # Show a second scenario with more aggressive config
    print(f"\n\n{'='*60}")
    print("  SCENARIO 2: Larger rank for complex task")
    print(f"{'='*60}")

    lora_config_complex = LoRAConfig(
        rank=64,
        alpha=128,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        dropout=0.1,
        learning_rate=1e-4,
        epochs=2,
        batch_size=2,
        gradient_accumulation=16,
    )

    results2 = run_training_simulation("mistral-7b", lora_config_complex, num_training_examples=5000)
    generate_recommendations(results2)


if __name__ == "__main__":
    main()
