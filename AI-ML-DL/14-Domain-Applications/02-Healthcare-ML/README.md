# Healthcare ML

## Overview

Healthcare ML has the potential to improve patient outcomes, reduce costs, and accelerate drug discovery. However, it faces unique challenges: data scarcity, privacy regulations, extreme consequences of errors, and complex regulatory approval paths.

---

## 1. Medical Imaging

### Radiology AI

```
┌─────────────────────────────────────────────────────────┐
│              MEDICAL IMAGING AI PIPELINE                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  DICOM Input ──▶ Preprocessing ──▶ Model Inference      │
│                   • Windowing       • Detection          │
│                   • Normalization    • Segmentation      │
│                   • Augmentation     • Classification    │
│                        │                   │             │
│                        ▼                   ▼             │
│                  ┌──────────┐      ┌─────────────┐      │
│                  │Quality   │      │Uncertainty  │      │
│                  │Check     │      │Estimation   │      │
│                  └──────────┘      └──────┬──────┘      │
│                                           │             │
│                         ┌─────────────────┤             │
│                         ▼                 ▼             │
│                  ┌─────────────┐   ┌───────────┐       │
│                  │High Conf.   │   │Low Conf.  │       │
│                  │Auto-report  │   │→ Radiologist│      │
│                  └─────────────┘   └───────────┘       │
│                         │                 │             │
│                         └────────┬────────┘             │
│                                  ▼                      │
│                         ┌─────────────┐                 │
│                         │Clinical     │                 │
│                         │Integration  │                 │
│                         │(PACS/EHR)   │                 │
│                         └─────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### Key Applications

| Modality | Task | Architecture | Notable Systems |
|----------|------|--------------|-----------------|
| Chest X-ray | Detection (14+ findings) | DenseNet, EfficientNet | CheXNet, CheXpert |
| CT Scan | Lung nodule detection | 3D CNN, U-Net | LUNA16 |
| Mammography | Breast cancer screening | ResNet + attention | Google Health |
| Retinal OCT | Diabetic retinopathy | Inception, EfficientNet | IDx-DR (FDA cleared) |
| Pathology | WSI classification | MIL, attention-based | PathAI |
| Dermatology | Skin lesion classification | EfficientNet | DermNet |

### Key Techniques

```python
class MedicalImageModel:
    def __init__(self):
        # Transfer learning from ImageNet (surprisingly effective)
        self.backbone = EfficientNetB4(pretrained=True)
        # Modify first conv for single-channel (grayscale) input
        self.backbone.conv1 = nn.Conv2d(1, 48, kernel_size=3, stride=2, padding=1)
        self.classifier = nn.Linear(1792, num_classes)
    
    def train_with_uncertainty(self, dataloader):
        """MC Dropout for uncertainty estimation"""
        self.train()  # Keep dropout active at inference
        predictions = []
        for _ in range(20):  # Multiple forward passes
            pred = self.forward(x)
            predictions.append(pred)
        
        mean_pred = torch.stack(predictions).mean(0)
        uncertainty = torch.stack(predictions).std(0)
        return mean_pred, uncertainty
```

### Medical Image Augmentation

- Rotation, flipping (anatomy-aware: don't flip laterality)
- Elastic deformation
- Intensity variation (simulating different scanners)
- CutMix/MixUp (with care for pathology)
- GAN-based synthetic data generation

---

## 2. Electronic Health Records (EHR) Modeling

### Challenges

- **Irregular time series**: Events happen at non-uniform intervals
- **Missing data**: Not random — missingness is informative
- **High dimensionality**: Thousands of diagnosis codes, medications, labs
- **Label noise**: Billing codes ≠ true diagnoses

### Temporal Modeling

```python
class EHRTransformer(nn.Module):
    """Transformer for irregular EHR time series"""
    
    def __init__(self, n_codes, d_model=256, n_heads=8, n_layers=4):
        super().__init__()
        self.code_embedding = nn.Embedding(n_codes, d_model)
        self.time_encoding = TimeEncoding(d_model)  # Continuous time
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model, n_heads), n_layers)
        self.predictor = nn.Linear(d_model, 1)
    
    def forward(self, codes, timestamps, mask):
        # Embed medical codes
        x = self.code_embedding(codes)
        # Add continuous time encoding (not positional)
        x = x + self.time_encoding(timestamps)
        # Transformer with causal mask
        x = self.transformer(x, src_key_padding_mask=mask)
        # Predict from [CLS] or last token
        return self.predictor(x[:, -1, :])


class TimeEncoding(nn.Module):
    """Learnable encoding for continuous time gaps"""
    def __init__(self, d_model):
        super().__init__()
        self.linear = nn.Linear(1, d_model)
    
    def forward(self, timestamps):
        # Time gaps between events
        dt = timestamps[:, 1:] - timestamps[:, :-1]
        return self.linear(dt.unsqueeze(-1))
```

### Common EHR Prediction Tasks

- **Readmission prediction** (30-day readmission)
- **Mortality prediction** (in-hospital, 1-year)
- **Length of stay** prediction
- **Diagnosis prediction** (next visit diagnoses)
- **Adverse drug events**
- **Sepsis early warning**

---

## 3. Drug Discovery Pipeline

```
┌─────────────────────────────────────────────────────────┐
│              ML IN DRUG DISCOVERY                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Target ID ──▶ Hit Finding ──▶ Lead Opt ──▶ ADMET      │
│  (genomics)    (virtual       (generative  (prediction) │
│                 screening)     chemistry)                │
│                                                          │
│  Methods:      Methods:       Methods:     Methods:     │
│  • GWAS        • Docking      • VAE        • GNN       │
│  • Network     • GNN          • RL         • Random    │
│    biology     • Fingerprint  • Flow       •  Forest   │
│  • Causal        similarity     matching   • MPNN      │
│    inference   • Transformers • Diffusion               │
│                                                          │
│  Timeline:     Timeline:      Timeline:    Timeline:    │
│  1-2 years     6-12 months    1-2 years    6 months    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Molecular Representations

| Representation | Pros | Cons | Models |
|---------------|------|------|--------|
| SMILES | Simple string | Not bijective, fragile | Transformer, RNN |
| Fingerprints (ECFP) | Fast, fixed-size | Lossy, no 3D | RF, XGBoost, MLP |
| Molecular Graph | Rich structure | Variable size | GNN, MPNN, SchNet |
| 3D Conformer | Physical accuracy | Expensive to compute | SE(3)-equivariant |

### ADMET Prediction

```python
class ADMETPredictor:
    """Predict Absorption, Distribution, Metabolism, Excretion, Toxicity"""
    
    def __init__(self):
        self.models = {
            'solubility': MPNNRegressor(),      # LogS
            'permeability': MPNNRegressor(),     # Caco-2
            'cyp_inhibition': MPNNClassifier(),  # CYP450 enzymes
            'herg_toxicity': MPNNClassifier(),   # Cardiac risk
            'clearance': MPNNRegressor(),        # Hepatic clearance
            'bbb_penetration': MPNNClassifier(), # Blood-brain barrier
        }
    
    def predict_profile(self, molecule_smiles):
        graph = smiles_to_graph(molecule_smiles)
        return {name: model.predict(graph) for name, model in self.models.items()}
```

---

## 4. Clinical Trial Design Optimization

- **Patient stratification**: Identify responder subgroups
- **Adaptive trial design**: Bayesian response-adaptive randomization
- **Synthetic control arms**: Use historical data to reduce placebo group size
- **Site selection**: Predict enrollment rates per site
- **Endpoint prediction**: Power analysis with ML-informed effect sizes

---

## 5. Genomics & Precision Medicine

### Genome-Wide Association Studies (GWAS)

- Millions of SNPs, thousands of samples
- Multiple testing correction (Bonferroni: p < 5×10⁻⁸)
- Population stratification as confounder
- Polygenic Risk Scores (PRS): weighted sum of risk alleles

### ML in Genomics

```python
class PolygenticRiskScore:
    """Compute PRS from GWAS summary statistics"""
    
    def compute_prs(self, genotypes, effect_sizes, p_values, threshold=5e-8):
        # Select significant SNPs
        significant = p_values < threshold
        selected_snps = genotypes[:, significant]
        weights = effect_sizes[significant]
        
        # Weighted sum
        prs = selected_snps @ weights
        return prs
    
    def ld_clumping(self, snps, r2_threshold=0.1, window=250000):
        """Remove correlated SNPs (linkage disequilibrium)"""
        # Keep most significant SNP in each LD block
        pass
```

---

## 6. Wearable/IoT Health Data

### Continuous Monitoring Applications

- **Arrhythmia detection** (Apple Watch, AliveCor)
- **Sleep staging** from accelerometer + HR
- **Glucose prediction** (continuous glucose monitors)
- **Fall detection** in elderly
- **Mental health** (activity patterns, HRV, sleep)

### Challenges

- Noisy signals (motion artifacts)
- Battery constraints limit model complexity
- On-device vs cloud inference tradeoffs
- Alarm fatigue (too many false alerts)

---

## 7. Survival Analysis

```python
class DeepSurvival(nn.Module):
    """Deep survival model (Cox PH extension)"""
    
    def __init__(self, input_dim, hidden_dim=256):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(), nn.BatchNorm1d(hidden_dim), nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(), nn.BatchNorm1d(hidden_dim), nn.Dropout(0.3),
            nn.Linear(hidden_dim, 1)  # Log-hazard ratio
        )
    
    def forward(self, x):
        return self.network(x)
    
    def cox_loss(self, log_hazard, time, event):
        """Partial likelihood loss for Cox model"""
        # Sort by time (descending)
        sorted_idx = torch.argsort(time, descending=True)
        log_hazard = log_hazard[sorted_idx]
        event = event[sorted_idx]
        
        # Log partial likelihood
        log_cumsum_hazard = torch.logcumsumexp(log_hazard, dim=0)
        loss = -torch.sum((log_hazard - log_cumsum_hazard) * event)
        return loss / event.sum()
```

---

## 8. Challenges in Healthcare ML

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| Small datasets | Overfitting | Transfer learning, data augmentation, few-shot |
| Label noise | Wrong ground truth | Multi-annotator, adjudication |
| Class imbalance | Rare diseases missed | Oversampling, focal loss, cost-sensitive |
| Distribution shift | Scanner/site variation | Domain adaptation, harmonization |
| Privacy (HIPAA) | Limited data sharing | Federated learning, differential privacy |
| Fairness | Disparities across demographics | Stratified evaluation, bias mitigation |
| Missing data | Biased predictions | Imputation models, missingness indicators |

---

## 9. Regulatory Path

### FDA Software as Medical Device (SaMD)

```
Risk Classification:
┌─────────────────────────────────────────────┐
│  Significance of Information                 │
│           │ Treat/Diagnose │ Drive │ Inform │
│  ─────────┼────────────────┼───────┼────────│
│  Critical │    Class III   │  III  │   II   │
│  Serious  │    Class III   │  II   │   II   │
│  Non-ser. │    Class II    │   I   │   I    │
└─────────────────────────────────────────────┘

Pathways:
• 510(k): Substantial equivalence to predicate device
• De Novo: Novel, low-moderate risk, no predicate
• PMA: High risk, requires clinical evidence
• Breakthrough: Expedited for unmet clinical need
```

### Key Requirements

- **Predetermined Change Control Plan**: How will the model be updated?
- **Clinical validation**: Prospective study with clinical endpoints
- **Labeling**: Clear intended use, limitations, target population
- **Real-world performance monitoring**: Post-market surveillance

---

## 10. Federated Learning for Healthcare

```
┌─────────────────────────────────────────────────────┐
│          FEDERATED LEARNING ARCHITECTURE             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Hospital A    Hospital B    Hospital C              │
│  ┌────────┐   ┌────────┐   ┌────────┐             │
│  │Local   │   │Local   │   │Local   │             │
│  │Training│   │Training│   │Training│             │
│  │(data   │   │(data   │   │(data   │             │
│  │ stays) │   │ stays) │   │ stays) │             │
│  └───┬────┘   └───┬────┘   └───┬────┘             │
│      │             │             │                   │
│      └─────── gradients/weights ─┘                  │
│                    │                                 │
│                    ▼                                 │
│           ┌──────────────┐                          │
│           │  Aggregation │                          │
│           │  Server      │                          │
│           │  (FedAvg)    │                          │
│           └──────┬───────┘                          │
│                  │                                   │
│           Updated global model                      │
│           distributed back                          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Considerations

- Non-IID data across hospitals (different patient populations)
- Communication efficiency (gradient compression)
- Privacy guarantees (differential privacy, secure aggregation)
- Handling stragglers (asynchronous updates)

---

## 11. Explainability in Clinical Decision Support

- **Saliency maps** for imaging (GradCAM, SHAP on pixels)
- **Feature attribution** for tabular EHR (SHAP, LIME)
- **Concept-based explanations** (TCAV for medical concepts)
- **Counterfactual explanations** ("If lab value X were lower, prediction would change")
- **Clinician-friendly reporting** (natural language summaries)

---

## Production Considerations

- **HIPAA compliance**: De-identification, access controls, audit logs
- **Integration**: HL7 FHIR for data exchange, DICOM for imaging
- **Monitoring**: Performance degradation detection per subgroup
- **Human-in-the-loop**: Most clinical AI is decision *support*, not autonomous
- **Calibration**: Well-calibrated probabilities crucial for clinical trust
- **Fail-safe design**: Graceful degradation when model is uncertain

---

## Common Pitfalls in Medical ML

1. **Shortcut learning**: Model learns hospital label from image metadata, not pathology
2. **Label leakage**: Severity encoded in scan ordering (sick patients get more scans)
3. **Unfair evaluation**: Testing on same institution as training
4. **Ignoring prevalence**: High AUC but terrible PPV at low disease prevalence
5. **Conflating AI performance with clinical utility**: Accuracy ≠ patient benefit
6. **Ignoring workflow integration**: Best model fails if clinicians don't use it
7. **Training on convenience samples**: Dataset doesn't represent target population

---

## Interview Questions

1. **How would you handle a medical imaging dataset with only 500 labeled examples?**
2. **Design a sepsis early warning system using EHR data. What features and architecture?**
3. **How do you evaluate a diagnostic AI model for a disease with 0.1% prevalence?**
4. **Explain federated learning for multi-hospital collaboration. What are the failure modes?**
5. **How would you detect and mitigate shortcut learning in a chest X-ray model?**
6. **What's the difference between FDA 510(k) and De Novo pathways?**
7. **How do you handle missing data in EHR models? When is imputation inappropriate?**
8. **Design a clinical trial matching system using NLP on medical records.**

---

## Key Papers

1. **"CheXpert"** - Irvin et al. (2019) - Large chest X-ray dataset with uncertainty labels
2. **"RETAIN"** - Choi et al. (2016) - Interpretable EHR model with attention
3. **"DeepSurv"** - Katzman et al. (2018) - Deep survival analysis
4. **"Federated Learning for Healthcare"** - Rieke et al. (2020) - Nature review
5. **"A Survey on Deep Learning in Medical Image Analysis"** - Litjens et al. (2017)
6. **"MoleculeNet"** - Wu et al. (2018) - Benchmark for molecular ML
7. **"Hidden Stratification"** - Oakden-Rayner et al. (2020) - Subgroup failures
8. **"MIMIC-III"** - Johnson et al. (2016) - Open ICU dataset
