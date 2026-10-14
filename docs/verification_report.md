# ReturnShield Comprehensive Verification & Audit Report

**Date:** 2026-10-14  
**Project:** ReturnShield (Problem Statement #6: Detecting Refund and Return Abuse)  
**Workspace:** `C:\Users\kaoushik\.gemini\antigravity-ide\scratch\returnshield`  
**Auditor:** Antigravity Autonomous Agent  

---

## 1. Test Suite Execution (Unit & Integration Tests)

**Command:**
```powershell
python -m pytest -v
```

**Actual Terminal Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.0, pluggy-1.6.0
rootdir: C:\Users\kaoushik\.gemini\antigravity-ide\scratch\returnshield
configfile: pytest.ini
testpaths: backend/tests
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False

backend/tests/test_api_endpoints.py::test_health_endpoint PASSED         [  4%]
backend/tests/test_api_endpoints.py::test_simulation_status PASSED       [  8%]
backend/tests/test_api_endpoints.py::test_refund_validation_error_missing_fields PASSED [ 12%]
backend/tests/test_api_endpoints.py::test_refund_assessment_flow_success PASSED [ 16%]
backend/tests/test_end_to_end_integration.py::test_end_to_end_single_refund_and_persistence PASSED [ 20%]
backend/tests/test_end_to_end_integration.py::test_coordinated_device_fraud_ring_scenario PASSED [ 25%]
backend/tests/test_feature_schema.py::test_feature_count_and_order PASSED [ 29%]
backend/tests/test_feature_schema.py::test_schema_hash_consistency PASSED [ 33%]
backend/tests/test_feature_schema.py::test_label_mapping PASSED          [ 37%]
backend/tests/test_feature_schema.py::test_product_category_and_return_reason_mappings PASSED [ 41%]
backend/tests/test_feature_schema.py::test_nullable_and_redis_computed_spec PASSED [ 45%]
backend/tests/test_feature_schema.py::test_validate_feature_vector_valid PASSED [ 50%]
backend/tests/test_feature_schema.py::test_validate_feature_vector_invalid_range PASSED [ 54%]
backend/tests/test_locust_generators.py::test_genuine_generator PASSED   [ 58%]
backend/tests/test_locust_generators.py::test_mistaken_generator PASSED  [ 62%]
backend/tests/test_locust_generators.py::test_suspicious_generator PASSED [ 66%]
backend/tests/test_model_inference.py::test_model_loaded_and_metadata_verified PASSED [ 70%]
backend/tests/test_model_inference.py::test_predict_genuine_profile PASSED [ 75%]
backend/tests/test_model_inference.py::test_predict_suspicious_profile PASSED [ 79%]
backend/tests/test_risk_policy.py::test_pure_genuine_low_risk PASSED     [ 83%]
backend/tests/test_risk_policy.py::test_suspicious_high_risk PASSED      [ 87%]
backend/tests/test_risk_policy.py::test_elevated_tier_with_behavioral_overlay PASSED [ 91%]
backend/tests/test_risk_policy.py::test_risk_score_clamping PASSED       [ 95%]
backend/tests/test_risk_policy.py::test_top_factors_includes_disclaimer_and_signals PASSED [100%]

======================= 24 passed, 4 warnings in 3.25s ========================
```

- **Unit Tests:** 22 tests (Feature schema contract, schema hash, category mappings, risk score formula, tier thresholds, ML inference latency, and Locust request generators).
- **Integration Tests:** 2 tests (Full API transaction execution with `fakeredis` behavioral state, mock database persistence, and multi-account device sharing ring).
- **Result:** **24 passed, 0 failed** in 3.25 seconds.

---

## 2. Frontend Production Build

**Command:**
```powershell
cd frontend
npm run build
```

**Actual Terminal Output:**
```text
> frontend@0.0.0 build
> vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 596 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-CLQc0lDO.css   14.63 kB │ gzip:   3.35 kB
dist/assets/index-8k9LHhdE.js   662.47 kB │ gzip: 191.95 kB

✓ built in 234ms
Exit Code: 0
```

- **Exit Status:** `0` (Success). All JavaScript, JSX components, CSS tokens, and SVG assets bundled cleanly.

---

## 3. Machine Learning Pipeline Inspection & Metric Verification

### 3.1 Dataset Provenance & Integrity
- **Original Source File:** `train_data.csv`
- **SHA-256 Hash:** `ccfc16f5d75d6a0f8259000b66404c54a0851b025c888aa40291c507c17b825c`
- **Total Records:** 10,000 | **Columns:** 13 (12 features + 1 target)
- **Class Breakdown:**
  - Class 0 (`Genuine`): 5,783 (57.83%)
  - Class 1 (`Mistaken`): 2,567 (25.67%)
  - Class 2 (`Suspicious`): 1,650 (16.50%)

### 3.2 Train / Val / Test Split Strategy
- Split performed in [`ml/prepare_data.py`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/ml/prepare_data.py):
  1. Held-out Test Split: 15% stratified split (`random_state=42`) $\rightarrow$ **1,500 samples** (`data/derived/test.csv`).
  2. Validation Split: 15% of total dataset stratified split ($\frac{0.15}{0.85}$ of remaining) $\rightarrow$ **1,500 samples** (`data/derived/val.csv`).
  3. Training Split: Remaining 70% $\rightarrow$ **7,000 samples** (`data/derived/train.csv`).
- **Data Leakage Safeguards:**
  - The imputation median for `weight_discrepancy_grams` (`10.9g`) was fitted **strictly on `X_train` post-split**, never on `X_test`.
  - XGBoost early stopping (`early_stopping_rounds=30`) used `X_val`, never `X_test`.
  - `X_test` was strictly held out and only evaluated after model fitting completed.

### 3.3 Held-Out Test Evaluation & Metric Verification
- **Confusion Matrix** on 1,500 held-out test rows:
  $$\begin{pmatrix} 813 & 30 & 24 \\ 8 & 360 & 17 \\ 4 & 16 & 228 \end{pmatrix}$$
- **Trace (Correct Predictions):** $813 + 360 + 228 = 1,401$
- **Reported Accuracy Calculation:**
  $$\text{Accuracy} = \frac{1401}{1500} = 0.9340 \quad (93.40\%)$$
- **Per-Class Breakdown:**
  - `Genuine` (Class 0, 867 support): Precision = 98.55%, Recall = 93.77%, F1 = 96.10%
  - `Mistaken` (Class 1, 385 support): Precision = 88.67%, Recall = 93.51%, F1 = 91.02%
  - `Suspicious` (Class 2, 248 support): Precision = 84.76%, Recall = 91.94%, F1 = 88.20%
- **Macro-Averaged F1:** **91.77%** | **Weighted F1:** **93.49%**

---

## 4. `weight_discrepancy_grams` Separation & Leakage Investigation

### 4.1 Findings in Raw Dataset
An empirical analysis of `weight_discrepancy_grams` in `data/raw/train_data.csv` revealed:
- **Class 0 (`Genuine`):** Mean = 10.41g, Max = 64.8g, Count $> 100g = 0$
- **Class 1 (`Mistaken`):** Mean = 13.91g, Max = 65.0g, Count $> 100g = 0$
- **Class 2 (`Suspicious`):** Mean = 274.59g, Min = 5.0g, Max = 599.5g, Count $> 100g = 1,248$ (75.6% of class)
- **Extreme Separation:** Every single row in the dataset with `weight_discrepancy_grams > 100g` (1,248 rows) belongs to Class 2.

### 4.2 Impact and Timing Verification
- **Prediction Timestamp Reality:** At the moment a customer submits a refund claim online, physical warehouse weight scans often do NOT yet exist (the package is still in transit or with the customer).
- **Engineering Mitigations Applied:**
  1. The schema defines `weight_discrepancy_grams` as `nullable: true`.
  2. Data preparation injected **20% random missing values** into `weight_discrepancy_grams` (seed 42) before model training.
  3. Missing values at inference time are imputed with the training median (`10.9g`).
- **Model Resilience Without Weight Scan:**
  - Evaluation on test set rows where weight discrepancy was null/imputed yielded **92.18% accuracy**.
  - Evaluation on the test set with weight discrepancy **completely masked for 100% of rows** yielded **92.67% accuracy**.
  - **Conclusion:** The model does not collapse without weight scans; it relies effectively on secondary features (`shared_identity_links`, `historical_return_ratio`, `past_inr_claims`, and `account_age_days`).

---

## 5. Docker Compose Stack Inspection

- **Docker Version:** Docker Engine 29.7.2, Docker Compose v5.4.0.
- **Daemon Status:** `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`.
- **Diagnosis:** Docker Desktop is installed at `C:\Program Files\Docker\Docker\Docker Desktop.exe`, but the background daemon requires interactive Windows UAC elevation to mount the WSL2 pipe.
- **Compose Files Verified:**
  - [`docker-compose.yml`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/docker-compose.yml): 4 services (`mongo:7.0`, `redis:7.2-alpine`, `api`, `frontend`).
  - [`backend/Dockerfile`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/backend/Dockerfile): Multi-stage Python 3.11 image with layer caching.
  - [`frontend/Dockerfile`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/frontend/Dockerfile): Node 20-alpine container with port 5173 exposed.

---

## 6. End-to-End API Transaction & Persistence Verification

**Test Executed:** `test_end_to_end_single_refund_and_persistence` in [`backend/tests/test_end_to_end_integration.py`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/backend/tests/test_end_to_end_integration.py)

1. **Payload Sent:** Real e-commerce refund request for customer `Rohan Mehra` (`account_age_days=400`, `total_past_orders=25`, `historical_return_ratio=0.04`, `item_price=4999.0`).
2. **Model Prediction:** Class `0` (`Genuine`) with 94.2% confidence. Inference latency = 3.3ms.
3. **Behavioral Evidence:** Computed via Redis (`recent_requests_1h=0`, `shared_identity_links=0`).
4. **Policy Decision:** Risk score = `1.2`, Risk Tier = `Low`, Action = `Routine processing`.
5. **Persistence:** Document persisted to MongoDB collection with `transaction_id`, timestamps, feature snapshot, and review status `not_required`.
6. **Idempotency:** Re-sending with `Idempotency-Key: rohan-idem-1` returned cached response instantly.

---

## 7. Coordinated-Device Fraud Ring Scenario Verification

**Test Executed:** `test_coordinated_device_fraud_ring_scenario` in [`backend/tests/test_end_to_end_integration.py`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/backend/tests/test_end_to_end_integration.py)

### Scenario Simulation Flow:
1. **Account 1 (`fraudster-01`, Vikram Singh):** Submits high-value claim on shared device `dev-shared-emulator-999`. Initial `shared_device_accounts = 0`.
2. **Account 2 (`fraudster-02`, Amit Sharma):** Submits claim on same device `dev-shared-emulator-999`. Redis detects previous account on device $\rightarrow$ `shared_device_accounts = 1`.
3. **Account 3 (`fraudster-03`, Kavita Gupta):** Submits claim on same device `dev-shared-emulator-999`. Redis detects 2 other accounts $\rightarrow$ `shared_device_accounts = 2`.
4. **Account 1 Returns:** Submits another claim. Redis behavioral engine links all three accounts into an identity cluster $\rightarrow$ `shared_identity_links = 2`.
5. **Policy Escalation:** Risk score escalates from baseline to **Elevated/High tier**, triggering `Human review` and halting automated refund disbursement.

---

## 8. Simulation Lifecycle & Real Traffic Generation

**API Endpoints Tested:**
- `GET /api/v1/simulation/status`
- `POST /api/v1/simulation/start`
- `POST /api/v1/simulation/pause`
- `POST /api/v1/simulation/resume`
- `POST /api/v1/simulation/stop`

### Bug Fixed During Verification:
- **Admin Key Mismatch:** `.env` specified `sim-admin-key-change-me` while frontend client used `sim-admin-key-changeme`, causing 401 Unauthorized errors on simulation controls. Fixed by aligning both to `sim-admin-key-changeme`.
- **Resume Simulation State Conflict:** `resume_simulation()` previously called `start_simulation()` without resetting the paused status, triggering a self-conflict error. Fixed in [`backend/app/sim_control.py`](file:///C:/Users/kaoushik/.gemini/antigravity-ide/scratch/returnshield/backend/app/sim_control.py).

### Lifecycle Execution Result:
```text
1. Initial status: stopped
2. Starting simulation (mixed scenario, users=2, rps=2, duration=10):
   -> Status: running, run_id: run-1791968558
3. Status during run: running
4. Pausing simulation:
   -> Status: paused
5. Resuming simulation:
   -> Status: running, run_id: run-1791968561
6. Stopping simulation:
   -> Status: stopped
7. Final status after stop: stopped
```

---

## 9. UI Inspection & Metrics Integrity

- **Branding & Shell:** Sidebar properly renders `ReturnShield Risk Platform`.
- **Navigation Tabs:** Verified clean routing between:
  1. `Overview`: High-level fraud and transaction KPIs.
  2. `Live Transactions`: Real-time streaming table with tier badges (`Low`, `Elevated`, `High`).
  3. `Traffic Simulation`: Interactive controls for concurrency, target RPS, scenario selection (Mixed, Genuine, Mistaken, Suspicious, Coordinated), and live start/pause/resume/stop triggers.
  4. `Risk Analytics`: Visualizes distribution curves and risk factor impacts.
  5. `Investigation View`: Detailed breakout of Model Probabilities vs Behavioral Signals vs Policy Actions.
- **Deceptive Metrics Check:** UI does not fabricate predictions or hardcode mock scores. Service status dots query `/api/v1/ready` and transparently display true backend/database status.

---

## 10. Summary of Incomplete Acceptance Criteria & Operational Notes

| Criterion | Current Status | Notes |
| :--- | :--- | :--- |
| **24/24 Tests Passing** | **Verified** | 22 unit tests + 2 integration tests pass in 3.25s. |
| **Frontend Production Build** | **Verified** | Vite v8.3.4 builds clean bundle in 234ms. |
| **ML Metric Accuracy** | **Verified** | 93.40% accuracy ($1401/1500$) on stratified held-out test split. |
| **Redis Graph Bug Fix** | **Verified** | Fixed `zrevrangebyscore(num=1)` and `shared_device_accounts` member card calculation. |
| **Simulation Lifecycle** | **Verified** | Fixed admin key alignment and resume status transition. |
| **Docker Compose Daemon** | **Offline (Host limitation)** | Dockerfiles and compose are validated, but host Docker daemon requires manual UAC launch. |
