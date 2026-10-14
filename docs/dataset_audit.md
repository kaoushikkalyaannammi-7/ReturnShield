# ReturnShield Dataset Audit

**Audit Date:** 2026-10-14
**Dataset:** data/raw/train_data.csv (read-only original preserved)
**SHA-256:** ccfc16f5d75d6a0f8259000b66404c54a0851b025c888aa40291c507c17b825c
**Auditor:** Antigravity autonomous agent (Stage 1)

## 1. Basic Facts
- Rows: 10,000
- Columns: 13 (12 features + 1 target: target_label)
- File size: ~446 KB
- SHA-256: ccfc16f5d75d6a0f8259000b66404c54a0851b025c888aa40291c507c17b825c

## 2. Target Variable
- 0 Genuine: 5,783 (57.83%)
- 1 Mistaken: 2,567 (25.67%)
- 2 Suspicious: 1,650 (16.50%)
Moderate class imbalance -> use XGBoost sample_weight.

## 3. Schema Match: PERFECT
All 12 features present in exact schema order. No extra columns.

## 4. Missing Values: ZERO in all columns.
WARNING: weight_discrepancy_grams is nullable at inference time (scan may not exist).
Mitigation: inject 20% random nulls in preprocessing (seed=42), impute with median.

## 5. Duplicates: ZERO exact or feature-only duplicates.

## 6. CRITICAL LEAKAGE FINDINGS

### weight_discrepancy_grams - Strong Label Separation
- Label 0 (Genuine): mean=10.4g, >100g count=0
- Label 1 (Mistaken): mean=13.9g, >100g count=0
- Label 2 (Suspicious): mean=274.6g, >100g count=1248/1650 (75.6%)
Every row with weight_disc > 100 is label=2. No label=0/1 rows exceed 100g.
Decision: Retain (operationally valid). Mitigate via null injection. Document SHAP reliance.

### shared_identity_links - Inference Source Conflict
- Label 0: mean=0.11
- Label 1: mean=0.32
- Label 2: mean=2.79
Training: pre-computed static column.
Inference: MUST be computed by Redis behavioral engine. Client cannot supply this value.

## 7. Training Suitability
SUITABLE - primary training source with documented modifications.
Labels match ReturnShield schema. Features correct. Manageable imbalance.

## 8. Limitations
- Provenance unknown (likely synthetic).
- weight_discrepancy separation inflates accuracy - real performance may differ.
- Metrics are demonstration metrics only, NOT production benchmarks.
- No temporal ordering - stratified random split used.
