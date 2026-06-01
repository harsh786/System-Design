# Privacy and Security in ML

## Overview

ML models are vulnerable to attacks at every stage: training data can be poisoned,
models can be reverse-engineered, and adversarial inputs can cause failures.
Privacy-preserving techniques add protection but come with trade-offs.

---

## Data Privacy in ML

### The Problem

ML models memorize training data. This creates risks:

```
Risks:
1. Model can leak individual training examples (memorization)
2. Attackers can determine if a specific person was in training data
3. Models can be inverted to reconstruct training inputs
4. Embeddings can encode sensitive information
```

### Types of Sensitive Data in ML

| Data Type | Risk | Example |
|-----------|------|---------|
| PII (names, SSN) | Identity theft | Training on customer records |
| Medical records | Privacy violation | Health prediction models |
| Location data | Stalking, surveillance | Mobility models |
| Financial data | Fraud, discrimination | Credit models |
| Biometric data | Permanent compromise | Face/voice recognition |

---

## Differential Privacy

### Definition

A mechanism M satisfies (ε, δ)-differential privacy if for any two adjacent datasets D and D'
(differing in one record) and any output set S:

```
P[M(D) ∈ S] ≤ e^ε × P[M(D') ∈ S] + δ

Where:
- ε (epsilon): privacy budget. Lower = more private. Typical: 1-10
- δ (delta): probability of privacy failure. Typical: 1/n² where n = dataset size
```

**Intuition**: Whether or not YOUR data is included barely changes the output.

### Mechanisms

#### Laplace Mechanism

```python
import numpy as np

def laplace_mechanism(true_answer, sensitivity, epsilon):
    """Add Laplace noise calibrated to sensitivity/epsilon."""
    noise = np.random.laplace(0, sensitivity / epsilon)
    return true_answer + noise

# Example: Private mean
true_mean = np.mean(salaries)
# Sensitivity = (max - min) / n for mean query
sensitivity = (max_salary - min_salary) / len(salaries)
private_mean = laplace_mechanism(true_mean, sensitivity, epsilon=1.0)
```

#### Gaussian Mechanism

```python
def gaussian_mechanism(true_answer, sensitivity, epsilon, delta):
    """Add Gaussian noise for (ε,δ)-DP."""
    sigma = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon
    noise = np.random.normal(0, sigma)
    return true_answer + noise
```

### DP-SGD (Differentially Private Stochastic Gradient Descent)

```python
# Using Opacus (PyTorch DP library)
from opacus import PrivacyEngine

model = MyModel()
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
data_loader = DataLoader(dataset, batch_size=64)

# Wrap with privacy engine
privacy_engine = PrivacyEngine()
model, optimizer, data_loader = privacy_engine.make_private_with_epsilon(
    module=model,
    optimizer=optimizer,
    data_loader=data_loader,
    epochs=10,
    target_epsilon=3.0,  # Privacy budget
    target_delta=1e-5,
    max_grad_norm=1.0,   # Gradient clipping bound
)

# Train as usual - DP-SGD clips gradients and adds noise automatically
for epoch in range(10):
    for batch in data_loader:
        loss = compute_loss(model, batch)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()

# Check actual privacy spent
print(f"ε = {privacy_engine.get_epsilon(delta=1e-5):.2f}")
```

### Privacy-Accuracy Tradeoff

```
ε = 0.1:  Very private, significant accuracy loss (often unusable)
ε = 1.0:  Strong privacy, moderate accuracy loss
ε = 3.0:  Moderate privacy, small accuracy loss (common in practice)
ε = 10.0: Weak privacy, minimal accuracy loss
ε = ∞:    No privacy (standard training)
```

---

## Federated Learning

### Concept

Train models across decentralized devices without sharing raw data.

```
        ┌─────────────┐
        │   Server    │
        │ (aggregate) │
        └──────┬──────┘
        ┌──────┼──────┐
        ▼      ▼      ▼
    ┌──────┐┌──────┐┌──────┐
    │Phone1││Phone2││Phone3│  (local data stays on device)
    │Train ││Train ││Train │
    │Local ││Local ││Local │
    └──────┘└──────┘└──────┘
    
Flow:
1. Server sends model to devices
2. Each device trains on local data
3. Devices send model UPDATES (not data) to server
4. Server aggregates updates (e.g., FedAvg)
5. Repeat
```

### FedAvg Algorithm

```python
def federated_averaging(global_model, client_data, num_rounds, num_clients_per_round):
    for round in range(num_rounds):
        # Select random subset of clients
        selected_clients = random.sample(all_clients, num_clients_per_round)
        
        client_updates = []
        for client in selected_clients:
            # Send global model to client
            local_model = copy.deepcopy(global_model)
            
            # Client trains locally
            local_model = train_local(local_model, client_data[client], epochs=5)
            
            # Client sends update (difference from global)
            update = compute_update(global_model, local_model)
            client_updates.append((update, len(client_data[client])))
        
        # Server aggregates (weighted by data size)
        global_model = weighted_average(global_model, client_updates)
    
    return global_model
```

### Challenges

- **Communication cost**: Model updates are large
- **Non-IID data**: Each device has different data distribution
- **Stragglers**: Some devices are slow or unavailable
- **Privacy**: Model updates can still leak information (use DP + FL)

---

## Model Inversion Attacks

Reconstructing training data from model outputs or parameters.

```python
# Simplified model inversion attack
# Given: access to model's confidence scores
# Goal: reconstruct a face that the model recognizes as "person X"

def model_inversion_attack(model, target_class, num_steps=1000):
    """Optimize an image to maximize model's confidence for target class."""
    # Start from random noise
    fake_image = torch.randn(1, 3, 224, 224, requires_grad=True)
    optimizer = torch.optim.Adam([fake_image], lr=0.01)
    
    for step in range(num_steps):
        output = model(fake_image)
        # Maximize probability of target class
        loss = -output[0, target_class]
        # Add regularization for realistic images
        loss += 0.001 * torch.norm(fake_image)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    
    return fake_image  # Approximation of training data for that class
```

**Defense**: Limit output information (no confidence scores), add noise, restrict query access.

---

## Membership Inference Attacks

Determine whether a specific data point was in the training set.

```python
def membership_inference_attack(target_model, shadow_models, data_point):
    """
    Attack idea: 
    - Models behave differently on training data vs unseen data
    - Training data typically gets HIGHER confidence / LOWER loss
    """
    # Simple threshold attack
    output = target_model.predict_proba(data_point)
    confidence = max(output)
    
    # If confidence > threshold → likely a member
    threshold = 0.9  # Calibrated using shadow models
    return confidence > threshold

# More sophisticated: train an attack model
# Features: target model's output probabilities
# Label: member (1) or non-member (0)
# Train on shadow model outputs where ground truth is known
```

**Defense**: Regularization, DP training, limit prediction information.

---

## Data Poisoning Attacks

Corrupting training data to compromise model behavior.

```python
# Backdoor attack example
def create_poisoned_data(clean_images, clean_labels, target_class, poison_rate=0.01):
    """Add a trigger pattern to some images and change their label."""
    poisoned_images = clean_images.copy()
    poisoned_labels = clean_labels.copy()
    
    n_poison = int(len(clean_images) * poison_rate)
    poison_indices = np.random.choice(len(clean_images), n_poison, replace=False)
    
    for idx in poison_indices:
        # Add trigger (e.g., small white square in corner)
        poisoned_images[idx, -5:, -5:, :] = 255  # White patch
        poisoned_labels[idx] = target_class  # Change label
    
    return poisoned_images, poisoned_labels

# Result: Model works normally on clean inputs
# but predicts target_class whenever trigger pattern is present
```

**Defenses**:
- Data sanitization (detect and remove outlier training examples)
- Robust aggregation (in federated learning)
- Neural Cleanse (detect and reverse-engineer backdoors)
- Certified defenses (provable robustness to poisoning)

---

## Adversarial Attacks

Small, imperceptible perturbations that cause misclassification.

### FGSM (Fast Gradient Sign Method)

```python
def fgsm_attack(model, image, label, epsilon=0.03):
    """One-step gradient attack."""
    image.requires_grad = True
    output = model(image)
    loss = F.cross_entropy(output, label)
    loss.backward()
    
    # Perturb in the direction that increases loss
    perturbation = epsilon * image.grad.sign()
    adversarial_image = image + perturbation
    adversarial_image = torch.clamp(adversarial_image, 0, 1)
    
    return adversarial_image

# Usage
adv_img = fgsm_attack(model, img, true_label, epsilon=0.03)
# model(img) → "panda" (99.3% confidence)
# model(adv_img) → "gibbon" (99.9% confidence)
# Human sees: identical images
```

### PGD (Projected Gradient Descent)

```python
def pgd_attack(model, image, label, epsilon=0.03, steps=40, step_size=0.01):
    """Iterative gradient attack (stronger than FGSM)."""
    adv_image = image.clone().detach()
    
    for _ in range(steps):
        adv_image.requires_grad = True
        output = model(adv_image)
        loss = F.cross_entropy(output, label)
        loss.backward()
        
        # Small step in gradient direction
        adv_image = adv_image + step_size * adv_image.grad.sign()
        # Project back into epsilon-ball around original
        perturbation = torch.clamp(adv_image - image, -epsilon, epsilon)
        adv_image = torch.clamp(image + perturbation, 0, 1).detach()
    
    return adv_image
```

### Adversarial Training as Defense

```python
def adversarial_training(model, train_loader, epsilon=0.03, epochs=100):
    """Train on adversarial examples to build robustness."""
    optimizer = torch.optim.Adam(model.parameters())
    
    for epoch in range(epochs):
        for images, labels in train_loader:
            # Generate adversarial examples
            adv_images = pgd_attack(model, images, labels, epsilon=epsilon)
            
            # Train on mix of clean and adversarial
            clean_loss = F.cross_entropy(model(images), labels)
            adv_loss = F.cross_entropy(model(adv_images), labels)
            loss = 0.5 * clean_loss + 0.5 * adv_loss
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
```

---

## Watermarking ML Models

Proving ownership of a model (IP protection).

```python
# Backdoor-based watermarking
# Embed a secret trigger that only the model owner knows about

def embed_watermark(model, trigger_images, trigger_label, fine_tune_epochs=5):
    """Fine-tune model to respond to secret trigger."""
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    
    for epoch in range(fine_tune_epochs):
        # Train on both normal data AND trigger data
        for normal_batch in normal_loader:
            normal_loss = compute_loss(model, normal_batch)
            trigger_loss = F.cross_entropy(
                model(trigger_images), 
                torch.full((len(trigger_images),), trigger_label)
            )
            loss = normal_loss + trigger_loss
            loss.backward()
            optimizer.step()

def verify_watermark(suspect_model, trigger_images, trigger_label):
    """Verify if a model contains our watermark."""
    predictions = suspect_model(trigger_images).argmax(dim=1)
    accuracy_on_trigger = (predictions == trigger_label).float().mean()
    return accuracy_on_trigger > 0.9  # Watermark detected
```

---

## Privacy Regulations

### GDPR (EU)

| Requirement | ML Implication |
|-------------|----------------|
| Right to be forgotten | Must be able to remove person's influence on model |
| Data minimization | Only collect/use necessary features |
| Purpose limitation | Can't repurpose data for new models without consent |
| Right to explanation | Must explain automated decisions (Art. 22) |
| Data protection by design | Privacy considerations from the start |

### CCPA (California)

- Right to know what data is collected
- Right to deletion
- Right to opt-out of "sale" of personal information
- Applies to companies serving California residents

### HIPAA (Healthcare)

- Protected Health Information (PHI) requires strict controls
- De-identification standards (Safe Harbor, Expert Determination)
- Business Associate Agreements for ML vendors
- Minimum necessary standard

---

## PII Detection and Anonymization

```python
# Using presidio (Microsoft) for PII detection
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

text = "John Smith's SSN is 123-45-6789 and he lives at 123 Main St"

# Detect PII
results = analyzer.analyze(text=text, language='en')
for result in results:
    print(f"  {result.entity_type}: '{text[result.start:result.end]}' "
          f"(confidence: {result.score:.2f})")

# Anonymize
anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
print(anonymized.text)
# "<PERSON>'s SSN is <US_SSN> and he lives at <LOCATION>"
```

---

## Secure Computation

### Secure Multi-Party Computation (MPC)

Multiple parties compute a function over their combined data without revealing individual inputs.

```
Party A has: salary data
Party B has: health data
Together compute: correlation between salary and health
Neither learns the other's raw data
```

### Homomorphic Encryption

Compute on encrypted data without decrypting it.

```
Encrypt(x) + Encrypt(y) = Encrypt(x + y)

Use case: Cloud ML inference where the cloud never sees plaintext data
Limitation: Currently very slow (1000-1000000x overhead)
```

### Trusted Execution Environments (TEEs)

Hardware-based secure enclaves (Intel SGX, ARM TrustZone, AMD SEV).

```
Use case: Train/infer on sensitive data in a hardware-protected environment
Advantage: Near-native performance
Limitation: Trust in hardware vendor, side-channel attacks exist
```

---

## Summary

Privacy and security in ML is a cat-and-mouse game. Key defenses:

1. **Differential Privacy** for training data protection (with accuracy trade-off)
2. **Federated Learning** to keep data decentralized
3. **Adversarial Training** for robustness to input attacks
4. **Data sanitization** against poisoning
5. **Access control** and output limiting against inference attacks
6. **PII detection** in data pipelines
7. **Regulatory compliance** baked into the ML lifecycle
