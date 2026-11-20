/**
 * FraudInvestigationDashboard.jsx
 * NEXA AI Fraud Detection Platform — Fraud Investigation workspace.
 * Tabs: investigation-overview | fraud-alerts | assigned-cases | evidence-management | ai-forensic-analysis | investigation-reports
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck, Timer, RotateCw, FileText, AlertTriangle, CheckCircle,
  Eye, Loader2, Users, Paperclip, TrendingUp, Brain,
} from 'lucide-react';
import { api } from '../../api/apiClient';

const fmtCurrency = (v) => (v != null ? new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR', maximumFractionDigits: 0 }).format(v) : '—');

function Card({ icon: Icon, title, value, colorCls, sub }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 border-t-4 ${colorCls}`}>
      <div className="flex justify-between items-center mb-1">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
      <p className="text-2xl font-extrabold text-slate-900 mt-1">{value}</p>
      {sub && <p className="text-[11px] text-slate-500 font-semibold mt-1">{sub}</p>}
    </div>
  );
}

function loadDetail(docId) {
  return api.getOcrDocument(docId).then(r => r.ok ? r.json() : null);
}

export default function FraudInvestigationDashboard() {
  const [tab, setTab] = useState('investigation-overview');
  const [dash, setDash] = useState(null);
  const [detailDoc, setDetailDoc] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.fraudInvestigatorDashboard();
      if (res.ok) {
        const d = await res.json();
        setDash(d);
      } else {
        // Fallback for environments where the endpoint is unavailable
        const [inv, alerts] = await Promise.all([api.listInvestigations(), api.highRiskForensicQueue()]);
        setDash({ open_cases: inv.ok ? await inv.json() : [], fraud_alerts: alerts.ok ? await alerts.json() : [] });
      }
    } catch (e) {
      console.error(e);
      setDash({ open_cases: [], fraud_alerts: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openDoc = async (docId) => {
    const doc = await loadDetail(docId);
    if (doc) setDetailDoc(doc);
  };

  if (loading) return <div className="flex justify-center py-24"><Loader2 className="w-8 h-8 animate-spin text-red-600" /></div>;

  const s = dash?.summary || {};
  const openCases = dash?.open_cases || [];
  const alerts = dash?.fraud_alerts || [];
  const highRisk = dash?.high_risk_claims || [];
  const evidence = dash?.ocr_evidence || [];
  const findings = dash?.ai_forensic_findings || [];
  const histPatterns = dash?.historical_suspicious_patterns || [];
  const evidenceCount = evidence.length;
  const findingsCount = findings.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Fraud Investigation Workspace</h1>
          <p className="text-xs text-slate-500 mt-0.5">Special Investigation Unit: AI alerts, assigned cases, and forensic evidence</p>
        </div>
        <div className="flex gap-2">
          {[
            { id: 'investigation-overview', label: 'Overview' },
            { id: 'fraud-alerts', label: 'Fraud Alerts' },
            { id: 'assigned-cases', label: 'Assigned Cases' },
            { id: 'ai-forensic-analysis', label: 'AI Forensics' },
            { id: 'evidence-management', label: 'Evidence' },
            { id: 'investigation-reports', label: 'Reports' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 text-xs font-bold rounded-xl transition-colors ${tab === t.id ? 'bg-[#0F2744] text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>{t.label}</button>
          ))}
        </div>
      </div>

      {/* Overview KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card icon={ShieldCheck} title="New Fraud Alerts" value={s.new_fraud_alerts ?? '—'} colorCls="border-t-red-600" />
        <Card icon={Timer} title="Assigned to Me" value={s.assigned_to_me ?? '—'} colorCls="border-t-blue-600" />
        <Card icon={Timer} title="Open Investigations" value={s.open_investigations ?? '—'} colorCls="border-t-red-600" />
        <Card icon={AlertTriangle} title="Escalated Cases" value={s.escalated_cases ?? '—'} colorCls="border-t-amber-600" />
        <Card icon={CheckCircle} title="Confirmed Fraud" value={s.confirmed_fraud ?? '—'} colorCls="border-t-emerald-600" />
        <Card icon={CheckCircle} title="Cases Awaiting Evidence" value={s.cases_awaiting_evidence ?? 0} colorCls="border-t-orange-600" />
      </div>

      {/* ─── FRAUD ALERTS ─── */}
      {tab === 'fraud-alerts' && (
        <div className="space-y-4">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700 flex items-center space-x-2"><AlertTriangle size={15} className="text-red-600" /><span>New AI Fraud Alerts</span></h2>
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {alerts.length === 0 ? (
              <div className="p-10 text-center"><CheckCircle className="w-8 h-8 text-emerald-400 mx-auto" /><p className="text-sm font-bold text-slate-500 mt-2">No high-risk alerts in queue</p></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-3 px-4">Claim ID</th><th className="py-3 px-4">Customer</th><th className="py-3 px-4">Risk</th><th className="py-3 px-4">Amount</th><th className="py-3 px-4">Status</th><th className="py-3 px-4">Has Investigation</th></tr></thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {alerts.map((a, i) => (
                      <tr key={a.claim_id || i} className="hover:bg-red-50/50">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{a.claim_id}</td>
                        <td className="py-3 px-4">{a.customer_name}</td>
                        <td className="py-3 px-4 font-mono font-bold text-red-700">{a.risk_score}/100 — {a.risk_category}</td>
                        <td className="py-3 px-4 font-mono font-bold">{fmtCurrency(a.amount)}</td>
                        <td className="py-3 px-4"><span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{a.claim_status || '—'}</span></td>
                        <td className="py-3 px-4 text-slate-600">{a.has_investigation ? <span className="font-bold text-emerald-600">Yes</span> : <span className="font-bold text-amber-600">No</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── ASSIGNED CASES ─── */}
      {tab === 'assigned-cases' && (
        <div className="space-y-4">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700 flex items-center space-x-2"><Users size={15} className="text-blue-600" /><span>Investigations Assigned to Me</span></h2>
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {dash?.assigned_investigations?.length === 0 && (
              <div className="p-10 text-center text-slate-400 text-xs">No investigations assigned to you.</div>
            )}
            {(dash?.assigned_investigations || []).map(c => (
              <div key={c.investigation_id} className="border-b border-slate-100 p-4 flex justify-between items-center">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-800">INV-{c.investigation_id}</span>
                    <span className="font-mono font-bold text-blue-600">{c.claim_id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${c.status === 'open' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{c.status}</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-1">{c.customer_name} · opened {c.opened_at ? new Date(c.opened_at).toLocaleString('en-ZA') : '—'}</div>
                  <div className="text-xs text-slate-500 mt-0.5">Evidence attached: {c.ocr_evidence_count} document(s)</div>
                </div>
                <div className="text-right text-xs text-slate-500">
                  <div className="flex space-x-1 font-mono font-bold">
                    {c.progress?.open && <span className="text-red-600">Open</span>}
                    {c.progress?.in_review && <span className="text-amber-600">In Review</span>}
                    {c.progress?.escalated && <span className="text-purple-600">Escalated</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">High-Risk Claims Awaiting Investigation</h3>
          {highRisk.length === 0 ? <p className="text-xs text-slate-400">No unassigned high-risk claims.</p> : (
            <table className="w-full text-left text-xs bg-white rounded-2xl border border-slate-200">
              <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-2.5 px-4">Claim</th><th className="py-2.5 px-4">Customer</th><th className="py-2.5 px-4">Risk</th><th className="py-2.5 px-4">Amount</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {highRisk.map((a, i) => (
                  <tr key={i}><td className="py-2.5 px-4 font-mono font-bold text-red-700">{a.claim_id}</td><td className="py-2.5 px-4">{a.customer_name}</td><td className="py-2.5 px-4 font-mono font-bold">{a.risk_score} — {a.risk_category}</td><td className="py-2.5 px-4 font-mono font-bold">{fmtCurrency(a.amount)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Open Investigation Cases</h3>
          {openCases.length === 0 ? <p className="text-xs text-slate-400">No open investigations.</p> : (
            <div className="space-y-2">
              {openCases.map(c => (
                <div key={c.investigation_id} className="p-4 border border-slate-200 rounded-2xl flex justify-between items-center">
                  <div>
                    <div className="text-sm font-bold text-slate-900">INV-{c.investigation_id} — {c.claim_id}</div>
                    <div className="text-xs text-slate-600">{c.customer_name}</div>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${['open','in_review','escalated'].includes(c.investigation_status) ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>{c.investigation_status}</span>
                    <p className="text-[10px] font-mono mt-0.5">Top Indicator: {c.top_indicator}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── AI FORENSIC ANALYSIS ─── */}
      {tab === 'ai-forensic-analysis' && (
        <div className="space-y-4">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700 flex items-center space-x-2"><Brain size={15} className="text-purple-600" /><span>AI Forensic Findings (Decision-Support Indicators)</span></h2>
          <div className="text-xs text-slate-500 p-4 bg-slate-50 rounded-xl border border-slate-200 italic">
            ⚠ AI Forensic Disclaimer: These findings are decision-support indicators generated by the NEXA AI Engine. They do not independently establish fraud and must not replace human investigation and evidence review.
          </div>
          {findings.length === 0 ? (
            <p className="text-xs text-slate-400 py-4">No AI forensic findings for open investigations yet.</p>
          ) : (
            <div className="space-y-2">
              {findings.map((f, i) => (
                <div key={i} className="p-4 bg-white border border-slate-200 rounded-2xl">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-mono font-bold text-slate-900">{f.claim_id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${f.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : f.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>{f.risk_category} — {f.risk_score}/100</span>
                  </div>
                  {f.explanation && <p className="text-xs text-slate-600">{f.explanation}</p>}
                </div>
              ))}
            </div>
          )}

          <h3 className="text-sm font-extrabold uppercase tracking-wider mt-6 text-slate-700">Historical Suspicious Patterns (Last 12 Months)</h3>
          <div className="flex items-end gap-2 h-28 mt-2">
            {(histPatterns.length ? histPatterns : [{ period: '—', suspicious_claims: 0 }]).map((p, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end h-28 gap-1">
                <div className="w-full bg-red-500 rounded-t-lg" style={{ height: `${Math.max(2, (p.suspicious_claims / Math.max(1, Math.max(...histPatterns.map(x => x.suspicious_claims)))) * 100) * 1.2}px` }} />
                <span className="text-[9px] font-mono font-bold text-slate-500">{p.period}</span>
                <span className="text-[9px] font-black text-slate-700">{p.suspicious_claims}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── EVIDENCE MANAGEMENT ─── */}
      {tab === 'evidence-management' && (
        <div className="space-y-4">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700 flex items-center space-x-2"><Paperclip size={15} className="text-red-600" /><span>OCR-Extracted Evidence ({evidenceCount} documents)</span></h2>
          {evidence.length === 0 ? (
            <p className="text-xs text-slate-400 py-4">No OCR evidence attached to open investigations.</p>
          ) : (
            <div className="space-y-2">
              {evidence.map((d, i) => (
                <div key={i} className="p-4 border border-slate-200 rounded-2xl flex justify-between items-center">
                  <div className="text-sm font-bold text-slate-900">{d.filename}</div>
                  <div className="text-right text-xs text-slate-500 flex items-center gap-3">
                    <span className="font-mono">Conf: {d.confidence_score?.toFixed(0) || '—'}%</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${d.has_date_mismatch ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-800'}`}>{d.has_date_mismatch ? 'Date Mismatch' : 'Clean'}</span>
                    <button onClick={() => openDoc(d.document_id)} className="text-[10px] font-bold bg-blue-50 text-blue-700 px-2 py-0.5 rounded-lg hover:bg-blue-100">View</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── INVESTIGATION REPORTS ─── */}
      {tab === 'investigation-reports' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700 flex items-center space-x-2"><FileText size={15} className="text-red-600" /><span>Investigation Reports & Outcomes</span></h2>
            <button onClick={() => load()} className="text-xs font-bold bg-slate-100 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-200"><RotateCw size={13} /> Refresh</button>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200"><h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Open Investigation Cases ({s.open_investigations})</h3></div>
            {openCases.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">No open investigations.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-2.5 px-4">Case #</th><th className="py-2.5 px-4">Claim</th><th className="py-2.5 px-4">Investigator</th><th className="py-2.5 px-4">Opened At</th><th className="py-2.5 px-4">Outcome</th></tr></thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {openCases.map(c => (
                    <tr key={c.investigation_id}>
                      <td className="py-2.5 px-4 font-mono font-bold text-slate-900">INV-{c.investigation_id}</td>
                      <td className="py-2.5 px-4 font-mono text-blue-700">{c.claim_id}</td>
                      <td className="py-2.5 px-4">{c.investigator}</td>
                      <td className="py-2.5 px-4 font-mono">{c.opened_at ? new Date(c.opened_at).toLocaleString('en-ZA') : '—'}</td>
                      <td className="py-2.5 px-4 text-slate-500">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ─── OVERVIEW (default) ─── */}
      {tab === 'investigation-overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">New Fraud Alerts</h3>
              <div className="text-4xl font-extrabold text-red-600">{alerts.length}</div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">Assigned to Me</h3>
              <div className="text-4xl font-extrabold text-blue-700">{s.assigned_to_me}</div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">OCR Evidence Attached</h3>
              <div className="text-4xl font-extrabold text-red-700">{evidenceCount}</div>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 flex items-center space-x-2"><TrendingUp size={14} className="text-red-600" /><span>Investigation Progress Overview</span></h3>
            {openCases.map(c => (
              <div key={c.investigation_id} className="border-b border-slate-100 py-3 last:border-0">
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-mono font-bold text-slate-800">INV-{c.investigation_id} — {c.claim_id}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${['open','in_review','escalated'].includes(c.investigation_status) ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>{c.investigation_status}</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1">Progress:
                  {' '}{['open','in_review','escalated'].map(st => <span key={st} className={`mx-1 ${st === c.investigation_status ? 'text-red-600 font-black' : 'text-slate-300'}`}>●</span>)}
                </div>
              </div>
            ))}
            {openCases.length === 0 && <p className="py-6 text-center text-slate-400 text-xs">No open investigations.</p>}
          </div>
        </div>
      )}

      {/* ─── OCR DOCUMENT DETAIL MODAL ─── */}
      {detailDoc && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl max-w-3xl w-full shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-slate-200 p-5 flex items-center justify-between rounded-t-3xl">
              <h2 className="text-base font-extrabold text-slate-900">OCR Document — Evidence</h2>
              <button onClick={() => setDetailDoc(null)} className="text-slate-400 hover:text-slate-700"><Eye size={18} className="rotate-90" /></button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ['Filename', detailDoc.filename],
                  ['Document Type', detailDoc.document_type],
                  ['Status', detailDoc.processing_status],
                  ['Confidence', `${(detailDoc.confidence_score || 0).toFixed(1)}%`],
                ].map(([k, v]) => <div key={k} className="bg-slate-50 rounded-xl p-3"><p className="text-slate-500 font-semibold mb-0.5">{k}</p><p className="font-bold text-slate-800">{v}</p></div>)}
              </div>
              {detailDoc.raw_text_snippet && (
                <div>
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-1.5">Extracted Text</h3>
                  <div className="bg-slate-900 text-slate-200 rounded-xl p-4 font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">{detailDoc.raw_text_snippet}</div>
                </div>
              )}
              {(detailDoc.extracted_dates?.length || detailDoc.extracted_amounts?.length || detailDoc.extracted_national_ids?.length) && (
                <div>
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-1.5">Structured Fields</h3>
                  <div className="flex flex-wrap gap-2">
                    {detailDoc.extracted_dates?.map((d, i) => <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-bold">{d}</span>)}
                    {detailDoc.extracted_amounts?.map((a, i) => <span key={i} className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded text-xs font-bold">${Number(a).toLocaleString()}</span>)}
                    {detailDoc.extracted_national_ids?.map((n, i) => <span key={i} className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-mono font-bold">{n}</span>)}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
