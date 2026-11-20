import random
from typing import Dict, Any

# Mock service for Policy Management System
class PolicyService:
    def get_policy(self, policy_number: str) -> Dict[str, Any]:
        # Return a synthetic policy record
        return {
            "policy_number": policy_number,
            "policy_type": random.choice(["Life", "Health", "Accident"]),
            "effective_date": "2022-01-01",
            "expiry_date": "2032-01-01",
            "customer_id": f"CUST{random.randint(1000,9999)}",
            "coverage_amount": random.uniform(50000, 500000),
        }

# Mock service for Customer Management System
class CustomerService:
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        return {
            "customer_id": customer_id,
            "name": f"John Doe {random.randint(1,100)}",
            "national_id": f"ID{random.randint(100000,999999)}",
            "date_of_birth": "1980-05-15",
        }

# Mock service for Claims Management System (read‑only placeholder)
class ClaimsService:
    def list_previous_claims(self, policy_number: str) -> list[Dict[str, Any]]:
        # Generate a few synthetic historic claims
        claims = []
        for i in range(random.randint(0, 3)):
            claims.append({
                "claim_id": f"CLM{random.randint(10000,99999)}",
                "policy_number": policy_number,
                "claim_type": random.choice(["Death", "Medical", "Accident"]),
                "amount": random.uniform(1000, 20000),
                "incident_date": "2023-06-01",
                "submission_date": "2023-06-05",
                "status": random.choice(["approved", "rejected", "under_review"]),
            })
        return claims

# Mock service for Payment & Financial Transaction Systems
class PaymentService:
    def verify_payment(self, claim_id: str) -> bool:
        # Randomly decide if payment is eligible (always true for mock)
        return True

# Mock service for Identity Verification Systems
class IdentityVerificationService:
    def verify_identity(self, national_id: str, name: str) -> bool:
        return True
