"""Zimbabwe Insurance Intelligence API (Phase 9).

Configuration, validation and compliance tools for the Zimbabwean
insurance operating environment. All rules are configurable defaults
documented as such; administrators verify against current legislation
with legal counsel.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..dependencies import get_current_active_user
from ..services import zim_config
from ..services.db import get_db

router = APIRouter(prefix="/zim", tags=["Zimbabwe Insurance Intelligence"])


class NationalIdValidationRequest(BaseModel):
    value: str


class DateNormalizationRequest(BaseModel):
    value: str
    strict: bool = False


class CurrencyValidationRequest(BaseModel):
    currency: str


@router.get("/config", summary="Zimbabwe insurance intelligence configuration snapshot")
async def get_config() -> Dict[str, Any]:
    return zim_config.get_zim_config()


@router.get("/regulatory-rules", summary="Configurable Zimbabwe regulatory rules")
async def get_rules() -> Dict[str, Any]:
    return zim_config.get_regulatory_rules()


@router.post("/validate/national-id", summary="Validate a Zimbabwean National ID format")
async def validate_national_id(request: NationalIdValidationRequest) -> Dict[str, Any]:
    result = zim_config.validate_national_id_format(request.value)
    return {
        "input": request.value,
        **result,
        "note": "Format valid but value may still be invalid — registration registry verification requires a dedicated official integration.",
    }


@router.post("/normalize-date", summary="Normalize a Zimbabwean date to ISO YYYY-MM-DD")
async def normalize_date(request: DateNormalizationRequest) -> Dict[str, Any]:
    result = zim_config.normalize_zim_date(request.value, strict=request.strict)
    return {"input": request.value, **result}


@router.post("/validate-currency", summary="Validate an accepted claim currency")
async def validate_currency(request: CurrencyValidationRequest) -> Dict[str, Any]:
    return zim_config.validate_claim_currency(request.currency)


@router.get("/timeline-context", summary="Contextual intelligence notes for AI assistant")
async def get_context() -> Dict[str, Any]:
    return zim_config.get_zim_timeline_context()
