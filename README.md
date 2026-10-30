# ReturnShield 🛡️

> **ML-Assisted Refund & Return Abuse Prevention Platform**  

> *Problem Statement #6: Detecting Refund and Return Abuse*

## Built in a 6-Hour Hackathon

ReturnShield was developed by Team Runtime Terror during a 6-hour hackathon. We began by reviewing and analyzing the available problem statements, discussing their real-world relevance, and identifying a challenge where technology could make a meaningful difference. After comparing the options, our team selected Problem Statement #6: Detecting Refund and Return Abuse.

We then researched the problem, explored how e-commerce platforms can distinguish genuine customer returns from potentially abusive claims, and designed a prototype combining machine learning, real-time behavioral signals, risk scoring, and a review workflow.

The result is ReturnShield, an ML-assisted platform designed to assess refund and return claims while keeping model predictions, behavioral evidence, and risk-policy decisions separate.

## Team Runtime Terror
- Kaoushik Kalyaan Nammi
- Ravi Teja Dasari
- Addari Vidyadhar
- Bhavani Krishna Jakkam
## Results at a Glance
Evaluation	Reported result
Held-out ML classification accuracy	93.4%
Genuine-class F1-score	0.96
Mistaken-class F1-score	0.91
Suspicious-class F1-score	0.88
Automated software tests	22 passed in 3.19 seconds
Load testing	Locust scenarios included; benchmark figures should be added after a measured run


Model metrics and test results reflect the project’s recorded evaluation. Reproduce them against the current code and dataset before presenting them as independently verified benchmarks.

---

## 📑 Table of Contents

1. [Core Architecture & Principles](#core-architecture--principles)

2. [Technology Stack](#technology-stack)

3. [Machine Learning Contract & Feature Schema](#machine-learning-contract--feature-schema)

4. [Dataset Audit & Leakage Mitigation](#dataset-audit--leakage-mitigation)

5. [Risk Policy & Separation of Concerns](#risk-policy--separation-of-concerns)

6. [Testing & Verification](#testing--verification)

7. [Local & Docker Deployment](#local--docker-deployment)

8. [Live Demonstration Script (3-Minute Walkthrough)](#live-demonstration-script-3-minute-walkthrough)

9. [Project Checklist & Deliverable Status](#project-checklist--deliverable-status)

---

## 1. Core Architecture & Principles

ReturnShield enforces four fundamental architectural invariants:

1. **Separation of Model, Evidence, and Policy**: The XGBoost classifier outputs calibrated probabilities for three classes (`Genuine`, `Mistaken`, `Suspicious`). The behavioral engine tracks multi-account identity graphs and velocity in Redis. The risk policy module combines both into an actionable risk score (0–100) and workflow tier.

2. **Authoritative Behavioral State**: Client-submitted claims can never supply or tamper with historical graph links or velocity. Redis computes `shared_identity_links` and velocity windows authoritatively.

3. **Graceful Degradation**: If hardware scan weights are missing at claim time (`weight_discrepancy_grams`), the pipeline imputes with median training weights without pipeline failure.

4. **Transparent Auditability**: Every transaction snapshot stores raw input features, Redis graph snapshots, model probabilities, and contributing domain factors.

```

                           +------------------------+

                           |  E-Commerce Client /   |

                           | Locust Traffic Engine  |

                           +-----------+------------+

                                       | POST /api/v1/refunds

                                       v

                           +------------------------+

                           |  FastAPI Backend Core  |

                           +-----+------------+-----+

                                 |            |

           Authoritative Signals |            | Real-time Read/Write

                                 v            v

                       +-------------+   +---------------+

                       | Redis Graph |   | MongoDB Store |

                       | (Velocity & |   | (Transactions |

                       | Identities) |   |  Audit Trail) |

                       +------+------+   +---------------+

                              |

                     Authoritative Features

                              |

                              v

             +----------------------------------+

             |  XGBoost Classifier (12 Features)|

             |  P(Genuine, Mistaken, Suspicious)|

             +----------------+-----------------+

                              |

                              v

             +----------------------------------+

             |    Risk Decision Policy Engine   |

             |   Score (0-100) -> Low/Elevated/ |

             |              High Tier           |

             +----------------+-----------------+

                              |

                              v SSE Live Event Stream

             +----------------------------------+

             | React / Vite Enterprise Dashboard|

             |   (Live Table, Recharts, Alerts) |

             +----------------------------------+

```

---

## 2. Technology Stack

- **ML & Inference**: Python 3.11/3.14, XGBoost 3.2.0, Scikit-learn 1.8, Pandas, NumPy

- **Backend API**: FastAPI 0.115, Pydantic v2, Uvicorn, Motor (Async MongoDB), Redis-py (AsyncIO)

- **Data Stores**: Redis 7.2 (real-time identity graph, velocity windows), MongoDB 7.0 (audit trail & decisions)

- **Traffic Simulation**: Locust 2.46+ (real concurrent HTTP load generator with scenario controls)

- **Frontend Dashboard**: React 18, Vite 8, Recharts, Vanilla CSS Design System with dark fintech palette

- **Deployment**: Multi-container Docker Compose with health checks

---

## 3. Machine Learning Contract & Feature Schema

ReturnShield strictly adheres to a single source of truth defined in [`shared/feature_schema.py`](shared/feature_schema.py) (`SCHEMA_HASH: 71b5937057f82bc0`):

| # | Feature Name | Type | Range / Values | Inference Origin | Description |

|---|--------------|------|----------------|------------------|-------------|

| 1 | `account_age_days` | int | [0, 36500] | Merchant profile | Days since account creation |

| 2 | `total_past_orders` | int | [0, 100000] | Merchant profile | Lifetime completed order count |

| 3 | `historical_return_ratio` | float | [0.0, 1.0] | Merchant profile | Past returns / past orders |

| 4 | `past_inr_claims` | int | [0, 1000] | Merchant profile | "Item Not Received" / empty-box claims |

| 5 | `item_price` | float | [0.01, 10,000,000] | Order cart | Value of item being claimed (INR) |

| 6 | `product_category_code` | int | 1..5 | Order cart | 1: Electronics, 2: Apparel, 3: Footwear, 4: Home, 5: Books |

| 7 | `return_reason_code` | int | 1..5 | Claim form | 1: Wrong Size, 2: Defective, 3: Empty Box, 4: Damaged, 5: Changed Mind |

| 8 | `hours_since_delivery` | float | [0.0, 87600.0] | Logistics | Elapsed time between delivery scan and claim |

| 9 | `weight_discrepancy_grams` | float (nullable) | [0.0, 50000.0] | Warehouse scan | Nullable at request time; imputed with training median (10.9g) |

| 10 | `shared_identity_links` | int | [0, 10000] | **Redis Graph** | **Authoritative**: Number of accounts linked by device/payment |

| 11 | `is_cod_order` | int | {0, 1} | Order cart | 1 if Cash-on-Delivery, 0 otherwise |

| 12 | `purchased_in_sale` | int | {0, 1} | Order cart | 1 if bought during promotional campaign |

---

## 4. Dataset Audit & Leakage Mitigation

The primary training dataset (`data/raw/train_data.csv`, SHA-256: `ccfc16f5d75d6a0f8259000b66404c54a0851b025c888aa40291c507c17b825c`) was comprehensively audited (see [`docs/dataset_audit.md`](docs/dataset_audit.md)):

- **Total Rows**: 10,000 records

- **Class Breakdown**: Genuine (57.8%), Mistaken (25.7%), Suspicious (16.5%)

- **Data Leakage Discovery**: In the raw dataset, every record with `weight_discrepancy_grams > 100g` belonged exclusively to label `2 (Suspicious)` (mean 274.6g vs 10.4g for Genuine).

- **Engineering Mitigation**: To prevent the tree model from degenerating into a simple single-feature split, we injected **20% random nulls** during data preparation (`ml/prepare_data.py`), computed the training median (`10.9g`), and trained with median imputation and sample weighting.

- **Model Performance**: Held-out test set accuracy is **93.4%** with balanced F1-scores (Genuine: 0.96, Mistaken: 0.91, Suspicious: 0.88).

---

## 5. Risk Policy & Separation of Concerns

The risk score is computed by a versioned, auditable formula:

\(\text{Base Score} = 100 \times \left(P(\text{Suspicious}) + 0.3 \times P(\text{Mistaken})\right)\)

\(\text{Risk Score} = \min(100, \max(0, \text{Base Score} + \text{Behavioral Overlay}))\)

### Behavioral Overlay Rules:

- \(+10\) points if recent refund requests within 1 hour \(\ge 3\)

- \(+18\) points if recent refund requests within 1 hour \(\ge 5\)

- \(+12\) points if linked identity accounts \(\ge 2\)

- \(+8\) points if shared device accounts \(\ge 3\)

- \(+10\) points if repeated return attempts \(\ge 3\)

### Operational Action Tiers:

- **Low Risk (`0 – 34.9`)**: Routine processing (instant refund eligible)

- **Elevated Risk (`35.0 – 64.9`)**: Additional verification required (receipt scan, packaging photo)

- **High Risk (`65.0 – 100.0`)**: Human review queue / physical return inspection required

---

## 6. Testing & Verification

ReturnShield features a test suite with **22 passing tests** across ML inference, feature contracts, API endpoints, risk formulas, and load generators.

Run the test suite locally:

```bash

python -m pytest -v

```

### Verified Test Results:

```text

backend/tests/test_api_endpoints.py::test_health_endpoint PASSED         [  4%]

backend/tests/test_api_endpoints.py::test_simulation_status PASSED       [  9%]

backend/tests/test_api_endpoints.py::test_refund_validation_error_missing_fields PASSED [ 13%]

backend/tests/test_api_endpoints.py::test_refund_assessment_flow_success PASSED [ 18%]

backend/tests/test_feature_schema.py::test_feature_count_and_order PASSED [ 22%]

backend/tests/test_feature_schema.py::test_schema_hash_consistency PASSED [ 27%]

backend/tests/test_feature_schema.py::test_label_mapping PASSED          [ 31%]

backend/tests/test_feature_schema.py::test_product_category_and_return_reason_mappings PASSED [ 36%]

backend/tests/test_feature_schema.py::test_nullable_and_redis_computed_spec PASSED [ 40%]

backend/tests/test_feature_schema.py::test_validate_feature_vector_valid PASSED [ 45%]

backend/tests/test_feature_schema.py::test_validate_feature_vector_invalid_range PASSED [ 50%]

backend/tests/test_locust_generators.py::test_genuine_generator PASSED   [ 54%]

backend/tests/test_locust_generators.py::test_mistaken_generator PASSED  [ 59%]

backend/tests/test_locust_generators.py::test_suspicious_generator PASSED [ 63%]

backend/tests/test_model_inference.py::test_model_loaded_and_metadata_verified PASSED [ 68%]

backend/tests/test_model_inference.py::test_predict_genuine_profile PASSED [ 72%]

backend/tests/test_model_inference.py::test_predict_suspicious_profile PASSED [ 77%]

backend/tests/test_risk_policy.py::test_pure_genuine_low_risk PASSED     [ 81%]

backend/tests/test_risk_policy.py::test_suspicious_high_risk PASSED      [ 86%]

backend/tests/test_risk_policy.py::test_elevated_tier_with_behavioral_overlay PASSED [ 90%]

backend/tests/test_risk_policy.py::test_risk_score_clamping PASSED       [ 95%]

backend/tests/test_risk_policy.py::test_top_factors_includes_disclaimer_and_signals PASSED [100%]

======================= 22 passed in 3.19s =======================

```

---

## 7. Local & Docker Deployment

### Prerequisites:

- Python 3.11+

- Node.js 18+

- Docker & Docker Compose (optional for local standalone mode)

### Option A: Local Standalone Development (Fastest)

1. **Environment Configuration**:

   ```bash

   cp .env.example .env

   ```

2. **Backend Server**:

   ```bash

   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

   ```

   - Health check: `http://127.0.0.1:8000/api/v1/health`

   - Interactive Swagger API documentation: `http://127.0.0.1:8000/api/v1/docs`

3. **Frontend Dashboard**:

   ```bash

   cd frontend

   npm install

   npm run dev

   ```

   - Visit dashboard at `http://localhost:5173`

### Option B: Complete Docker Compose Deployment

When Docker Desktop daemon is started:

```bash

docker compose up --build

```

Services deployed:

- `rs_mongo`: MongoDB 7.0 (Port 27017)

- `rs_redis`: Redis 7.2 (Port 6379)

- `rs_api`: FastAPI Backend (Port 8000)

- `rs_frontend`: React Fintech Dashboard (Port 5173)

---

## 8. Live Demonstration Script (3-Minute Walkthrough)

### Minute 1: The Problem & Baseline Live Traffic

1. Open the ReturnShield dashboard at `http://localhost:5173`.

2. Notice the **Service Status Indicators** in the sidebar (Model: Online, Redis, MongoDB).

3. Navigate to **Traffic Simulation** tab. Click **"Start Live Simulation"** under the *Mixed Baseline* scenario (5 users, 5 req/sec).

4. Watch the live Server-Sent Events (SSE) populate the **Live Transactions** table in real time with millisecond latencies (~3ms inference).

### Minute 2: Simulating Coordinated Fraud Rings

1. Change the simulation scenario dropdown to **"Coordinated Abuse"** (multiple accounts sharing device IDs and payment tokens).

2. Observe how transactions trigger the Redis behavioral graph engine:

   - Notice the `shared_identity_links` incrementing across different customer names.

   - The risk tier elevates from *Routine* to *Human Review* even when individual transaction features appear moderate.

3. Click on any high-risk transaction in the table to open the **Transaction Investigation View**.

### Minute 3: Explainable Risk Signals & Decision Separation

1. In the **Investigation View**, observe:

   - **Model Prediction**: Raw calibrated probabilities (e.g., \(P(\text{Suspicious}) = 0.88\)).

   - **Behavioral Evidence**: Redis velocity counts and device sharing graph.

   - **Policy Action**: "Human review" with recommended hold on automatic refund disbursement.

   - **Top Contributing Factors**: High weight discrepancy scan and linked identity accounts.

2. Demonstrate the analyst review workflow: select "Approve with Escalation" or "Reject Refund" to update the MongoDB audit trail.

---

## 9. Project Checklist & Deliverable Status

| Component | Status | Verification Evidence |

|-----------|--------|----------------------|

| **Dataset Audit & Integrity** | **Verified** | SHA-256 matched (`ccfc16f5...`), `docs/dataset_audit.md` and `audit_report.json` generated |

| **Data Leakage Mitigation** | **Verified** | 20% weight discrepancy null injection, median imputation (10.9g) |

| **Model Training & Artifacts** | **Verified** | 3-class XGBoost, 93.4% accuracy, `model.pkl` + `model_metadata.json` |

| **Schema Contract** | **Verified** | Single source of truth in `shared/feature_schema.py` (`SCHEMA_HASH: 71b5937057f82bc0`) |

| **Risk Policy Engine** | **Verified** | Strict separation of prediction, evidence & policy; unit tested with 100% pass |

| **FastAPI Backend** | **Verified** | Pydantic validation, health & ready endpoints, SSE streaming |

| **Locust Traffic Generator** | **Verified** | 5 scenarios (mixed, genuine, mistaken, suspicious, coordinated); pure generator tests |

| **Enterprise Frontend** | **Verified** | Built with Vite 8 + Recharts, dark fintech theme, 5 pages (Overview, Live Tx, Sim, Analytics, Inspect) |

| **Automated Test Suite** | **Verified** | 22/22 unit & integration tests passing (`python -m pytest -v`) |

| **Docker Configuration** | **Verified** | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |