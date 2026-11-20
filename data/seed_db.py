import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import SessionLocal, init_db
from backend.app.models.sqlalchemy_models import (
    User, RoleEnum, Customer, Policy, Claim, ClaimDocument, FraudAssessment, Investigation, AuditLog, Notification
)
from backend.app.auth import get_password_hash
from backend.app.ml.fraud_engine import fraud_engine

def seed_database():
    print("=" * 65)
    print("FIDELITY LIFE ASSURANCE - POPULATING SEED & DEMONSTRATION DATA")
    print("=" * 65)

    init_db()
    db = SessionLocal()

    # 1. Clean existing tables if needed or check if already seeded
    if db.query(User).filter(User.username == "admin").first():
        print("Database already contains seed users. Re-seeding claims and cases...")
    else:
        # 2. Seed Enterprise Users (6 required roles)
        users = [
            User(
                username="admin",
                full_name="Admire Chidzero (System Admin)",
                email="admin@fidelitylife.co.zw",
                hashed_password=get_password_hash("AdminPass123!"),
                role=RoleEnum.SYSTEM_ADMIN,
                is_active=True,
            ),
            User(
                username="claims.officer",
                full_name="Tendai Moyo (Claims Officer)",
                email="tmoyo@fidelitylife.co.zw",
                hashed_password=get_password_hash("OfficerPass123!"),
                role=RoleEnum.CLAIMS_OFFICER,
                is_active=True,
            ),
            User(
                username="claims.manager",
                full_name="Rudo Shumba (Claims Manager)",
                email="rshumba@fidelitylife.co.zw",
                hashed_password=get_password_hash("ManagerPass123!"),
                role=RoleEnum.CLAIMS_MANAGER,
                is_active=True,
            ),
            User(
                username="investigator",
                full_name="Farai Ncube (Senior Fraud Investigator)",
                email="fncube@fidelitylife.co.zw",
                hashed_password=get_password_hash("Investigate123!"),
                role=RoleEnum.FRAUD_INVESTIGATOR,
                is_active=True,
            ),
            User(
                username="compliance",
                full_name="Nyasha Zhou (Compliance Officer)",
                email="nzhou@fidelitylife.co.zw",
                hashed_password=get_password_hash("Compliance123!"),
                role=RoleEnum.COMPLIANCE_OFFICER,
                is_active=True,
            ),
            User(
                username="executive",
                full_name="Dr. Tinashe Dube (Chief Risk Officer)",
                email="tdube@fidelitylife.co.zw",
                hashed_password=get_password_hash("Executive123!"),
                role=RoleEnum.MANAGEMENT,
                is_active=True,
            ),
        ]
        db.add_all(users)
        db.commit()
        print(f"Created {len(users)} enterprise demonstration users across all roles.")

    # 3. Seed Customers & Policies
    if db.query(Customer).count() < 5:
        customers_data = [
            ("CUST-1001", "Simbarashe Mpofu", "63-289412-A-18", "1978-04-12"),
            ("CUST-1002", "Chipo Ndlovu", "08-119420-X-42", "1985-09-23"),
            ("CUST-1003", "Tatenda Mutasa", "29-389104-B-71", "1969-11-05"),
            ("CUST-1004", "Blessing Tshuma", "15-782190-C-09", "1991-02-18"),
            ("CUST-1005", "Nomsa Sibanda", "63-490218-D-88", "1982-07-30"),
            ("CUST-1006", "Kudakwashe Gumbo", "44-590123-K-15", "1975-12-14"),
            ("CUST-1007", "Grace Chirwa", "63-718290-E-33", "1994-06-25"),
        ]

        cust_objs = []
        for cid, name, nat_id, dob in customers_data:
            c = Customer(
                customer_id=cid,
                name=name,
                national_id=nat_id,
                date_of_birth=datetime.fromisoformat(dob),
            )
            db.add(c)
            cust_objs.append(c)
        db.commit()

        # Policies
        policies_data = [
            ("POL-LIF-801294", "Life Assurance", cust_objs[0].id, "2021-03-01", "2041-03-01", 100000.0),
            ("POL-FUN-409182", "Funeral Cash Plan", cust_objs[0].id, "2023-01-15", "2033-01-15", 25000.0),
            ("POL-LIF-918234", "Group Life Scheme", cust_objs[1].id, "2026-08-01", "2036-08-01", 75000.0),  # Recent policy
            ("POL-ACC-312984", "Personal Accident", cust_objs[2].id, "2022-05-10", "2032-05-10", 50000.0),
            ("POL-LIF-102938", "Life Assurance", cust_objs[3].id, "2026-10-01", "2046-10-01", 150000.0),  # Very recent
            ("POL-FUN-592810", "Funeral Cash Plan", cust_objs[4].id, "2020-09-12", "2030-09-12", 20000.0),
            ("POL-LIF-772910", "Life Assurance", cust_objs[5].id, "2019-11-20", "2039-11-20", 80000.0),
        ]

        for p_num, p_type, c_id, eff, exp, cov in policies_data:
            p = Policy(
                policy_number=p_num,
                policy_type=p_type,
                customer_id=c_id,
                effective_date=datetime.fromisoformat(eff),
                expiry_date=datetime.fromisoformat(exp),
            )
            setattr(p, "coverage_amount", cov)
            db.add(p)
        db.commit()
        print(f"Created {len(customers_data)} customers and {len(policies_data)} active insurance policies.")

    # 4. Seed Diverse Claims with Authentic Life Assurance Scenarios
    existing_claims_count = db.query(Claim).count()
    if existing_claims_count < 10:
        p1 = db.query(Policy).filter(Policy.policy_number == "POL-LIF-801294").first()
        p2 = db.query(Policy).filter(Policy.policy_number == "POL-LIF-918234").first()
        p3 = db.query(Policy).filter(Policy.policy_number == "POL-LIF-102938").first()
        p4 = db.query(Policy).filter(Policy.policy_number == "POL-ACC-312984").first()
        p5 = db.query(Policy).filter(Policy.policy_number == "POL-FUN-592810").first()

        investigator_user = db.query(User).filter(User.username == "investigator").first()

        scenarios = [
            # SCENARIO 1: Critical Risk - Exact Duplicate Claim
            {
                "claim_id": "CLM-2026-9001",
                "policy": p1,
                "type": "Death Benefit",
                "amount": 45000.0,
                "incident_date": "2026-05-10",
                "submission_date": "2026-05-20",
                "desc": "Initial death benefit claim submitted with authentic hospital death confirmation.",
                "status": "approved",
                "fake_dup": False,
            },
            {
                "claim_id": "CLM-2026-9002",
                "policy": p1,
                "type": "Death Benefit",
                "amount": 45000.0,
                "incident_date": "2026-05-10",
                "submission_date": "2026-08-14",
                "desc": "Resubmitted death benefit claim for same insured event using duplicate medical records.",
                "status": "flagged",
                "fake_dup": True,
            },
            # SCENARIO 2: Critical Risk - Policy Inception Fraud (< 15 days from start)
            {
                "claim_id": "CLM-2026-9003",
                "policy": p3,  # Started 2026-10-01
                "type": "Death Benefit",
                "amount": 140000.0,
                "incident_date": "2026-10-12",  # 11 days after policy commencement!
                "submission_date": "2026-10-16",
                "desc": "Sudden terminal cardiac arrest reported 11 days following policy commencement.",
                "status": "flagged",
                "fake_dup": False,
            },
            # SCENARIO 3: Critical Risk - Fictitious Death & Beneficiary Alteration
            {
                "claim_id": "CLM-2026-9004",
                "policy": p2,
                "type": "Death Benefit",
                "amount": 75000.0,
                "incident_date": "2026-09-18",
                "submission_date": "2026-09-25",
                "desc": "Claim filed immediately after sudden emergency change of sole designated beneficiary.",
                "status": "under_investigation",
                "fake_dup": False,
                "recent_beneficiary_change": True,
            },
            # SCENARIO 4: High Risk - Inflated Claim Value
            {
                "claim_id": "CLM-2026-9005",
                "policy": p4,  # Coverage 50000
                "type": "Accidental Death",
                "amount": 115000.0,  # Exceeds maximum limit
                "incident_date": "2026-07-22",
                "submission_date": "2026-08-01",
                "desc": "High claim demand submitted exceeding policy schedule benefit limits.",
                "status": "flagged",
                "fake_dup": False,
            },
            # SCENARIO 5: Genuine Low Risk Claims
            {
                "claim_id": "CLM-2026-9006",
                "policy": p5,
                "type": "Funeral Expense",
                "amount": 12000.0,
                "incident_date": "2026-06-15",
                "submission_date": "2026-06-20",
                "desc": "Standard funeral cash plan claim with verified clinic death certificate.",
                "status": "approved",
                "fake_dup": False,
            },
            {
                "claim_id": "CLM-2026-9007",
                "policy": p1,
                "type": "Funeral Expense",
                "amount": 8500.0,
                "incident_date": "2026-01-10",
                "submission_date": "2026-01-14",
                "desc": "Routine funeral assistance payout with verified receipts and death certificate.",
                "status": "cleared",
                "fake_dup": False,
            },
            {
                "claim_id": "CLM-2026-9008",
                "policy": p4,
                "type": "Personal Accident",
                "amount": 18500.0,
                "incident_date": "2026-04-05",
                "submission_date": "2026-04-18",
                "desc": "Road traffic injury disability compensation with official police and hospital report.",
                "status": "in_review",
                "fake_dup": False,
            },
        ]

        history_so_far = []
        for sc in scenarios:
            policy_obj = sc["policy"]
            claim = Claim(
                claim_id=sc["claim_id"],
                policy_id=policy_obj.id,
                customer_id=policy_obj.customer_id,
                claim_type=sc["type"],
                amount=sc["amount"],
                incident_date=datetime.fromisoformat(sc["incident_date"]),
                submission_date=datetime.fromisoformat(sc["submission_date"]),
                description=sc["desc"],
                status=sc["status"],
            )
            db.add(claim)
            db.commit()
            db.refresh(claim)

            # Evaluate with AI Fraud Engine
            policy_dict = {
                "policy_number": policy_obj.policy_number,
                "policy_type": policy_obj.policy_type,
                "effective_date": policy_obj.effective_date.isoformat(),
                "coverage_amount": getattr(policy_obj, "coverage_amount", 50000.0),
            }
            cust_dict = {
                "customer_id": policy_obj.customer.customer_id,
                "national_id": policy_obj.customer.national_id,
            }

            eval_res = fraud_engine.evaluate_claim(
                claim_data={
                    "claim_id": claim.claim_id,
                    "policy_number": policy_dict["policy_number"],
                    "amount": claim.amount,
                    "incident_date": claim.incident_date.isoformat(),
                    "submission_date": claim.submission_date.isoformat(),
                    "claim_type": claim.claim_type,
                },
                policy_data=policy_dict,
                customer_data=cust_dict,
                historical_claims=history_so_far if sc.get("fake_dup") else [],
                recent_beneficiary_change=sc.get("recent_beneficiary_change", False),
            )

            history_so_far.append({
                "claim_id": claim.claim_id,
                "policy_number": policy_dict["policy_number"],
                "amount": claim.amount,
                "incident_date": claim.incident_date.isoformat(),
            })

            assessment = FraudAssessment(
                claim_id=claim.id,
                risk_score=eval_res["risk_score"],
                risk_category=eval_res["risk_category"],
                indicators=eval_res["indicators"],
                explanation=eval_res["explanation"],
                model_version=eval_res["model_version"],
                assessed_at=datetime.now(timezone.utc),
            )
            db.add(assessment)

            # If high or critical, link an investigation
            if eval_res["risk_category"] in ["High", "Critical"]:
                inv = Investigation(
                    claim_id=claim.id,
                    investigator_id=investigator_user.id if investigator_user else 1,
                    status="in_review" if sc["claim_id"] != "CLM-2026-9002" else "confirmed_fraud",
                    notes=f"Priority AI Trigger [{eval_res['risk_category']} Risk]: {eval_res['explanation']}",
                    opened_at=datetime.now(timezone.utc) - timedelta(days=2),
                )
                if sc["claim_id"] == "CLM-2026-9002":
                    inv.closed_at = datetime.now(timezone.utc)
                    inv.notes += "\n[Investigator Conclusion] Confirmed duplicate submission of prior claim CLM-2026-9001. Claim rejected and referred to Legal."
                db.add(inv)

            db.commit()

        # Seed initial audit logs and notifications
        db.add(AuditLog(
            user_id=1,
            action="SYSTEM_INITIALIZED",
            target="NEXA-AI-Fraud-Engine",
            detail={"version": "1.0.0", "status": "Ready"},
        ))
        db.add(Notification(
            recipient_id=1,
            message="NEXA AI Fraud Engine active. 4 high-priority claims queued for review.",
            read=False,
        ))
        db.commit()
        print(f"Successfully seeded {len(scenarios)} realistic claims with AI fraud evaluations and investigation cases.")

    db.close()
    print("=" * 65)
    print("DEMO DATA SEEDING COMPLETE")
    print("Default Login Credentials:")
    print("  • System Admin:         admin / AdminPass123!")
    print("  • Claims Officer:       claims.officer / OfficerPass123!")
    print("  • Claims Manager:       claims.manager / ManagerPass123!")
    print("  • Fraud Investigator:   investigator / Investigate123!")
    print("  • Compliance Officer:   compliance / Compliance123!")
    print("  • Executive Management: executive / Executive123!")
    print("=" * 65)

if __name__ == "__main__":
    seed_database()
