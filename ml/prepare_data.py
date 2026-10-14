"""
ReturnShield ML Data Preparation
==================================
Loads raw training data, validates, injects weight_discrepancy nulls,
splits into train/val/test, and saves to data/derived/.

Usage:
    python ml/prepare_data.py

Outputs:
    data/derived/train.csv
    data/derived/val.csv
    data/derived/test.csv
    ml/artifacts/audit_report.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

from shared.feature_schema import (
    FEATURE_NAMES, LABEL_MAP, NULLABLE_FEATURES, SCHEMA_HASH, N_FEATURES
)

RAW_CSV = Path("data/raw/train_data.csv")
DERIVED_DIR = Path("data/derived")
ARTIFACTS_DIR = Path("ml/artifacts")
TARGET_COL = "target_label"
RANDOM_SEED = 42
NULL_INJECTION_RATE = 0.20  # 20% of weight_discrepancy_grams will be nulled


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_raw(df: pd.DataFrame) -> list[str]:
    errors = []
    missing_cols = [c for c in FEATURE_NAMES + [TARGET_COL] if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")
    extra_cols = [c for c in df.columns if c not in FEATURE_NAMES + [TARGET_COL]]
    if extra_cols:
        errors.append(f"Unexpected columns: {extra_cols}")
    if TARGET_COL in df.columns:
        invalid_labels = set(df[TARGET_COL].unique()) - set(LABEL_MAP.keys())
        if invalid_labels:
            errors.append(f"Invalid labels: {invalid_labels}")
        if df[TARGET_COL].isnull().any():
            errors.append("Target column has nulls")
    for feat in FEATURE_NAMES:
        if feat not in df.columns:
            continue
        if feat == "weight_discrepancy_grams":
            continue  # Nullable, handled separately
        if df[feat].isnull().any():
            errors.append(f"{feat} has unexpected nulls in raw data")
    # Validate product_category_code
    if "product_category_code" in df.columns:
        invalid = df["product_category_code"][~df["product_category_code"].isin([1,2,3,4,5])]
        if len(invalid) > 0:
            errors.append(f"Invalid product_category_code values: {invalid.unique()}")
    # Validate return_reason_code
    if "return_reason_code" in df.columns:
        invalid = df["return_reason_code"][~df["return_reason_code"].isin([1,2,3,4,5])]
        if len(invalid) > 0:
            errors.append(f"Invalid return_reason_code values: {invalid.unique()}")
    # Validate binary
    for col in ["is_cod_order", "purchased_in_sale"]:
        if col in df.columns:
            invalid = df[col][~df[col].isin([0, 1])]
            if len(invalid) > 0:
                errors.append(f"Invalid {col} values: {invalid.unique()}")
    # Validate ratio
    if "historical_return_ratio" in df.columns:
        bad = df[(df["historical_return_ratio"] < 0) | (df["historical_return_ratio"] > 1)]
        if len(bad) > 0:
            errors.append(f"historical_return_ratio out of [0,1]: {len(bad)} rows")
    return errors


def inject_weight_nulls(df: pd.DataFrame, rate: float, seed: int) -> pd.DataFrame:
    """Randomly set weight_discrepancy_grams to NaN for 'rate' fraction of rows."""
    df = df.copy()
    rng = np.random.RandomState(seed)
    null_mask = rng.random(len(df)) < rate
    df.loc[null_mask, "weight_discrepancy_grams"] = np.nan
    n_nulls = null_mask.sum()
    print(f"  Injected {n_nulls} nulls ({n_nulls/len(df)*100:.1f}%) into weight_discrepancy_grams")
    return df


def main():
    print("=" * 60)
    print("ReturnShield Data Preparation")
    print("=" * 60)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load
    print(f"\n[1] Loading {RAW_CSV}")
    if not RAW_CSV.exists():
        print(f"ERROR: {RAW_CSV} not found")
        sys.exit(1)
    sha256 = compute_sha256(RAW_CSV)
    df = pd.read_csv(RAW_CSV)
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
    print(f"  SHA-256: {sha256}")

    # 2. Validate
    print("\n[2] Validating schema and values")
    errors = validate_raw(df)
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("  All validations passed")

    # 3. Class distribution
    print("\n[3] Class distribution")
    dist = df[TARGET_COL].value_counts().sort_index()
    for label_id, count in dist.items():
        print(f"  {label_id} ({LABEL_MAP[label_id]}): {count} ({count/len(df)*100:.1f}%)")

    # 4. Inject nulls into weight_discrepancy_grams
    print(f"\n[4] Injecting {NULL_INJECTION_RATE*100:.0f}% nulls into weight_discrepancy_grams")
    df = inject_weight_nulls(df, NULL_INJECTION_RATE, RANDOM_SEED)

    # 5. Compute imputation median (on non-null training data only - computed post-split)
    # We do this after split to avoid test leakage
    print("\n[5] Splitting into train/val/test (70/15/15, stratified, seed=42)")
    X = df[FEATURE_NAMES]
    y = df[TARGET_COL]

    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=RANDOM_SEED
    )
    val_size_of_remaining = 0.15 / 0.85
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=val_size_of_remaining,
        stratify=y_train_val, random_state=RANDOM_SEED
    )

    print(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # 6. Compute weight imputation median from training set only
    weight_median = float(X_train["weight_discrepancy_grams"].median())
    print(f"\n[6] Weight discrepancy training median (for imputation): {weight_median:.2f}g")

    # 7. Save splits
    print("\n[7] Saving splits")
    train_df = X_train.copy()
    train_df[TARGET_COL] = y_train
    val_df = X_val.copy()
    val_df[TARGET_COL] = y_val
    test_df = X_test.copy()
    test_df[TARGET_COL] = y_test

    train_df.to_csv(DERIVED_DIR / "train.csv", index=False)
    val_df.to_csv(DERIVED_DIR / "val.csv", index=False)
    test_df.to_csv(DERIVED_DIR / "test.csv", index=False)
    print(f"  Saved to {DERIVED_DIR}/")

    # 8. Save audit report
    audit_report = {
        "source_file": str(RAW_CSV),
        "source_sha256": sha256,
        "schema_hash": SCHEMA_HASH,
        "n_features": N_FEATURES,
        "feature_names": FEATURE_NAMES,
        "target_col": TARGET_COL,
        "label_map": {str(k): v for k, v in LABEL_MAP.items()},
        "random_seed": RANDOM_SEED,
        "null_injection_rate": NULL_INJECTION_RATE,
        "weight_imputation_median": weight_median,
        "total_rows": len(df),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "class_distribution": {str(k): int(v) for k, v in dist.items()},
        "train_class_distribution": {str(k): int(v) for k, v in y_train.value_counts().sort_index().items()},
        "test_class_distribution": {str(k): int(v) for k, v in y_test.value_counts().sort_index().items()},
        "leakage_warning_weight_disc": "weight_discrepancy_grams >100 perfectly predicts label=2 in raw data. 20% null injection mitigates over-reliance.",
        "inference_note_shared_identity": "shared_identity_links must be computed from Redis at inference. Training column used as proxy.",
        "transformations": [
            "20% random null injection into weight_discrepancy_grams (seed=42)",
            "Stratified 70/15/15 split (seed=42)",
        ],
    }
    report_path = ARTIFACTS_DIR / "audit_report.json"
    with open(report_path, "w") as f:
        json.dump(audit_report, f, indent=2)
    print(f"\n[8] Audit report saved to {report_path}")

    print("\n[DONE] Data preparation complete")
    return audit_report


if __name__ == "__main__":
    main()
