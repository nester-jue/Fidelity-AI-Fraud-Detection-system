/**
 * ComplianceDashboard.jsx
 * NEXA AI Fraud Detection Platform — Compliance & Regulatory Monitoring workspace.
 * Tabs: compliance-overview | compliance-alerts | claims-under-review | investigations | audit-trails | regulatory-reports
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck, Eye, Building2, UserCheck, AlertTriangle, Timer, RotateCw, FileUp,
  Activity, Loader2, CheckCircle, Users, MessageSquare, User, History, ClipboardList,
  Search, ArrowUpRight,
} from 'lucide-react';
import { api } from '../../api/apiClient';

const fmtCurrency = (v) => (v != null ? new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR', maximumFractionDigits: 0 }).format(v) : '—');

function Card({ icon: Icon, title, value, colorCls, children }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 border-t-4 ${colorCls}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
      <p className="text-2xl font-extrabold text-slate-900 mt-1">{value}</p>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

function SectionCard({ icon: Icon, title, subtitle, children, actions }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-red-600" />
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">{title}</h2>
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}

function ComplianceAlertsTab() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.complianceDashboard();
      if (res.ok) {
        const d = await res.json();
        setAlerts(d.compliance_alerts || []);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-red-600" /></div>;

  if (alerts.length === 0) {
    return (
      <div className="p-10 text-center">
        <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
        <p className="text-sm font-bold text-slate-500">No active compliance alerts</p>
        <p className="text-xs text-slate-400">All flagged claims and high-risk assessments are under review.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-100">
      {alerts.map((a, i) => (
        <div key={i} className="px-5 py-4 flex items-start gap-4 hover:bg-slate-50">
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${a.severity === 'Critical' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>{a.severity}</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-slate-900">{a.claim_id}</span>
              <span className="text-[10px] font-mono font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">{a.type}</span>
            </div>
            <div className="text-xs font-semibold text-slate-600 mt-1">Risk: {a.risk_score}/100 — {a.risk_category}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ClaimsUnderReviewTab() {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.complianceDashboard();
        if (res.ok) {
          const d = await res.json();
          setClaims(d.active_investigations || []);
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-red-600" /></div>;
  if (claims.length === 0) return <EmptyState />;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
          <tr><th className="py-3 px-4">Investigation ID</th><th className="py-3 px-4">Claim ID</th><th className="py-3 px-4">Claimant</th><th className="py-3 px-4">Amount</th><th className="py-3 px-4">Risk</th><th className="py-3 px-4">Investigator</th><th className="py-3 px-4">Status</th><th className="py-3 px-4">Opened</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100 font-medium">
          {claims.map(c => (
            <tr key={c.investigation_id} className="hover:bg-slate-50">
              <td className="py-3 px-4 font-mono font-bold text-slate-600">INV-{c.investigation_id}</td>
              <td className="py-3 px-4 font-mono text-blue-600">{c.claim_id}</td>
              <td className="py-3 px-4 text-slate-800">{c.customer_name}</td>
              <td className="py-3 px-4 font-mono font-bold">{fmtCurrency(c.amount)}</td>
              <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${c.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : c.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>{c.risk_category}</span></td>
              <td className="py-3 px-4">{c.investigator}</td>
              <td className="py-3 px-4"><span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-amber-100 text-amber-700">{c.investigation_status}</span></td>
              <td className="py-3 px-4 font-mono text-slate-500">{c.opened_at ? new Date(c.opened_at).toLocaleString('en-ZA') : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState() {
  return <div className="p-12 text-center"><ShieldCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" /><p className="text-sm font-bold text-slate-500">Nothing to review</p><p className="text-xs text-slate-400 mt-1">No active investigations or compliance exceptions.</p></div>;
}

function AuditTrailsTab() {
  const [logs, setLogs] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.auditLogs({ limit: 50 });
        if (res.ok) setLogs(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const filtered = logs.filter(l =>
    !q || [l.action, l.user, l.target].some(v => String(v || '').toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div>
      <SectionCard icon={ClipboardList} title="Immutable Audit Trail" subtitle="All compliance-relevant activity, user activity, and system events" actions={<input placeholder="Search..." className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-slate-50 w-48" value={q} onChange={e => setQ(e.target.value)} />}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
              <tr><th className="py-3 px-4">Time</th><th className="py-3 px-4">User</th><th className="py-3 px-4">Role</th><th className="py-3 px-4">Action</th><th className="py-3 px-4">Target</th><th className="py-3 px-4">Detail</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading && !filtered.length && <tr><td colSpan="6" className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin text-red-600 mx-auto" /></td></tr>}
              {!loading && filtered.length === 0 && <tr><td colSpan="6" className="py-8 text-center text-slate-400">No audit events</td></tr>}
              {filtered.map(l => (
                <tr key={l.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 font-mono text-slate-500 whitespace-nowrap">{l.timestamp ? new Date(l.timestamp).toLocaleString('en-ZA') : '—'}</td>
                  <td className="py-3 px-4 text-slate-800">{l.user}</td>
                  <td className="py-3 px-4 text-slate-600">{l.user_role}</td>
                  <td className="py-3 px-4 font-mono font-bold text-slate-700">{l.action}</td>
                  <td className="py-3 px-4 font-mono text-slate-600 max-w-xs truncate">{l.target}</td>
                  <td className="py-3 px-4 text-slate-500 text-[10px]">{JSON.stringify(l.detail || {})}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

function RegulatoryReportsTab() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [excs, setExcs] = useState([]);
  const [message, setMessage] = useState('');
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [r, e] = await Promise.all([api.listComplianceReports(), api.listComplianceExceptions()]);
        if (r.ok) setReports(await r.json());
        if (e.ok) setExcs((await e.json()).exceptions || []);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="space-y-6 nexa-report">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2"><FileUp size={14} className="text-red-600" /><span>Regulatory Compliance Reports</span></h3>
        <button className="px-4 py-2 text-xs font-bold bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors disabled:opacity-50" disabled={loading} onClick={async () => {
          setLoading(true);
          setMessage('');
          try {
            const res = await api.generateComplianceReport();
            if (!res.ok) throw new Error(`Request failed (${res.status})`);
            const created = await res.json();
            const refreshed = await api.listComplianceReports();
            if (refreshed.ok) setReports(await refreshed.json());
            setMessage(`Report #${created.id} generated and recorded.`);
          } catch (err) {
            setMessage(`Could not generate report: ${err.message || 'unknown error'}`);
          } finally {
            setLoading(false);
          }
        }}>Generate Report</button>
      </div>
      {message && <div className="px-4 py-2 text-xs font-bold rounded-lg bg-slate-100 text-slate-700">{message}</div>}
      <SectionCard icon={ShieldCheck} title="Compliance Exceptions — Policy & Regulatory Exceptions">
        <div className="divide-y divide-slate-100">
          {excs.length === 0 && <div className="py-8 text-center text-slate-400 text-xs">No compliance exceptions. All claims are within regulatory thresholds.</div>}
          {excs.map(x => (
            <div key={x.claim_id} className="px-5 py-3 flex items-center gap-3 hover:bg-slate-50">
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${x.exception_type === 'FRAUD_RISK_EXCEPTION' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{x.exception_type}</span>
              <span className="font-mono font-bold text-slate-800">{x.claim_id}</span>
              <span className="text-slate-700">{x.customer_name}</span>
              <span className="font-mono text-red-600 font-bold text-sm" title="AI risk score (0–100), not a currency amount">Risk {x.risk_score ?? '—'}</span>
              <span className="text-[10px] bg-slate-100 px-2 py-0.5 rounded-full font-bold text-slate-700">{x.investigation_status}</span>
              <span className="ml-auto text-xs text-slate-500">{x.claim_status}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard icon={ShieldCheck} title="Generated Compliance Reports">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-2.5 px-4">ID</th><th className="py-2.5 px-4">Type</th><th className="py-2.5 px-4">Generated At</th><th className="py-2.5 px-4">Period</th></tr></thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {reports.length === 0 && <tr><td colSpan="4" className="py-8 text-center text-slate-400">No reports generated</td></tr>}
              {reports.map(r => (
                <tr key={r.id}><td className="py-2.5 px-4 font-mono text-slate-600">#{r.id}</td><td className="py-2.5 px-4 font-semibold text-slate-800">{r.report_type}</td><td className="py-2.5 px-4 font-mono text-slate-500">{r.generated_at ? new Date(r.generated_at).toLocaleString('en-ZA') : '—'}</td><td className="py-2.5 px-4">{r.period_start ? new Date(r.period_start).toLocaleDateString() : ''} — {r.period_end ? new Date(r.period_end).toLocaleDateString() : ''}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

function UserActivityTab() {
  const [activity, setActivity] = useState([]);
  const [userFilter, setUserFilter] = useState('');
  const load = useCallback(async () => {
    try {
      const res = await api.complianceDashboard();
      if (res.ok) {
        const d = await res.json();
        setActivity(d.user_activity || []);
      }
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <SectionCard icon={UserCheck} title="User Activity Records">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
            <tr><th className="py-3 px-4">User</th><th className="py-3 px-4">Role</th><th className="py-3 px-4">Action</th><th className="py-3 px-4 text-right">Count</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {activity.map((a, i) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="py-3 px-4">{a.user}</td>
                <td className="py-3 px-4 text-slate-500">{a.user_role}</td>
                <td className="py-3 px-4 font-mono font-bold text-slate-800">{a.action}</td>
                <td className="py-3 px-4 text-right font-mono">{a.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function ComplianceOverviewTab() {
  const [summary, setSummary] = useState(null);
  const [alertsSummary, setAlertsSummary] = useState([]);
  const load = useCallback(async () => {
    try {
      const res = await api.complianceDashboard();
      if (res.ok) {
        const d = await res.json();
        setSummary(d.summary);
        setAlertsSummary(d.compliance_alerts || []);
      }
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card icon={AlertTriangle} title="Claims Requiring Review" value={summary?.claims_requiring_review ?? '—'} colorCls="border-t-red-600" />
        <Card icon={ShieldCheck} title="High-Risk Claims" value={summary?.high_risk_claims ?? '—'} colorCls="border-t-orange-600" />
        <Card icon={History} title="Open Investigations" value={summary?.open_investigations ?? '—'} colorCls="border-t-blue-600" />
        <Card icon={AlertTriangle} title="Escalated Cases" value={summary?.escalated_investigations ?? '—'} colorCls="border-t-amber-600" />
        <Card icon={CheckCircle} title="Confirmed Fraud" value={summary?.confirmed_fraud_cases ?? '—'} colorCls="border-t-emerald-600" />
        <Card icon={UserCheck} title="Compliance Alerts" value={summary?.compliance_alerts ?? '—'} colorCls="border-t-red-600" />
      </div>
      <SectionCard icon={Timer} title="Recent Compliance Alerts">
        <div className="px-5 py-4">
          {alertsSummary.length === 0 ? (
            <div className="p-6 text-center"><CheckCircle className="w-8 h-8 text-emerald-400 mx-auto" /><p className="text-sm font-bold text-slate-500 mt-2">No active alerts</p></div>
          ) : (
            <div className="space-y-2">
              {alertsSummary.slice(0, 10).map((a, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-red-50 border border-red-100 rounded-xl">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-red-600 text-white">{a.type}</span>
                  <span className="font-mono font-bold text-slate-800">{a.claim_id}</span>
                  <span className="text-xs text-slate-600">{a.risk_category} — {a.severity}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </SectionCard>
    </div>
  );
}

export default function ComplianceDashboard({ activeTab }) {
  // Mirror the parent App's activeTab into the internal view so each sidebar
  // item (Dashboard, Compliance Alerts, Regulatory Reports, …) shows its own
  // section instead of the default overview.
  const [tab, setTab] = useState(activeTab || 'compliance-overview');
  useEffect(() => { if (activeTab) setTab(activeTab); }, [activeTab]);
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Compliance & Regulatory Monitoring Workspace</h1>
          <p className="text-xs text-slate-500 mt-0.5">Regulatory compliance exceptions, case escalation history & immutable audit trails</p>
        </div>
        <div className="flex gap-2">
          {[
            { id: 'compliance-overview', label: 'Compliance Overview' },
            { id: 'compliance-alerts', label: 'Compliance Alerts' },
            { id: 'claims-under-review', label: 'Claims Under Review' },
            { id: 'investigations', label: 'Investigations' },
            { id: 'audit-trails', label: 'Audit Trails' },
            { id: 'regulatory-reports', label: 'Regulatory Reports' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 text-xs font-bold rounded-xl transition-colors ${tab === t.id ? 'bg-[#0F2744] text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>{t.label}</button>
          ))}
        </div>
      </div>

      {tab === 'compliance-overview' && <ComplianceOverviewTab />}
      {tab === 'compliance-alerts' && <ComplianceAlertsTab />}
      {tab === 'claims-under-review' && <ClaimsUnderReviewTab />}
      {tab === 'investigations' && <ClaimsUnderReviewTab />}
      {tab === 'audit-trails' && <AuditTrailsTab />}
      {tab === 'user-activity' && <UserActivityTab />}
      {tab === 'regulatory-reports' && <RegulatoryReportsTab />}

      {tab === 'case-escalation' && <SectionCard icon={History} title="Case Escalation History"><div className="py-8 text-center text-slate-400 text-xs">Escalation timeline loaded on demand.</div></SectionCard>}
    </div>
  );
}
