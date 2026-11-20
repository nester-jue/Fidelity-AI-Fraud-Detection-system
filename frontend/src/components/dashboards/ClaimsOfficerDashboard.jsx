/**
 * ClaimsOfficerDashboard.jsx
 * NEXA AI Fraud Detection Platform — Claims Officer role dashboard.
 * Tabs: dashboard | my-claims | new-claim | fnol | ai-assessment | profile
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  RefreshCw,
  Search,
  Filter,
  Upload,
  Plus,
  Eye,
  X,
  CheckCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
  Shield,
  User,
  Calendar,
  DollarSign,
  ChevronRight,
  Loader2,
  AlertCircle,
  InboxIcon,
  BarChart2,
  ClipboardList,
  Zap,
} from 'lucide-react';
import { api } from '../../../api/apiClient';

// ─────────────────────────────────────────────
// Utility helpers
// ─────────────────────────────────────────────

const fmtCurrency = (v) =>
  v != null
    ? new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR', maximumFractionDigits: 0 }).format(v)
    : '—';

const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('en-ZA') : '—');

function statusBadge(status) {
  const map = {
    submitted: 'bg-blue-100 text-blue-700 border-blue-200',
    in_review: 'bg-amber-100 text-amber-700 border-amber-200',
    flagged: 'bg-red-100 text-red-700 border-red-200',
    approved: 'bg-green-100 text-green-700 border-green-200',
    rejected: 'bg-slate-100 text-slate-600 border-slate-200',
  };
  const cls = map[status] || 'bg-slate-100 text-slate-500 border-slate-200';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border ${cls}`}>
      {status?.replace(/_/g, ' ') || 'unknown'}
    </span>
  );
}

function riskBadge(risk) {
  const map = {
    critical: 'bg-red-100 text-red-700 border-red-300',
    high: 'bg-orange-100 text-orange-700 border-orange-300',
    medium: 'bg-amber-100 text-amber-700 border-amber-300',
    low: 'bg-green-100 text-green-700 border-green-300',
    pending: 'bg-slate-100 text-slate-500 border-slate-200',
  };
  const key = (risk || 'pending').toLowerCase();
  const cls = map[key] || 'bg-slate-100 text-slate-500 border-slate-200';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border ${cls}`}>
      {risk || 'Pending'}
    </span>
  );
}

function severityBadge(sev) {
  const map = {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-green-100 text-green-700',
  };
  const cls = map[(sev || '').toLowerCase()] || 'bg-slate-100 text-slate-500';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${cls}`}>
      {sev}
    </span>
  );
}

function RiskScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score ?? 0));
  let barColor = 'bg-green-500';
  if (pct >= 75) barColor = 'bg-red-500';
  else if (pct >= 50) barColor = 'bg-orange-400';
  else if (pct >= 25) barColor = 'bg-amber-400';
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-7 text-right">{pct}</span>
    </div>
  );
}

// ─────────────────────────────────────────────
// Shared sub-components
// ─────────────────────────────────────────────

function LoadingState({ label = 'Loading data…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <AlertCircle className="w-10 h-10 text-red-400" />
      <p className="text-sm font-semibold text-slate-600">Something went wrong</p>
      <p className="text-xs text-slate-400 max-w-xs text-center">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 px-4 py-1.5 text-xs font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Retry
        </button>
      )}
    </div>
  );
}

function EmptyState({ icon: Icon = InboxIcon, title = 'No data', message = 'Nothing to display yet.' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Icon className="w-10 h-10 text-slate-300" />
      <p className="text-sm font-semibold text-slate-500">{title}</p>
      <p className="text-xs text-slate-400">{message}</p>
    </div>
  );
}

function SectionCard({ children, className = '' }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl overflow-hidden ${className}`}>
      {children}
    </div>
  );
}

function TableHeader({ children }) {
  return (
    <thead>
      <tr className="bg-slate-50 border-b border-slate-200">
        {children}
      </tr>
    </thead>
  );
}

function Th({ children, className = '' }) {
  return (
    <th className={`px-4 py-3 text-left text-[10px] font-extrabold uppercase tracking-wider text-slate-500 whitespace-nowrap ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, className = '' }) {
  return (
    <td className={`px-4 py-3 text-xs text-slate-700 whitespace-nowrap ${className}`}>
      {children}
    </td>
  );
}

// ─────────────────────────────────────────────
// Modal overlay
// ─────────────────────────────────────────────

function Modal({ title, onClose, children, wide = false }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className={`bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[90vh] ${wide ? 'w-full max-w-4xl' : 'w-full max-w-2xl'}`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 flex-shrink-0">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-800">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-6">{children}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// TAB 1 — Dashboard Overview
// ─────────────────────────────────────────────

function DashboardTab({ user }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.claimsOfficerDashboard();
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const kpis = data
    ? [
        { label: 'Total Claims', value: data.total_claims ?? data.stats?.total_claims ?? 0, icon: FileText, color: 'border-blue-500', iconColor: 'text-blue-500', bg: 'bg-blue-50' },
        { label: 'New Claims', value: data.new_claims ?? data.stats?.new_claims ?? 0, icon: Plus, color: 'border-emerald-500', iconColor: 'text-emerald-500', bg: 'bg-emerald-50' },
        { label: 'In Review', value: data.in_review ?? data.stats?.in_review ?? 0, icon: Clock, color: 'border-amber-500', iconColor: 'text-amber-500', bg: 'bg-amber-50' },
        { label: 'Flagged Claims', value: data.flagged_claims ?? data.stats?.flagged_claims ?? 0, icon: AlertTriangle, color: 'border-red-500', iconColor: 'text-red-500', bg: 'bg-red-50' },
      ]
    : [];

  const recentClaims = data?.recent_claims ?? data?.claims ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold text-slate-800">Claims Officer Dashboard</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Welcome back, <span className="font-semibold text-slate-700">{user?.full_name || user?.username || 'Officer'}</span>
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      {loading && !data && <LoadingState />}
      {error && !data && <ErrorState message={error} onRetry={load} />}
      {data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {kpis.map((k) => (
              <div key={k.label} className={`bg-white border border-slate-200 border-t-4 ${k.color} rounded-2xl p-5 flex items-center gap-4`}>
                <div className={`p-3 rounded-xl ${k.bg}`}>
                  <k.icon className={`w-5 h-5 ${k.iconColor}`} />
                </div>
                <div>
                  <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{k.label}</p>
                  <p className="text-2xl font-extrabold text-slate-800 mt-0.5">{k.value.toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Recent Claims Table */}
          <SectionCard>
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-blue-500" />
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">Recent Claims</h2>
              </div>
              <span className="text-xs text-slate-400">{recentClaims.length} claims</span>
            </div>
            {recentClaims.length === 0 ? (
              <EmptyState icon={FileText} title="No recent claims" message="Submitted claims will appear here." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <TableHeader>
                    <Th>Claim ID</Th>
                    <Th>Customer</Th>
                    <Th>Type</Th>
                    <Th>Amount</Th>
                    <Th>Status</Th>
                    <Th>Risk Score</Th>
                    <Th>Documents</Th>
                    <Th>Actions</Th>
                  </TableHeader>
                  <tbody className="divide-y divide-slate-100">
                    {recentClaims.map((c) => (
                      <tr key={c.id || c.claim_id} className="hover:bg-slate-50 transition-colors">
                        <Td>
                          <span className="font-mono font-semibold text-blue-600">
                            #{(c.id || c.claim_id || '').toString().slice(-8).toUpperCase()}
                          </span>
                        </Td>
                        <Td>{c.customer_name || c.customer || '—'}</Td>
                        <Td>{c.claim_type?.replace(/_/g, ' ') || '—'}</Td>
                        <Td className="font-semibold">{fmtCurrency(c.claim_amount)}</Td>
                        <Td>{statusBadge(c.status)}</Td>
                        <Td><RiskScoreBar score={c.fraud_score ?? c.risk_score} /></Td>
                        <Td>
                          <span className="inline-flex items-center gap-1 text-slate-500">
                            <FileText className="w-3 h-3" />
                            {c.document_count ?? c.documents?.length ?? 0}
                          </span>
                        </Td>
                        <Td>
                          <button className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
                            <Eye className="w-3 h-3" /> View
                          </button>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Claim Detail Modal
// ─────────────────────────────────────────────

function ClaimDetailModal({ claimId, onClose }) {
  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.getClaim(claimId);
        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        setClaim(await res.json());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [claimId]);

  const Field = ({ label, value }) => (
    <div>
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-0.5">{label}</p>
      <p className="text-xs font-medium text-slate-700">{value || '—'}</p>
    </div>
  );

  return (
    <Modal title={`Claim Detail — #${String(claimId).slice(-8).toUpperCase()}`} onClose={onClose} wide>
      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {claim && (
        <div className="space-y-6">
          {/* Core Fields */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Field label="Claim ID" value={`#${String(claim.id).slice(-8).toUpperCase()}`} />
            <Field label="Policy Number" value={claim.policy_number} />
            <Field label="Claim Type" value={claim.claim_type?.replace(/_/g, ' ')} />
            <Field label="Amount" value={fmtCurrency(claim.claim_amount)} />
            <Field label="Incident Date" value={fmtDate(claim.incident_date)} />
            <Field label="Submission Date" value={fmtDate(claim.created_at || claim.submission_date)} />
            <Field label="Beneficiary" value={claim.beneficiary_name} />
            <Field label="Status" value={null} />
            <div>{statusBadge(claim.status)}</div>
          </div>

          {/* Description */}
          {claim.description && (
            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-1">Description</p>
              <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 rounded-xl p-3 border border-slate-200">{claim.description}</p>
            </div>
          )}

          {/* Assessment */}
          {(claim.assessment || claim.fraud_assessment) && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-4 h-4 text-amber-600" />
                <p className="text-xs font-extrabold uppercase tracking-wider text-amber-700">AI Risk Assessment</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Field label="Risk Score" value={(claim.assessment || claim.fraud_assessment)?.fraud_score?.toFixed(1)} />
                <Field label="Risk Category" value={(claim.assessment || claim.fraud_assessment)?.risk_category} />
                <Field label="Indicators" value={(claim.assessment || claim.fraud_assessment)?.indicators?.length ?? 0} />
              </div>
            </div>
          )}

          {/* Documents */}
          {claim.documents?.length > 0 && (
            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-2">Documents ({claim.documents.length})</p>
              <div className="space-y-2">
                {claim.documents.map((doc, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <FileText className="w-4 h-4 text-blue-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-slate-700 truncate">{doc.filename || doc.name || `Document ${i + 1}`}</p>
                      <p className="text-[10px] text-slate-400">{doc.document_type || doc.type || 'Document'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// ─────────────────────────────────────────────
// TAB 2 — My Claims Register
// ─────────────────────────────────────────────

function MyClaimsTab() {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [selectedClaimId, setSelectedClaimId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (riskFilter) params.risk_category = riskFilter;
      const res = await api.listClaims(params);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      setClaims(Array.isArray(json) ? json : json.claims || json.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, riskFilter]);

  useEffect(() => { load(); }, [load]);

  const filtered = claims.filter((c) => {
    const q = search.toLowerCase();
    return !q || [c.id, c.claim_id, c.policy_number, c.customer_name, c.beneficiary_name]
      .some((v) => String(v || '').toLowerCase().includes(q));
  });

  return (
    <div className="space-y-6">
      {selectedClaimId && (
        <ClaimDetailModal claimId={selectedClaimId} onClose={() => setSelectedClaimId(null)} />
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold text-slate-800">Claims Register</h1>
          <p className="text-xs text-slate-500 mt-0.5">All submitted claims assigned to your portfolio</p>
        </div>
        <button onClick={load} disabled={loading} className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <SectionCard>
        <div className="p-4 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Claim ID, Policy #, Customer…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-slate-50"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="submitted">Submitted</option>
              <option value="in_review">In Review</option>
              <option value="flagged">Flagged</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Risk Levels</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>

        {loading && <LoadingState />}
        {error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && (
          filtered.length === 0 ? (
            <EmptyState icon={FileText} title="No claims found" message="Try adjusting your filters or search term." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <TableHeader>
                  <Th>Claim ID</Th>
                  <Th>Policy #</Th>
                  <Th>Customer</Th>
                  <Th>Type</Th>
                  <Th>Amount</Th>
                  <Th>Status</Th>
                  <Th>Risk</Th>
                  <Th>Submission Date</Th>
                  <Th>Action</Th>
                </TableHeader>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((c) => {
                    const id = c.id || c.claim_id;
                    return (
                      <tr
                        key={id}
                        className="hover:bg-slate-50 transition-colors cursor-pointer"
                        onClick={() => setSelectedClaimId(id)}
                      >
                        <Td>
                          <span className="font-mono font-semibold text-blue-600">
                            #{String(id || '').slice(-8).toUpperCase()}
                          </span>
                        </Td>
                        <Td>{c.policy_number || '—'}</Td>
                        <Td>{c.customer_name || c.beneficiary_name || '—'}</Td>
                        <Td>{c.claim_type?.replace(/_/g, ' ') || '—'}</Td>
                        <Td className="font-semibold">{fmtCurrency(c.claim_amount)}</Td>
                        <Td>{statusBadge(c.status)}</Td>
                        <Td>{riskBadge(c.risk_category)}</Td>
                        <Td>{fmtDate(c.created_at || c.submission_date)}</Td>
                        <Td onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setSelectedClaimId(id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
                          >
                            <Eye className="w-3 h-3" /> View
                          </button>
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="px-4 py-3 border-t border-slate-100 text-[10px] text-slate-400">
                Showing {filtered.length} of {claims.length} claims
              </div>
            </div>
          )
        )}
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// TAB 3 — Register New Claim
// ─────────────────────────────────────────────

const CLAIM_TYPES = [
  { value: '', label: 'Select claim type…' },
  { value: 'death_benefit', label: 'Death Benefit' },
  { value: 'funeral_cash_plan', label: 'Funeral Cash Plan' },
  { value: 'accident_disability', label: 'Accident & Disability' },
  { value: 'medical_expense', label: 'Medical Expense' },
  { value: 'critical_illness', label: 'Critical Illness' },
  { value: 'other', label: 'Other' },
];

function NewClaimTab() {
  const [form, setForm] = useState({
    policy_number: '',
    claim_type: '',
    claim_amount: '',
    incident_date: '',
    beneficiary_name: '',
    description: '',
  });
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleFiles = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
      files.forEach((f) => fd.append('documents', f));
      const res = await api.submitClaim(fd);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error: ${res.status}`);
      }
      const json = await res.json();
      setSuccess(json);
      setForm({ policy_number: '', claim_type: '', claim_amount: '', incident_date: '', beneficiary_name: '', description: '' });
      setFiles([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls = 'w-full text-xs border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors placeholder:text-slate-300';
  const labelCls = 'block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1';

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-lg font-extrabold text-slate-800">Register New Claim</h1>
        <p className="text-xs text-slate-500 mt-0.5">Complete all required fields to submit a new insurance claim</p>
      </div>

      {success && (
        <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-2xl">
          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-green-700">Claim submitted successfully!</p>
            <p className="text-xs text-green-600 mt-0.5">
              Claim ID: <span className="font-mono font-semibold">#{String(success.id || success.claim_id || '').slice(-8).toUpperCase()}</span>
              {success.status && <> · Status: <span className="font-semibold">{success.status}</span></>}
            </p>
            <button
              onClick={() => setSuccess(null)}
              className="mt-2 text-[10px] font-semibold text-green-700 underline hover:no-underline"
            >
              Submit another claim
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-2xl">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-bold text-red-700">Submission failed</p>
            <p className="text-xs text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {!success && (
        <SectionCard>
          <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">Claim Details</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className={labelCls}>Policy Number *</label>
                <input
                  name="policy_number"
                  type="text"
                  required
                  placeholder="e.g. POL-2024-001234"
                  value={form.policy_number}
                  onChange={handleChange}
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>Claim Type *</label>
                <select
                  name="claim_type"
                  required
                  value={form.claim_type}
                  onChange={handleChange}
                  className={inputCls}
                >
                  {CLAIM_TYPES.map((t) => (
                    <option key={t.value} value={t.value} disabled={!t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>Claim Amount (ZAR) *</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                  <input
                    name="claim_amount"
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={form.claim_amount}
                    onChange={handleChange}
                    className={`${inputCls} pl-8`}
                  />
                </div>
              </div>
              <div>
                <label className={labelCls}>Incident Date *</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                  <input
                    name="incident_date"
                    type="date"
                    required
                    value={form.incident_date}
                    onChange={handleChange}
                    className={`${inputCls} pl-8`}
                  />
                </div>
              </div>
              <div className="sm:col-span-2">
                <label className={labelCls}>Beneficiary Name *</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                  <input
                    name="beneficiary_name"
                    type="text"
                    required
                    placeholder="Full name of beneficiary"
                    value={form.beneficiary_name}
                    onChange={handleChange}
                    className={`${inputCls} pl-8`}
                  />
                </div>
              </div>
            </div>

            <div>
              <label className={labelCls}>Description</label>
              <textarea
                name="description"
                rows={4}
                placeholder="Describe the incident and circumstances of the claim…"
                value={form.description}
                onChange={handleChange}
                className={`${inputCls} resize-none`}
              />
            </div>

            {/* Document Upload */}
            <div>
              <label className={labelCls}>Supporting Documents</label>
              <label className="flex flex-col items-center justify-center w-full border-2 border-dashed border-slate-300 rounded-xl p-6 cursor-pointer hover:border-blue-400 hover:bg-blue-50/40 transition-colors bg-slate-50">
                <Upload className="w-6 h-6 text-slate-400 mb-2" />
                <p className="text-xs font-semibold text-slate-600">Click to upload or drag and drop</p>
                <p className="text-[10px] text-slate-400 mt-0.5">PDF, JPG, PNG up to 10MB each</p>
                <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png" onChange={handleFiles} className="hidden" />
              </label>
              {files.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-slate-100 rounded-lg">
                      <FileText className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                      <span className="text-xs text-slate-700 truncate flex-1">{f.name}</span>
                      <span className="text-[10px] text-slate-400">{(f.size / 1024).toFixed(1)} KB</span>
                      <button
                        type="button"
                        onClick={() => setFiles((p) => p.filter((_, j) => j !== i))}
                        className="p-0.5 text-slate-400 hover:text-red-500 transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-bold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm"
              >
                {submitting ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Submitting…</>
                ) : (
                  <><FileText className="w-3.5 h-3.5" /> Submit Claim</>
                )}
              </button>
            </div>
          </form>
        </SectionCard>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// TAB 4 — FNOL Intake
// ─────────────────────────────────────────────

function FnolTab() {
  const [fnols, setFnols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [fnolForm, setFnolForm] = useState({
    policy_number: '',
    claimant_name: '',
    event_type: '',
    incident_date: '',
    estimated_amount: '',
    channel: 'phone',
    description: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [fnolSuccess, setFnolSuccess] = useState(null);
  const [fnolError, setFnolError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listFnol();
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      setFnols(Array.isArray(json) ? json : json.fnols || json.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleFnolChange = (e) => setFnolForm((p) => ({ ...p, [e.target.name]: e.target.value }));

  const handleFnolSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFnolError(null);
    setFnolSuccess(null);
    try {
      const fd = new FormData();
      Object.entries(fnolForm).forEach(([k, v]) => v && fd.append(k, v));
      const res = await api.submitFnol(fd);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error: ${res.status}`);
      }
      const json = await res.json();
      setFnolSuccess(json);
      setShowForm(false);
      load();
    } catch (e) {
      setFnolError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const triageBadge = (triage) => {
    const map = {
      immediate: 'bg-red-100 text-red-700 border-red-200',
      routine: 'bg-green-100 text-green-700 border-green-200',
      standard: 'bg-blue-100 text-blue-700 border-blue-200',
    };
    const cls = map[(triage || '').toLowerCase()] || 'bg-slate-100 text-slate-500 border-slate-200';
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border ${cls}`}>
        {triage || '—'}
      </span>
    );
  };

  const inputCls = 'w-full text-xs border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors placeholder:text-slate-300';
  const labelCls = 'block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1';

  return (
    <div className="space-y-6">
      {showForm && (
        <Modal title="Log New FNOL" onClose={() => { setShowForm(false); setFnolError(null); }}>
          <form onSubmit={handleFnolSubmit} className="space-y-4">
            {fnolError && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" /> {fnolError}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Policy Number *</label>
                <input name="policy_number" required type="text" placeholder="POL-…" value={fnolForm.policy_number} onChange={handleFnolChange} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Claimant Name *</label>
                <input name="claimant_name" required type="text" placeholder="Full name" value={fnolForm.claimant_name} onChange={handleFnolChange} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Event Type *</label>
                <select name="event_type" required value={fnolForm.event_type} onChange={handleFnolChange} className={inputCls}>
                  <option value="">Select…</option>
                  <option value="death">Death</option>
                  <option value="accident">Accident</option>
                  <option value="disability">Disability</option>
                  <option value="illness">Illness</option>
                  <option value="funeral">Funeral</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Incident Date *</label>
                <input name="incident_date" required type="date" value={fnolForm.incident_date} onChange={handleFnolChange} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Estimated Amount (ZAR)</label>
                <input name="estimated_amount" type="number" min="0" placeholder="0.00" value={fnolForm.estimated_amount} onChange={handleFnolChange} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Notification Channel</label>
                <select name="channel" value={fnolForm.channel} onChange={handleFnolChange} className={inputCls}>
                  <option value="phone">Phone</option>
                  <option value="email">Email</option>
                  <option value="portal">Portal</option>
                  <option value="branch">Branch</option>
                  <option value="agent">Agent</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className={labelCls}>Additional Notes</label>
                <textarea name="description" rows={3} placeholder="Any additional information…" value={fnolForm.description} onChange={handleFnolChange} className={`${inputCls} resize-none`} />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={submitting} className="inline-flex items-center gap-2 px-5 py-2 text-xs font-bold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors">
                {submitting ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Logging…</> : 'Log FNOL'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold text-slate-800">FNOL Intake</h1>
          <p className="text-xs text-slate-500 mt-0.5">First Notice of Loss — incoming event notifications</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} disabled={loading} className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 disabled:opacity-60 transition-colors">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button onClick={() => { setShowForm(true); setFnolError(null); setFnolSuccess(null); }} className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-sm">
            <Plus className="w-3.5 h-3.5" /> Log New FNOL
          </button>
        </div>
      </div>

      {fnolSuccess && (
        <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-2xl">
          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-bold text-green-700">FNOL logged successfully!</p>
            <p className="text-xs text-green-600 mt-0.5">
              Reference: <span className="font-mono font-semibold">{fnolSuccess.fnol_reference || fnolSuccess.id}</span>
            </p>
          </div>
        </div>
      )}

      <SectionCard>
        {loading && <LoadingState />}
        {error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && (
          fnols.length === 0 ? (
            <EmptyState icon={InboxIcon} title="No FNOL records" message="Logged FNOLs will appear here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <TableHeader>
                  <Th>FNOL Ref</Th>
                  <Th>Claim ID</Th>
                  <Th>Policy #</Th>
                  <Th>Claimant</Th>
                  <Th>Event Type</Th>
                  <Th>Incident Date</Th>
                  <Th>Channel</Th>
                  <Th>Est. Amount</Th>
                  <Th>Triage</Th>
                  <Th>Status</Th>
                </TableHeader>
                <tbody className="divide-y divide-slate-100">
                  {fnols.map((f) => (
                    <tr key={f.id || f.fnol_reference} className="hover:bg-slate-50 transition-colors">
                      <Td><span className="font-mono font-semibold text-blue-600">{f.fnol_reference || f.id || '—'}</span></Td>
                      <Td>{f.claim_id ? <span className="font-mono text-slate-600">#{String(f.claim_id).slice(-8).toUpperCase()}</span> : <span className="text-slate-300">—</span>}</Td>
                      <Td>{f.policy_number || '—'}</Td>
                      <Td>{f.claimant_name || '—'}</Td>
                      <Td className="capitalize">{f.event_type || '—'}</Td>
                      <Td>{fmtDate(f.incident_date)}</Td>
                      <Td className="capitalize">{f.channel || '—'}</Td>
                      <Td className="font-semibold">{fmtCurrency(f.estimated_amount)}</Td>
                      <Td>{triageBadge(f.triage_category || f.triage)}</Td>
                      <Td>{statusBadge(f.status)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-3 border-t border-slate-100 text-[10px] text-slate-400">
                {fnols.length} FNOL {fnols.length === 1 ? 'record' : 'records'}
              </div>
            </div>
          )
        )}
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// TAB 5 — AI Risk Assessment
// ─────────────────────────────────────────────

function AssessmentDetailPanel({ assessment, onClose }) {
  if (!assessment) return null;
  const indicators = assessment.fraud_indicators || assessment.indicators || [];

  return (
    <Modal title={`Assessment — Claim #${String(assessment.claim_id || '').slice(-8).toUpperCase()}`} onClose={onClose} wide>
      <div className="space-y-5">
        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Risk Score', value: assessment.fraud_score?.toFixed(1) ?? '—' },
            { label: 'Risk Category', value: riskBadge(assessment.risk_category) },
            { label: 'Indicators', value: indicators.length },
            { label: 'Assessed', value: fmtDate(assessment.assessed_at || assessment.created_at) },
          ].map((item) => (
            <div key={item.label} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-1">{item.label}</p>
              <div className="text-sm font-bold text-slate-800">{item.value}</div>
            </div>
          ))}
        </div>

        {/* Explanation */}
        {(assessment.explanation || assessment.assessment_explanation) && (
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-2">AI Explanation</p>
            <p className="text-xs text-slate-600 leading-relaxed bg-blue-50 border border-blue-100 rounded-xl p-4">
              {assessment.explanation || assessment.assessment_explanation}
            </p>
          </div>
        )}

        {/* Indicators */}
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-2">
            Fraud Indicators ({indicators.length})
          </p>
          {indicators.length === 0 ? (
            <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-xl">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <p className="text-xs text-green-700 font-semibold">No fraud indicators detected</p>
            </div>
          ) : (
            <div className="space-y-2">
              {indicators.map((ind, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-white border border-slate-200 rounded-xl">
                  <div className="flex-shrink-0 mt-0.5">{severityBadge(ind.severity)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-slate-700 font-mono">{ind.code || ind.indicator_code}</span>
                      {ind.weight != null && (
                        <span className="text-[10px] text-slate-400">weight: {ind.weight}</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{ind.detail || ind.description || ind.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

function AiAssessmentTab() {
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listAssessments();
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      setAssessments(Array.isArray(json) ? json : json.assessments || json.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      {selected && <AssessmentDetailPanel assessment={selected} onClose={() => setSelected(null)} />}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold text-slate-800">AI Risk Assessment</h1>
          <p className="text-xs text-slate-500 mt-0.5">Machine-learning fraud scores for all submitted claims</p>
        </div>
        <button onClick={load} disabled={loading} className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Explanation Banner */}
      <div className="flex items-start gap-3 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-2xl">
        <Zap className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-bold text-blue-800">How AI Assessment Works</p>
          <p className="text-xs text-blue-600 mt-0.5 leading-relaxed">
            Our ML model analyses each claim against historical fraud patterns, policy data, document consistency, 
            and behavioural signals to produce a fraud risk score from 0–100. Scores ≥75 are flagged as{' '}
            <strong>Critical</strong>, ≥50 as <strong>High</strong>, ≥25 as <strong>Medium</strong>, and below 
            as <strong>Low</strong>. Click any row to view the detailed explanation and individual fraud indicators.
          </p>
        </div>
      </div>

      <SectionCard>
        {loading && <LoadingState />}
        {error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && (
          assessments.length === 0 ? (
            <EmptyState icon={Shield} title="No assessments yet" message="AI assessments will appear as claims are processed." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <TableHeader>
                  <Th>Claim ID</Th>
                  <Th>Customer</Th>
                  <Th>Claim Type</Th>
                  <Th>Amount</Th>
                  <Th>Risk Score</Th>
                  <Th>Risk Category</Th>
                  <Th>Indicators</Th>
                  <Th>Assessed Date</Th>
                  <Th>Detail</Th>
                </TableHeader>
                <tbody className="divide-y divide-slate-100">
                  {assessments.map((a) => (
                    <tr
                      key={a.id || a.claim_id}
                      className="hover:bg-slate-50 transition-colors cursor-pointer"
                      onClick={() => setSelected(a)}
                    >
                      <Td>
                        <span className="font-mono font-semibold text-blue-600">
                          #{String(a.claim_id || a.id || '').slice(-8).toUpperCase()}
                        </span>
                      </Td>
                      <Td>{a.customer_name || a.claimant_name || '—'}</Td>
                      <Td>{(a.claim_type || a.claim?.claim_type || '—').replace(/_/g, ' ')}</Td>
                      <Td className="font-semibold">{fmtCurrency(a.claim_amount || a.claim?.claim_amount)}</Td>
                      <Td><RiskScoreBar score={a.fraud_score} /></Td>
                      <Td>{riskBadge(a.risk_category)}</Td>
                      <Td>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          (a.fraud_indicators?.length || a.indicators?.length || 0) > 0 ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'
                        }`}>
                          {a.fraud_indicators?.length ?? a.indicators?.length ?? 0}
                        </span>
                      </Td>
                      <Td>{fmtDate(a.assessed_at || a.created_at)}</Td>
                      <Td onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => setSelected(a)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition-colors"
                        >
                          <ChevronRight className="w-3 h-3" /> Detail
                        </button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-3 border-t border-slate-100 text-[10px] text-slate-400">
                {assessments.length} assessments
              </div>
            </div>
          )
        )}
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// TAB 6 — Profile
// ─────────────────────────────────────────────

function ProfileTab({ user }) {
  const fields = [
    { label: 'Full Name', value: user?.full_name, icon: User },
    { label: 'Username', value: user?.username, icon: User },
    { label: 'Email Address', value: user?.email, icon: TrendingUp },
    { label: 'Role', value: user?.role?.replace(/_/g, ' '), icon: Shield },
    { label: 'Department', value: user?.department, icon: BarChart2 },
  ];

  const initials = (user?.full_name || user?.username || 'CO')
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-lg font-extrabold text-slate-800">My Profile</h1>
        <p className="text-xs text-slate-500 mt-0.5">Your account information and role details</p>
      </div>

      <SectionCard>
        {/* Avatar header */}
        <div className="p-6 flex items-center gap-4 border-b border-slate-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center text-white text-xl font-extrabold shadow-md flex-shrink-0">
            {initials}
          </div>
          <div>
            <p className="text-base font-extrabold text-slate-800">{user?.full_name || user?.username || 'Claims Officer'}</p>
            <p className="text-xs text-slate-500 mt-0.5">{user?.email || '—'}</p>
            <div className="mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-blue-100 text-blue-700 rounded-full text-[10px] font-bold uppercase tracking-wide border border-blue-200">
              <Shield className="w-3 h-3" />
              {user?.role?.replace(/_/g, ' ') || 'Claims Officer'}
            </div>
          </div>
        </div>

        {/* Profile fields */}
        <div className="p-6 space-y-4">
          {fields.map((f) => (
            <div key={f.label} className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div className="p-2 bg-white rounded-lg border border-slate-200 flex-shrink-0">
                <f.icon className="w-3.5 h-3.5 text-slate-400" />
              </div>
              <div>
                <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">{f.label}</p>
                <p className="text-xs font-semibold text-slate-700 mt-0.5 capitalize">{f.value || '—'}</p>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// Root — ClaimsOfficerDashboard
// ─────────────────────────────────────────────

export default function ClaimsOfficerDashboard({ user, activeTab, setActiveTab, token }) {
  const renderTab = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardTab user={user} />;
      case 'my-claims':
        return <MyClaimsTab />;
      case 'new-claim':
        return <NewClaimTab />;
      case 'fnol':
        return <FnolTab />;
      case 'ai-assessment':
        return <AiAssessmentTab />;
      case 'profile':
        return <ProfileTab user={user} />;
      default:
        return <DashboardTab user={user} />;
    }
  };

  return (
    <div className="min-h-full p-6">
      {renderTab()}
    </div>
  );
}
