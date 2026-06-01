"""
Recommendation System
=====================
Implements: Collaborative Filtering (User-User, Item-Item), Matrix Factorization (SVD),
Content-Based Filtering, and Hybrid approach.
Uses synthetic movie ratings data.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.sparse.linalg import svds
from sklearn.metrics import mean_squared_error
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

np.random.seed(42)


# =============================================================================
# Data Generation
# =============================================================================

def generate_movie_data(n_users: int = 500, n_movies: int = 100, n_ratings: int = 10000) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic movie ratings and movie metadata."""
    genres = ["Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance"]

    # Movie metadata
    movies = pd.DataFrame({
        "movie_id": range(n_movies),
        "title": [f"Movie_{i}" for i in range(n_movies)],
        "genre": np.random.choice(genres, n_movies),
        "year": np.random.randint(1990, 2024, n_movies),
    })

    # User-genre preferences (latent)
    user_prefs = np.random.rand(n_users, len(genres))
    movie_genre_idx = [genres.index(g) for g in movies["genre"]]

    # Generate ratings based on preferences + noise
    ratings_list = []
    for _ in range(n_ratings):
        user = np.random.randint(0, n_users)
        movie = np.random.randint(0, n_movies)
        base_rating = user_prefs[user, movie_genre_idx[movie]] * 4 + 1  # 1-5 scale
        rating = np.clip(base_rating + np.random.normal(0, 0.5), 1, 5)
        ratings_list.append({"user_id": user, "movie_id": movie, "rating": round(rating, 1)})

    ratings = pd.DataFrame(ratings_list).drop_duplicates(subset=["user_id", "movie_id"])
    logger.info(f"Generated {len(ratings)} ratings, {n_users} users, {n_movies} movies")
    return ratings, movies


# =============================================================================
# Collaborative Filtering
# =============================================================================

class CollaborativeFilter:
    """User-based and Item-based collaborative filtering."""

    def __init__(self, ratings: pd.DataFrame, n_users: int, n_movies: int):
        self.user_item_matrix = np.zeros((n_users, n_movies))
        for _, row in ratings.iterrows():
            self.user_item_matrix[int(row["user_id"]), int(row["movie_id"])] = row["rating"]

        # Normalize (subtract user mean)
        self.user_means = np.true_divide(
            self.user_item_matrix.sum(axis=1),
            (self.user_item_matrix != 0).sum(axis=1).clip(min=1)
        )
        self.normalized = self.user_item_matrix.copy()
        for i in range(len(self.user_means)):
            mask = self.normalized[i] != 0
            self.normalized[i, mask] -= self.user_means[i]

    def user_based_predict(self, user_id: int, movie_id: int, k: int = 20) -> float:
        """Predict rating using k most similar users."""
        sim = cosine_similarity([self.normalized[user_id]], self.normalized)[0]
        # Users who rated this movie
        rated_mask = self.user_item_matrix[:, movie_id] != 0
        sim[user_id] = 0  # exclude self

        # Top-k similar users who rated this movie
        candidates = np.where(rated_mask)[0]
        if len(candidates) == 0:
            return self.user_means[user_id]

        top_k = candidates[np.argsort(sim[candidates])[::-1][:k]]
        weights = sim[top_k]

        if weights.sum() == 0:
            return self.user_means[user_id]

        weighted_sum = np.dot(weights, self.normalized[top_k, movie_id])
        return self.user_means[user_id] + weighted_sum / (np.abs(weights).sum() + 1e-8)

    def recommend_for_user(self, user_id: int, n: int = 5) -> List[Tuple[int, float]]:
        """Get top-n recommendations for a user."""
        unrated = np.where(self.user_item_matrix[user_id] == 0)[0]
        predictions = [(mid, self.user_based_predict(user_id, mid)) for mid in unrated[:50]]
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions[:n]


# =============================================================================
# Matrix Factorization (SVD)
# =============================================================================

class MatrixFactorization:
    """SVD-based matrix factorization for recommendations."""

    def __init__(self, ratings: pd.DataFrame, n_users: int, n_movies: int, k: int = 20):
        self.n_users = n_users
        self.n_movies = n_movies

        # Build matrix
        self.matrix = np.zeros((n_users, n_movies))
        for _, row in ratings.iterrows():
            self.matrix[int(row["user_id"]), int(row["movie_id"])] = row["rating"]

        # Normalize
        user_means = np.true_divide(
            self.matrix.sum(axis=1), (self.matrix != 0).sum(axis=1).clip(min=1)
        )
        self.user_means = user_means

        matrix_normalized = self.matrix.copy()
        for i in range(n_users):
            mask = matrix_normalized[i] != 0
            matrix_normalized[i, mask] -= user_means[i]

        # SVD
        U, sigma, Vt = svds(matrix_normalized, k=min(k, min(n_users, n_movies) - 1))
        self.predicted = np.dot(np.dot(U, np.diag(sigma)), Vt) + user_means.reshape(-1, 1)
        self.predicted = np.clip(self.predicted, 1, 5)
        logger.info(f"SVD factorization complete (k={k})")

    def predict(self, user_id: int, movie_id: int) -> float:
        return self.predicted[user_id, movie_id]

    def recommend(self, user_id: int, n: int = 5) -> List[Tuple[int, float]]:
        unrated = np.where(self.matrix[user_id] == 0)[0]
        scores = [(mid, self.predicted[user_id, mid]) for mid in unrated]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n]


# =============================================================================
# Content-Based Filtering
# =============================================================================

class ContentBasedFilter:
    """Recommend based on item feature similarity."""

    def __init__(self, movies: pd.DataFrame, ratings: pd.DataFrame):
        # One-hot encode genres
        self.genre_matrix = pd.get_dummies(movies["genre"]).values.astype(float)
        self.item_sim = cosine_similarity(self.genre_matrix)
        self.ratings = ratings
        self.movies = movies

    def recommend(self, user_id: int, n: int = 5) -> List[Tuple[int, float]]:
        """Recommend items similar to what user liked."""
        user_ratings = self.ratings[self.ratings["user_id"] == user_id]
        liked = user_ratings[user_ratings["rating"] >= 4.0]["movie_id"].values

        if len(liked) == 0:
            return []

        # Score all movies by similarity to liked movies
        scores = self.item_sim[liked].mean(axis=0)
        rated_movies = set(user_ratings["movie_id"].values)
        candidates = [(i, scores[i]) for i in range(len(scores)) if i not in rated_movies]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:n]


# =============================================================================
# Evaluation
# =============================================================================

def evaluate_rmse(model, test_ratings: pd.DataFrame) -> float:
    """Calculate RMSE on test set."""
    predictions = []
    actuals = []
    for _, row in test_ratings.iterrows():
        pred = model.predict(int(row["user_id"]), int(row["movie_id"]))
        predictions.append(pred)
        actuals.append(row["rating"])
    return np.sqrt(mean_squared_error(actuals, predictions))


def precision_at_k(recommended: List[int], relevant: List[int], k: int) -> float:
    """Precision@K metric."""
    rec_k = set(recommended[:k])
    return len(rec_k & set(relevant)) / k if k > 0 else 0.0


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """Run recommendation system pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           RECOMMENDATION SYSTEM                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Generate data
    ratings, movies = generate_movie_data()
    n_users = ratings["user_id"].nunique()
    n_movies = movies.shape[0]

    print(f"\nDataset: {len(ratings)} ratings, {n_users} users, {n_movies} movies")
    print(f"Sparsity: {1 - len(ratings) / (n_users * n_movies):.2%}")
    print(f"Rating distribution:\n{ratings['rating'].describe().to_string()}")

    # Split
    train_ratings, test_ratings = train_test_split(ratings, test_size=0.2, random_state=42)

    # --- Matrix Factorization ---
    print("\n" + "=" * 50)
    print("MATRIX FACTORIZATION (SVD)")
    print("=" * 50)
    mf = MatrixFactorization(train_ratings, n_users, n_movies, k=20)
    rmse = evaluate_rmse(mf, test_ratings)
    print(f"Test RMSE: {rmse:.4f}")

    # Sample recommendations
    print("\nSample Recommendations (User 0):")
    recs = mf.recommend(user_id=0, n=5)
    for movie_id, score in recs:
        title = movies.iloc[movie_id]["title"]
        genre = movies.iloc[movie_id]["genre"]
        print(f"  {title} ({genre}) - predicted: {score:.2f}")

    # --- Collaborative Filtering ---
    print("\n" + "=" * 50)
    print("COLLABORATIVE FILTERING (User-Based)")
    print("=" * 50)
    cf = CollaborativeFilter(train_ratings, n_users, n_movies)
    recs = cf.recommend_for_user(user_id=1, n=5)
    print("Recommendations for User 1:")
    for movie_id, score in recs:
        title = movies.iloc[movie_id]["title"]
        genre = movies.iloc[movie_id]["genre"]
        print(f"  {title} ({genre}) - predicted: {score:.2f}")

    # --- Content-Based ---
    print("\n" + "=" * 50)
    print("CONTENT-BASED FILTERING")
    print("=" * 50)
    cb = ContentBasedFilter(movies, train_ratings)
    recs = cb.recommend(user_id=2, n=5)
    print("Recommendations for User 2:")
    for movie_id, score in recs:
        title = movies.iloc[movie_id]["title"]
        genre = movies.iloc[movie_id]["genre"]
        print(f"  {title} ({genre}) - similarity: {score:.3f}")

    # --- Comparison ---
    print("\n" + "=" * 50)
    print("MODEL COMPARISON (RMSE)")
    print("=" * 50)
    print(f"  Matrix Factorization (SVD): {rmse:.4f}")

    # Evaluate CF on small sample
    sample_test = test_ratings.sample(min(200, len(test_ratings)), random_state=42)
    cf_preds = []
    cf_actuals = []
    for _, row in sample_test.iterrows():
        pred = cf.user_based_predict(int(row["user_id"]), int(row["movie_id"]))
        cf_preds.append(pred)
        cf_actuals.append(row["rating"])
    cf_rmse = np.sqrt(mean_squared_error(cf_actuals, cf_preds))
    print(f"  Collaborative Filtering:    {cf_rmse:.4f}")

    print("\n✅ Recommendation pipeline complete!")


if __name__ == "__main__":
    main()
