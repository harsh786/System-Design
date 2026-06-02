# Game Theory for ML

## 1. Why Game Theory for ML

Game theory provides the mathematical framework for understanding multi-agent interactions in ML:

| ML Application | Game Theory Connection |
|---|---|
| GANs | Two-player zero-sum game (Generator vs Discriminator) |
| Multi-Agent RL | N-player general-sum games |
| Adversarial attacks | Attacker vs Defender (Stackelberg game) |
| Ad auctions | Mechanism design, auction theory |
| Federated learning | Incentive-compatible mechanisms |
| Self-play (AlphaGo) | Two-player zero-sum, Nash equilibrium via self-play |

---

## 2. Basic Game Theory Concepts

### Players, Strategies, Payoffs

A game consists of:
- **Players**: decision-makers (e.g., Generator and Discriminator)
- **Strategies**: available actions for each player
- **Payoffs**: rewards/losses for each strategy combination

### Normal Form (Matrix) Game

```
                    Player 2
                  Left    Right
Player 1  Up   [ (3,1)   (0,0) ]
          Down [ (1,1)   (2,3) ]
          
Payoffs: (Player 1's payoff, Player 2's payoff)
```

### Pure vs Mixed Strategies

- **Pure strategy**: deterministic choice (always play "Up")
- **Mixed strategy**: probability distribution over actions (play "Up" with p=0.6)

### Dominant Strategies and Best Response

```python
import numpy as np
from scipy.optimize import linprog

def find_dominant_strategy(payoff_matrix):
    """Check if any row dominates all others for Player 1."""
    n_strategies = payoff_matrix.shape[0]
    for i in range(n_strategies):
        dominates_all = True
        for j in range(n_strategies):
            if i != j:
                if not np.all(payoff_matrix[i] >= payoff_matrix[j]):
                    dominates_all = False
                    break
        if dominates_all:
            return i
    return None  # No dominant strategy

# Prisoner's Dilemma
# Payoffs for Player 1 (row player)
pd_payoff = np.array([
    [-1, -3],  # Cooperate: (-1 if both cooperate, -3 if I cooperate they defect)
    [0, -2]    # Defect:    (0 if I defect they cooperate, -2 if both defect)
])
dom = find_dominant_strategy(pd_payoff)
print(f"Dominant strategy for Player 1: {'Defect' if dom == 1 else 'Cooperate'}")
# Output: Defect (always better regardless of opponent)
```

---

## 3. Nash Equilibrium

### Definition

A strategy profile where **no player can improve their payoff by unilaterally changing their strategy**.

Formally: For all players i and all alternative strategies s'ᵢ:
```
uᵢ(sᵢ*, s₋ᵢ*) ≥ uᵢ(s'ᵢ, s₋ᵢ*)
```

### Computing Nash Equilibria for 2×2 Games

```python
def find_mixed_nash_2x2(A, B):
    """Find mixed strategy Nash equilibrium for 2x2 game.
    
    A = Player 1's payoff matrix (2x2)
    B = Player 2's payoff matrix (2x2)
    
    Player 1 mixes to make Player 2 indifferent.
    Player 2 mixes to make Player 1 indifferent.
    """
    # Player 2 plays Left with probability q to make Player 1 indifferent:
    # A[0,0]*q + A[0,1]*(1-q) = A[1,0]*q + A[1,1]*(1-q)
    # q*(A[0,0] - A[0,1] - A[1,0] + A[1,1]) = A[1,1] - A[0,1]
    denom_q = A[0,0] - A[0,1] - A[1,0] + A[1,1]
    if abs(denom_q) < 1e-10:
        q = None
    else:
        q = (A[1,1] - A[0,1]) / denom_q
    
    # Player 1 plays Up with probability p to make Player 2 indifferent:
    denom_p = B[0,0] - B[0,1] - B[1,0] + B[1,1]
    if abs(denom_p) < 1e-10:
        p = None
    else:
        p = (B[1,1] - B[0,1]) / denom_p
    
    return p, q

# Example: Battle of the Sexes
#              Opera    Football
# Opera     [ (3,2)    (0,0) ]
# Football  [ (0,0)    (2,3) ]
A = np.array([[3, 0], [0, 2]])  # Player 1 payoffs
B = np.array([[2, 0], [0, 3]])  # Player 2 payoffs

p, q = find_mixed_nash_2x2(A, B)
print(f"Mixed NE: Player 1 plays Opera with p={p:.3f}, Player 2 plays Opera with q={q:.3f}")
# p = 3/5 = 0.6, q = 2/5 = 0.4

# Pure NE: (Opera, Opera) and (Football, Football) are both NE
print("\nPure strategy Nash Equilibria:")
for i in range(2):
    for j in range(2):
        # Check if (i,j) is NE
        row_best = A[i,j] >= A[:,j].max()
        col_best = B[i,j] >= B[i,:].max()
        if row_best and col_best:
            actions = ['Opera', 'Football']
            print(f"  ({actions[i]}, {actions[j]}) with payoffs ({A[i,j]}, {B[i,j]})")
```

### Nash's Theorem

Every finite game has at least one Nash equilibrium (possibly in mixed strategies).

---

## 4. Minimax Theorem and Zero-Sum Games

### Zero-Sum Games

One player's gain equals the other's loss: A + B = 0 (so B = -A).

### Minimax Strategy

```
Player 1 (maximizer): max_i min_j A[i,j]   (maximize worst case)
Player 2 (minimizer): min_j max_i A[i,j]   (minimize opponent's best)
```

**Von Neumann's Minimax Theorem:** In zero-sum games, maximin = minimax (at equilibrium).

### Direct Connection to GANs

```
GAN objective:  min_G max_D V(D, G)

V(D, G) = E_{x~data}[log D(x)] + E_{z~noise}[log(1 - D(G(z)))]

This IS a two-player zero-sum game:
- Discriminator (maximizer): maximize V → correctly classify real/fake
- Generator (minimizer): minimize V → fool discriminator
```

```python
def gan_minimax_value(D_real_accuracy, D_fake_accuracy):
    """Compute GAN's minimax value function.
    
    V(D,G) = E[log D(x)] + E[log(1 - D(G(z)))]
    
    At optimal D*: D*(x) = p_data(x) / (p_data(x) + p_g(x))
    At Nash equilibrium: D*(x) = 0.5 everywhere, V* = -2*log(2)
    """
    V = np.log(D_real_accuracy + 1e-8) + np.log(1 - (1 - D_fake_accuracy) + 1e-8)
    return V

# Training trajectory analysis
print("GAN Training Stages:")
print(f"  Early (D strong):  V = {gan_minimax_value(0.95, 0.95):.3f}")
print(f"  Mid training:      V = {gan_minimax_value(0.7, 0.7):.3f}")
print(f"  Near equilibrium:  V = {gan_minimax_value(0.55, 0.55):.3f}")
print(f"  At equilibrium:    V = {gan_minimax_value(0.5, 0.5):.3f}")
print(f"  Theoretical opt:   V = {-2*np.log(2):.3f}")

def minimax_solver_2x2(A):
    """Solve 2x2 zero-sum game for both players' mixed strategies."""
    # Player 1 (row) maximizes, Player 2 (col) minimizes
    # Player 1's mixed strategy: play row 0 with prob p
    denom = A[0,0] - A[0,1] - A[1,0] + A[1,1]
    if abs(denom) < 1e-10:
        return 0.5, 0.5, A[0,0]
    
    p = (A[1,1] - A[0,1]) / denom
    q = (A[1,1] - A[1,0]) / denom
    value = (A[0,0]*A[1,1] - A[0,1]*A[1,0]) / denom
    
    return np.clip(p, 0, 1), np.clip(q, 0, 1), value

# Rock-Paper-Scissors (extended to show concept)
# Matching Pennies (simpler zero-sum game)
A = np.array([[1, -1], [-1, 1]])  # Matching pennies
p, q, v = minimax_solver_2x2(A)
print(f"\nMatching Pennies NE: p={p:.2f}, q={q:.2f}, game value={v:.2f}")
```

---

## 5. GAN Training as a Game

### The Two Players

| | Generator G | Discriminator D |
|---|---|---|
| **Strategy space** | Parameters θ_G (neural net weights) | Parameters θ_D (neural net weights) |
| **Action** | Generate image G(z) | Output probability D(x) ∈ [0,1] |
| **Goal** | Minimize: E[log(1-D(G(z)))] | Maximize: E[log D(x)] + E[log(1-D(G(z)))] |

### Optimal Discriminator and Nash Equilibrium

```python
def optimal_discriminator(p_data, p_gen):
    """Optimal D for fixed G: D*(x) = p_data(x) / (p_data(x) + p_g(x))"""
    return p_data / (p_data + p_gen + 1e-8)

def gan_training_dynamics(n_steps=100, lr=0.1):
    """Simulate simplified GAN training dynamics.
    
    Simplified 1D case: G outputs mean μ, D is a threshold.
    True data ~ N(0,1), G outputs ~ N(μ, 1).
    """
    mu_g = 5.0      # Generator's mean (starts far from 0)
    d_threshold = 0  # Discriminator's decision boundary
    
    history = {'mu_g': [], 'd_thresh': [], 'g_loss': [], 'd_loss': []}
    
    for step in range(n_steps):
        # D's gradient: push threshold between real (0) and fake (mu_g)
        d_gradient = mu_g / 2 - d_threshold  # Move toward midpoint
        d_threshold += lr * d_gradient
        
        # G's gradient: push mu toward where D thinks is real
        g_gradient = d_threshold - mu_g  # Move toward threshold
        mu_g += lr * g_gradient
        
        history['mu_g'].append(mu_g)
        history['d_thresh'].append(d_threshold)
    
    return history

history = gan_training_dynamics(n_steps=50)
print("GAN Training Convergence (simplified):")
print(f"  Initial G mean: 5.0 (target: 0.0)")
print(f"  Final G mean:   {history['mu_g'][-1]:.4f}")
print(f"  Final D thresh: {history['d_thresh'][-1]:.4f}")
# Both converge toward 0 (equilibrium)
```

### Why GAN Training is Unstable

1. **Non-convex optimization**: Loss landscape has saddle points
2. **Simultaneous gradient descent ≠ finding Nash equilibrium**: GD can cycle
3. **Mode collapse**: G finds one mode that fools D, ignores diversity

```
Convergence Diagram:

Stable (convex-concave):     Unstable (GAN reality):
                              
    D →  ←  G                   D →  G ↑
         ↓                         ↗
    Converge to NE               D ← G ↓    (cycling!)
                                   ↙
                              Oscillates, may not converge
```

### Training Stabilization (Game Theory Perspective)

```python
# WGAN-GP: Change the game to have better convergence properties
def wgan_gp_loss(D_real, D_fake, D_interpolated, gradients, lambda_gp=10):
    """WGAN with Gradient Penalty.
    
    Instead of log-based minimax, use Wasserstein distance:
    max_D E[D(x)] - E[D(G(z))]  subject to ||∇D|| ≤ 1
    
    The Lipschitz constraint ensures the game is well-behaved.
    """
    wasserstein_loss = D_real.mean() - D_fake.mean()
    
    # Gradient penalty enforces 1-Lipschitz (constrains strategy space)
    gradient_penalty = lambda_gp * ((gradients.norm(2, dim=1) - 1) ** 2).mean()
    
    d_loss = -wasserstein_loss + gradient_penalty
    g_loss = -D_fake.mean()
    
    return d_loss, g_loss
```

---

## 6. Multi-Agent Systems and MARL

### Cooperative vs Competitive

```
Cooperative: All agents share reward (team games)
Competitive: Zero-sum between agents (adversarial)
Mixed:       Some shared, some conflicting interests (most real scenarios)
```

### Self-Play

The agent plays against copies of itself, creating a curriculum of increasing difficulty.

```python
def self_play_training(agent, n_episodes=1000):
    """Conceptual self-play training loop (AlphaGo-style).
    
    Key insight: By playing against yourself, you're computing
    approximate Nash equilibria through iterated best response.
    """
    for episode in range(n_episodes):
        # Current agent plays against a past version
        opponent = agent.copy()  # or sample from history
        
        # Play game
        state = initialize_game()
        while not game_over(state):
            if current_player(state) == 1:
                action = agent.select_action(state)
            else:
                action = opponent.select_action(state)
            state = step(state, action)
        
        # Update agent based on outcome
        reward = get_reward(state, player=1)
        agent.update(reward)
        
        # Periodically add current agent to opponent pool
        if episode % 100 == 0:
            agent.opponent_pool.append(agent.copy())
    
    return agent

# Self-play converges to Nash equilibrium in two-player zero-sum games
# (by fictitious play / double oracle arguments)
```

### Emergent Behavior

In MARL, complex behaviors emerge from simple rules:
- Communication protocols (agents learn to signal)
- Specialization (agents take different roles)
- Deception (agents learn to mislead opponents)

---

## 7. Mechanism Design for ML

### Reverse Game Theory

Instead of analyzing existing games, **design the rules** to achieve desired outcomes.

### Auction Theory (Ad ML)

```python
def vickrey_auction(bids):
    """Second-price sealed-bid auction (Vickrey).
    
    Properties:
    - Truthful: bidding true value is dominant strategy
    - Efficient: highest-value bidder wins
    - Used in: Google Ad auctions (generalized second price)
    """
    sorted_indices = np.argsort(bids)[::-1]
    winner = sorted_indices[0]
    # Winner pays second-highest bid (not their own)
    payment = bids[sorted_indices[1]]
    return winner, payment

# Why truthful? If you bid below value, you might lose an auction you'd profit from.
# If you bid above value, you might win but pay more than it's worth.
bids = np.array([5.0, 3.0, 7.0, 2.0])  # True values
winner, price = vickrey_auction(bids)
print(f"Winner: bidder {winner} (value={bids[winner]}), pays: {price}")
# Winner: bidder 2 (value=7.0), pays: 5.0 (profit = 2.0)
```

### Application: Incentive-Compatible Federated Learning

```
Problem: In federated learning, clients may submit low-quality updates
         to save computation while still benefiting from the model.

Solution: Design payment/reward mechanisms where:
- Truthful reporting (honest computation) is the dominant strategy
- Free-riding is not profitable
- Uses Shapley values to measure each client's contribution
```

---

## 8. Adversarial ML as a Game

### Game Formulation

```
Players:  Attacker (A) vs Defender/Model (D)
Attacker: Find perturbation δ to fool model    max L(f(x+δ), y)  s.t. ||δ|| ≤ ε
Defender: Train model robust to perturbations   min_θ max_{||δ||≤ε} L(f_θ(x+δ), y)
```

This is a **Stackelberg game** (defender commits first, attacker observes and responds).

```python
def pgd_attack(model_fn, x, y_true, epsilon=0.1, steps=10, step_size=0.01):
    """Projected Gradient Descent attack (attacker's strategy).
    
    Iteratively maximizes loss subject to L∞ perturbation budget.
    This is the attacker's best response given the defender's model.
    """
    x_adv = x.copy()
    
    for _ in range(steps):
        # Gradient of loss w.r.t. input (attacker wants to MAXIMIZE loss)
        grad = compute_gradient(model_fn, x_adv, y_true)
        
        # Step in direction of increasing loss
        x_adv = x_adv + step_size * np.sign(grad)
        
        # Project back to ε-ball around original
        x_adv = np.clip(x_adv, x - epsilon, x + epsilon)
        x_adv = np.clip(x_adv, 0, 1)  # Valid pixel range
    
    return x_adv

def adversarial_training(model, train_data, epsilon=0.1):
    """Adversarial training (defender's strategy).
    
    min_θ E[ max_{||δ||≤ε} L(f_θ(x+δ), y) ]
    
    This is the defender's minimax strategy: train on worst-case inputs.
    """
    for x_batch, y_batch in train_data:
        # Inner maximization: find strongest attack
        x_adv = pgd_attack(model, x_batch, y_batch, epsilon)
        
        # Outer minimization: train on adversarial examples
        loss = compute_loss(model, x_adv, y_batch)
        update_model(model, loss)

# The defender-attacker game often doesn't converge to NE
# because:
# 1. Strategy spaces are continuous and high-dimensional
# 2. New attacks keep being discovered (arms race)
# 3. Robust optimization is computationally harder than standard training
```

### Types of Adversarial Games

| Attack Type | Game Structure | Defender's Response |
|---|---|---|
| Evasion (test-time) | Stackelberg (D moves first) | Adversarial training |
| Poisoning (train-time) | Simultaneous | Data sanitization |
| Model extraction | Repeated game | Query limiting, watermarking |
| Backdoor | Principal-agent | Certified defenses |

---

## Exercises

### Exercise 1: Find Nash Equilibrium
Find all Nash equilibria (pure and mixed) of:
```
        L    R
U    (2,1) (0,0)
D    (0,0) (1,2)
```

**Solution:**
```python
A = np.array([[2, 0], [0, 1]])
B = np.array([[1, 0], [0, 2]])
# Pure NE: (U,L) and (D,R) — check best responses
# Mixed NE:
p, q = find_mixed_nash_2x2(A, B)
print(f"Pure NE: (U,L) with payoff (2,1), (D,R) with payoff (1,2)")
print(f"Mixed NE: P1 plays U with p={p:.3f}, P2 plays L with q={q:.3f}")
# p = 2/3, q = 1/3
```

### Exercise 2: Prisoner's Dilemma
Show that mutual defection is the unique Nash equilibrium.

**Solution:**
```python
A = np.array([[-1, -3], [0, -2]])  # P1: (C,C)=-1, (C,D)=-3, (D,C)=0, (D,D)=-2
# For P1: D dominates C (0>-1, -2>-3)
# For P2 (symmetric): D dominates C
# Unique NE: (D,D) with payoff (-2,-2)
# Both would prefer (C,C)=(-1,-1) but can't sustain it — the GAN analogy:
# Both G and D might prefer cooperation but gradient dynamics push to competition
print("Defect dominates Cooperate for both players")
print("NE: (Defect, Defect) = (-2, -2), Pareto-dominated by (Cooperate, Cooperate) = (-1, -1)")
```

### Exercise 3: GAN Optimal Discriminator
Derive and verify D*(x) = p_data(x)/(p_data(x) + p_g(x)).

**Solution:**
```python
# For fixed G, D maximizes: E_data[log D(x)] + E_G[log(1-D(x))]
# Pointwise: maximize p_data(x)*log(D) + p_g(x)*log(1-D)
# Take derivative, set to 0:
# p_data/D - p_g/(1-D) = 0 → D* = p_data/(p_data + p_g)

x = np.linspace(-3, 3, 100)
p_data = np.exp(-x**2/2) / np.sqrt(2*np.pi)
p_gen = np.exp(-(x-1)**2/2) / np.sqrt(2*np.pi)  # G hasn't converged yet
D_star = p_data / (p_data + p_gen)

print(f"Where p_data = p_gen: D* = {0.5}")
print(f"Where p_data >> p_gen: D* → 1 (definitely real)")
print(f"Where p_data << p_gen: D* → 0 (definitely fake)")
# At equilibrium (p_data = p_gen everywhere): D* = 0.5 everywhere
```

### Exercise 4: Minimax Value of a Zero-Sum Game
Compute the minimax value and optimal mixed strategies.

**Solution:**
```python
A = np.array([[3, -1], [-2, 4]])  # Row player maximizes
p, q, v = minimax_solver_2x2(A)
print(f"Row player: play row 0 with p={p:.3f}")
print(f"Col player: play col 0 with q={q:.3f}")
print(f"Game value: {v:.3f}")
# Verify: expected payoff = p*q*3 + p*(1-q)*(-1) + (1-p)*q*(-2) + (1-p)*(1-q)*4
expected = p*q*A[0,0] + p*(1-q)*A[0,1] + (1-p)*q*A[1,0] + (1-p)*(1-q)*A[1,1]
print(f"Verification: E[payoff] = {expected:.3f} (should equal game value)")
```

### Exercise 5: Mode Collapse as Game Failure
Explain mode collapse using game theory concepts.

**Solution:**
```python
# Mode collapse: G learns to output only one mode of multi-modal distribution
# Game theory interpretation:
# - G's best response to current D might be to concentrate mass where D is weakest
# - But then D adapts, G shifts to new mode — cycling, not convergence
# - This is "best response cycling" in game theory

def simulate_mode_collapse(n_modes=3, n_steps=50):
    """Simulate mode collapse as best-response dynamics."""
    modes = np.array([0, 3, 6])  # True data has 3 modes
    g_position = 0.0  # G starts at mode 0
    
    for step in range(n_steps):
        # D learns: focus on where G is generating
        d_focus = g_position
        
        # G's "best response": jump to mode furthest from D's focus
        distances = np.abs(modes - d_focus)
        g_position = modes[np.argmax(distances)]  # Jump to least-defended mode
    
    print(f"G cycles between modes instead of covering all — mode collapse!")

simulate_mode_collapse()
```

### Exercise 6: Stackelberg Game for Adversarial ML
Model adversarial attack as a Stackelberg game and find equilibrium.

**Solution:**
```python
# Stackelberg: Defender (leader) chooses model θ, Attacker (follower) best-responds
# Simplified: defender chooses threshold t, attacker chooses perturbation δ

def stackelberg_adversarial(epsilon_budget=0.3):
    """Simplified Stackelberg adversarial game."""
    # Defender: choose robustness level r (0=no defense, 1=max defense)
    # Cost of defense: accuracy drops by r*0.1
    # Attacker: succeeds if perturbation budget ε > r
    
    best_r = 0
    best_defender_utility = -np.inf
    
    for r in np.linspace(0, 1, 100):
        # Attacker's best response: attack if ε > r, else don't
        attack_success = 1.0 if epsilon_budget > r else 0.0
        
        # Defender's utility: accuracy - attack_damage
        accuracy = 1.0 - 0.1 * r  # Defense costs accuracy
        damage = attack_success * 0.5  # Successful attack costs 0.5
        utility = accuracy - damage
        
        if utility > best_defender_utility:
            best_defender_utility = utility
            best_r = r
    
    print(f"Optimal defense level: r={best_r:.2f}")
    print(f"Attack blocked: {epsilon_budget <= best_r}")
    print(f"Defender utility: {best_defender_utility:.3f}")

stackelberg_adversarial(epsilon_budget=0.3)
```

### Exercise 7: Vickrey Auction Truthfulness
Prove that bidding truthfully is a dominant strategy in second-price auctions.

**Solution:**
```python
def analyze_truthfulness(true_value=7.0):
    """Show that any bid ≠ true_value can't improve outcome."""
    other_bids = [3, 5, 8]  # Other bidders' bids
    
    for my_bid in [4, 5, 6, 7, 8, 9, 10]:
        all_bids = other_bids + [my_bid]
        winner = np.argmax(all_bids)
        i_win = (winner == len(other_bids))
        
        if i_win:
            payment = sorted(all_bids)[-2]  # Second highest
            profit = true_value - payment
        else:
            profit = 0
        
        truthful = "← TRUTHFUL" if my_bid == true_value else ""
        print(f"  Bid={my_bid}: {'Win' if i_win else 'Lose'}, "
              f"profit={profit:.1f} {truthful}")
    
    # Bidding above value: might win but pay more than value (negative profit)
    # Bidding below value: might lose auction you'd profit from
    # Bidding true value: optimal in all cases

analyze_truthfulness(7.0)
```

### Exercise 8: Multi-Agent Reward Shaping
Design rewards for cooperative multi-agent system that avoids free-riding.

**Solution:**
```python
def shapley_value(contributions, n_agents=3):
    """Compute Shapley values for fair credit assignment.
    
    Shapley value: average marginal contribution across all orderings.
    Used in federated learning to reward honest participants.
    """
    from itertools import permutations
    
    shapley = np.zeros(n_agents)
    
    for perm in permutations(range(n_agents)):
        coalition_value = 0
        for i, agent in enumerate(perm):
            # Marginal contribution of agent joining coalition
            new_value = contributions[frozenset(perm[:i+1])]
            marginal = new_value - coalition_value
            shapley[agent] += marginal
            coalition_value = new_value
    
    shapley /= np.math.factorial(n_agents)
    return shapley

# Example: 3 agents contributing to model quality
contributions = {
    frozenset(): 0,
    frozenset([0]): 0.5,  frozenset([1]): 0.3,  frozenset([2]): 0.1,
    frozenset([0,1]): 0.7, frozenset([0,2]): 0.6, frozenset([1,2]): 0.4,
    frozenset([0,1,2]): 0.9
}

sv = shapley_value(contributions)
print(f"Shapley values: Agent0={sv[0]:.3f}, Agent1={sv[1]:.3f}, Agent2={sv[2]:.3f}")
print(f"Sum = {sv.sum():.3f} (equals total value {contributions[frozenset([0,1,2])]})")
# Fair: agents are rewarded proportional to their true contribution
```

---

## Interview Questions

**Q1: How is GAN training related to game theory? Why is it unstable?**
A: GAN training is a two-player zero-sum game where G minimizes and D maximizes the same objective. The Nash equilibrium is D*(x)=0.5 everywhere (can't distinguish real from fake). Instability arises because: (1) simultaneous gradient descent doesn't converge to NE in general games, (2) the loss landscape is non-convex, (3) best-response dynamics can cycle (mode collapse). Solutions like WGAN-GP constrain the game to have better convergence properties.

**Q2: What is Nash equilibrium and why does it matter for multi-agent RL?**
A: NE is a state where no agent can improve by unilaterally changing strategy. In MARL, we want agents to converge to stable policies (NE). Without NE, agents perpetually adapt to each other (non-stationary environment). Self-play in zero-sum games converges to NE. In general-sum games, finding NE is computationally hard (PPAD-complete), so we use approximate methods.

**Q3: Explain adversarial robustness as a minimax problem.**
A: Adversarial training solves: min_θ E[max_{||δ||≤ε} L(f_θ(x+δ), y)]. The inner max finds the worst-case perturbation (attacker's best response). The outer min trains the model to be robust against it (defender's strategy). This is a Stackelberg game where the defender commits to parameters first, then the attacker responds optimally.

**Q4: Why are second-price auctions used in ad ranking?**
A: Vickrey (second-price) auctions are truthful — bidding your true value is the dominant strategy regardless of others' bids. This simplifies the game for advertisers (no need to guess competitors' bids), leads to efficient allocation (highest-value bidder wins), and provides stable revenue. Google's GSP (Generalized Second Price) extends this to multiple ad slots.

**Q5: How does self-play lead to superhuman performance?**
A: Self-play creates an automatic curriculum: as the agent improves, its opponent (past self) also improves, providing increasingly difficult challenges. In two-player zero-sum games, self-play with sufficient exploration converges to minimax-optimal play (Nash equilibrium). AlphaGo/AlphaZero achieved superhuman play because: (1) NE in Go/Chess IS optimal play, (2) neural networks approximate the value function, (3) MCTS provides look-ahead for better action selection. The agent never needs human games — it discovers optimal strategies from scratch.
