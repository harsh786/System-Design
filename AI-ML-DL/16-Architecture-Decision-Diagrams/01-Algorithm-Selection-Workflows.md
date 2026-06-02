# Algorithm Selection Decision Workflows

> Staff ML Architect reference: Decision paths with reasoning for algorithm, architecture, optimizer, loss, ensemble, regularization, and attention mechanism selection.

---

## Diagram 1: Master Algorithm Selection

```mermaid
flowchart TD
    Start([New ML Problem]) --> Labeled{Is data labeled?}

    Labeled -->|Yes| Supervised[Supervised Learning]
    Labeled -->|No| Unlabeled{Any structure to exploit?}
    Labeled -->|Partially| Semi[Semi-supervised / Self-supervised]

    Semi --> SemiChoice["Use pseudo-labels or contrastive pretraining<br/>WHY: Leverages unlabeled data to regularize"]

    Unlabeled -->|Find groups| Clustering[Clustering]
    Unlabeled -->|Reduce dimensions| DimRed[Dimensionality Reduction]
    Unlabeled -->|Find anomalies| Anomaly[Anomaly Detection]

    Clustering --> ClusterSize{How many samples?}
    ClusterSize -->|"<10k"| KMeans["K-Means / HDBSCAN<br/>WHY: K-Means=fast+simple, HDBSCAN=no k needed"]
    ClusterSize -->|">10k, complex shapes"| DBSCAN["DBSCAN / Spectral Clustering<br/>WHY: Handles non-convex clusters"]

    DimRed --> DimGoal{Goal?}
    DimGoal -->|Visualization| TSNE["t-SNE / UMAP<br/>WHY: Preserves local structure for 2D/3D"]
    DimGoal -->|Feature extraction| PCA["PCA / Autoencoders<br/>WHY: PCA=linear+fast, AE=nonlinear"]

    Anomaly --> AnomalyType["Isolation Forest / Autoencoder reconstruction<br/>WHY: IF=fast+no assumptions, AE=learns normal manifold"]

    Supervised --> TaskType{Output type?}
    TaskType -->|Continuous value| Regression[Regression]
    TaskType -->|Discrete classes| Classification[Classification]
    TaskType -->|Structured output| Structured["Seq2Seq / CRF<br/>WHY: Models output dependencies"]

    %% Classification Branch
    Classification --> ClassSamples{How many samples?}
    ClassSamples -->|"<1k"| SmallClass{Need interpretability?}
    SmallClass -->|Yes| LogReg["Logistic Regression / Decision Tree<br/>WHY: Transparent decisions, audit-friendly"]
    SmallClass -->|No| SVM["SVM with RBF kernel<br/>WHY: Works well in high-dim, small sample regime"]

    ClassSamples -->|"1k-100k"| MedClass{Need probability outputs?}
    MedClass -->|Yes| GBProb["XGBoost + calibration / Random Forest<br/>WHY: RF gives natural probabilities, XGB needs calibration"]
    MedClass -->|No| GBClass["XGBoost / LightGBM<br/>WHY: Best accuracy on tabular, handles mixed features"]

    ClassSamples -->|">100k"| LargeClass{Data type?}
    LargeClass -->|Tabular| GBLarge["LightGBM / CatBoost<br/>WHY: LightGBM=histogram-based speed, CatBoost=handles categoricals"]
    LargeClass -->|Image/Text/Sequence| DL["Deep Learning<br/>WHY: Representation learning dominates at scale"]

    %% Regression Branch
    Regression --> RegRelation{Linear relationship?}
    RegRelation -->|Yes| LinReg{Many features?}
    LinReg -->|"Features > Samples"| Lasso["Lasso / ElasticNet<br/>WHY: L1 sparsity selects features automatically"]
    LinReg -->|Normal| OLS["Linear Regression / Ridge<br/>WHY: Ridge if multicollinearity, OLS if clean"]

    RegRelation -->|No| NonLinReg{Need uncertainty?}
    NonLinReg -->|Yes| BayesReg["Gaussian Process / Bayesian NN / NGBoost<br/>WHY: Principled uncertainty quantification"]
    NonLinReg -->|No| TreeReg["XGBoost / Random Forest / Neural Net<br/>WHY: Trees=fast+robust, NN=if massive data"]
```

---

## Diagram 2: Deep Learning Architecture Selection

```mermaid
flowchart TD
    DLStart([What is your data modality?]) --> Modality{Data Type}

    Modality -->|Images| IMG[Image Data]
    Modality -->|Text / Sequential| SEQ[Sequential Data]
    Modality -->|Tabular| TAB[Tabular Data]
    Modality -->|Time Series| TS[Time Series]
    Modality -->|Graphs| GR[Graph Data]
    Modality -->|Multimodal| MM["Multimodal Fusion<br/>WHY: Different modalities need different encoders"]

    %% Image Branch
    IMG --> ImgSize{Dataset size?}
    ImgSize -->|"<10k samples"| PreTrained["Pretrained ResNet/EfficientNet + fine-tune<br/>WHY: Transfer learning dominates with limited data<br/>ImageNet features are universal edge/texture detectors"]
    ImgSize -->|"10k-1M, real-time needed"| MobileNet["MobileNet / EfficientNet-Lite<br/>WHY: Depthwise separable convs cut FLOPs 8-9x<br/>Latency constraint is the primary driver"]
    ImgSize -->|"Detection task"| Detection{Speed vs Accuracy?}
    Detection -->|Speed priority| YOLO["YOLOv8 / RT-DETR<br/>WHY: Single-shot detection, real-time on edge"]
    Detection -->|Accuracy priority| DETR["DETR / Mask R-CNN<br/>WHY: Set prediction removes NMS heuristics"]
    ImgSize -->|">1M samples"| ViT["Vision Transformer (ViT)<br/>WHY: Scales better with data than CNNs<br/>Global receptive field from layer 1"]

    %% Sequential Branch
    SEQ --> SeqTask{Task type?}
    SeqTask -->|Classification / NLU| BERT["BERT / RoBERTa / DeBERTa<br/>WHY: Bidirectional context captures meaning<br/>MLM pretraining learns deep representations"]
    SeqTask -->|Generation| GenSize{Model budget?}
    GenSize -->|"<1B params"| SmallGen["GPT-2 / Phi / Gemma<br/>WHY: Autoregressive fits generation naturally<br/>Smaller models for fine-tuning feasibility"]
    GenSize -->|">1B params"| LargeGen["Llama / Mistral / GPT-4<br/>WHY: Emergent capabilities at scale<br/>Use RLHF/DPO for alignment"]
    SeqTask -->|"Low latency needed"| Distil["DistilBERT / TinyBERT<br/>WHY: Knowledge distillation preserves 97% accuracy<br/>60% smaller, 2x faster inference"]
    SeqTask -->|"Very long sequences >4k"| LongSeq["Longformer / Mamba / RWKV<br/>WHY: O(n) or O(n log n) attention<br/>Full attention is O(n^2) = impractical for 100k+ tokens"]

    %% Tabular Branch
    TAB --> TabWhy["STILL USE GRADIENT BOOSTING!<br/>WHY: Trees handle missing values natively<br/>No normalization needed<br/>Fast training, great out-of-box<br/>Wins most Kaggle tabular competitions"]
    TabWhy --> TabException{Exception cases?}
    TabException -->|"Need embeddings for entities"| TabNet["TabNet / FT-Transformer<br/>WHY: Learns entity embeddings like DL<br/>Attention over features for interpretability"]
    TabException -->|"Multi-task learning"| TabNN["Neural Network with shared layers<br/>WHY: Shared representations across tasks<br/>Hard to do multi-task with trees"]
    TabException -->|"Streaming / online"| TabOnline["Vowpal Wabbit / River<br/>WHY: Online learning without full retraining"]

    %% Time Series Branch
    TS --> TSType{Complexity?}
    TSType -->|"Univariate, short horizon"| ARIMA["ARIMA / Prophet / ETS<br/>WHY: Simple, interpretable, well-understood<br/>Statistical guarantees, easy to explain"]
    TSType -->|"Multivariate, complex patterns"| LSTM["LSTM / Temporal CNN / N-BEATS<br/>WHY: Learns nonlinear temporal patterns<br/>TCN=parallelizable, LSTM=variable length"]
    TSType -->|"Long-range dependencies"| TSTransformer["Temporal Transformers / PatchTST / iTransformer<br/>WHY: Attention handles long-range dependencies<br/>Patching reduces sequence length"]
    TSType -->|"Forecasting at scale"| TSScale["TimesFM / Chronos<br/>WHY: Foundation models for zero-shot forecasting<br/>Pretrained on millions of time series"]

    %% Graph Branch
    GR --> GRTask{Task?}
    GRTask -->|Node classification| GCN["GCN / GAT / GraphSAGE<br/>WHY: Message passing aggregates neighborhood info<br/>GAT=learned attention weights on neighbors"]
    GRTask -->|Link prediction| GraphSAGE["GraphSAGE / SEAL<br/>WHY: Inductive - works on unseen nodes<br/>Samples neighborhood for scalability"]
    GRTask -->|Graph classification| GIN["GIN / Graph Transformers<br/>WHY: GIN is maximally expressive among MPNNs<br/>Isomorphism test power"]
```

---

## Diagram 3: Optimizer Selection

```mermaid
flowchart LR
    Start([Choose Optimizer]) --> Compute{Have compute<br/>budget for<br/>HP tuning?}

    Compute -->|"Yes, extensive tuning OK"| SGD["SGD + Momentum + Cosine Schedule<br/>─────────────────────<br/>WHY: Often best FINAL performance<br/>Generalizes better than adaptive methods<br/>Flatter minima → better test accuracy<br/>Used by top ImageNet submissions"]

    Compute -->|"No, need it to just work"| Default{What architecture?}

    Default -->|Transformer / NLP / CV| AdamW["AdamW (lr=1e-4 to 3e-4)<br/>─────────────────────<br/>WHY: Decoupled weight decay is correct L2<br/>Standard for all transformer training<br/>Original Adam conflates decay with gradient adapt"]

    Default -->|CNN / General| Adam["Adam (lr=1e-3)<br/>─────────────────────<br/>WHY: Adaptive LR per parameter<br/>Less sensitive to initial learning rate<br/>Good default for most architectures"]

    Default -->|Very large batch distributed| LAMB["LAMB / LARS<br/>─────────────────────<br/>WHY: Layer-wise adaptive rates<br/>Enables batch sizes of 32k-64k<br/>Trust ratio prevents layer collapse"]

    Default -->|"Memory constrained, large model"| Lion["Lion / Adafactor<br/>─────────────────────<br/>WHY: Lion uses sign of momentum only=less memory<br/>Adafactor factorizes second moment<br/>Both reduce optimizer state by 50%+"]

    Default -->|"GAN training"| GANOpt["Adam with β1=0.0, β2=0.9<br/>─────────────────────<br/>WHY: Low β1 reduces oscillation<br/>GANs need careful momentum handling"]

    SGD --> Schedule1["Pair with: Cosine Annealing + Warmup<br/>WHY: Warmup stabilizes early training<br/>Cosine avoids LR scheduling decisions"]
    AdamW --> Schedule2["Pair with: Linear warmup + cosine/linear decay<br/>WHY: Transformers are sensitive to early LR<br/>Warmup prevents divergence"]

    Start --> NotSure["Not sure?<br/>─────────────────────<br/>START: AdamW, lr=3e-4, wd=0.01<br/>NOT WORKING? → SGD + Cosine, lr=0.1<br/>STILL BAD? → Check LR with LR finder"]
```

---

## Diagram 4: Loss Function Selection

```mermaid
flowchart TD
    Task([What is your task?]) --> TaskType{Task Category}

    TaskType -->|Binary Classification| BC[Binary Classification]
    TaskType -->|Multi-class| MC[Multi-class Classification]
    TaskType -->|Regression| REG[Regression]
    TaskType -->|Generation| GEN[Generation]
    TaskType -->|Contrastive / Metric| METRIC[Metric Learning]

    %% Binary Classification
    BC --> BCBalance{Class balance?}
    BCBalance -->|Balanced| BCE["BCEWithLogitsLoss<br/>WHY: Numerically stable (log-sum-exp trick)<br/>Sigmoid + BCE fused avoids overflow"]
    BCBalance -->|"Imbalanced (>10:1)"| Focal["Focal Loss (γ=2)<br/>WHY: Down-weights easy negatives automatically<br/>(1-p)^γ reduces loss for confident predictions<br/>Originally for object detection"]
    BCBalance -->|"Extreme imbalance + ranking"| Hinge["Hinge Loss / BPR Loss<br/>WHY: Learns relative ordering not absolute probs<br/>Better for retrieval/ranking tasks"]

    %% Multi-class Classification
    MC --> MCType{Label structure?}
    MCType -->|Mutually exclusive| CE["CrossEntropyLoss<br/>WHY: Softmax + NLL combined<br/>Maximum likelihood for categorical distribution<br/>The standard for classification"]
    MCType -->|Multi-label| MLBCE["BCEWithLogitsLoss per class<br/>WHY: Each class is independent Bernoulli<br/>Sigmoid per class, not softmax across classes"]
    MCType -->|"Need calibration"| LabelSmooth["CrossEntropy + label_smoothing=0.1<br/>WHY: Prevents overconfident predictions<br/>Soft targets act as regularization<br/>Better calibrated probabilities"]
    MCType -->|"Noisy labels"| Symmetric["Symmetric CE / GCE<br/>WHY: Robust to label noise<br/>Symmetric = CE + Reverse CE"]

    %% Regression
    REG --> RegDist{Error distribution?}
    RegDist -->|"Gaussian / normal"| MSE["MSELoss (L2)<br/>WHY: Maximum likelihood for Gaussian errors<br/>Penalizes large errors quadratically"]
    RegDist -->|"Outliers present"| Robust{How robust?}
    Robust -->|Moderate| Huber["HuberLoss (δ=1.0)<br/>WHY: L2 for small errors, L1 for large<br/>Best of both worlds, smooth"]
    Robust -->|Very robust| MAE["L1Loss (MAE)<br/>WHY: Median regression, constant gradient<br/>Outliers don't dominate the loss"]
    RegDist -->|"Scale matters"| MAPE["MAPE / SMAPE<br/>WHY: Scale-independent percentage errors<br/>Use SMAPE to avoid division by zero"]
    RegDist -->|"Need prediction intervals"| Quantile["Quantile Loss / Pinball Loss<br/>WHY: Predicts specific quantiles<br/>τ=0.5 gives median, τ=0.9 gives 90th percentile"]

    %% Generation
    GEN --> GenType{What are you generating?}
    GenType -->|Text / Tokens| TokenCE["CrossEntropy on vocabulary<br/>WHY: Next-token prediction = categorical over vocab<br/>Teacher forcing during training"]
    GenType -->|Images| ImgLoss["L1 + Perceptual + Adversarial<br/>WHY: L1=pixel structure<br/>Perceptual=high-level feature similarity<br/>Adversarial=sharpness/realism"]
    GenType -->|"VAE latent space"| ELBO["ELBO = Recon + β·KL<br/>WHY: Principled variational inference<br/>KL regularizes latent space to prior<br/>β controls disentanglement"]
    GenType -->|Diffusion| DiffLoss["Simple MSE on noise prediction<br/>WHY: Denoising score matching<br/>Predict noise ε added at timestep t"]

    %% Metric Learning
    METRIC --> MetricType{Training setup?}
    MetricType -->|Pairs available| ContrastiveLoss["Contrastive Loss (margin)<br/>WHY: Pull positives to distance=0<br/>Push negatives beyond margin"]
    MetricType -->|"Triplets (anchor, pos, neg)"| TripletLoss["Triplet Loss (margin=0.2)<br/>WHY: Learns relative distances<br/>d(a,p) + margin < d(a,n)<br/>Hard mining critical for convergence"]
    MetricType -->|"Large batches, self-supervised"| InfoNCE["InfoNCE / NT-Xent<br/>WHY: In-batch negatives = free negatives<br/>Scales with batch size<br/>Used by SimCLR, CLIP, etc."]
```

---

## Diagram 5: Ensemble Method Selection

```mermaid
flowchart TD
    Start([Model Performance Issue]) --> Issue{What's the problem?}

    Issue -->|"High variance<br/>(overfitting, unstable)"| Bagging[Bagging / Random Forest]
    Issue -->|"High bias<br/>(underfitting)"| Boosting[Boosting Methods]
    Issue -->|"Multiple good models,<br/>want to combine"| Stacking[Stacking / Blending]
    Issue -->|"Need speed + accuracy"| Single[Single Strong Model]
    Issue -->|"Need interpretability"| Interp[Interpretable Model]

    Bagging --> BagWhy["WHY BAGGING WORKS:<br/>• Trains N models on bootstrap samples<br/>• Averaging reduces variance by ~1/N<br/>• Each tree sees different data subset<br/>• Decorrelation via feature subsampling (RF)"]
    Bagging --> BagChoices["Random Forest: 100-500 trees<br/>Bagged SVMs: If non-tabular<br/>Bagged Neural Nets: Expensive but powerful"]

    Boosting --> BoostWhy["WHY BOOSTING WORKS:<br/>• Each model corrects previous errors<br/>• Focuses on hard examples sequentially<br/>• Reduces bias while controlling variance<br/>• Gradient descent in function space"]
    Boosting --> BoostChoices{Data size?}
    BoostChoices -->|"<1M rows"| XGB["XGBoost<br/>WHY: Regularized objective, handles sparse<br/>Newton method = faster convergence"]
    BoostChoices -->|">1M rows"| LGB["LightGBM<br/>WHY: Histogram-based = O(data × bins)<br/>Leaf-wise growth = deeper trees faster"]
    BoostChoices -->|"Many categoricals"| CatB["CatBoost<br/>WHY: Ordered target encoding built-in<br/>No manual category handling needed"]

    Stacking --> StackWhy["WHY STACKING WORKS:<br/>• Meta-learner finds optimal combination<br/>• Diverse base models capture different patterns<br/>• Non-linear combination > simple averaging<br/>• Use out-of-fold predictions to avoid leakage"]
    Stacking --> StackRecipe["Recipe for good stacking:<br/>Level 0: XGBoost + LightGBM + CatBoost + NN + Ridge<br/>Level 1: Logistic Regression or Ridge<br/>WHY Ridge as meta: Prevents overfitting to base preds"]

    Single --> SingleWhy["XGBoost with good hyperparameters<br/>WHY: Already an ensemble internally (100+ trees)<br/>Diminishing returns from additional ensembling<br/>Simpler deployment, faster inference"]

    Interp --> InterpWhy["Single Decision Tree or Linear/GAM<br/>WHY: Ensembles are black boxes<br/>SHAP can explain, but adds complexity<br/>Regulation may require inherent interpretability"]

    %% Decision Summary
    Start --> Summary["QUICK DECISION:<br/>─────────────────────<br/>Kaggle competition? → Stack everything<br/>Production system? → Single XGBoost/LightGBM<br/>Need uncertainty? → Random Forest (variance of predictions)<br/>Small data + overfitting? → Bagging<br/>Underfitting? → Boosting with more trees"]
```

---

## Diagram 6: Regularization Strategy Selection

```mermaid
flowchart TD
    Start([Neural Network Overfitting]) --> Diagnose{Diagnose first!<br/>Train acc >> Val acc?}

    Diagnose -->|"Gap < 5%"| Mild["Mild overfitting - try these first"]
    Diagnose -->|"Gap 5-20%"| Moderate["Moderate overfitting"]
    Diagnose -->|"Gap > 20%"| Severe["Severe overfitting"]

    Mild --> M1["1. Early Stopping<br/>WHY: Free regularization, no hyperparams<br/>Just stop when val loss increases<br/>Patience=5-10 epochs typical"]
    Mild --> M2["2. Weight Decay (1e-4 to 1e-2)<br/>WHY: Penalizes large weights → smoother functions<br/>Smoother = better generalization<br/>Equivalent to Gaussian prior on weights"]

    Moderate --> Mo1["All of mild PLUS:"]
    Mo1 --> Mo2["3. Dropout (0.1-0.5)<br/>WHY: Kills random neurons each forward pass<br/>Prevents co-adaptation of features<br/>Implicit ensemble of subnetworks<br/>Higher rate = more regularization"]
    Mo1 --> Mo3["4. Data Augmentation<br/>WHY: Creates virtual training examples<br/>Teaches invariances (rotation, flip, crop)<br/>Most bang-for-buck regularizer<br/>Image: RandAugment; Text: Back-translation"]

    Severe --> S1["All of moderate PLUS:"]
    S1 --> S2["5. Reduce Model Size<br/>WHY: Fewer parameters = fewer degrees of freedom<br/>Only as LAST RESORT - try other methods first<br/>Smaller model may underfit"]
    S1 --> S3["6. Label Smoothing (0.1)<br/>WHY: Soft targets prevent overconfident logits<br/>Logit magnitudes stay controlled<br/>Acts as output regularizer"]
    S1 --> S4["7. Mixup / CutMix<br/>WHY: Interpolates training examples<br/>Linearizes between classes<br/>Reduces memorization of individual samples"]

    %% Architecture-specific
    Start --> ArchSpecific{Architecture-specific:}
    ArchSpecific -->|CNN| CNNReg["Batch Normalization<br/>WHY: Normalizes activations per batch<br/>Smooths loss landscape<br/>Slight regularization from batch noise"]
    ArchSpecific -->|Transformer| TransReg["Layer Norm + Dropout on attention<br/>WHY: Attention weights can overfit<br/>Pre-norm more stable than post-norm"]
    ArchSpecific -->|RNN/LSTM| RNNReg["Recurrent Dropout (same mask across time)<br/>WHY: Standard dropout breaks temporal info<br/>Variational dropout preserves sequences"]

    %% Decision Flow
    Start --> Flow["RECOMMENDED ORDER:<br/>─────────────────────<br/>1. Early Stopping (always, it's free)<br/>2. Weight Decay = 0.01 (AdamW default)<br/>3. Data Augmentation (biggest impact per effort)<br/>4. Dropout = 0.1-0.3 (after attention/FC layers)<br/>5. Label Smoothing = 0.1 (for classification)<br/>6. Reduce model size (LAST RESORT)<br/>─────────────────────<br/>MORE DATA > ALL REGULARIZATION COMBINED"]
```

---

## Diagram 7: Attention Mechanism Selection

```mermaid
sequenceDiagram
    participant Q as Query Sequence
    participant K as Key Sequence
    participant V as Value Sequence
    participant Out as Output

    Note over Q,Out: SELF-ATTENTION (Full O(n²))
    Note over Q,Out: Every token attends to ALL other tokens
    Q->>K: Compute attention scores (Q·K^T / √d)
    K->>V: Softmax weights applied to Values
    V->>Out: Weighted sum = context-aware representation
    Note over Q,Out: WHY: Captures any pairwise relationship<br/>regardless of distance. No inductive bias.
    Note over Q,Out: COST: O(n²) memory and compute

    Note over Q,Out: ─────────────────────────────

    Note over Q,Out: CROSS-ATTENTION
    Note over Q: Query from decoder
    Note over K,V: Keys/Values from encoder
    Q->>K: Decoder queries attend to encoder outputs
    K->>V: Find relevant source information
    V->>Out: Decoder gets source-conditioned output
    Note over Q,Out: WHY: Connects two different sequences<br/>Translation: target attends to source<br/>Image captioning: text attends to image patches

    Note over Q,Out: ─────────────────────────────

    Note over Q,Out: MULTI-HEAD ATTENTION (h=8 typical)
    Q->>K: Head 1: syntactic relationships
    Q->>K: Head 2: semantic similarity
    Q->>K: Head 3: positional patterns
    Q->>K: Head h: ...other learned patterns
    K->>Out: Concatenate all heads + linear projection
    Note over Q,Out: WHY: Single attention = one relationship type<br/>Multiple heads = parallel diverse patterns<br/>Empirically: different heads learn different things

    Note over Q,Out: ─────────────────────────────

    Note over Q,Out: SPARSE ATTENTION (Longformer-style)
    Q->>K: Local window attention (nearby tokens)
    Q->>K: Global tokens attend to everything
    Q->>K: Dilated/strided for longer range
    K->>Out: Combined local + global context
    Note over Q,Out: WHY: O(n) instead of O(n²)<br/>Most tokens only need local context<br/>Few global tokens handle long-range<br/>Enables sequences of 16k-100k tokens

    Note over Q,Out: ─────────────────────────────

    Note over Q,Out: FLASH ATTENTION (Hardware-aware)
    Q->>K: Same math as standard attention
    Note over Q,K: But: Tiled computation in GPU SRAM
    Note over Q,K: Never materializes full N×N matrix
    K->>Out: Exact same output, 2-4x faster
    Note over Q,Out: WHY: GPU SRAM is 10-100x faster than HBM<br/>Standard attention bottlenecked by memory bandwidth<br/>Tiling = compute in fast SRAM, stream results<br/>No approximation - exact attention, just faster

    Note over Q,Out: ─────────────────────────────

    Note over Q,Out: DECISION GUIDE
    Note over Q,Out: Seq < 512 tokens → Standard self-attention (fast enough)
    Note over Q,Out: Seq 512-4k → Flash Attention (same result, faster)
    Note over Q,Out: Seq 4k-100k → Sparse / Sliding Window (Mistral-style)
    Note over Q,Out: Seq > 100k → Mamba/RWKV (linear recurrence, not attention)
```

---

## Quick Reference Table

| Problem | First Try | Why | If Not Working |
|---------|-----------|-----|----------------|
| Image classification | ResNet50 pretrained | Best accuracy/speed tradeoff, universal features | EfficientNet-B3 if smaller model needed |
| Object detection | YOLOv8 | Real-time, single-shot, great accuracy | DETR if accuracy > speed |
| Text classification | DistilBERT fine-tuned | 97% of BERT accuracy, 60% smaller, 2x faster | RoBERTa/DeBERTa if accuracy critical |
| Text generation | Llama 3 (8B) | Open-source, strong, fine-tunable | GPT-4 via API if budget allows |
| Tabular classification | XGBoost | Handles everything, fast, minimal preprocessing | LightGBM if >1M rows, CatBoost if many categoricals |
| Tabular regression | LightGBM | Fast histogram splits, good defaults | XGBoost + Optuna tuning if accuracy critical |
| Time series forecast | Prophet / ARIMA | Interpretable, fast, good baselines | N-BEATS / PatchTST if complex patterns |
| Anomaly detection | Isolation Forest | No assumptions, fast, works on any distribution | Autoencoder if high-dimensional |
| Recommendation | Matrix Factorization | Simple, scalable, well-understood | Two-tower neural model if rich features |
| Clustering | HDBSCAN | No k needed, finds arbitrary shapes | K-Means if need speed on >1M points |
| Semantic search | Sentence-BERT embeddings | Dense retrieval, captures meaning | ColBERT if need token-level matching |
| Speech recognition | Whisper (medium) | Multilingual, robust, pretrained | Whisper large-v3 if accuracy critical |
| Graph node classification | GCN / GAT | Simple, effective message passing | GraphSAGE if inductive (new nodes at inference) |
| Multi-label classification | Binary relevance + BCE | Independent per label, simple | Classifier chains if label correlations matter |

---

## Meta-Decision: When to Use Deep Learning vs Traditional ML

```mermaid
flowchart TD
    Question([Should I use Deep Learning?]) --> DataSize{Data size?}

    DataSize -->|"<1k samples"| NoDL["NO: Use traditional ML<br/>WHY: DL needs data to learn representations<br/>Small data → overfitting guaranteed<br/>USE: Logistic Regression, SVM, RF"]

    DataSize -->|"1k-10k"| Maybe{Pretrained model available?}
    Maybe -->|Yes| TransferDL["YES with transfer learning<br/>WHY: Pretrained = already learned features<br/>Fine-tuning only adapts last layers<br/>Effective even with 100 samples if good pretrained model"]
    Maybe -->|No| TraditionalPlus["PROBABLY NO: Traditional ML<br/>WHY: Not enough data to learn from scratch<br/>USE: XGBoost, feature engineering, domain knowledge"]

    DataSize -->|"10k-100k"| DataType2{Data type?}
    DataType2 -->|"Tabular"| StillTrad["Traditional ML still wins<br/>WHY: Trees + feature engineering > neural nets on tabular<br/>Benchmark: XGBoost beats MLP in 90%+ of Kaggle tabular"]
    DataType2 -->|"Unstructured (image/text/audio)"| YesDL["YES: Deep Learning<br/>WHY: Learned representations > hand-crafted features<br/>CNNs learn hierarchical visual features<br/>Transformers learn contextual language features"]

    DataSize -->|">100k"| AlmostAlways["Almost always Deep Learning<br/>WHY: DL scales with data, traditional ML plateaus<br/>Representation learning is the key advantage<br/>EXCEPTION: Tabular still consider XGBoost first"]
```

---

## Tradeoff Summary: The Axes That Matter

When selecting algorithms, these are the dimensions a staff architect weighs:

1. **Accuracy vs Latency** - Can you afford 100ms inference? Or need <10ms?
2. **Accuracy vs Interpretability** - Regulated domain? Need to explain decisions?
3. **Accuracy vs Data Efficiency** - How much labeled data do you have?
4. **Training Cost vs Inference Cost** - Train once, serve millions? Or retrain daily?
5. **Complexity vs Maintainability** - Who maintains this in 2 years?
6. **Generalization vs Specialization** - One model for all, or fine-tuned per segment?

The best algorithm is often the simplest one that meets your requirements.
