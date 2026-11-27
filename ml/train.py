import os
import csv
from datetime import datetime, timezone
from backend.app.services.db import SessionLocal, init_db
from backend.app.models.sqlalchemy_models import ModelPerformance
from backend.app.ml.fraud_engine import fraud_engine

def train_and_evaluate_model():
    """Runs evaluation on synthetic historic claims using pure Python standard library."""
    init_db()
    db = SessionLocal()
    
    print("=" * 65)
    print("FIDELITY LIFE ASSURANCE - AI FRAUD MODEL TRAINING & BENCHMARK")
    print("=" * 65)

    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    claims_csv = os.path.join(raw_dir, "claims.csv")
    policies_csv = os.path.join(raw_dir, "policies.csv")
    customers_csv = os.path.join(raw_dir, "customers.csv")

    if not os.path.exists(claims_csv):
        print(f"Generating synthetic training dataset at {raw_dir}...")
        from data.generate_synthetic_data import main as gen_data
        gen_data()

    # Load policies into dict
    policies_map = {}
    if os.path.exists(policies_csv):
        with open(policies_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                policies_map[row["policy_number"]] = row

    # Load customers into dict
    customers_map = {}
    if os.path.exists(customers_csv):
        with open(customers_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                customers_map[row["customer_id"]] = row

    # Read claims
    claims_rows = []
    with open(claims_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims_rows.append(row)

    print(f"Loaded {len(claims_rows)} historical training claims.")

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    history_cache = []

    for row in claims_rows:
        synth_indicators = str(row.get("synthetic_indicators", "")).strip()
        is_actual_fraud = bool(synth_indicators)

        policy_info = policies_map.get(row["policy_number"], {
            "policy_number": row["policy_number"],
            "coverage_amount": 50000.0,
            "effective_date": "2023-01-01",
        })

        customer_info = customers_map.get(row["customer_id"], {
            "customer_id": row["customer_id"],
            "national_id": "63-999888-A-12",
        })

        claim_dict = {
            "claim_id": row["claim_id"],
            "policy_number": row["policy_number"],
            "amount": float(row["amount"]),
            "incident_date": row["incident_date"],
            "submission_date": row["submission_date"],
            "claim_type": row["claim_type"],
        }

        # TARGET-LEAKAGE GUARD: `synthetic_indicators` is the ground-truth label
        # source (is_actual_fraud == bool(synthetic_indicators)). Deriving
        # `recent_beneficiary_change` from it would leak the label into the
        # RECENT_BENEFICIARY_ALTERATION rule. Real beneficiary-change events
        # are a separate signal not present in this synthetic CSV, so we do NOT
        # infer them from the label.
        recent_change = False

        assessment = fraud_engine.evaluate_claim(
            claim_data=claim_dict,
            policy_data=policy_info,
            customer_data=customer_info,
            historical_claims=history_cache[-15:],  # test duplicate against recent history
            recent_beneficiary_change=recent_change,
        )

        history_cache.append(claim_dict)

        predicted_fraud = assessment["risk_category"] in ["High", "Critical"]

        if is_actual_fraud and predicted_fraud:
            true_positives += 1
        elif not is_actual_fraud and predicted_fraud:
            false_positives += 1
        elif not is_actual_fraud and not predicted_fraud:
            true_negatives += 1
        elif is_actual_fraud and not predicted_fraud:
            false_negatives += 1

    total = len(claims_rows)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    print("-" * 65)
    print("Validated Benchmark Performance against Historical Scenarios:")
    print(f"  • Total Evaluated Claims:  {total}")
    print(f"  • True Positives:          {true_positives}")
    print(f"  • False Positives:         {false_positives}")
    print(f"  • True Negatives:          {true_negatives}")
    print(f"  • False Negatives:         {false_negatives}")
    print(f"  • Precision:               {precision:.4f} ({precision * 100:.2f}%)")
    print(f"  • Recall:                  {recall:.4f} ({recall * 100:.2f}%)")
    print(f"  • F1-Score:                {f1:.4f} ({f1 * 100:.2f}%)")
    print("-" * 65)

    perf = ModelPerformance(
        model_name="NEXA-LifeFraud-HybridEnsemble",
        version=fraud_engine.version,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        evaluated_at=datetime.now(timezone.utc),
    )
    db.add(perf)
    db.commit()
    db.close()
    print("Model performance metrics saved to database.")

if __name__ == "__main__":
    train_and_evaluate_model()
