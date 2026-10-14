"""
ReturnShield ML Training Script
=================================
Trains a 3-class XGBoost classifier on the prepared dataset.
Saves model artifact + metadata to ml/artifacts/.

Usage:
    python ml/train.py [--data-dir data/derived] [--artifacts-dir ml/artifacts]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import hashlib
import pickle
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

import xgboost as xgb
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight

from shared.feature_schema import (
    FEATURE_NAMES, LABEL_MAP, LABEL_NAMES, NULLABLE_FEATURES,
    SCHEMA_HASH, N_FEATURES
)


def load_split(data_dir: Path, split: str) -> tuple[pd.DataFrame, pd.Series]:
    path = data_dir / f"{split}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing split file: {path}. Run ml/prepare_data.py first.")
    df = pd.read_csv(path)
    X = df[FEATURE_NAMES]
    y = df["target_label"]
    return X, y


def impute_weight(X: pd.DataFrame, median: float) -> pd.DataFrame:
    """Fill weight_discrepancy_grams nulls with training median."""
    X = X.copy()
    X["weight_discrepancy_grams"] = X["weight_discrepancy_grams"].fillna(median)
    return X


def get_weight_median(X_train: pd.DataFrame) -> float:
    return float(X_train["weight_discrepancy_grams"].median())


def train_model(X_train, y_train, X_val, y_val, seed: int = 42):
    """Train XGBoost 3-class classifier."""
    # Compute sample weights for class imbalance
    sample_weights = compute_sample_weight("balanced", y_train)

    params = {
        "objective": "multi:softprob",
        "num_class": 3,
        "n_estimators": 500,
        "learning_rate": 0.05,
        "max_depth": 6,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": seed,
        "eval_metric": "mlogloss",
        "early_stopping_rounds": 30,
        "verbosity": 0,
        "tree_method": "hist",
    }

    model = xgb.XGBClassifier(**params)
    model.fit(
        X_train, y_train,
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    print(f"  Best iteration: {model.best_iteration}")
    return model


def evaluate_model(model, X_test, y_test, weight_median: float) -> dict:
    """Evaluate on held-out test set. Returns metrics dict."""
    X_test_imp = impute_weight(X_test, weight_median)
    y_pred = model.predict(X_test_imp)
    y_proba = model.predict_proba(X_test_imp)

    report = classification_report(
        y_test, y_pred,
        target_names=LABEL_NAMES,
        output_dict=True
    )
    cm = confusion_matrix(y_test, y_pred).tolist()

    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=LABEL_NAMES))
    print(f"  Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    return {
        "classification_report": report,
        "confusion_matrix": cm,
        "test_size": len(y_test),
        "test_class_distribution": {
            LABEL_MAP[i]: int((y_test == i).sum()) for i in range(3)
        },
        "note": "Metrics on held-out test set. weight_discrepancy_grams imputed with training median for null rows.",
        "warning": "weight_discrepancy_grams has near-perfect separation for Suspicious label in training data. These metrics may not reflect real-world performance.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/derived")
    parser.add_argument("--artifacts-dir", default="ml/artifacts")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ReturnShield Model Training")
    print("=" * 60)

    # 1. Load splits
    print("\n[1] Loading data splits")
    X_train, y_train = load_split(data_dir, "train")
    X_val, y_val = load_split(data_dir, "val")
    X_test, y_test = load_split(data_dir, "test")
    print(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # 2. Compute imputation median from training set
    weight_median = get_weight_median(X_train)
    print(f"\n[2] Weight discrepancy imputation median: {weight_median:.2f}g")

    # 3. Impute
    X_train_imp = impute_weight(X_train, weight_median)
    X_val_imp = impute_weight(X_val, weight_median)
    X_test_imp = impute_weight(X_test, weight_median)

    # 4. Verify feature order
    assert list(X_train_imp.columns) == FEATURE_NAMES, "Feature order mismatch!"
    print(f"\n[3] Feature order verified: {N_FEATURES} features, schema hash={SCHEMA_HASH}")

    # 5. Train
    print("\n[4] Training XGBoost model")
    model = train_model(X_train_imp, y_train, X_val_imp, y_val, args.seed)

    # 6. Evaluate
    print("\n[5] Evaluating on held-out test set")
    metrics = evaluate_model(model, X_test, y_test, weight_median)

    # 7. Save model
    model_path = artifacts_dir / "model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\n[6] Model saved to {model_path}")

    # 8. Save metadata
    import xgboost as xgb_module
    import sklearn
    metadata = {
        "model_version": "1.0.0",
        "schema_hash": SCHEMA_HASH,
        "feature_names": FEATURE_NAMES,
        "n_features": N_FEATURES,
        "label_map": {str(k): v for k, v in LABEL_MAP.items()},
        "nullable_features": list(NULLABLE_FEATURES),
        "weight_imputation_median": weight_median,
        "random_seed": args.seed,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "library_versions": {
            "xgboost": xgb_module.__version__,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "hyperparameters": {
            "n_estimators": model.best_iteration + 1,
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
        "evaluation": metrics,
        "warnings": [
            "weight_discrepancy_grams has near-perfect label separation for Suspicious class.",
            "Metrics are demonstration metrics only. Not validated on real-world fraud data.",
            "shared_identity_links is pre-computed in training; Redis-computed at inference.",
        ],
    }

    metadata_path = artifacts_dir / "model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[7] Metadata saved to {metadata_path}")

    print("\n[DONE] Training complete. Artifacts:")
    print(f"  Model:    {model_path}")
    print(f"  Metadata: {metadata_path}")

    return model, metadata


if __name__ == "__main__":
    main()
