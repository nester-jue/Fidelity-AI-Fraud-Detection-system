"""Backend-enforced organisation (tenant) isolation.

The rules are applied at the ORM session layer so they cannot be forgotten by
an individual endpoint:

* every SELECT on a tenant-scoped entity automatically receives an
  ``organisation_id == current_organisation`` criterion;
* every INSERT on a tenant-scoped entity is stamped with the organisation of
  the current request when the endpoint did not set it explicitly;
* if no authenticated organisation is available, the criterion is impossible
  (``organisation_id == -1``) — the request fails closed instead of leaking
  cross-tenant rows.

Unauthenticated endpoints that must locate an account globally (sign-in,
registration, reset) explicitly opt out with ``PUBLIC_ACCESS``. They never
receive tenant data; they only resolve the account that supplied credentials.

The feature is activated with ``TENANT_ISOLATION_ENABLED=true``. With the flag
off (single-tenant deployments and legacy databases) no query is modified.
"""
import contextvars
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession, with_loader_criteria

from ..core.config import settings


class _PublicAccess:
    """Marker used only by credential-verification endpoints."""

    def __repr__(self):
        return "PUBLIC_ACCESS"


PUBLIC_ACCESS = _PublicAccess()

_context: contextvars.ContextVar = contextvars.ContextVar("nexa_organisation_id", default=None)
_installed = False


def set_tenant(organisation_id: Optional[int]):
    """Bind an organisation to the current execution context."""
    return _context.set(organisation_id)


def reset_tenant(token):
    """Restore the previous context (always call in a ``finally`` block)."""
    _context.reset(token)


def current_tenant():
    return _context.get()


@contextmanager
def bound_tenant(organisation_id: Optional[int]):
    """Bind an organisation for work that runs outside an HTTP request.

    Starlette executes response background tasks after the request middleware
    has reset the context variable, so a background AI analysis must capture
    the organisation explicitly. Without this the ORM filter would fail closed
    and the task would silently see no records.
    """
    token = set_tenant(organisation_id)
    try:
        yield
    finally:
        reset_tenant(token)


def tenant_models():
    from ..models import sqlalchemy_models as models

    return [
        models.User,
        models.Customer,
        models.Policy,
        models.Claim,
        models.ClaimBeneficiaryChange,
        models.ClaimTimelineEvent,
        models.EvidenceRecord,
        models.FraudNetworkNode,
        models.FraudNetworkEdge,
        models.PredictiveAlert,
        models.ModelRetrainingRequest,
        models.ClaimDocument,
        models.FraudAssessment,
        models.Investigation,
        models.ClaimNote,
        models.InvestigationNote,
        models.ComplianceReport,
        models.ManagementReport,
        models.AuditLog,
        models.Notification,
        models.ModelPerformance,
        models.OCRDocument,
        models.OCRCorrection,
        models.ChatMessage,
        models.KnowledgeDocument,
        models.KnowledgeChunk,
        models.FirstNoticeOfLoss,
    ]


def install():
    """Register the session-wide isolation listeners (idempotent)."""
    global _installed
    if _installed:
        return
    models = tenant_models()
    _installed = True

    @event.listens_for(OrmSession, "do_orm_execute")
    def _apply_tenant_criteria(execute_state):
        if not settings.TENANT_ISOLATION_ENABLED or not execute_state.is_select:
            return
        current = _context.get()
        if current is PUBLIC_ACCESS:
            return
        organisation_id = current if isinstance(current, int) else -1
        # with_loader_criteria() targets one entity per option, so register
        # one criterion for every tenant-scoped mapped class.
        execute_state.statement = execute_state.statement.options(*[
            with_loader_criteria(
                model,
                lambda cls: cls.organisation_id == organisation_id,
                include_aliases=True,
                propagate_to_loaders=True,
            )
            for model in models
        ])

    def _stamp(mapper, connection, target):
        if not settings.TENANT_ISOLATION_ENABLED:
            return
        current = _context.get()
        if target.organisation_id is None and isinstance(current, int):
            target.organisation_id = current

    for model in models:
        event.listen(model, "before_insert", _stamp)
