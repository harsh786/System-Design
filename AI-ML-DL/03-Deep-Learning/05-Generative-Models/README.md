# Generative Models

## 1. Overview

Generative models learn the data distribution P(x) and can sample new data from it.

```
Discriminative: P(y|x)  → "Is this a cat?"
Generative:     P(x)    → "Generate a cat image"
                P(x|y)  → "Generate a cat image given label 'cat'"
```

### Taxonomy

```
Generative Models
├── Explicit Density
│   ├── Tractable: Autoregressive (PixelCNN, GPT), Flow-based (RealNVP)
│   └── Approximate: VAE (variational inference)
└── Implicit Density
    └── GAN (learn to generate via adversarial game)
    
+ Diffusion Models (score-based / denoising)
```

## 2. Autoencoders

### Vanilla Autoencoder

```
Input (x)         Latent (z)        Reconstruction (x̂)
[784] ──→ Encoder ──→ [32] ──→ Decoder ──→ [784]

Loss = ||x - x̂||²  (reconstruction error)
```

```
Architecture:
x ──→ [FC 784→512] ──→ [FC 512→256] ──→ [FC 256→32] ──→ z (bottleneck)
                                                           │
x̂ ←── [FC 512→784] ←── [FC 256→512] ←── [FC 32→256] ←───┘
```

```python
class Autoencoder(nn.Module):
    def __init__(self, input_dim=784, latent_dim=32):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 512), nn.ReLU(),
            nn.Linear(512, 256), nn.ReLU(),
            nn.Linear(256, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 256), nn.ReLU(),
            nn.Linear(256, 512), nn.ReLU(),
            nn.Linear(512, input_dim), nn.Sigmoid(),
        )
    
    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)
```

**Limitation**: Latent space is not structured — can't sample meaningful new data from it.

### Variational Autoencoder (VAE) — Kingma & Welling, 2013

**Key idea**: Encode to a distribution, not a point. Regularize latent space to be a smooth Gaussian.

```
Encoder outputs:  μ(x), σ(x)   (mean and std of latent distribution)
Sampling:         z = μ + σ ⊙ ε,  ε ~ N(0, I)   ← "reparameterization trick"
Decoder:          p(x|z)
```

### VAE Loss (ELBO)

```
L = E_q[log p(x|z)] - KL(q(z|x) || p(z))
    └─────────────┘   └──────────────────┘
    Reconstruction     Regularization
    (make x̂ ≈ x)      (push q(z|x) toward N(0,I))

KL divergence (closed form for Gaussians):
KL = -½ Σ (1 + log σ² - μ² - σ²)
```

### Reparameterization Trick

Can't backprop through sampling. Instead:
```
z = μ + σ ⊙ ε     (ε ~ N(0,I), not dependent on parameters)
∂L/∂μ and ∂L/∂σ exist!
```

```python
class VAE(nn.Module):
    def __init__(self, input_dim=784, latent_dim=20):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 512), nn.ReLU())
        self.fc_mu = nn.Linear(512, latent_dim)
        self.fc_logvar = nn.Linear(512, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 512), nn.ReLU(),
            nn.Linear(512, input_dim), nn.Sigmoid(),
        )
    
    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)
    
    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std
    
    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decoder(z), mu, logvar

def vae_loss(recon_x, x, mu, logvar):
    recon = F.binary_cross_entropy(recon_x, x, reduction='sum')
    kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return recon + kl
```

## 3. Generative Adversarial Networks (GANs) — Goodfellow et al., 2014

### Core Idea: Two-Player Game

```
Generator (G):     Random noise z → Fake data G(z)
Discriminator (D): Real/Fake data → Probability of being real

         z ~ N(0,I)
            │
     ┌──────┴──────┐
     │  Generator   │
     │     G(z)     │
     └──────┬──────┘
            │ fake samples
            ↓
     ┌──────────────┐       Real data x
     │Discriminator │ ←─────────────────
     │   D(x)       │
     └──────┬──────┘
            │
     P(real) ∈ [0,1]
```

### Training Objective (Minimax Game)

```
min_G max_D  V(D, G) = E_x[log D(x)] + E_z[log(1 - D(G(z)))]

D wants to maximize:  log D(x_real) + log(1 - D(x_fake))  (correctly classify)
G wants to minimize:  log(1 - D(G(z)))  (fool D)

In practice, G maximizes log D(G(z)) instead (stronger gradient early in training)
```

### Training Algorithm

```
for each training iteration:
    # 1. Train Discriminator (k steps, typically k=1)
    Sample minibatch of m noise samples {z₁...zₘ}
    Sample minibatch of m real samples {x₁...xₘ}
    Update D by ascending:  ∇_D [1/m Σ log D(xᵢ) + log(1 - D(G(zᵢ)))]
    
    # 2. Train Generator (1 step)
    Sample minibatch of m noise samples {z₁...zₘ}
    Update G by descending: ∇_G [1/m Σ log(1 - D(G(zᵢ)))]
    # Or ascending: ∇_G [1/m Σ log D(G(zᵢ))]  (non-saturating)
```

```python
class Generator(nn.Module):
    def __init__(self, latent_dim=100, img_dim=784):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(latent_dim, 256), nn.LeakyReLU(0.2),
            nn.Linear(256, 512), nn.LeakyReLU(0.2),
            nn.Linear(512, 1024), nn.LeakyReLU(0.2),
            nn.Linear(1024, img_dim), nn.Tanh(),
        )
    def forward(self, z): return self.net(z)

class Discriminator(nn.Module):
    def __init__(self, img_dim=784):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(img_dim, 512), nn.LeakyReLU(0.2), nn.Dropout(0.3),
            nn.Linear(512, 256), nn.LeakyReLU(0.2), nn.Dropout(0.3),
            nn.Linear(256, 1), nn.Sigmoid(),
        )
    def forward(self, x): return self.net(x)

# Training loop
for real_imgs in dataloader:
    # Train D
    z = torch.randn(batch_size, latent_dim)
    fake_imgs = G(z).detach()
    d_loss = -torch.mean(torch.log(D(real_imgs)) + torch.log(1 - D(fake_imgs)))
    d_loss.backward(); opt_d.step()
    
    # Train G
    z = torch.randn(batch_size, latent_dim)
    fake_imgs = G(z)
    g_loss = -torch.mean(torch.log(D(fake_imgs)))  # Non-saturating
    g_loss.backward(); opt_g.step()
```

## 4. GAN Variants

### DCGAN (Deep Convolutional GAN)

Architecture guidelines that stabilize training:
- Replace pooling with strided convolutions (D) and transposed convolutions (G)
- Use BatchNorm in both G and D (except G output and D input)
- Use ReLU in G (except output: Tanh), LeakyReLU in D
- No fully connected layers (all convolutional)

### StyleGAN (Karras et al., 2019)

```
Mapping Network:  z → w (512-dim style vector, 8 FC layers)
Synthesis Network: Constant input → progressive upsampling
  At each layer:  style w → AdaIN (controls features)
  + noise injection (stochastic variation: hair, freckles)

Key insight: Disentangled latent space w (vs entangled z)
```

### CycleGAN (Unpaired Image-to-Image Translation)

```
Domain A (horses) ←→ Domain B (zebras)

G_AB: A → B,  G_BA: B → A
D_A: real A vs fake A,  D_B: real B vs fake B

Losses:
1. Adversarial: G_AB fools D_B, G_BA fools D_A
2. Cycle consistency: G_BA(G_AB(a)) ≈ a  and  G_AB(G_BA(b)) ≈ b
3. Identity (optional): G_AB(b) ≈ b
```

### Mode Collapse

**Problem**: Generator produces limited variety — ignores parts of the data distribution.

```
Real distribution: multi-modal (many clusters)
Generator output:  collapses to one or few modes

Example: Generate digits → only produces "1" (gets high D score for it)
```

**Solutions**:
- Wasserstein GAN (WGAN): Replace JS divergence with Wasserstein distance
- Spectral Normalization: Stabilize D by constraining Lipschitz constant
- Progressive Growing: Start at low resolution, gradually increase
- Minibatch discrimination: Let D see statistics across batch

## 5. Diffusion Models

### DDPM (Denoising Diffusion Probabilistic Models) — Ho et al., 2020

#### Forward Process (Add Noise)

Gradually add Gaussian noise over T steps:
```
q(xₜ|xₜ₋₁) = N(xₜ; √(1-βₜ)·xₜ₋₁, βₜ·I)

Closed form (skip to any step t):
q(xₜ|x₀) = N(xₜ; √ᾱₜ·x₀, (1-ᾱₜ)·I)
where αₜ = 1-βₜ, ᾱₜ = Π αᵢ

xₜ = √ᾱₜ·x₀ + √(1-ᾱₜ)·ε,   ε ~ N(0,I)
```

```
x₀ (clean) → x₁ (tiny noise) → ... → x_T (pure noise ~ N(0,I))
   ↓            ↓                          ↓
[image]    [slightly noisy]         [random static]
```

#### Reverse Process (Denoise) — LEARNED

```
p_θ(xₜ₋₁|xₜ) = N(xₜ₋₁; μ_θ(xₜ,t), σₜ²·I)

Train neural network ε_θ(xₜ, t) to predict the noise ε that was added.

Loss (simplified):
L = E_{t,x₀,ε} [||ε - ε_θ(√ᾱₜ·x₀ + √(1-ᾱₜ)·ε, t)||²]
```

#### Sampling (Generation)

```
Start with x_T ~ N(0, I)
For t = T, T-1, ..., 1:
    ε_pred = ε_θ(xₜ, t)    ← neural network predicts noise
    xₜ₋₁ = (1/√αₜ) · (xₜ - (βₜ/√(1-ᾱₜ))·ε_pred) + σₜ·z
    where z ~ N(0,I)
```

```python
class DiffusionModel(nn.Module):
    def __init__(self, model, T=1000, beta_start=1e-4, beta_end=0.02):
        super().__init__()
        self.model = model  # U-Net that predicts noise
        self.T = T
        betas = torch.linspace(beta_start, beta_end, T)
        alphas = 1 - betas
        alpha_bars = torch.cumprod(alphas, dim=0)
        self.register_buffer('betas', betas)
        self.register_buffer('alpha_bars', alpha_bars)
        self.register_buffer('sqrt_alpha_bars', torch.sqrt(alpha_bars))
        self.register_buffer('sqrt_one_minus_alpha_bars', torch.sqrt(1 - alpha_bars))
    
    def forward_diffusion(self, x0, t):
        """Add noise to x0 at timestep t"""
        noise = torch.randn_like(x0)
        sqrt_ab = self.sqrt_alpha_bars[t].view(-1, 1, 1, 1)
        sqrt_omab = self.sqrt_one_minus_alpha_bars[t].view(-1, 1, 1, 1)
        xt = sqrt_ab * x0 + sqrt_omab * noise
        return xt, noise
    
    def loss(self, x0):
        t = torch.randint(0, self.T, (x0.shape[0],), device=x0.device)
        xt, noise = self.forward_diffusion(x0, t)
        noise_pred = self.model(xt, t)
        return F.mse_loss(noise_pred, noise)
```

### Stable Diffusion (Latent Diffusion Models)

```
Key insight: Run diffusion in LATENT space (much smaller than pixel space)

Image (512×512×3) → VAE Encoder → Latent (64×64×4) → Diffusion → Latent → VAE Decoder → Image

Components:
1. VAE: Compress images to/from latent space
2. U-Net: Predict noise in latent space (conditioned on text)
3. Text Encoder (CLIP): Convert text prompt to embeddings
4. Scheduler: Controls noise schedule during sampling

Conditioning via cross-attention:
U-Net layers attend to text embeddings from CLIP
```

### Classifier-Free Guidance

```
At inference, interpolate between conditional and unconditional predictions:
ε_guided = ε_uncond + w · (ε_cond - ε_uncond)

w > 1: stronger adherence to condition (but less diversity)
Typical: w = 7.5 for Stable Diffusion
```

## 6. Flow-Based Models

### Key Idea: Invertible Transformations

```
z ~ N(0, I) → f⁻¹(z) = x    (generation: transform simple distribution)
x → f(x) = z                  (inference: exact likelihood computation)

Requirement: f must be invertible with tractable Jacobian determinant

log p(x) = log p(z) + log|det(∂f/∂x)|
```

### Examples
- **RealNVP**: Affine coupling layers (split, transform half, swap)
- **Glow**: 1×1 invertible convolutions + affine coupling
- **Neural ODE / Continuous Flows**: Continuous-time transformations

Advantage: Exact likelihood computation (unlike VAE/GAN)
Disadvantage: Architectural constraints (must be invertible), often lower quality

## 7. Applications

| Application | Best Model | Notes |
|-------------|-----------|-------|
| Photorealistic images | Diffusion (DALL-E 3, Midjourney) | Highest quality |
| Real-time image gen | GAN (StyleGAN) | Fast sampling |
| Image editing | Diffusion (inpainting, SDEdit) | Flexible conditioning |
| Text generation | Autoregressive (GPT) | Token by token |
| Video generation | Diffusion (Sora) | Temporal consistency challenge |
| Audio synthesis | Diffusion (AudioLDM) | In latent audio space |
| Data augmentation | VAE, GAN | Synthetic training data |
| Drug discovery | Flow-based, Diffusion | Molecule generation |

## Training Tips

1. **GANs**: Use learning rate 2e-4, Adam β₁=0.5. Train D more than G initially.
2. **Diffusion**: Linear or cosine noise schedule. U-Net with attention at 16×16 resolution.
3. **VAE**: Balance reconstruction and KL terms (β-VAE: use weight on KL).
4. **Monitor**: FID (Frechet Inception Distance) for image quality, IS (Inception Score).

## Production Considerations

1. **Diffusion models are slow** (many denoising steps). Solutions: DDIM (fewer steps), distillation, consistency models.
2. **Safety**: Content filtering, watermarking generated content.
3. **Cost**: Image generation is GPU-intensive. Cache, batch, use optimized schedulers.
4. **IP/Legal**: Training data attribution, opt-out mechanisms.

## Interview Questions

1. **VAE vs GAN?** VAE: stable training, explicit likelihood, blurry outputs. GAN: sharp outputs, unstable training, no likelihood, mode collapse risk.

2. **Why is the reparameterization trick needed?** Can't backprop through random sampling. Reparameterize as deterministic function of params + external noise.

3. **What causes mode collapse?** G finds one output that consistently fools D and keeps producing it. D can't recover because it only sees one mode.

4. **Why diffusion models produce better images than GANs?** Stable training (no adversarial dynamics), better mode coverage, and progressive refinement from noise. Trade-off: much slower sampling.

5. **How does classifier-free guidance work?** Train model both conditionally and unconditionally (randomly drop condition). At inference, amplify the difference between conditional and unconditional predictions.

6. **Why run diffusion in latent space?** Pixel space is high-dimensional (512×512×3 = 786K dims). Latent space (64×64×4 = 16K dims) is ~50× smaller → much faster training/sampling with similar quality.

7. **What's the ELBO?** Evidence Lower BOund. VAE maximizes a lower bound on log p(x) because true posterior p(z|x) is intractable. ELBO = reconstruction - KL divergence.
