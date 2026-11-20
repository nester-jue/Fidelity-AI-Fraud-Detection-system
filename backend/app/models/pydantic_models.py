from pydantic import BaseModel, Field
from typing import Optional, List

class ClaimBase(BaseModel):
    policy_number: str = Field(..., description="Policy number associated with the claim")
    claim_type: str = Field(..., description="Type of claim, e.g., death benefit, medical")
    claim_date: str = Field(..., description="ISO date of claim submission")
    claim_amount: float = Field(..., description="Monetary amount claimed")
    beneficiary_name: Optional[str] = None

class ClaimCreate(ClaimBase):
    documents: List[str] = []  # filenames or storage IDs

class ClaimResponse(ClaimBase):
    id: int
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None
    explanation: Optional[str] = None

    class Config:
        orm_mode = True
