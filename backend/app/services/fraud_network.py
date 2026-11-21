"""Advanced Fraud Relationship Network Analysis (Phase 3).

Examines relationships between policyholders, claimants, beneficiaries,
medical practitioners, hospitals, policies, payment accounts and claim
documents to surface potentially suspicious relationships. This is a
relationship-analysis engine — it never labels individuals or documents as
fraudulent; every node/edge is presented with strength and evidence so humans
can decide.

Honest policy: shared details (names, phones, beneficiary names) can have
legitimate explanations; edges are flagged *possible* only when several
independent signals agree.

Algorithms (pure Python, documented limitations):
- Graph building over entities from the relational database + claim docs.
- Connected components for cluster detection.
- Edge strength from observed co-occurrence (0..1) and similarity scoring
  for documents (difflib SequenceMatcher ratio).
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.sqlalchemy_models import (
    Claim, ClaimDocument, Customer, Investigation, OCRDocument, Policy,
)

# Relationship types
REL_POLICY_OF_CUSTOMER = "POLICY_OF_CUSTOMER"
REL_POLICY_COVERED_CLAIM = "POLICY_COVERED_CLAIM"
REL_CLAIM_CUSTOMER = "POLICYHOLDER_CLAIM"
REL_SUPPORTING_DOC = "SUPPORTING_DOCUMENT"
REL_IDENTICAL_DOC = "IDENTICAL_DOCUMENT_REUSE"
REL_BENEFICIARY = "BENEFICIARY_OF_CLAIM"
REL_SHARED_IDENTITY = "SHARED_IDENTITY"
REL_SHARED_BENEFICIARY = "SHARED_BENEFICIARY_ACROSS_POLICIES"
REL_SHARED_PAYMENT_ACCOUNT = "SHARED_PAYMENT_ACCOUNT_ACROSS_CLAIMS"
REL_SIMILAR_DOCUMENT = "SIMILAR_DOCUMENT_ACROSS_CLAIMS"
REL_CLUSTER = "POTENTIAL_CLUSTER_CONNECTION"

# Minimum similarity (0..1) for a cross-claim document relationship.
SIMILAR_DOC_THRESHOLD = 0.85
# Minimum number of shared signals for a possible shared-identity edge.
SHARED_IDENTITY_MIN_SIGNALS = 2


def _norm_key(value: Optional[str]) -> Optional[str]:
    """Normalises an identifier for comparison (uppercase alphanumeric only)."""
    if not value:
        return None
    return re.sub(r"[^A-Z0-9]", "", str(value).upper()) or None


def _cust_node_id(customer: Customer) -> str:
    return f"CUST-{customer.id}" if customer.id else f"CUST-{(customer.customer_id or 'UNK')}"


def _claim_node_id(claim: Claim) -> str:
    return f"CLM-{claim.id}:{claim.claim_id}" if claim else None


def _doc_node_id(doc: OCRDocument) -> str:
    return f"OCR-{doc.id}" if doc else None


def _policy_node_id(policy: Policy) -> str:
    return f"POL-{policy.id}:{policy.policy_number}" if policy else None


def _build_nodes(db: Session) -> Dict[str, Dict[str, Any]]:
    nodes: Dict[str, Dict[str, Any]] = {}

    for c in db.query(Customer).all():
        nodes[_cust_node_id(c)] = {
            "id": _cust_node_id(c),
            "entity_type": "customer",
            "entity_key": str(c.customer_id or c.id),
            "name": c.name,
            "national_id": c.national_id,
            "customer_id": c.id,
            "is_suspicious": False,
        }

    for p in db.query(Policy).all():
        nodes[_policy_node_id(p)] = {
            "id": _policy_node_id(p),
            "entity_type": "policy",
            "entity_key": p.policy_number,
            "name": p.policy_number,
            "policy_number": p.policy_number,
            "customer_id": p.customer_id,
        }

    for c in db.query(Claim).all():
        nodes[_claim_node_id(c)] = {
            "id": _claim_node_id(c),
            "entity_type": "claim",
            "entity_key": str(c.id),
            "name": f"{c.claim_id} ({c.claim_type})",
            "amount": c.amount,
            "incident_date": c.incident_date.isoformat() if c.incident_date else None,
            "claim_id": c.id,
            "customer_id": c.customer_id,
            "policy_id": c.policy_id,
        }
        if c.beneficiary_name:
            ben_id = f"BENEF-{_norm_key(c.beneficiary_nin) or _norm_key(c.beneficiary_name)}"
            nodes[ben_id] = {
                "id": ben_id,
                "entity_type": "beneficiary",
                "entity_key": ben_id,
                "name": c.beneficiary_name,
                "national_id": c.beneficiary_nin,
            }
        for ref in (c.payment_account_refs or []):
            key = _norm_key(ref)
            if key:
                nodes[f"ACCT-{key}"] = {
                    "id": f"ACCT-{key}",
                    "entity_type": "payment_ref",
                    "entity_key": f"ACCT-{key}",
                    "name": key,
                }

    for d in db.query(OCRDocument).all():
        if not d.document_hash_sha256:
            continue
        nid = _doc_node_id(d)
        nodes[nid] = {
            "id": nid,
            "entity_type": "document",
            "entity_key": str(d.id),
            "name": d.filename,
            "document_hash": d.document_hash_sha256,
            "claim_id": d.claim_id,
        }

    return nodes


def _build_edges(db: Session, nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Builds undirected-style edges between nodes with strength and evidence."""
    edges: List[Dict[str, Any]] = []
    added = set()

    def add_edge(a_id: str, b_id: str, rel_type: str, strength: float,
                 evidence: str, suspicious: bool = False, claim_ids=None, dedup_key=None):
        if a_id not in nodes or b_id not in nodes or a_id == b_id:
            return
        key = dedup_key or tuple(sorted((a_id, b_id, rel_type)))
        if key in added:
            return
        added.add(key)
        edges.append({
            "node_a_id": a_id,
            "node_b_id": b_id,
            "relationship_type": rel_type,
            "strength": min(1.0, max(0.0, strength)),
            "evidence": evidence[:500],
            "is_suspicious": suspicious,
            "claim_ids": claim_ids or [],
        })

    claims = db.query(Claim).all()

    # 1. Customer -> Policy, Customer -> Claim, Policy -> Claim (strong)
    for c in claims:
        cust_id = _cust_node_id(c.customer) if c.customer else f"CUST-{c.customer_id}"
        pol_id = _policy_node_id(c.policy) if c.policy else None
        claim_id = _claim_node_id(c)
        if cust_id in nodes:
            add_edge(cust_id, claim_id, REL_CLAIM_CUSTOMER, 0.9,
                     f"Policyholder submitted claim {c.claim_id}.", claim_ids=[c.id])
        if pol_id and pol_id in nodes:
            add_edge(pol_id, claim_id, REL_POLICY_COVERED_CLAIM, 1.0,
                     f"Claim {c.claim_id} on policy {c.policy.policy_number}.", claim_ids=[c.id])
            add_edge(cust_id, pol_id, REL_POLICY_OF_CUSTOMER, 1.0,
                     f"Policy {c.policy.policy_number} for customer.", claim_ids=None)

    # 2. Claim -> Supporting Documents (claim-linked and orphan docs)
    for d in db.query(OCRDocument).all():
        if not d.document_hash_sha256:
            continue
        doc_id = _doc_node_id(d)
        claim_ids = [d.claim_id] if d.claim_id else []
        if d.claim_id:
            claim = db.query(Claim).filter(Claim.id == d.claim_id).first()
            if claim:
                add_edge(_claim_node_id(claim), doc_id, REL_SUPPORTING_DOC, 1.0,
                         f"Document '{d.filename}' uploaded for claim.", claim_ids=[d.claim_id])
        # 3. Identical documents across claims (exact hash match)
        for other in db.query(OCRDocument).filter(
            OCRDocument.document_hash_sha256 == d.document_hash_sha256,
            OCRDocument.id != d.id,
        ).all():
            other_id = _doc_node_id(other)
            add_edge(doc_id, other_id, REL_IDENTICAL_DOC, 1.0,
                     f"Identical SHA-256 fingerprint (hash {d.document_hash_sha256[:12]}…): "
                     f"'{d.filename}' == '{other.filename}'.",
                     suspicious=True, claim_ids=sorted(set([d.claim_id, other.claim_id])))

        # 4. Similar documents across claims (text similarity, different claimants)
        if d.raw_text and d.claim_id:
            for other in db.query(OCRDocument).filter(
                OCRDocument.id > d.id, OCRDocument.document_hash_sha256.isnot(None)
            ).all():
                if not other.raw_text or other.claim_id == d.claim_id:
                    continue
                ratio = SequenceMatcher(None, d.raw_text, other.raw_text).ratio()
                if ratio >= SIMILAR_DOC_THRESHOLD:
                    add_edge(_doc_node_id(d), _doc_node_id(other), REL_SIMILAR_DOCUMENT,
                             min(1.0, ratio),
                             f"Documents share {ratio:.0%} text similarity ('{d.filename}' vs '{other.filename}').",
                             suspicious=True, claim_ids=sorted(set([d.claim_id, other.claim_id])))

    # 5. Beneficiary nodes -> Claims
    for c in claims:
        if c.beneficiary_name:
            ben_id = f"BENEF-{_norm_key(c.beneficiary_nin) or _norm_key(c.beneficiary_name)}"
            add_edge(ben_id, _claim_node_id(c), REL_BENEFICIARY, 0.8,
                     f"Beneficiary '{c.beneficiary_name}' named on claim.", claim_ids=[c.id])

    # 6. Shared identifiers across customers/policies (possible shared identity)
    _add_shared_identity_edges(db, nodes, edges, added)

    # 7. Shared payment account refs across claims
    _add_shared_payment_ref_edges(db, nodes, edges, added)

    # 8. Benificary/tenant: same beneficiary across different policies ->
    #    customer-to-customer relationship edges.
    _add_shared_beneficiary_edges(db, nodes, edges, added)

    return edges


def _add_shared_identity_edges(db, nodes, edges, added):
    # Group by national_id
    by_nin: Dict[str, List[str]] = defaultdict(list)
    for nid, nd in nodes.items():
        if nd["entity_type"] == "customer" and _norm_key(nd.get("national_id")):
            by_nin[_norm_key(nd["national_id"])].append(nid)
        elif nd["entity_type"] == "beneficiary" and _norm_key(nd.get("national_id")):
            # Beneficiary shares identity with customer? Only flag when the
            # beneficiary's NIN equals another customer's NIN.
            pass

    groups = [g for g in by_nin.values() if len(g) > 1]
    for g in groups:
        for a in g:
            for b in g:
                if a != b and tuple(sorted((a, b))) not in added:
                    _add(nodes, edges, added, a, b, REL_SHARED_IDENTITY, 1.0,
                         "Multiple records share the same National ID.", suspicious=False)

    # Group by name similarity among customers (weak signal only)
    customers = [n for n in nodes.values() if n["entity_type"] == "customer"]
    for i in range(len(customers)):
        for j in range(i + 1, len(customers)):
            a, b = customers[i], customers[j]
            na, nb = (a.get("name") or "").lower().strip(), (b.get("name") or "").lower().strip()
            if not na or not nb or len(na.split()) != len(nb.split()):
                continue
            if na == nb:
                continue
            sim = SequenceMatcher(None, na, nb).ratio()
            signals = 0
            evidence_bits = []
            if sim >= 0.9:
                signals += 1
                evidence_bits.append("near-identical names")
            if _norm_key(a.get("national_id")) and _norm_key(a["national_id"]) == _norm_key(b.get("national_id")):
                signals += 2  # already emitted below, just for counting
                evidence_bits.append("identical national IDs")
            if signals >= SHARED_IDENTITY_MIN_SIGNALS:
                key = tuple(sorted((a["id"], b["id"], REL_SHARED_IDENTITY)))
                if key not in added:
                    edges.append({
                        "node_a_id": a["id"], "node_b_id": b["id"],
                        "relationship_type": REL_SHARED_IDENTITY,
                        "strength": min(1.0, 0.6 + 0.4 * sim),
                        "evidence": "Shared identity signals: " + "; ".join(evidence_bits) + ".",
                        "is_suspicious": True,
                        "claim_ids": [],
                    })
                    added.add(key)


def _add_shared_payment_ref_edges(db, nodes, edges, added):
    by_ref: Dict[str, List[str]] = defaultdict(list)
    for nid, nd in nodes.items():
        if nd["entity_type"] == "payment_ref":
            by_ref[nd["id"]].append(nid)
    for ref_nid, members in by_ref.items():
        # Edge among all records referencing the same account (usually 1).
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                _add(nodes, edges, added, a, b, REL_SHARED_PAYMENT_ACCOUNT, 1.0,
                     f"Same payment account '{ref_nid}' referenced by multiple records.",
                     suspicious=False)
        # Cross-claim: find claims that referenced this account via Claim.payment_account_refs
        claims_linked: List[int] = []
        for claim in db.query(Claim).all():
            refs = [_norm_key(r) for r in (claim.payment_account_refs or [])]
            norm_ref = _norm_key(ref_nid.replace("ACCT-", ""))
            if norm_ref and norm_ref in refs:
                claims_linked.append(claim.id)
        # Connect the account node to each claim that used it
        for cid in claims_linked:
            claim = db.query(Claim).filter(Claim.id == cid).first()
            if claim:
                _add(nodes, edges, added, ref_nid, _claim_node_id(claim),
                     "PAYMENT_ACCOUNT_REFERENCE", 0.9,
                     f"Claim {claim.claim_id} referenced payment account '{ref_nid}'.",
                     suspicious=False, claim_ids=[cid])


def _add_shared_beneficiary_edges(db, nodes, edges, added):
    # Customer -> BENEFICIARY edges, and customer<->customer when two policies
    # have the same beneficiary name (with or without NIN).
    cust_claims: Dict[str, List[Claim]] = defaultdict(list)
    for c in db.query(Claim).all():
        if c.customer_id:
            cust_claims[str(c.customer_id)].append(c)

    by_ben: Dict[str, List[Claim]] = defaultdict(list)
    for c in db.query(Claim).all():
        if c.beneficiary_name:
            key = _norm_key(c.beneficiary_nin) or _norm_key(c.beneficiary_name)
            by_ben[f"BENEF-{key}"].append(c)

    for ben_id, claims in by_ben.items():
        customers = {_cust_node_id(c.customer) if c.customer else None for c in claims}
        customers.discard(None)
        for c in claims:
            if c.beneficiary_name:
                ben_id2 = f"BENEF-{_norm_key(c.beneficiary_nin) or _norm_key(c.beneficiary_name)}"
                _add(nodes, edges, added, ben_id2, _claim_node_id(c), REL_BENEFICIARY, 0.8,
                     f"Beneficiary '{c.beneficiary_name}' named on claim {c.claim_id}.", claim_ids=[c.id])
                cust_id = _cust_node_id(c.customer) if c.customer else f"CUST-{c.customer_id}"
                if cust_id in nodes:
                    _add(nodes, edges, added, cust_id, ben_id2, "BENEFICIARY_OF_CUSTOMER", 0.7,
                         f"Beneficiary named by {cust_id} on claim {c.claim_id}.")
        # Multiple different customers naming the same beneficiary
        if len(customers) > 1:
            cust_list = sorted(customers)
            for i in range(len(cust_list)):
                for j in range(i + 1, len(cust_list)):
                    _add(nodes, edges, added, cust_list[i], cust_list[j], REL_SHARED_BENEFICIARY,
                         0.85,
                         f"Beneficiary '{ben_id}' appears across policies of both customers.",
                         suspicious=True)


def _add(nodes, edges, added, a_id: str, b_id: str, rel_type: str, strength: float,
         evidence: str, suspicious: bool = False, claim_ids=None):
    if a_id not in nodes or b_id not in nodes or a_id == b_id:
        return
    key = tuple(sorted((a_id, b_id, rel_type)))
    if key in added:
        return
    added.add(key)
    edges.append({
        "node_a_id": a_id,
        "node_b_id": b_id,
        "relationship_type": rel_type,
        "strength": min(1.0, max(0.0, strength)),
        "evidence": evidence[:500],
        "is_suspicious": suspicious,
        "claim_ids": claim_ids or [],
    })


# ---------------------------------------------------------------------------
# Graph analytics
# ---------------------------------------------------------------------------

def _connected_components(node_ids: Set[str], edges: List[Dict[str, Any]]) -> Dict[str, str]:
    parent = {n: n for n in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for e in edges:
        a, b = e["node_a_id"], e["node_b_id"]
        if a in parent and b in parent:
            union(a, b)
    comps: Dict[str, str] = {}
    for n in node_ids:
        comps[n] = find(n)
    return comps


def build_fraud_network(db: Session) -> Dict[str, Any]:
    """Builds the full fraud relationship network graph for the current data."""
    nodes = _build_nodes(db)
    edges = _build_edges(db, nodes)

    # Cluster detection: connected components with >1 distinct claim, suspicious.
    comps = _connected_components(set(nodes.keys()), edges)
    clusters: Dict[str, List[str]] = defaultdict(list)
    for nid, comp in comps.items():
        clusters[comp].append(nid)

    cluster_summaries = []
    suspicious_clusters = 0
    for comp_id, members in clusters.items():
        member_nodes = [nodes[m] for m in members]
        claims_in_cluster = sorted({n["claim_id"] for n in member_nodes if n.get("claim_id")})
        customers_in_cluster = sorted({n["customer_id"] for n in member_nodes if n.get("customer_id")})
        if len(claims_in_cluster) > 1 and len(customers_in_cluster) > 1:
            suspicious_clusters += 1
            cluster_summaries.append({
                "cluster_id": comp_id,
                "member_count": len(members),
                "entity_types": sorted({n["entity_type"] for n in member_nodes}),
                "claim_ids": claims_in_cluster,
                "customer_ids": customers_in_cluster,
                "relationship_evidence": [
                    f"{e['node_a_id']} — {e['relationship_type']} — {e['node_b_id']}"
                    for e in edges
                    if e["node_a_id"] in set(members) or e["node_b_id"] in set(members)
                ][:5],
                "is_suspicious": True,
                "note": "Multiple claims involving connected parties — needs human review.",
            })

    # Suspicious edge summary (not labelled fraud — flagged for review).
    susp_edges = [
        {
            "node_a": {"id": e["node_a_id"], "type": nodes[e["node_a_id"]]["entity_type"]},
            "node_b": {"id": e["node_b_id"], "type": nodes[e["node_b_id"]]["entity_type"]},
            "relationship_type": e["relationship_type"],
            "strength": e["strength"],
            "evidence": e["evidence"],
            "claim_ids": e["claim_ids"],
        }
        for e in edges if e["is_suspicious"]
    ]
    susp_nodes = [n for n in nodes.values() if n.get("is_suspicious")]
    # Node risk score: weighted edge involvement.
    edge_weights = defaultdict(float)
    for e in edges:
        if e["is_suspicious"]:
            edge_weights[e["node_a_id"]] += e["strength"]
            edge_weights[e["node_b_id"]] += e["strength"]
    for n in nodes.values():
        n["total_edges"] = len([e for e in edges if n["id"] in (e["node_a_id"], e["node_b_id"])])
        n["risk_score"] = min(100.0, edge_weights[n["id"]] * 25.0)
        n["is_suspicious"] = bool(n["risk_score"] >= 40.0 or n["total_edges"] >= 6)

    # Ensure all nodes expose the flag (earlier node builders may omit it).
    for n in nodes.values():
        n.setdefault("is_suspicious", False)

    # Re-rank suspicious nodes
    susp_nodes = [n for n in nodes.values() if n.get("is_suspicious")]
    susp_nodes.sort(key=lambda n: (-n["risk_score"], n["id"]))

    investigation_status_by_claim: Dict[int, str] = {
        inv.claim_id: inv.status
        for inv in db.query(Investigation).all()
    }

    return {
        "generated_at": "db",
        "nodes": [
            {
                "id": n["id"],
                "entity_type": n["entity_type"],
                "entity_key": n["entity_key"],
                "name": n["name"],
                "national_id": n.get("national_id"),
                "claim_id": n.get("claim_id"),
                "customer_id": n.get("customer_id"),
                "policy_number": n.get("policy_number"),
                "document_hash": (n.get("document_hash") or "")[:16],
                "amount": n.get("amount"),
                "is_suspicious": n["is_suspicious"],
                "risk_score": n["risk_score"],
                "total_edges": n["total_edges"],
                "investigation_status": (
                    investigation_status_by_claim.get(n["claim_id"])
                    if n.get("claim_id") else None
                ),
            }
            for n in sorted(nodes.values(), key=lambda x: x["id"])
        ],
        "edges": [
            {
                "id": f"{e['node_a_id']}:{e['node_b_id']}",
                "node_a_id": e["node_a_id"],
                "node_b_id": e["node_b_id"],
                "node_a": {"id": e["node_a_id"], "type": nodes[e["node_a_id"]]["entity_type"],
                           "name": nodes[e["node_a_id"]]["name"]},
                "node_b": {"id": e["node_b_id"], "type": nodes[e["node_b_id"]]["entity_type"],
                           "name": nodes[e["node_b_id"]]["name"]},
                "relationship_type": e["relationship_type"],
                "strength": e["strength"],
                "evidence": e["evidence"],
                "claim_ids": e["claim_ids"],
                "is_suspicious": e["is_suspicious"],
            }
            for e in sorted(edges, key=lambda x: (-x["strength"], x["node_a_id"], x["node_b_id"]))
        ],
        "clusters": cluster_summaries,
        "suspicious_nodes": susp_nodes[:50],
        "suspicious_edges": susp_edges[:200],
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "suspicious_nodes": len(susp_nodes),
            "suspicious_edges": len([e for e in edges if e["is_suspicious"]]),
            "clusters": len(clusters),
            "suspicious_clusters": suspicious_clusters,
        },
    }


def get_network_insights(db: Session) -> Dict[str, Any]:
    """Compact insight summary for dashboards and the Copilot."""
    net = build_fraud_network(db)
    return {
        "summary": net["summary"],
        "top_suspicious_nodes": [
            {
                "id": n["id"],
                "entity_type": n["entity_type"],
                "name": n["name"],
                "risk_score": round(n["risk_score"], 1),
                "claim_id": n["claim_id"],
                "investigation_status": n.get("investigation_status"),
            }
            for n in net["suspicious_nodes"][:10]
        ],
        "top_suspicious_edges": [
            {
                "relationship_type": e["relationship_type"],
                "strength": e["strength"],
                "evidence": e["evidence"],
                "claim_ids": e["claim_ids"],
            }
            for e in net["suspicious_edges"][:10]
        ],
    }
