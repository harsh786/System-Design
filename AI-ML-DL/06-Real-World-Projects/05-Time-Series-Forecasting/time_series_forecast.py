"""
Time Series Forecasting
========================
Approach 1: sklearn (Ridge regression with lag features)
Approach 2: LSTM (PyTorch) - optional, requires torch
Uses synthetic time series data with trend + seasonality.
"""

import logging
import warnings
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
except ImportError:
    TORCH_AVAILABLE = False
    logger.info("PyTorch not available. LSTM approach will be skipped.")


# =============================================================================
# Data Generation
# =============================================================================

def generate_time_series(n_points: int = 1000) -> pd.Series:
    """Generate synthetic time series with trend, seasonality, and noise."""
    t = np.arange(n_points)
    trend = 0.02 * t
    seasonality = 5 * np.sin(2 * np.pi * t / 50) + 3 * np.sin(2 * np.pi * t / 12)
    noise = np.random.normal(0, 1, n_points)
    values = 50 + trend + seasonality + noise

    dates = pd.date_range(start="2020-01-01", periods=n_points, freq="D")
    series = pd.Series(values, index=dates, name="value")
    logger.info(f"Generated time series: {n_points} points, range [{values.min():.1f}, {values.max():.1f}]")
    return series


# =============================================================================
# Approach 1: Sklearn (Ridge with lag features)
# =============================================================================

def create_lag_features(series: np.ndarray, n_lags: int = 30) -> Tuple[np.ndarray, np.ndarray]:
    """Create lag feature matrix."""
    X, y = [], []
    for i in range(n_lags, len(series)):
        X.append(series[i - n_lags:i])
        y.append(series[i])
    return np.array(X), np.array(y)


def sklearn_forecast(train: pd.Series, test: pd.Series, n_lags: int = 30) -> np.ndarray:
    """Fit Ridge regression with lag features and forecast."""
    print("\n" + "=" * 50)
    print("APPROACH 1: Ridge Regression (Lag Features)")
    print("=" * 50)

    # Scale
    scaler = MinMaxScaler()
    train_scaled = scaler.fit_transform(train.values.reshape(-1, 1)).flatten()

    # Create features from training data
    X_train, y_train = create_lag_features(train_scaled, n_lags)
    logger.info(f"Training features shape: {X_train.shape}")

    # Fit model
    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)

    # Forecast iteratively
    full_scaled = np.concatenate([train_scaled])
    predictions = []
    current_seq = list(train_scaled[-n_lags:])

    for _ in range(len(test)):
        x = np.array(current_seq[-n_lags:]).reshape(1, -1)
        pred = model.predict(x)[0]
        predictions.append(pred)
        current_seq.append(pred)

    # Inverse scale
    predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()

    mae = mean_absolute_error(test.values, predictions)
    rmse = np.sqrt(mean_squared_error(test.values, predictions))
    print(f"\nRidge Forecast Metrics:")
    print(f"  MAE:  {mae:.4f}")
    print(f"  RMSE: {rmse:.4f}")

    return predictions


# =============================================================================
# Approach 2: LSTM (PyTorch) - Optional
# =============================================================================

if TORCH_AVAILABLE:
    class LSTMForecaster(nn.Module):
        """LSTM for time series forecasting."""

        def __init__(self, input_size: int = 1, hidden_size: int = 64, num_layers: int = 2):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
            self.fc = nn.Linear(hidden_size, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])


def create_sequences(data: np.ndarray, seq_len: int = 30) -> Tuple[np.ndarray, np.ndarray]:
    """Create input sequences and targets for LSTM."""
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i:i + seq_len])
        y.append(data[i + seq_len])
    return np.array(X), np.array(y)


def lstm_forecast(train: pd.Series, test: pd.Series, seq_len: int = 30) -> np.ndarray:
    """Train LSTM and forecast."""
    if not TORCH_AVAILABLE:
        print("\n[SKIPPED] LSTM approach requires PyTorch")
        return None

    print("\n" + "=" * 50)
    print("APPROACH 2: LSTM (PyTorch)")
    print("=" * 50)

    # Scale
    scaler = MinMaxScaler()
    train_scaled = scaler.fit_transform(train.values.reshape(-1, 1)).flatten()

    # Create sequences
    X_train, y_train = create_sequences(train_scaled, seq_len)
    X_train = torch.FloatTensor(X_train).unsqueeze(-1).to(DEVICE)
    y_train = torch.FloatTensor(y_train).unsqueeze(-1).to(DEVICE)

    # Model
    model = LSTMForecaster(input_size=1, hidden_size=64, num_layers=2).to(DEVICE)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Train
    epochs = 20
    print(f"\n{'Epoch':>5} {'Loss':>10}")
    print("-" * 17)
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        output = model(X_train)
        loss = criterion(output, y_train)
        loss.backward()
        optimizer.step()

        if epoch % 5 == 0:
            print(f"{epoch:>5d} {loss.item():>10.6f}")

    # Forecast iteratively
    model.eval()
    predictions = []
    current_seq = train_scaled[-seq_len:].tolist()

    with torch.no_grad():
        for _ in range(len(test)):
            x = torch.FloatTensor([current_seq[-seq_len:]]).unsqueeze(-1).to(DEVICE)
            pred = model(x).item()
            predictions.append(pred)
            current_seq.append(pred)

    # Inverse scale
    predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()

    mae = mean_absolute_error(test.values, predictions)
    rmse = np.sqrt(mean_squared_error(test.values, predictions))
    print(f"\nLSTM Forecast Metrics:")
    print(f"  MAE:  {mae:.4f}")
    print(f"  RMSE: {rmse:.4f}")

    return predictions


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """Run time series forecasting pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         TIME SERIES FORECASTING                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Generate data
    np.random.seed(42)
    series = generate_time_series(n_points=500)

    # Split (last 50 points as test)
    train = series[:-50]
    test = series[-50:]
    print(f"\nTrain: {len(train)} points, Test: {len(test)} points")
    print(f"Series stats: mean={series.mean():.2f}, std={series.std():.2f}")

    # Approach 1: Sklearn
    sklearn_preds = sklearn_forecast(train, test)

    # Approach 2: LSTM (optional)
    lstm_preds = lstm_forecast(train, test)

    # Comparison
    print("\n" + "=" * 50)
    print("COMPARISON")
    print("=" * 50)
    print(f"\n{'Method':<12} {'MAE':>8} {'RMSE':>8}")
    print("-" * 30)

    sklearn_mae = mean_absolute_error(test.values, sklearn_preds)
    sklearn_rmse = np.sqrt(mean_squared_error(test.values, sklearn_preds))
    print(f"{'Ridge':<12} {sklearn_mae:>8.4f} {sklearn_rmse:>8.4f}")

    if lstm_preds is not None:
        lstm_mae = mean_absolute_error(test.values, lstm_preds)
        lstm_rmse = np.sqrt(mean_squared_error(test.values, lstm_preds))
        print(f"{'LSTM':<12} {lstm_mae:>8.4f} {lstm_rmse:>8.4f}")

    print("\n✅ Forecasting pipeline complete!")


if __name__ == "__main__":
    main()
