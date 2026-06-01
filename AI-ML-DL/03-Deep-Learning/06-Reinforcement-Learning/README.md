# Reinforcement Learning (RL)

## 1. Overview

RL is learning through interaction: an agent takes actions in an environment, receives rewards, and learns a policy to maximize cumulative reward.

```
┌─────────────────────────────────────────────┐
│                                             │
│    ┌───────┐   action aₜ    ┌───────────┐  │
│    │ Agent │ ──────────────→ │Environment│  │
│    │  (π)  │ ←────────────── │           │  │
│    └───────┘  state sₜ₊₁    └───────────┘  │
│               reward rₜ₊₁                   │
│                                             │
└─────────────────────────────────────────────┘
```

### Key Differences from Supervised Learning

| Supervised Learning | Reinforcement Learning |
|--------------------|-----------------------|
| i.i.d. labeled data | Sequential, correlated data |
| Immediate feedback | Delayed rewards |
| Static dataset | Agent influences data distribution |
| Minimize loss | Maximize cumulative reward |

## 2. Markov Decision Process (MDP) Framework

### Formal Definition

MDP = (S, A, P, R, γ)

- **S**: State space (all possible states)
- **A**: Action space (all possible actions)
- **P(s'|s,a)**: Transition probability (dynamics)
- **R(s,a,s')**: Reward function
- **γ ∈ [0,1]**: Discount factor (preference for immediate vs future rewards)

### Key Concepts

```
Policy:         π(a|s) = P(aₜ=a | sₜ=s)    (what action to take)
Return:         Gₜ = rₜ₊₁ + γrₜ₊₂ + γ²rₜ₊₃ + ... = Σₖ₌₀^∞ γᵏrₜ₊ₖ₊₁
Value function: V^π(s) = E_π[Gₜ | sₜ=s]    (expected return from state s)
Q-function:     Q^π(s,a) = E_π[Gₜ | sₜ=s, aₜ=a]  (expected return from s,a)
Advantage:      A^π(s,a) = Q^π(s,a) - V^π(s)       (how much better than average)
```

### Bellman Equations

```
Value:  V^π(s) = Σ_a π(a|s) Σ_{s'} P(s'|s,a) [R(s,a,s') + γV^π(s')]
Q:      Q^π(s,a) = Σ_{s'} P(s'|s,a) [R(s,a,s') + γ Σ_{a'} π(a'|s')Q^π(s',a')]

Optimal (Bellman Optimality):
V*(s) = max_a Σ_{s'} P(s'|s,a) [R(s,a,s') + γV*(s')]
Q*(s,a) = Σ_{s'} P(s'|s,a) [R(s,a,s') + γ max_{a'} Q*(s',a')]
```

## 3. Dynamic Programming (Known Model)

Requires complete knowledge of P and R.

### Policy Iteration

```
1. Policy Evaluation: Given π, compute V^π (solve linear system or iterate)
   V^π(s) ← Σ_a π(a|s) Σ_{s'} P(s'|s,a)[R + γV^π(s')]
   
2. Policy Improvement: Make π greedy w.r.t. V^π
   π'(s) = argmax_a Σ_{s'} P(s'|s,a)[R + γV^π(s')]

Repeat until convergence.
```

### Value Iteration

```
Combine evaluation and improvement:
V(s) ← max_a Σ_{s'} P(s'|s,a)[R + γV(s')]

Iterate until convergence, then extract policy:
π*(s) = argmax_a Q*(s,a)
```

## 4. Monte Carlo Methods (Model-Free)

Learn from complete episodes (no bootstrapping).

```
For each episode:
  Generate episode following π: s₀,a₀,r₁,...,sT
  For each state sₜ in episode:
    Gₜ = rₜ₊₁ + γrₜ₊₂ + ... + γ^(T-t-1)rT
    V(sₜ) ← V(sₜ) + α(Gₜ - V(sₜ))   (incremental mean update)
```

**Pros**: Unbiased, no model needed, works with episodes
**Cons**: High variance, must wait for episode to end

## 5. Temporal Difference (TD) Learning

Bootstrap: update after every step using estimate of future value.

### TD(0)

```
V(sₜ) ← V(sₜ) + α[rₜ₊₁ + γV(sₜ₊₁) - V(sₜ)]
              └── learning rate    └── TD target    └── current estimate
                                   └────────── TD error δₜ ──────────┘
```

**Pros**: Online (no need to wait for episode end), lower variance
**Cons**: Biased (bootstraps from estimate)

### TD(λ) — Unifying MC and TD

```
λ = 0: TD(0), one-step bootstrap
λ = 1: Monte Carlo (full return)
0 < λ < 1: Weighted average of n-step returns
```

## 6. Q-Learning (Off-Policy TD Control)

```
Q(sₜ,aₜ) ← Q(sₜ,aₜ) + α[rₜ₊₁ + γ max_a Q(sₜ₊₁,a) - Q(sₜ,aₜ)]
                                      └── greedy over next state (off-policy!)
```

Off-policy: behavior policy (ε-greedy) ≠ target policy (greedy max)

```python
# Tabular Q-Learning
import numpy as np

Q = np.zeros((n_states, n_actions))
for episode in range(n_episodes):
    state = env.reset()
    done = False
    while not done:
        # ε-greedy action selection
        if np.random.random() < epsilon:
            action = env.action_space.sample()
        else:
            action = np.argmax(Q[state])
        
        next_state, reward, done, _ = env.step(action)
        
        # Q-learning update
        td_target = reward + gamma * np.max(Q[next_state]) * (1 - done)
        Q[state, action] += alpha * (td_target - Q[state, action])
        
        state = next_state
    epsilon *= epsilon_decay
```

### SARSA (On-Policy)

```
Q(sₜ,aₜ) ← Q(sₜ,aₜ) + α[rₜ₊₁ + γQ(sₜ₊₁,aₜ₊₁) - Q(sₜ,aₜ)]
                                      └── actual next action (on-policy)
```

## 7. Deep Q-Network (DQN) — Mnih et al., 2015

Approximate Q with neural network: Q(s,a; θ) ≈ Q*(s,a)

### Key Innovations

1. **Experience Replay**: Store transitions in buffer, sample random mini-batches (breaks correlation)
2. **Target Network**: Separate network for TD targets, updated periodically (stabilizes training)

```
DQN Architecture:
State (pixels/features) → CNN/MLP → Q-values for all actions

Loss = E[(r + γ max_a Q(s', a; θ⁻) - Q(s, a; θ))²]
              └── target network (frozen) ──┘    └── online network (trained)
```

```python
import torch
import torch.nn as nn
from collections import deque
import random

class DQN(nn.Module):
    def __init__(self, state_dim, action_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128), nn.ReLU(),
            nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, action_dim),
        )
    def forward(self, x): return self.net(x)

class ReplayBuffer:
    def __init__(self, capacity=100000):
        self.buffer = deque(maxlen=capacity)
    def push(self, transition): self.buffer.append(transition)
    def sample(self, batch_size): return random.sample(self.buffer, batch_size)

# Training
q_net = DQN(state_dim, action_dim)
target_net = DQN(state_dim, action_dim)
target_net.load_state_dict(q_net.state_dict())
buffer = ReplayBuffer()

for step in range(total_steps):
    action = epsilon_greedy(q_net, state, epsilon)
    next_state, reward, done, _ = env.step(action)
    buffer.push((state, action, reward, next_state, done))
    
    if len(buffer) >= batch_size:
        batch = buffer.sample(batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        # Compute target
        with torch.no_grad():
            max_next_q = target_net(next_states).max(dim=1).values
            targets = rewards + gamma * max_next_q * (1 - dones)
        
        # Compute current Q
        current_q = q_net(states).gather(1, actions.unsqueeze(1))
        
        loss = F.mse_loss(current_q.squeeze(), targets)
        optimizer.zero_grad(); loss.backward(); optimizer.step()
    
    # Update target network periodically
    if step % target_update_freq == 0:
        target_net.load_state_dict(q_net.state_dict())
```

### DQN Improvements

| Method | Idea |
|--------|------|
| Double DQN | Use online net to SELECT action, target net to EVALUATE (reduces overestimation) |
| Dueling DQN | Split Q into V(s) + A(s,a) (advantage stream) |
| Prioritized Replay | Sample important transitions more often (high TD error) |
| Rainbow | Combine all improvements |

## 8. Policy Gradient Methods

Instead of learning Q-values, directly parameterize and optimize the policy π_θ.

### REINFORCE (Williams, 1992)

```
Objective: J(θ) = E_π[Gₜ]

Policy Gradient Theorem:
∇_θ J(θ) = E_π[∇_θ log π_θ(aₜ|sₜ) · Gₜ]

Intuition: Increase probability of actions that led to high returns.
```

```python
# REINFORCE
class PolicyNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128), nn.ReLU(),
            nn.Linear(128, action_dim), nn.Softmax(dim=-1),
        )
    def forward(self, x): return self.net(x)

policy = PolicyNetwork(state_dim, action_dim)
optimizer = torch.optim.Adam(policy.parameters(), lr=1e-3)

for episode in range(n_episodes):
    states, actions, rewards = [], [], []
    state = env.reset()
    done = False
    while not done:
        probs = policy(torch.FloatTensor(state))
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        next_state, reward, done, _ = env.step(action.item())
        states.append(state); actions.append(action); rewards.append(reward)
        state = next_state
    
    # Compute returns
    returns = []
    G = 0
    for r in reversed(rewards):
        G = r + gamma * G
        returns.insert(0, G)
    returns = torch.FloatTensor(returns)
    returns = (returns - returns.mean()) / (returns.std() + 1e-8)  # Baseline
    
    # Policy gradient update
    loss = 0
    for t in range(len(actions)):
        probs = policy(torch.FloatTensor(states[t]))
        dist = torch.distributions.Categorical(probs)
        loss -= dist.log_prob(actions[t]) * returns[t]
    
    optimizer.zero_grad(); loss.backward(); optimizer.step()
```

### PPO (Proximal Policy Optimization) — Schulman et al., 2017

Most widely used policy gradient method. Prevents too-large policy updates.

```
L^CLIP(θ) = E[min(rₜ(θ)Âₜ, clip(rₜ(θ), 1-ε, 1+ε)Âₜ)]

where rₜ(θ) = π_θ(aₜ|sₜ) / π_θ_old(aₜ|sₜ)   (probability ratio)
      Âₜ = advantage estimate (GAE)
      ε = 0.2 (clipping range)
```

```
Clipping visualization:
        L
        │      ╱  (unclipped)
        │    ╱
        │  ╱────── (clipped at 1+ε)
        │╱
   ─────┼────────── r(θ)
       ╱│
  ────╱  │         (clipped at 1-ε)
    ╱    │
  ╱      │
```

### A3C / A2C (Asynchronous Advantage Actor-Critic)

Multiple parallel workers collect experience asynchronously:
```
Worker 1: env₁ → rollout → gradients → update shared params
Worker 2: env₂ → rollout → gradients → update shared params
Worker 3: env₃ → rollout → gradients → update shared params
...
```

## 9. Actor-Critic Methods

Combine policy gradient (actor) with value function (critic):

```
Actor:  π_θ(a|s)     ← policy (what to do)
Critic: V_φ(s)       ← value function (how good is this state)

Update actor using advantage from critic:
∇_θ J = E[∇_θ log π_θ(a|s) · A(s,a)]
where A(s,a) = r + γV_φ(s') - V_φ(s)  (TD error as advantage estimate)

Update critic to minimize TD error:
L_critic = (r + γV_φ(s') - V_φ(s))²
```

### GAE (Generalized Advantage Estimation)

```
δₜ = rₜ + γV(sₜ₊₁) - V(sₜ)   (TD error)

Â_t^GAE(λ) = Σₗ₌₀^∞ (γλ)ˡ δₜ₊ₗ

λ=0: A = δₜ (high bias, low variance)
λ=1: A = Gₜ - V(sₜ) (low bias, high variance)
Typical: λ=0.95
```

## 10. Applications

### Games
- **Atari** (DQN, 2015): Superhuman on 29/49 games from pixels
- **Go** (AlphaGo/Zero, 2016-17): Beat world champion, learned from self-play
- **StarCraft** (AlphaStar, 2019): Grandmaster level
- **DOTA 2** (OpenAI Five, 2019): Beat world champions

### Robotics
- Locomotion (sim-to-real transfer)
- Manipulation (grasping, assembly)
- Challenge: sample efficiency (real-world interaction is expensive)

### Recommendation Systems
- State: user history, Action: item to recommend, Reward: click/purchase
- Handles long-term user satisfaction (not just immediate clicks)

### LLM Alignment (RLHF)

```
Pipeline:
1. Pre-train LLM (next token prediction)
2. Supervised Fine-Tuning (SFT) on human demonstrations
3. Train Reward Model (RM) from human preference comparisons
4. Optimize LLM with PPO against reward model

          ┌──────────────────────────────────────┐
          │         RLHF Pipeline                 │
          │                                      │
          │  Prompt → LLM → Response             │
          │                    │                  │
          │              Reward Model             │
          │                    │                  │
          │               Reward r               │
          │                    │                  │
          │         PPO updates LLM              │
          │         (with KL penalty             │
          │          from SFT model)             │
          └──────────────────────────────────────┘

PPO objective for RLHF:
J = E[R(response) - β·KL(π_RL || π_SFT)]
    └── reward model score    └── stay close to SFT model
```

### DPO (Direct Preference Optimization) — Alternative to RLHF

Skip the reward model, directly optimize from preferences:
```
L_DPO = -E[log σ(β(log π_θ(y_w|x)/π_ref(y_w|x) - log π_θ(y_l|x)/π_ref(y_l|x)))]

where y_w = preferred response, y_l = dispreferred response
```

## Training Tips

1. **Reward shaping**: Dense rewards >> sparse rewards. Add intermediate signals.
2. **Normalization**: Normalize observations and rewards.
3. **Frame stacking**: Stack last 4 frames for Atari (capture motion).
4. **Curriculum learning**: Start with easy tasks, progressively harder.
5. **Hyperparameters**: PPO clip=0.2, γ=0.99, λ=0.95, epochs=4-10 per batch.

## Production Considerations

1. **Sim-to-real gap**: Train in simulation, fine-tune in real world. Domain randomization helps.
2. **Safety constraints**: Constrained MDP, safe RL (avoid dangerous states during exploration).
3. **Sample efficiency**: Model-based RL (learn world model) for expensive environments.
4. **Evaluation**: RL policies are stochastic — evaluate over many episodes, report mean±std.
5. **Deployment**: Convert learned policy to inference-only mode (no exploration noise).

## Interview Questions

1. **On-policy vs off-policy?** On-policy (SARSA, PPO): learn from current policy's experience. Off-policy (Q-learning, DQN): learn from any experience (replay buffer). Off-policy is more sample efficient but less stable.

2. **Why experience replay in DQN?** Breaks temporal correlation between consecutive samples, enables data reuse, stabilizes training.

3. **Why target network?** Without it, the target changes with every update (moving target problem), causing oscillation/divergence.

4. **Value-based vs policy-based?** Value-based (DQN): learn Q, derive policy (argmax). Works for discrete actions only. Policy-based (PPO): directly optimize policy. Works for continuous actions, can learn stochastic policies.

5. **What is the exploration-exploitation tradeoff?** Exploit: take best known action. Explore: try new actions to discover better ones. ε-greedy, UCB, entropy bonus are solutions.

6. **Why is RLHF needed for LLMs?** Next-token prediction (pre-training) doesn't optimize for helpfulness/safety. RLHF aligns model behavior with human preferences using reward signal from human evaluators.

7. **PPO vs TRPO?** Both prevent large policy updates. TRPO: hard KL constraint (expensive, requires conjugate gradient). PPO: clipped objective (simple, similar performance, much easier to implement).

8. **Model-based vs model-free?** Model-free: learn policy/value directly from interactions (DQN, PPO). Model-based: learn environment dynamics, plan with it (MuZero, Dreamer). Model-based is more sample efficient but model errors compound.

9. **What's the deadly triad?** Combination of: (1) function approximation, (2) bootstrapping, (3) off-policy training → can cause instability/divergence. DQN addresses this with replay + target networks.
