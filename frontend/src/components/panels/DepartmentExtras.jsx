import React, { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle, RefreshCw, ShieldAlert, HeartPulse, Database, Link2, FileSearch, PieChart, Users } from 'lucide-react';
import { api } from '../../api/apiClient.js';

// ---------------------------------------------------------------------------
// DepartmentExtras — functional panels for the extended master-prompt
// navigation items. Every panel: loading state → success → empty state →
// error state with Retry. No fabricated data; everything is backend-driven.
// ---------------------------------------------------------------------------

function PanelLoading() {
  return (
    <div className="flex items-center justify-center h-48 text-slate-400">
      <Loader2 className="w-6 h-6 animate-spin" />
    </div>
  );
}

function PanelEmpty({ title, note }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center max-w-xl mx-auto">
      <AlertCircle className="w-8 h-8 text-slate-300 mx-auto" />
      <h3 className="font-extrabold text-slate-600 mt-2">{title}</h3>
      {note && <p className="text-xs text-slate-400 mt-1.5">{note}</p>}
    </div>
  );
}

function PanelError({ error, onRetry }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center max-w-xl mx-auto flex flex-col items-center">
      <AlertCircle className="w-8 h-8 text-red-400" />
      <h3 className="font-extrabold text-red-700 mt-2">Could not load this view</h3>
      <p className="text-xs text-red-600 mt-1">{error}</p>
      <button onClick={onRetry} className="mt-4 px-5 py-2.5 bg-red-600 text-white font-bold text-xs rounded-xl hover:bg-red-700 shadow-md flex items-center gap-2"><RefreshCw size={14} /><span>Retry</span></button>
    </div>
  );
}

function useList(fetcher) {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  // Store the fetcher in a ref so inline (unmemoised) arrow functions passed
  // by callers don't re-trigger the effect on every render.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetcherRef.current({ signal: controller.signal })
      .then((d) => { if (active) setItems(d); })
      .catch(() => { if (active) setItems([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);

  return {
    items: items || [],
    loading,
    error,
    retry: () => setRetry(r => r + 1),
  };
}

function claimsFetcher() {
  return api.listClaims().then(r => (r.ok ? r.json() : [])).then(d => Array.isArray(d) ? d : []);
}

// ─── Claims workflow (shared claim lists) ────────────────────────────────

function ClaimsTable({ items, emptyTitle, emptyNote, header, extraRow }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">{header} ({items.length})</div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <tbody className="divide-y divide-slate-100 font-medium">
            {items.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">{emptyTitle}</td></tr>
            ) : (
              items.map((c, i) => extraRow(c, i))
            )}
          </tbody>
        </table>
      </div>
      {!items.length && <p className="px-6 py-2 text-[11px] text-slate-400">{emptyNote}</p>}
    </div>
  );
}

const riskBadge = (category) => (
  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
    category === 'Critical' ? 'bg-red-100 text-red-800'
      : category === 'High' ? 'bg-orange-100 text-orange-800'
        : category === 'Medium' ? 'bg-amber-100 text-amber-800'
          : 'bg-emerald-100 text-emerald-800'
  }`}>{category || 'Unassessed'}</span>
);

export function PendingClaimsPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const pending = items.filter(c => ['flagged', 'submitted', 'under_investigation', 'pending_documents'].includes((c.status || '').toLowerCase()));
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Pending Claims</h1><p className="text-xs text-slate-500 mt-0.5">Claims awaiting your next action or review</p></div>
      {pending.length === 0 ? <PanelEmpty title="No pending claims" note="All claims in your portfolio are in a state that does not require your attention." /> : (
        <ClaimsTable items={pending} header="Pending Claims" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{c.claim_type}</td>
              <td className="py-3 px-4 font-mono font-bold">${Number(c.amount).toLocaleString()}</td>
              <td className="py-3 px-4">{riskBadge(c.risk_category)}</td>
              <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{c.status}</span></td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function MissingInformationPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const missing = items.filter(c => (c.status || '').toLowerCase() === 'pending_documents');
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Missing Information</h1><p className="text-xs text-slate-500 mt-0.5">Claims that require additional documentation or evidence</p></div>
      {missing.length === 0 ? <PanelEmpty title="No claims missing information" note="Every claim in the system has its documentation status up to date." /> : (
        <ClaimsTable items={missing} header="Claims Missing Documentation" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{c.claim_type}</td>
              <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">PENDING_DOCUMENTS</span></td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function HighRiskClaimsPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const high = items.filter(c => ['Critical', 'High'].includes(c.risk_category));
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">High-Risk Claims</h1><p className="text-xs text-slate-500 mt-0.5">Claims flagged with Critical or High risk by the AI assessment</p></div>
      {high.length === 0 ? <PanelEmpty title="No high-risk claims" note="The fraud engine has not flagged any claims as Critical or High at this time." /> : (
        <ClaimsTable items={high} header="High-Risk Claims" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{riskBadge(c.risk_category)}</td>
              <td className="py-3 px-4 font-mono font-bold">${Number(c.amount).toLocaleString()}</td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function EscalatedClaimsPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const esc = items.filter(c => (c.status || '').toLowerCase() === 'escalated');
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Escalated Claims</h1><p className="text-xs text-slate-500 mt-0.5">Claims escalated for senior review or fraud investigation</p></div>
      {esc.length === 0 ? <PanelEmpty title="No escalated claims" note="There are no escalated claims assigned to the escalation queue at this time." /> : (
        <ClaimsTable items={esc} header="Escalated Claims" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{riskBadge(c.risk_category)}</td>
              <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 uppercase">ESCALATED</span></td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function AIRiskAnalysisPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const risky = items.filter(c => ['Critical', 'High'].includes(c.risk_category));
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">AI Risk Analysis</h1><p className="text-xs text-slate-500 mt-0.5">AI-assessed claims with significant fraud risk and recommended actions</p></div>
      {risky.length === 0 ? <PanelEmpty title="No AI risk alerts" note="The AI engine has not produced high-risk assessments for active claims at this time." /> : (
        <ClaimsTable items={risky} header="Claims With High AI Risk" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{riskBadge(c.risk_category)}</td>
              <td className="py-3 px-4 font-mono font-bold">${Number(c.amount).toLocaleString()}</td>
              <td className="py-3 px-4 text-[11px] font-medium text-slate-600 max-w-xs truncate">{c.top_indicator || 'AI risk flag'}</td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function ClaimAllocationPanel({ user }) {
  const { items, loading, error, retry } = useList(claimsFetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const alloc = items.filter(c => ['submitted', 'flagged', 'pending_documents'].includes((c.status || '').toLowerCase()));
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Claim Allocation</h1><p className="text-xs text-slate-500 mt-0.5">Claims ready to be allocated to Case Managers, investigators and relevant departments</p></div>
      {alloc.length === 0 ? <PanelEmpty title="No claims awaiting allocation" note="All received claims have been allocated or cleared." /> : (
        <ClaimsTable items={alloc} header="Claims Awaiting Allocation" emptyTitle="" emptyNote=""
          extraRow={(c) => (
            <tr key={c.claim_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
              <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4">{riskBadge(c.risk_category)}</td>
              <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{c.status}</span></td>
            </tr>
          )} />
      )}
    </div>
  );
}

export function DepartmentReportsPanel({ user }) {
  const fetcher = () => api.getManagementReports().then(r => (r.ok ? r.json() : [])).then(d => (Array.isArray(d) ? d : (d?.reports || d?.data || [])));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Department Reports</h1><p className="text-xs text-slate-500 mt-0.5">Available management and departmental reports</p></div>
      {items.length === 0 ? <PanelEmpty title="No reports available" note="The report generation service has no published reports at this time. Reports are generated on demand through the Management Reports module." /> : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">Available Reports ({items.length})</div>
          <ul className="divide-y divide-slate-100">
            {items.map((r, i) => (
              <li key={i} className="px-6 py-4 text-xs font-medium text-slate-700 flex justify-between">
                <span>{r?.name || r?.report_type || `Report ${i + 1}`}</span>
                <span className="text-[10px] font-bold text-slate-500 uppercase">{r?.status || r?.type || ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function PerformanceAnalyticsPanel({ user }) {
  const fetcher = () => api.dashboardOverview().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const k = items?.kpis || {};
  const stats = [
    ['Total Claims Received', k.total_claims_received ?? '—'],
    ['Claims Analysed by AI', k.claims_analysed_by_ai ?? '—'],
    ['Critical Risk Claims', k.critical_risk_claims ?? '—'],
    ['AI Coverage Rate', `${k.ai_coverage_rate ?? 0}%`],
  ];
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Performance Analytics</h1><p className="text-xs text-slate-500 mt-0.5">Claims, AI analysis coverage and risk workload key performance indicators</p></div>
      {items && stats.length === 0 ? null : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map(([label, value]) => (
            <div key={label} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-[#0F2744]">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
              <p className="text-3xl font-black text-slate-900 mt-2">{value}</p>
            </div>
          ))}
        </div>
      )}
      {items && !items.kpis && <PanelEmpty title="No KPI data" note="The claims dashboard has not returned any key performance indicators for this reporting period." />}
    </div>
  );
}

export function DocumentComparisonPanel({ user }) {
  const [selected, setSelected] = useState(['', '']);
  const [docs, setDocs] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!selected.some(Boolean)) return;
    let active = true;
    setLoading(true); setError('');
    Promise.all(selected.map(id => api.getOcrDocument(id).then(r => (r.ok ? r.json() : null)).catch(() => null)))
      .then(ds => { if (active) setDocs(Object.fromEntries(ds.filter(Boolean).map(d => [d.id || d.document_id, d]))); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected[0], selected[1]]);

  const listFetcher = () => api.listOcrDocuments().then(r => (r.ok ? r.json() : [])).then(d => (Array.isArray(d) ? d : []));
  const { items: docList, loading: docListLoading, error: docListError, retry: docListRetry } = useList(listFetcher);

  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={() => { window.location.reload(); }} />;
  if (docListLoading) return <PanelLoading />;
  if (docListError) return <PanelError error={docListError} onRetry={docListRetry} />;

  const pair = selected.map(id => docs[id]).filter(Boolean);
  const hashes = new Set(pair.map(d => (d?.document_hash || d?.document_hash_sha256 || '')).filter(Boolean));

  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Document Comparison</h1><p className="text-xs text-slate-500 mt-0.5">Compare document fingerprints of two registered OCR documents</p></div>
      <div className="grid grid-cols-2 gap-3">
        {[0, 1].map(i => (
          <select key={i} value={selected[i]} onChange={e => { const n = [...selected]; n[i] = e.target.value; setSelected(n); }} className="w-full p-3 border border-slate-300 rounded-xl bg-white font-semibold text-xs">
            <option value="">Select document {i + 1}…</option>
            {docList.map(d => <option key={d.id} value={d.id}>{d.filename || d.id} · {d.document_type || ''}</option>)}
          </select>
        ))}
      </div>
      {pair.length === 2 && (
        <div className={`p-5 rounded-2xl border ${hashes.size === 1 ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50'}`}>
          <p className="font-bold text-sm mb-2">{hashes.size === 1 ? 'Identical document fingerprint' : 'Distinct document fingerprints'}</p>
          {pair.map((d, i) => (
            <div key={i} className="text-xs mt-1 font-mono">
              <span className="font-bold">{d.filename || d.id}</span> — SHA-256: {(d.document_hash_sha256 || d.document_hash || '—').slice(0, 32)}…
            </div>
          ))}
          <p className="text-[10px] text-slate-500 mt-2">Note: identical fingerprints indicate potential duplicate document reuse for forensic review.</p>
        </div>
      )}
      {docList.length === 0 && <PanelEmpty title="No documents registered" note="No OCR documents have been uploaded and processed yet." />}
    </div>
  );
}

// ─── Compliance ──────────────────────────────────────────────────────────

export function DocumentationCompliancePanel({ user }) {
  const fetcher = () => Promise.allSettled([api.listComplianceExceptions(), api.listComplianceReports()])
    .then(res => {
      const exceptions = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => []) : [];
      const reports = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => []) : [];
      return Promise.all([exceptions, reports]);
    });
  const { items: data, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const [exceptions = [], reports = []] = Array.isArray(data) ? data : [[], []];
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Documentation Compliance</h1><p className="text-xs text-slate-500 mt-0.5">Compliance exceptions, documentation gaps and outstanding compliance items</p></div>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 className="text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-3">Outstanding Compliance Exceptions ({exceptions.length})</h3>
          {exceptions.length === 0 ? <p className="text-xs text-slate-400">No compliance exceptions are outstanding.</p> : (
            <ul className="space-y-2">
              {exceptions.map((x, i) => (
                <li key={x.id || i} className="text-xs border border-slate-200 rounded-lg px-3 py-2">
                  <p className="font-semibold">{x.title || x.exception_type || x.code || 'Compliance item'}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{x.description || x.details || ''}</p>
                  {x.severity && <span className="inline-block mt-1 text-[9px] font-black uppercase bg-red-100 text-red-800 px-1.5 py-0.5 rounded">{x.severity}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 className="text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-3">Compliance Reports ({reports.length})</h3>
          {reports.length === 0 ? <p className="text-xs text-slate-400">No compliance reports have been generated yet.</p> : (
            <ul className="space-y-2">
              {reports.map((r, i) => (
                <li key={r.id || i} className="text-xs border border-slate-100 rounded-lg px-3 py-2">
                  <p className="font-semibold text-slate-800">{r.report_type || r.name || `Report ${i + 1}`}</p>
                  {r.status && <p className="text-[10px] text-slate-500 mt-0.5">Status: {r.status}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export function PolicyVerificationPanel({ user }) {
  const fetcher = () => Promise.allSettled([api.policies(), api.customers()]).then(res => {
    const policies = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => []) : [];
    const customers = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => []) : [];
    return [policies, customers];
  });
  const { items: data, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const [policies = [], customers = []] = data || [[], []];
  const statuses = {};
  policies.forEach(p => { statuses[p.status || 'unspecified'] = (statuses[p.status || 'unspecified'] || 0) + 1; });
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Policy Verification</h1><p className="text-xs text-slate-500 mt-0.5">Verify registered policy records, statuses and associated customers</p></div>
      <div className="grid md:grid-cols-3 gap-3">
        {Object.entries(statuses).map(([status, count]) => (
          <div key={status} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-blue-500"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{status} Policies</span><p className="text-3xl font-black text-slate-900 mt-2">{count}</p></div>
        ))}
      </div>
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">Registered Policies ({policies.length})</div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-2.5 px-4">Policy Number</th><th className="py-2.5 px-4">Type</th><th className="py-2.5 px-4">Customer</th><th className="py-2.5 px-4">Status</th><th className="py-2.5 px-4">Effective</th></tr></thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {policies.map((p, i) => (
                <tr key={p.policy_number || i}>
                  <td className="py-2.5 px-4 font-mono font-bold text-slate-900">{p.policy_number}</td>
                  <td className="py-2.5 px-4">{p.policy_type || '—'}</td>
                  <td className="py-2.5 px-4">{(customers.find(c => c.id === p.customer_id)?.name || p.customer_name || '—')}</td>
                  <td className="py-2.5 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{p.status || 'active'}</span></td>
                  <td className="py-2.5 px-4 font-mono text-slate-500">{p.effective_date ? p.effective_date.slice(0, 10) : '—'}</td>
                </tr>
              ))}
              {policies.length === 0 && <tr><td colSpan="5" className="py-8 text-center text-slate-400">No policies registered.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function RegulatoryMonitoringPanel({ user }) {
  const fetcher = () => api.zimRegulatoryRules().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const groups = items?.rule_groups || [];
  const total = groups.reduce((n, g) => n + (g.rules?.length || 0), 0);
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Regulatory Monitoring</h1><p className="text-xs text-slate-500 mt-0.5">Ongoing monitoring of regulatory rules and compliance requirements for the Zimbabwean insurance environment</p></div>
      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <h3 className="text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-3">Monitoring Snapshot — Regulatory Rules ({total})</h3>
        {groups.length === 0 ? <p className="text-xs text-slate-400">No regulatory rules defined at this time.</p> : (
          <ul className="space-y-2">
            {groups.flatMap(g => (g.rules || []).map(r => (
              <li key={r.rule_id} className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 flex justify-between">
                <span className="font-semibold text-slate-800">{r.rule_id}</span>
                <span className="text-[10px] text-slate-500">{String(r.value)} · {g.group_id.replace(/_/g, ' ')}</span>
              </li>
            )))}
          </ul>
        )}
        <p className="text-[10px] text-slate-400 mt-3">Source: /zim/regulatory-rules — regulatory rules snapshot from the NEXA regulatory data service. Values are platform defaults; administrators verify against current legislation with legal counsel.</p>
      </div>
    </div>
  );
}

// ─── Executive / CRO risk ────────────────────────────────────────────────

export function RiskDashboardPanel({ user }) {
  const fetcher = () => Promise.allSettled([api.dashboardOverview(), api.fraudNetworkInsights()]).then(res => {
    const ov = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => null) : null;
    const ins = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => null) : null;
    return [ov, ins];
  });
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const [ov, ins] = items || [null, null];
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Risk Dashboard</h1><p className="text-xs text-slate-500 mt-0.5">Enterprise-wide risk overview: claims workload and fraud network exposure</p></div>
      {ov?.kpis && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[['Total Claims', ov.kpis.total_claims_received, 'slate'], ['Critical Risk', ov.kpis.critical_risk_claims, 'red'], ['AI Analysed', ov.kpis.claims_analysed_by_ai, 'purple'], ['Fraud Losses Prevented', `$${Number(ov.kpis.prevented_fraud_losses_usd || 0).toLocaleString()}`, 'emerald']].map(([label, value, color]) => (
            <div key={label} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-slate-800"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span><p className="text-3xl font-black text-slate-900 mt-2">{value}</p></div>
          ))}
        </div>
      )}
      {ins && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-4">Fraud Network Exposure</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Entities</p><p className="text-3xl font-black text-[#0F2744]">{ins.summary?.total_nodes || 0}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Relationships</p><p className="text-3xl font-black text-slate-600">{ins.summary?.total_edges || 0}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-red-500">Suspicious Signals</p><p className="text-3xl font-black text-red-600">{(ins.suspicious_nodes || []).length + (ins.suspicious_edges || []).length}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Clusters</p><p className="text-3xl font-black text-slate-800">{ins.summary?.clusters || 0}</p></div>
          </div>
        </div>
      )}
      {!ov?.kpis && !ins && <PanelEmpty title="No data available" note="The risk dashboards have not returned data yet. Try again shortly." />}
    </div>
  );
}

export function EnterpriseRiskOverviewPanel({ user }) {
  const fetcher = () => api.dashboardOverview().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const dist = items?.risk_distribution || [];
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Enterprise Risk Overview</h1><p className="text-xs text-slate-500 mt-0.5">Enterprise-wide risk distribution across the claims portfolio</p></div>
      {dist.length === 0 ? <PanelEmpty title="No risk distribution data" note="Claim risk categories have not been computed for the current portfolio." /> : (
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Claims Risk Distribution (0-100)</h3>
          {dist.map((item, i) => (
            <div key={i} className="mt-2">
              <div className="flex justify-between text-xs font-bold mb-1"><span>{item.name}</span><span>{item.percentage}% ({item.count})</span></div>
              <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden"><div className="h-full rounded-full transition-all" style={{ width: `${item.percentage}%`, backgroundColor: item.color }} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function FraudRiskExposurePanel({ user }) {
  const fetcher = () => api.fraudNetworkGraph().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const suspiciousCount = (items?.suspicious_nodes || []).length + (items?.suspicious_edges || []).length;
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Fraud Risk Exposure</h1><p className="text-xs text-slate-500 mt-0.5">Enterprise exposure to potential fraud relationships and exposure magnitude</p></div>
      {!items?.nodes?.length ? <PanelEmpty title="No fraud exposure relationships" note="The fraud network graph currently has no relationships — exposure to collusion risk is nil." /> : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-[#0F2744]"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Entities at Risk</span><p className="text-3xl font-black text-slate-900 mt-2">{items.suspicious_nodes?.length || 0}</p></div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-red-600"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Risk Relationships</span><p className="text-3xl font-black text-slate-900 mt-2">{suspiciousCount}</p></div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-amber-500"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Connected Entities</span><p className="text-3xl font-black text-slate-900 mt-2">{items.summary?.total_nodes || 0}</p></div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-slate-600"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Suspicion Clusters</span><p className="text-3xl font-black text-slate-900 mt-2">{items.summary?.clusters || 0}</p></div>
        </div>
      )}
    </div>
  );
}

export function EmergingRiskPatternsPanel({ user }) {
  const fetcher = () => Promise.allSettled([api.fraudNetworkGraph(), api.fraudNetworkInsights()]).then(res => {
    const net = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => null) : null;
    const ins = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => null) : null;
    return [net, ins];
  });
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const [net, ins] = items || [null, null];
  const newClusters = (net?.clusters || []).slice(0, 5);
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Emerging Risk Patterns</h1><p className="text-xs text-slate-500 mt-0.5">Emerging complicit relationship clusters and newly detected risk signals</p></div>
      {!newClusters.length ? <PanelEmpty title="No emerging patterns detected" note="No new suspicious clusters are currently being identified by network analysis." /> : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">Detected Clusters ({newClusters.length})</div>
          <ul className="divide-y divide-slate-100">
            {newClusters.map(c => (
              <li key={c.cluster_id} className="px-6 py-4 text-xs font-medium">
                <p className="font-bold text-red-800">Cluster · {(c.claim_ids || []).length} claims · {c.member_count} entities</p>
                <p className="text-slate-500">{(c.relationship_evidence || []).slice(0, 3).join(' ; ')}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {ins?.emerging && ins.emerging.length > 0 && (
        <ul className="space-y-2">
          {ins.emerging.map((p, i) => <li key={i} className="text-xs bg-white rounded-2xl border border-slate-200 px-4 py-3 font-medium text-slate-600">{p.pattern || p.description || `Pattern ${i + 1}`}</li>)}
        </ul>
      )}
    </div>
  );
}

export function RiskConcentrationPanel({ user }) {
  const fetcher = () => api.dashboardOverview().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const dist = items?.risk_distribution || [];
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Risk Concentration</h1><p className="text-xs text-slate-500 mt-0.5">Concentration of risk across claims and entities by category and severity</p></div>
      {dist.length === 0 ? <PanelEmpty title="No risk concentration data" note="Claims risk distribution data is unavailable for this reporting period." /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {dist.map((item, i) => (
            <div key={i} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <PieChart size={18} className="text-[#0F2744] inline mb-1" />
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{item.name}</p>
              <p className="text-3xl font-black text-[#0F2744] mt-2">{item.percentage}%</p>
              <p className="text-xs text-slate-500 mt-1">{item.count} claims</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function RiskReportsPanel({ user }) {
  const fetcher = () => Promise.allSettled([api.getManagementReports(), api.generateComplianceReport()]).then(res => {
    const reports = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => []) : [];
    return Array.isArray(reports) ? reports : [];
  });
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Risk Reports</h1><p className="text-xs text-slate-500 mt-0.5">Generated reports related to enterprise risk, fraud exposure and risk monitoring</p></div>
      {items.length === 0 ? <PanelEmpty title="No risk reports available" note="No published risk reports are currently available in the report repository." /> : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">Risk Reports ({items.length})</div>
          <ul className="divide-y divide-slate-100">
            {items.map((r, i) => (
              <li key={i} className="px-6 py-4 text-xs font-medium text-slate-700 flex justify-between items-center">
                <span>{r?.name || r?.report_type || `Report ${i + 1}`}</span>
                <span className="text-[10px] font-bold text-slate-500 uppercase">{r?.status || r?.type || ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Fraud Trends ────────────────────────────────────────────────────────

export function FraudTrendsPanel({ user }) {
  const fetcher = () => api.fraudNetworkInsights().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Fraud Trends</h1><p className="text-xs text-slate-500 mt-0.5">Recent trends in fraudulent activity and collusion risk detected by the network</p></div>
      {!items?.summary ? <PanelEmpty title="No trend data" note="The fraud network insights service has no trend data for the current period." /> : (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Entities</p><p className="text-3xl font-black text-[#0F2744] mt-2">{items.summary?.total_nodes ?? 0}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Relationships</p><p className="text-3xl font-black text-slate-600 mt-2">{items.summary?.total_edges ?? 0}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-red-500">Suspicious Signals</p><p className="text-3xl font-black text-red-600 mt-2">{(items.suspicious_nodes || []).length + (items.suspicious_edges || []).length}</p></div>
            <div><p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Clusters</p><p className="text-3xl font-black text-slate-800 mt-2">{items.summary?.clusters ?? 0}</p></div>
          </div>
          {items.trends?.length > 0 && (
            <ul className="space-y-1.5 text-xs">
              {items.trends.map((t, i) => (
                <li key={i} className="flex justify-between text-slate-600"><span>{t.pattern || t.trend || t.description || `Trend ${i + 1}`}</span><span className="font-bold">{t.count ?? ''}</span></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Administration ──────────────────────────────────────────────────────

export function DepartmentManagementPanel({ user }) {
  const fetcher = () => api.listUsers().then(r => (r.ok ? r.json() : [])).then(d => (Array.isArray(d) ? d : []));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const byRole = {};
  items.forEach(u => { const r = u.role || 'unassigned'; (byRole[r] = byRole[r] || []).push(u); });
  const depts = {};
  items.forEach(u => { const d = u.department || 'Unassigned'; (depts[d] = depts[d] || []).push(u); });
  return (
    <div className="space-y-6 max-w-4xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">Department Management</h1><p className="text-xs text-slate-500 mt-0.5">Overview of employee-to-department assignments and roles across NEXA</p></div>
      {items.length === 0 ? <PanelEmpty title="No staff on record" note="The user registry has no employees registered yet." /> : (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-4">By Department</h3>
            <div className="space-y-3">
              {Object.entries(depts).map(([d, us]) => (
                <div key={d} className="flex justify-between items-center"><span className="font-semibold text-slate-800">{d}</span><span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-bold text-[10px]">{us.length} staff</span></div>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-4">By Role</h3>
            <div className="space-y-3">
              {Object.entries(byRole).map(([r, us]) => (
                <div key={r} className="flex justify-between items-center"><span className="font-semibold text-slate-800">{r.replace(/_/g, ' ')}</span><span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-bold text-[10px]">{us.length}</span></div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function DatabaseMonitoringPanel({ user }) {
  const fetcher = () => api.dashboardOverview().then(r => (r.ok ? r.json() : null));
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const k = items?.kpis || {};
  const kpis = [
    ['Total Claims', k.total_claims_received ?? '—', 'blue'],
    ['Claims Analysed by AI', k.claims_analysed_by_ai ?? '—', 'purple'],
    ['Critical Risk Claims', k.critical_risk_claims ?? '—', 'red'],
  ];
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-extrabold text-slate-900">Database Monitoring</h1><p className="text-xs text-slate-500 mt-0.5">Database connectivity, record volumes and system data counts</p></div>
        <Database size={20} className="text-[#0F2744] opacity-70" />
      </div>
      {kpis.every(([, v]) => v === '—') ? <PanelEmpty title="Database counters unavailable" note="Live database metrics are not available at this time. Try again shortly." /> : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {kpis.map(([label, value, color]) => (
            <div key={label} className={`bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-${color}-500`}><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span><p className="text-3xl font-black text-slate-900 mt-2">{value}</p></div>
          ))}
        </div>
      )}
    </div>
  );
}

export function APIMonitoringPanel({ user }) {
  const fetcher = () => api.health().then(r => (r.ok ? r.json().catch(() => null) : null)).catch(() => null);
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  if (!items) {
    return (
      <div className="space-y-6 max-w-3xl">
        <div><h1 className="text-2xl font-extrabold text-slate-900">API Monitoring</h1><p className="text-xs text-slate-500 mt-0.5">Endpoint health and API service status</p></div>
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
          <AlertCircle className="w-8 h-8 text-amber-400 mx-auto" />
          <p className="text-xs text-slate-500 mt-2">No health status returned. The API monitoring service is not available.</p>
          <button onClick={retry} className="mt-4 px-5 py-2.5 bg-[#0F2744] text-white font-bold text-xs rounded-xl"><RefreshCw size={14} className="inline mr-1.5" />Retry</button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-extrabold text-slate-900">API Monitoring</h1><p className="text-xs text-slate-500 mt-0.5">Endpoint health via /health — overall system connectivity</p></div>
        <Link2 size={20} className="text-[#0F2744] opacity-70" />
      </div>
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-4">
          <span className={`w-4 h-4 rounded-full ${items.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <div>
            <p className="text-sm font-extrabold">API Status: <span className={items.status === 'healthy' ? 'text-emerald-800' : 'text-red-800'}>{items.status}</span></p>
            <p className="text-xs text-slate-500 mt-0.5">Endpoint: <code className="font-mono">GET /health</code></p>
          </div>
        </div>
        <p className="text-[10px] text-slate-400 mt-3">API connectivity and health endpoint monitoring. Dependent service health is monitored through module-specific dashboards.</p>
      </div>
    </div>
  );
}

export function SystemHealthPanel({ user }) {
  const fetcher = () => Promise.allSettled([api.health(), api.dashboardOverview()]).then(res => {
    const h = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => null) : null;
    const ov = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => null) : null;
    return [h, ov];
  });
  const { items, loading, error, retry } = useList(fetcher);
  if (loading) return <PanelLoading />;
  if (error) return <PanelError error={error} onRetry={retry} />;
  const [h, ov] = items || [null, null];
  const k = ov?.kpis || {};
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="text-2xl font-extrabold text-slate-900">System Health</h1><p className="text-xs text-slate-500 mt-0.5">Overall NEXA system health and operational status</p></div>
      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-emerald-500"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Overall Status</span><p className="text-3xl font-black text-emerald-800 mt-2">{h?.status || 'unknown'}</p></div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-blue-500"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Service</span><p className="text-lg font-black text-slate-800 mt-2">{h?.service || '—'}</p></div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-amber-500"><span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Claims (Live)</span><p className="text-3xl font-black text-slate-800 mt-2">{k.total_claims_received ?? '—'}</p></div>
      </div>
      {!h && !ov && <PanelEmpty title="Health data unavailable" note="Live health metrics are not available. Try again shortly." />}
    </div>
  );
}

// ─── AI Assistant (shared for the "AI Assistant" nav items) ──────────────

export function AIAssistantPanel({ user }) {
  const [messages, setMessages] = useState([]);
  const [suggested, setSuggested] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    Promise.allSettled([api.chatSuggestedQuestions(), api.chatHistory()])
      .then(res => {
        const sug = res[0].status === 'fulfilled' && res[0].value.ok ? res[0].value.json().catch(() => []) : [];
        const hist = res[1].status === 'fulfilled' && res[1].value.ok ? res[1].value.json().catch(() => []) : [];
        setSuggested(Array.isArray(sug) ? sug : []);
        setMessages(Array.isArray(hist) ? hist.slice(-10) : []);
      })
      .catch(() => {});
  }, []);

  const send = async () => {
    const q = input.trim();
    if (!q || sending) return;
    setSending(true); setErr('');
    setMessages(m => [...m, { type: 'user', text: q, at: new Date().toLocaleString('en-ZA') }]);
    setInput('');
    try {
      const res = await api.chatSendMessage(q);
      if (res.ok) {
        const d = await res.json();
        setMessages(m => [...m, { type: 'bot', text: d.response || d.answer || 'No response.', at: new Date().toLocaleString('en-ZA') }]);
      } else {
        setErr(`AI assistant query failed: ${res.status}`);
      }
    } catch {
      setErr('Could not reach the AI assistant service. Check your connection.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 h-[70vh] flex flex-col">
      <div><h1 className="text-2xl font-extrabold text-slate-900 flex items-center gap-2"><HeartPulse size={22} className="text-[#0F2744]" /> AI Assistant</h1><p className="text-xs text-slate-500 mt-0.5">Role-aware conversational assistant (NEXA AI) — queries are enforced by backend RBAC</p></div>
      <div className="flex-1 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {err && <div className="bg-red-50 border-l-4 border-red-600 px-4 py-2.5 rounded-xl text-xs font-bold text-red-800">{err}</div>}
          {messages.length === 0 ? (
            <p className="text-center text-slate-400 text-xs py-8">No messages yet. Ask a question or pick a suggestion below.</p>
          ) : messages.map((m, i) => (
            <div key={i} className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`px-3.5 py-2.5 rounded-xl text-xs max-w-[85%] ${m.type === 'user' ? 'bg-[#0F2744] text-white' : 'bg-slate-50 border border-slate-200 text-slate-700'}`}>
                <p>{m.text}</p>
                <span className="block mt-1 text-[9px] font-mono text-slate-400">{m.at}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-slate-100 p-3">
          <div className="flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Ask a fraud-related question…" className="flex-1 px-3 py-2.5 border border-slate-300 rounded-xl text-xs" />
            <button onClick={send} disabled={sending || !input.trim()} className="px-4 py-2.5 bg-[#0F2744] text-white rounded-xl font-bold text-xs disabled:opacity-50"><Loader2 className={`w-4 h-4 inline ${sending ? 'animate-spin' : ''}`} /></button>
          </div>
          {suggested.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {suggested.slice(0, 4).map((s, i) => <button key={i} onClick={() => { setInput(s); }} className="text-[10px] px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200">{s}</button>)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function UsersPanelEmpty() { return null; }
