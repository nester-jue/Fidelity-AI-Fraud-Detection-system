import os
import random
import uuid
import csv
from datetime import datetime, timedelta

# Directory where synthetic CSVs will be stored
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "raw"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def generate_customers(n=60):
    customers = []
    first_names = ["Tendai", "Chipo", "Farai", "Tatenda", "Rudo", "Simbarashe", "Nyasha", "Kudakwashe", "Blessing", "Tinashe", "Grace", "Nomsa", "Tapiwa"]
    last_names = ["Moyo", "Ncube", "Sibanda", "Mpofu", "Dube", "Gumbo", "Chirwa", "Mutasa", "Ndlovu", "Zhou", "Shumba", "Tshuma"]
    
    for i in range(n):
        cust_id = f"CUST{1000 + i}"
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        nat_id = f"{random.randint(10, 99)}-{random.randint(100000, 999999)}-{random.choice(['A','B','C','D','X'])}-{random.randint(10, 99)}"
        dob = (datetime.now() - timedelta(days=random.randint(22*365, 72*365))).date().isoformat()
        customers.append({
            "customer_id": cust_id,
            "name": name,
            "national_id": nat_id,
            "date_of_birth": dob,
        })
    return customers

def generate_policies(customers, n_per_customer=2):
    policies = []
    policy_types = ["Life Assurance", "Funeral Cash Plan", "Personal Accident", "Group Life", "Retirement Annuity"]
    for cust in customers:
        num_policies = random.randint(1, n_per_customer)
        for _ in range(num_policies):
            policy_number = f"POL-{random.choice(['LIF','FUN','ACC','GRP'])}-{random.randint(100000, 999999)}"
            p_type = random.choice(policy_types)
            effective = (datetime.now() - timedelta(days=random.randint(10, 365*6))).date().isoformat()
            expiry = (datetime.now() + timedelta(days=random.randint(365, 365*15))).date().isoformat()
            coverage = random.choice([25000.0, 50000.0, 75000.0, 100000.0, 150000.0, 250000.0])
            policies.append({
                "policy_number": policy_number,
                "policy_type": p_type,
                "customer_id": cust["customer_id"],
                "effective_date": effective,
                "expiry_date": expiry,
                "coverage_amount": coverage,
            })
    return policies

def generate_claims(policies, n=150):
    claims = []
    claim_types = ["Death Benefit", "Funeral Expense", "Accidental Death", "Critical Illness", "Disability"]
    
    for i in range(n):
        policy = random.choice(policies)
        claim_id = f"CLM-2026-{random.randint(10000, 99999)}"
        claim_type = random.choice(claim_types)
        coverage = float(policy.get("coverage_amount", 50000.0))
        
        # Base realistic claim amount
        amount = round(random.uniform(5000.0, coverage * 0.8), 2)
        eff_dt = datetime.fromisoformat(policy["effective_date"])
        
        # Standard incident date after inception
        incident_dt = eff_dt + timedelta(days=random.randint(70, 700))
        if incident_dt > datetime.now():
            incident_dt = datetime.now() - timedelta(days=random.randint(5, 60))
        
        submission_dt = incident_dt + timedelta(days=random.randint(2, 25))
        incident_str = incident_dt.date().isoformat()
        submission_str = submission_dt.date().isoformat()
        description = f"Claim for {claim_type} under policy {policy['policy_number']}."
        
        indicators = []
        
        # Fraud Scenarios
        scenario_dice = random.random()
        if scenario_dice < 0.08:
            # 1. Duplicate claim
            if claims:
                prior = random.choice(claims)
                incident_str = prior["incident_date"]
                amount = prior["amount"]
                description = f"Resubmitted claim duplicate of incident on {incident_str}"
                indicators.append("duplicate_claim")
        elif scenario_dice < 0.15:
            # 2. Inception fraud: incident within 15 days of policy commencement
            incident_dt = eff_dt + timedelta(days=random.randint(3, 20))
            incident_str = incident_dt.date().isoformat()
            submission_str = (incident_dt + timedelta(days=3)).date().isoformat()
            description = f"Death claim filed immediately following policy inception."
            indicators.append("early_policy_inception")
        elif scenario_dice < 0.22:
            # 3. Inflated claim: amount exceeding coverage limit
            amount = round(coverage * random.uniform(1.3, 2.5), 2)
            description = f"Inflated claim value requested exceeding standard product limits."
            indicators.append("inflated_amount")
        elif scenario_dice < 0.28:
            # 4. Beneficiary manipulation / identity mismatch
            description = f"Claim submitted following emergency change in designated beneficiary."
            indicators.append("beneficiary_alteration")

        claims.append({
            "claim_id": claim_id,
            "policy_number": policy["policy_number"],
            "customer_id": policy["customer_id"],
            "claim_type": claim_type,
            "amount": amount,
            "incident_date": incident_str,
            "submission_date": submission_str,
            "description": description,
            "status": "flagged" if indicators else "submitted",
            "synthetic_indicators": ",".join(indicators) if indicators else "",
        })
    return claims

def save_csv(filename, rows, fieldnames):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} records in {filepath}")

def main():
    customers = generate_customers()
    save_csv("customers.csv", customers, ["customer_id", "name", "national_id", "date_of_birth"])

    policies = generate_policies(customers)
    save_csv("policies.csv", policies, ["policy_number", "policy_type", "customer_id", "effective_date", "expiry_date", "coverage_amount"])

    claims = generate_claims(policies)
    save_csv("claims.csv", claims, ["claim_id", "policy_number", "customer_id", "claim_type", "amount", "incident_date", "submission_date", "description", "status", "synthetic_indicators"])
    print("Synthetic data generation finished successfully.")

if __name__ == "__main__":
    main()
