# Finance ML

## Overview

Financial ML is uniquely challenging due to low signal-to-noise ratios, adversarial environments, non-stationary data, and strict regulatory requirements. Models must operate under extreme uncertainty while maintaining explainability.

---

## 1. Algorithmic Trading

### Signal Generation & Alpha Factors

Alpha factors are features that predict future returns:

```python
# Example alpha factors
class AlphaFactors:
    def momentum(self, prices, window=20):
        """Price momentum factor"""
        return prices.pct_change(window)
    
    def mean_reversion(self, prices, window=20):
        """Mean reversion z-score"""
        rolling_mean = prices.rolling(window).mean()
        rolling_std = prices.rolling(window).std()
        return (prices - rolling_mean) / rolling_std
    
    def volume_surprise(self, volume, window=20):
        """Unusual volume activity"""
        return volume / volume.rolling(window).mean() - 1
    
    def order_flow_imbalance(self, bids, asks):
        """Microstructure signal"""
        return (bids - asks) / (bids + asks)
```

### Execution Algorithms

- **TWAP**: Time-weighted average price
- **VWAP**: Volume-weighted average price
- **Implementation Shortfall**: Minimize slippage vs decision price
- **Optimal Execution** (Almgren-Chriss): Balance market impact vs timing risk

### HFT & Market Microstructure

- Latency arbitrage (sub-microsecond decisions)
- Market making (spread capture, inventory management)
- Order book modeling (queue position, cancellation prediction)
- Feature engineering from Level 2 data (bid-ask imbalance, trade flow toxicity)

---

## 2. Credit Scoring & Risk Modeling

### Key Risk Parameters

| Parameter | Description | Models Used |
|-----------|-------------|-------------|
| PD | Probability of Default | Logistic regression, XGBoost, neural nets |
| LGD | Loss Given Default | Beta regression, two-stage models |
| EAD | Exposure at Default | Regression on credit conversion factors |

### Credit Scoring Pipeline

```python
class CreditScoringPipeline:
    def __init__(self):
        self.features = [
            # Bureau features
            'num_tradelines', 'utilization_ratio', 'delinquency_history',
            'avg_account_age', 'num_inquiries_6m',
            # Application features  
            'income', 'employment_length', 'debt_to_income',
            # Behavioral features
            'payment_patterns', 'balance_trends'
        ]
    
    def build_scorecard(self, X, y):
        """Traditional scorecard with WoE binning"""
        # 1. Weight of Evidence transformation
        woe_transformer = WoEEncoder()
        X_woe = woe_transformer.fit_transform(X, y)
        
        # 2. Logistic regression (interpretable)
        model = LogisticRegression(penalty='l1')
        model.fit(X_woe, y)
        
        # 3. Convert to points-based scorecard
        scorecard = self.coefficients_to_points(model, woe_transformer)
        return scorecard
    
    def validate_model(self, model, X_test, y_test):
        """Regulatory-compliant validation"""
        metrics = {
            'gini': 2 * roc_auc_score(y_test, model.predict_proba(X_test)[:,1]) - 1,
            'ks_statistic': self.kolmogorov_smirnov(y_test, model.predict_proba(X_test)[:,1]),
            'psi': self.population_stability_index(train_scores, test_scores),
        }
        return metrics
```

---

## 3. Fraud Detection

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRAUD DETECTION SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐        │
│  │Transaction│───▶│ Rules Engine │───▶│ ML Scoring      │        │
│  │ Stream    │    │ (fast reject)│    │ (real-time)     │        │
│  └──────────┘    └──────────────┘    └────────┬────────┘        │
│                                                │                  │
│                         ┌──────────────────────┼──────────┐      │
│                         │                      │          │      │
│                         ▼                      ▼          ▼      │
│                  ┌─────────────┐    ┌──────────────┐ ┌────────┐ │
│                  │Graph Analysis│    │Anomaly Detect│ │Ensemble│ │
│                  │(network)     │    │(behavioral)  │ │Decision│ │
│                  └─────────────┘    └──────────────┘ └────┬───┘ │
│                                                           │      │
│                         ┌─────────────────────────────────┘      │
│                         ▼                                        │
│                  ┌─────────────┐    ┌──────────────┐            │
│                  │Case Manager │───▶│ Feedback Loop │            │
│                  │(human review)│    │ (retraining) │            │
│                  └─────────────┘    └──────────────┘            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Approaches

1. **Rule-based** (fast, interpretable, brittle)
2. **Supervised ML** (XGBoost, neural nets on labeled fraud/non-fraud)
3. **Anomaly detection** (isolation forest, autoencoders for unseen fraud types)
4. **Graph-based** (detect fraud rings via community detection, GNNs)
5. **Sequence models** (LSTM/Transformer on transaction sequences)

### Real-time Requirements

- Latency: <100ms for card-present, <500ms for card-not-present
- Throughput: 10K-100K+ TPS for large issuers
- Feature store: pre-computed aggregates (30-day velocity, merchant risk scores)

### Key Challenges

- Extreme class imbalance (fraud rate: 0.01-0.1%)
- Adversarial drift (fraudsters adapt to models)
- Label delay (chargebacks arrive 30-90 days later)
- Cost-sensitive: false negatives >> false positives in cost

---

## 4. Anti-Money Laundering (AML)

### Transaction Monitoring

```python
class AMLMonitoring:
    def suspicious_pattern_detection(self, transactions):
        """Detect structuring (smurfing) patterns"""
        # Transactions just below reporting threshold ($10K in US)
        structured = transactions[
            (transactions['amount'] > 8000) & 
            (transactions['amount'] < 10000)
        ]
        
        # Rapid movement patterns
        velocity = self.compute_velocity_features(transactions)
        
        # Network-based features
        graph_features = self.extract_graph_features(transactions)
        
        return self.score_suspicion(structured, velocity, graph_features)
    
    def extract_graph_features(self, transactions):
        """Build transaction graph and extract features"""
        G = nx.DiGraph()
        for _, tx in transactions.iterrows():
            G.add_edge(tx['sender'], tx['receiver'], 
                      amount=tx['amount'], time=tx['timestamp'])
        
        features = {
            'pagerank': nx.pagerank(G),
            'communities': nx.community.louvain_communities(G),
            'flow_centrality': nx.current_flow_betweenness_centrality(G),
        }
        return features
```

### Network Analysis for AML

- Shell company detection via ownership graphs
- Layering detection (rapid transfers across jurisdictions)
- Beneficial ownership identification
- Cross-border flow analysis

---

## 5. Portfolio Optimization

### Classical Approaches

| Method | Description | Limitation |
|--------|-------------|------------|
| Markowitz (MVO) | Minimize variance for target return | Estimation error amplification |
| Black-Litterman | Bayesian update on market equilibrium | Still requires views |
| Risk Parity | Equal risk contribution per asset | Ignores expected returns |
| HRP | Hierarchical clustering + bisection | May underperform in stable markets |

### RL-Based Portfolio Management

```python
class PortfolioEnv(gym.Env):
    """RL environment for portfolio allocation"""
    
    def __init__(self, returns_data, transaction_cost=0.001):
        self.returns = returns_data
        self.n_assets = returns_data.shape[1]
        self.transaction_cost = transaction_cost
        
        # Action: target portfolio weights
        self.action_space = spaces.Box(
            low=0, high=1, shape=(self.n_assets,))
        
        # State: past returns + current weights + market features
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, 
            shape=(self.n_assets * 20 + self.n_assets,))
    
    def step(self, action):
        # Normalize weights to sum to 1
        weights = action / action.sum()
        
        # Transaction costs
        turnover = np.abs(weights - self.current_weights).sum()
        cost = turnover * self.transaction_cost
        
        # Portfolio return
        portfolio_return = np.dot(weights, self.returns[self.t]) - cost
        
        # Reward: Sharpe-like (return / risk)
        self.current_weights = weights
        self.t += 1
        
        reward = portfolio_return  # or risk-adjusted
        done = self.t >= len(self.returns)
        
        return self._get_obs(), reward, done, {}
```

---

## 6. Time Series Challenges in Finance

### Non-Stationarity

- Price series are non-stationary; returns are closer to stationary
- Regime changes (bull/bear markets, volatility regimes)
- Structural breaks (policy changes, black swan events)

### Fat Tails

- Financial returns exhibit kurtosis >> 3 (Gaussian)
- Extreme events are far more common than normal distribution predicts
- Use Student-t, stable distributions, or EVT for tail modeling

### Backtesting Pitfalls

```python
class WalkForwardBacktest:
    """Proper backtesting with walk-forward optimization"""
    
    def __init__(self, train_window=252, test_window=21, embargo=5):
        self.train_window = train_window
        self.test_window = test_window
        self.embargo = embargo  # Gap to prevent lookahead
    
    def run(self, data, model_factory):
        results = []
        
        for t in range(self.train_window, len(data) - self.test_window, self.test_window):
            # Training data (with embargo gap)
            train_end = t - self.embargo
            train_data = data[t - self.train_window:train_end]
            
            # Test data
            test_data = data[t:t + self.test_window]
            
            # Fit and predict
            model = model_factory()
            model.fit(train_data)
            predictions = model.predict(test_data)
            
            results.append({
                'period_start': test_data.index[0],
                'predictions': predictions,
                'actuals': test_data['returns']
            })
        
        return self.compute_metrics(results)
    
    def compute_metrics(self, results):
        """Compute strategy performance metrics"""
        all_returns = pd.concat([r['predictions'] * r['actuals'] for r in results])
        return {
            'sharpe_ratio': all_returns.mean() / all_returns.std() * np.sqrt(252),
            'max_drawdown': self.max_drawdown(all_returns.cumsum()),
            'calmar_ratio': all_returns.mean() * 252 / abs(self.max_drawdown(all_returns.cumsum())),
            'sortino_ratio': all_returns.mean() / all_returns[all_returns < 0].std() * np.sqrt(252),
        }
```

### Cross-Validation for Time Series

- **Purged K-Fold**: Remove overlapping samples between train/test
- **Combinatorial Purged CV**: Multiple test paths for robust estimation
- **Expanding window**: Growing training set, fixed test size

---

## 7. Alternative Data Sources

| Data Source | Signal Type | Challenges |
|-------------|-------------|------------|
| Satellite imagery | Retail foot traffic, oil storage | Processing cost, cloud cover |
| SEC filings (NLP) | Sentiment, risk factor changes | Parsing complexity |
| Social media | Retail sentiment, event detection | Noise, manipulation |
| Credit card data | Revenue nowcasting | Privacy, representativeness |
| Web scraping | Pricing, inventory | Legal gray area, anti-bot |
| Patent filings | Innovation pipeline | Long lead times |
| Supply chain data | Disruption detection | Incomplete coverage |

---

## 8. Regulatory Challenges

### SR 11-7 (Model Risk Management)

- **Model Validation**: Independent review of all models
- **Documentation**: Full model development documentation
- **Ongoing Monitoring**: Performance tracking, stability tests
- **Governance**: Model inventory, approval workflows

### Explainability Requirements

- ECOA/Fair Lending: Adverse action reasons for credit decisions
- GDPR Article 22: Right to explanation for automated decisions
- Basel III: Interpretable risk models preferred by regulators

### Model Risk Management Framework

```
┌─────────────────────────────────────────────┐
│           MODEL RISK MANAGEMENT              │
├─────────────────────────────────────────────┤
│                                              │
│  Development ──▶ Validation ──▶ Approval    │
│       │              │              │        │
│       ▼              ▼              ▼        │
│  Documentation   Independent    Governance   │
│  & Testing       Challenge      Committee    │
│       │              │              │        │
│       └──────────────┼──────────────┘        │
│                      ▼                       │
│              Ongoing Monitoring              │
│              (PSI, CSI, backtesting)         │
│                      │                       │
│                      ▼                       │
│              Annual Revalidation             │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 9. Feature Engineering for Financial Data

### Common Feature Categories

```python
def compute_financial_features(df):
    """Standard feature engineering for financial ML"""
    features = {}
    
    # Price-based
    features['returns_1d'] = df['close'].pct_change(1)
    features['returns_5d'] = df['close'].pct_change(5)
    features['volatility_20d'] = df['close'].pct_change().rolling(20).std()
    
    # Volume-based
    features['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    features['dollar_volume'] = df['close'] * df['volume']
    
    # Technical indicators
    features['rsi_14'] = compute_rsi(df['close'], 14)
    features['macd'] = ema(df['close'], 12) - ema(df['close'], 26)
    features['bollinger_position'] = (df['close'] - df['close'].rolling(20).mean()) / (2 * df['close'].rolling(20).std())
    
    # Microstructure
    features['bid_ask_spread'] = (df['ask'] - df['bid']) / df['mid']
    features['kyle_lambda'] = estimate_kyle_lambda(df)  # Price impact
    
    # Cross-sectional
    features['sector_relative_momentum'] = df['returns_20d'] - df['sector_returns_20d']
    
    return pd.DataFrame(features)
```

---

## 10. Challenges Unique to Finance

1. **Adversarial environment**: Other participants adapt to your strategy
2. **Low signal-to-noise**: Typical IC (information coefficient) is 0.02-0.05
3. **Survivorship bias**: Only successful firms/strategies remain in datasets
4. **Look-ahead bias**: Accidentally using future information
5. **Regime changes**: Models trained in one regime fail in another
6. **Transaction costs**: Alpha must exceed costs to be profitable
7. **Capacity constraints**: Strategies degrade with more capital deployed
8. **Data snooping**: Multiple hypothesis testing without correction
9. **Non-IID data**: Serial correlation, heteroscedasticity
10. **Short history**: Rare events have few historical examples

---

## Production Considerations

- **Latency**: Trading systems need microsecond to millisecond response
- **Reliability**: Financial systems need 99.99%+ uptime
- **Audit trail**: Every decision must be traceable and reproducible
- **Disaster recovery**: Hot-standby systems, failover mechanisms
- **Data quality**: Missing data, corporate actions, survivorship bias corrections
- **Model monitoring**: Real-time PSI/CSI tracking, automated alerts

---

## Interview Questions

1. **How would you detect concept drift in a credit scoring model? What metrics would you monitor?**
2. **Design a real-time fraud detection system that handles 50K TPS with <100ms latency. What's your architecture?**
3. **Why can't you use standard k-fold cross-validation for financial time series? What alternatives exist?**
4. **How would you handle extreme class imbalance (0.01% positive rate) in fraud detection?**
5. **Explain the difference between PD, LGD, and EAD. How would you model each?**
6. **What is look-ahead bias in backtesting? Give three examples of how it can creep in.**
7. **How would you build a feature store for a trading system? What are the freshness requirements?**
8. **Explain why a model with great backtest Sharpe ratio might fail in production.**
9. **How would you make a deep learning credit model explainable for regulatory compliance?**
10. **Design an AML system that detects layering across multiple financial institutions.**

---

## Key Papers

1. **"Advances in Financial Machine Learning"** - Marcos López de Prado (2018)
2. **"Machine Learning for Asset Managers"** - López de Prado (2020)
3. **"Deep Learning for Credit Scoring"** - Kvamme et al. (2018)
4. **"Graph Neural Networks for Financial Fraud Detection"** - Liu et al. (2021)
5. **"The Black-Litterman Model"** - He & Litterman (1999)
6. **"Optimal Execution of Portfolio Transactions"** - Almgren & Chriss (2000)
7. **"Anti-Money Laundering in Bitcoin"** - Weber et al. (2019)
8. **"Deep Hedging"** - Buehler et al. (2019)

---

## Common Pitfalls

| Pitfall | Consequence | Mitigation |
|---------|-------------|------------|
| Overfitting to backtest | Strategy fails live | Walk-forward validation, multiple datasets |
| Ignoring transaction costs | Negative real returns | Include realistic cost models |
| Survivorship bias | Inflated performance | Use point-in-time datasets |
| Data snooping | False discoveries | Bonferroni correction, out-of-sample |
| Ignoring market impact | Slippage eats alpha | Model capacity constraints |
| Static model in non-stationary market | Degrading performance | Online learning, regime detection |
| Ignoring correlations | Concentrated risk | Stress testing, correlation breakdown analysis |
