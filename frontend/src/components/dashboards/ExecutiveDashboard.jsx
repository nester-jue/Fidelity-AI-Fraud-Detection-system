/**
 * ExecutiveDashboard.jsx — Executive / CRO workspace (enterprise upgrade).
 *
 * Tabs: executive-overview | claims-performance | fraud-analytics |
 *       financial-exposure | department-performance | management-reports
 *       ai-fraud-intelligence
 *
 * All figures come from the backend (no fabricated data):
 *   - /departmental/executive                 — KPI, trends, product, dept, exec data
 *   - /departmental/executive/monthly-trends  — monthly trend (with date filter)
 *   - /departmental/executive/yearly-exposure — year-over-year exposure
 *   - /departmental/executive/product-analysis— fraud by insurance product
 *   - /departmental/executive/suspicions      — priority suspicious queue
 *   - /departmental/executive/investigations  — investigation progress
 *   - /departmental/executive/ai-insights     — data-driven AI insights
 *   - /claims/{id}, /investigations/{id}      — drill-down views
 *   - /management-reports/                    — report generate/list/export
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  DollarSign, ShieldCheck, Building2, RotateCw, TrendingUp,
  FileText, AlertTriangle, Users, MapPinned, AlertCircle,
  Loader2, CheckCircle, X, ClipboardList, Flag, Activity, ShieldAlert,
  Star, Download, LineChart, PieChart, BarChart3,
} from 'lucide-react';
import { api } from '../../api/apiClient';

const money = (v) => (v == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v));
const num = (v) => (v == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v));
const fmtPct = (v, def = '—') => (v == null ? def : `${Number(v).toFixed(1)}%`);
const iso = (v) => (v ? new Date(v).toLocaleString('en-ZA') : '—');
const fmtYmd = (v) => (v ? v.slice(0, 10) : '—');

// ─────────────────────────────────────────────
// Design system
// ─────────────────────────────────────────────

function KpiCard({ icon: Icon, title, value, trend, colorCls = 'border-t-blue-600', topColor = '#0F2744' }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 border-t-4 ${colorCls}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1.5">{title}</p>
          <p className="text-3xl font-extrabold text-slate-900 mt-1 leading-none">{value}</p>
        </div>
        <div className="p-3 rounded-xl bg-slate-50 text-slate-900">
          <Icon className="w-5 h-5" />
        </div>
      </div>
      {trend && <p className={`text-xs font-bold mt-2 flex items-center space-x-1 ${trend.startsWith('+') ? 'text-emerald-600' : trend.startsWith('-') ? 'text-red-600' : 'text-slate-500'}`}>{trend}</p>}
    </div>
  );
}

function StatCard({ icon: Icon, title, value, subtitle, colorCls = 'border-t-blue-600' }) {
  return (
    <div className={`bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 ${colorCls}`}>
      <div className="flex justify-between items-center">
        <div className="p-3 rounded-xl bg-slate-50 text-slate-900"><Icon className="w-5 h-5" /></div>
        <div className="text-right"><p className="text-3xl font-extrabold text-slate-900 mt-1">{value}</p></div>
      </div>
      <div className="mt-2">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>
        {subtitle && <p className="text-[11px] font-medium text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function Table({ headers, rows, emptyText = 'No data', textColor = 'text-slate-400', maxH = 320 }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
            <tr>{headers.map((h, i) => <th key={i} className="py-3 px-4">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {rows.length === 0 ? (
              <tr><td colSpan={headers.length} className={`py-8 text-center ${textColor}`}>{emptyText}</td></tr>
            ) : rows.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50 transition">
                {row}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProgressBar({ pct, colorCls = 'bg-blue-500' }) {
  const v = Math.min(100, Math.max(0, Number(pct) || 0));
  return <div className="h-2 bg-slate-100 rounded-full overflow-hidden w-28"><div className={`h-full ${colorCls}`} style={{ width: `${v}%` }} /></div>;
}

function Loading() {
  return <div className="flex justify-center py-24"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;
}
function ErrorBlock({ error, retry }) {
  return (
    <div className="bg-white rounded-2xl border border-red-200 p-6 text-center">
      <AlertCircle className="w-8 h-8 text-red-400 mx-auto" /><p className="text-sm font-bold text-red-600 mt-2">Could not load this view</p>
      <p className="text-xs text-red-500 mt-1">{error || 'The backend did not respond.'}</p>
      <button onClick={retry} className="mt-3 px-4 py-2 bg-red-600 text-white text-xs font-bold rounded-lg hover:bg-red-700">Retry</button>
    </div>
  );
}
function EmptyState({ icon: Icon, title, note }) {
  return (
    <div className="p-8 text-center">
      <Icon className="w-10 h-10 text-slate-300 mx-auto" /><p className="font-bold text-slate-500 mt-2">{title}</p>
      {note && <p className="text-xs text-slate-400 mt-1">{note}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────
// SVG Charts
// ─────────────────────────────────────────────

function MonthlyTrendsChart({ trends }) {
  const W = 760, H = 300;
  const padL = 64, padR = 18, padT = 34, padB = 54;
  const data = trends || [];
  const maxBars = Math.max(...data.flatMap(d => [d.suspected || 0, d.confirmed || 0, d.submitted || 0]), 1);
  const maxLine = Math.max(...data.map(d => d.exposure_amount || 0), 1);
  const n = data.length;
  const slot = n ? (W - padL - padR) / n : 1;
  const barW = Math.max(5, slot * 0.28);
  const gap = Math.max(2, slot * 0.08);
  const top = padT + H, bottom = H - padB;
  const scale = (v, max) => bottom - ((v || 0) / max) * (bottom - padT);
  const linePoints = data.map((d, i) => `${padL + i * slot + slot / 2},${scale(d.exposure_amount, maxLine)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[300px]" role="img" aria-label="Monthly fraud trends">
      {data.map((d, i) => d.submitted > 0 && <rect key={`sub-${i}`} x={padL + i * slot + gap + barW + gap} y={scale(d.submitted, maxBars)} width={barW} height={bottom - scale(d.submitted, maxBars)} fill="#3B82F6" rx="2" />)}
      {data.map((d, i) => d.suspected > 0 && <rect key={`sus-${i}`} x={padL + i * slot + gap} y={scale(d.suspected, maxBars)} width={barW} height={bottom - scale(d.suspected, maxBars)} fill="#F59E0B" rx="2" />)}
      {data.map((d, i) => d.confirmed > 0 && <rect key={`con-${i}`} x={padL + i * slot + 2 * gap + 2 * barW} y={scale(d.confirmed, maxBars)} width={barW} height={bottom - scale(d.confirmed, maxBars)} fill="#EF4444" rx="2" />)}
      <polyline points={linePoints} fill="none" stroke="#0F2744" strokeWidth="2.5" strokeDasharray="7 5" />
      {data.map((d, i) => <text key={`t-${i}`} x={padL + i * slot + slot / 2} y={bottom + 13} fontSize="7" fill="#64748B" textAnchor="middle">{d.period}</text>)}
      <line x1={padL} y1={bottom} x2={W - padR} y2={bottom} stroke="#E2E8F0" />
      <line x1={padL} y1={padT} x2={padL} y2={bottom} stroke="#E2E8F0" />
      <text x={14} y={padT - 2} fontSize="7" fontWeight="bold" fill="#64748B">Suspected (amber) &bull; Confirmed (red) vs Exposure in USD (dashed blue)</text>
      <text x={W - padR} y={padT - 2} fontSize="7" textAnchor="end" fill="#64748B">Exposure: ${maxLine >= 1000000 ? `${(maxLine / 1000000).toFixed(1)}M` : num(maxLine)}</text>
    </svg>
  );
}

function YoYExposureChart({ rows }) {
  const W = 760, H = 300;
  const padL = 64, padR = 18, padT = 34, padB = 62;
  const data = rows || [];
  const max = Math.max(...data.map(r => r.exposure_amount || 0), 1);
  const n = data.length;
  const slot = n ? (W - padL - padR) / n : 1;
  const barW = Math.min(30, slot * 0.7);
  const bottom = H - padB;
  const scale = v => bottom - ((v || 0) / max) * (bottom - padT);
  const pos = i => padL + i * slot + slot / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[300px]" role="img" aria-label="Year-over-year financial exposure">
      {data.map((r, i) => (
        <g key={r.year}>
          <rect x={pos(i) - barW / 2} y={scale(r.exposure_amount)} width={barW} height={bottom - scale(r.exposure_amount)} fill="#2563EB" rx="3" />
          <text x={pos(i)} y={bottom + 13} fontSize="8" fill="#64748B" textAnchor="middle">{r.year}</text>
          <text x={pos(i)} y={scale(r.exposure_amount) - 9} fontSize="8" fontWeight="bold" fill="#0F2744" textAnchor="middle">${r.exposure_amount.toLocaleString('en-US')}</text>
          {r.year_over_year_growth_pct != null && (
            <text x={pos(i)} y={scale(r.exposure_amount) + 18} fontSize="8" fontWeight="bold"
              fill={r.year_over_year_growth_pct > 0 ? '#10B981' : r.year_over_year_growth_pct < 0 ? '#EF4444' : '#64748B'}
              textAnchor="middle">
              {r.year_over_year_growth_pct > 0 ? '+' : ''}{r.year_over_year_growth_pct}%
            </text>
          )}
        </g>
      ))}
      <line x1={padL} y1={bottom} x2={W - padR} y2={bottom} stroke="#E2E8F0" />
      <line x1={padL} y1={padT} x2={padL} y2={bottom} stroke="#E2E8F0" />
      <text x={14} y={padT - 2} fontSize="7" fontWeight="bold" fill="#64748B">Annual Financial Exposure (+/- year-over-year growth)</text>
    </svg>
  );
}

function ProductAnalysisChart({ rows }) {
  // Horizontal bars — suspected claims per product
  const data = rows || [];
  const W = 620, H = Math.max(120, data.length * 30 + 40);
  const padT = 44, padR = 168, padB = 24, padL = 8;
  const max = Math.max(...data.map(r => r.suspected_risk || 0), 1);
  const barY = (i) => padT + i * 30;
  const barH = 20;
  const widthOf = (v) => ((v || 0) / max) * (W - padL - padR);
  return (
    <svg viewBox={`0 0 ${W + padL} ${H}`} className="w-full h-auto" role="img" aria-label="Insurance product fraud analysis">
      <text x={14} y={22} fontSize="8" fontWeight="bold" fill="#64748B">Product Fraud Analysis — suspected claims by product</text>
      {data.map((r, i) => (
        <g key={r.product_name} transform={`translate(${padL}, 0)`}>
          <text x={0} y={barY(i) + 15} fontSize="8" fill="#475569">{(r.product_name || '—').slice(0, 26)}</text>
          <rect x={88} y={barY(i)} width={widthOf(r.suspected_risk)} height={barH} fill="#F59E0B" rx="3" />
          <text x={88 + widthOf(r.suspected_risk) + 6} y={barY(i) + 14} fontSize="8" fill="#0F2744">{num(r.suspected_risk)}</text>
          <text x={400} y={barY(i) + 15} fontSize="7" fill="#64748B">${r.total_exposure?.toLocaleString('en-US')} · {fmtPct(r.suspected_share_pct, '0%')} suspected</text>
        </g>
      ))}
      {data.length === 0 && <text x={14} y={60} fontSize="9" fill="#94A3B8">No product data available.</text>}
    </svg>
  );
}

function RiskDistributionChart({ riskDist }) {
  const data = riskDist || [];
  const map = { Critical: { color: '#EF4444', label: 'Critical' }, High: { color: '#F97316', label: 'High' }, Medium: { color: '#F59E0B', label: 'Medium' }, Low: { color: '#10B981', label: 'Low' } };
  const items = Object.entries(map).map(([k, v]) => {
    const row = data.find(d => (d.name || '').startsWith(k));
    return { ...v, count: row?.count || 0, pct: row?.percentage || 0 };
  }).filter(x => x.count > 0);
  const max = Math.max(...items.map(x => x.count), 1);
  const W = 620, H = 96;
  const padL = 70;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[96px]" role="img" aria-label="Fraud risk distribution">
      {items.map((it, i) => (
        <g key={it.label} transform={`translate(${padL}, 0)`}>
          <rect x={0} y={8} width={((it.count / max) * 460)} height={16} fill={it.color} rx="8" />
          <text x={(it.count / max) * 460 + 6} y={22} fontSize="8" fontWeight="bold" fill={it.color}>{num(it.count)}</text>
          <text x={0} y={38} fontSize="8" fontWeight="bold" fill="#475569">{it.label}</text>
          <text x={0} y={51} fontSize="7" fill="#94A3B8">{fmtPct(it.pct)} of assessed</text>
        </g>
      ))}
      {items.length === 0 && <text x={14} y={16} fontSize="9" fill="#94A3B8">No risk distribution data available.</text>}
    </svg>
  );
}

// ─────────────────────────────────────────────
// Drill-down: Claim Detail Modal
// ─────────────────────────────────────────────

function ClaimDetailModal({ claimId, onClose, onEscalate, onUpdate }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [evidenceDocs, setEvidenceDocs] = useState([]);
  const [notes, setNotes] = useState([]);
  const [updateNotes, setUpdateNotes] = useState('');
  const [updating, setUpdating] = useState(false);
  const [escalating, setEscalating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [claimRes, notesRes] = await Promise.all([
        api.getClaim(claimId),
        api.claimNotes(claimId),
      ]);
      const d = claimRes.ok ? await claimRes.json() : null;
      if (d) {
        setDetail(d);
        setEvidenceDocs(d.documents || []);
      }
      if (notesRes.ok) setNotes(await notesRes.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [claimId]);

  useEffect(() => { load(); }, [load]);

  if (!detail) return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white rounded-3xl p-6"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>
    </div>
  );

  const a = detail.assessment || {};
  const inv = detail.investigation;

  const doUpdate = async () => {
    setUpdating(true);
    try { await onUpdate(detail.claim_id, { status: inv?.status || 'open', notes: updateNotes }); setUpdateNotes(''); } catch (e) { console.error(e); }
    finally { setUpdating(false); }
  };
  const doEscalate = async () => {
    setEscalating(true);
    try { await onEscalate(detail.claim_id); } catch (e) { console.error(e); }
    finally { setEscalating(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-3xl w-full max-w-3xl max-h-[85vh] overflow-y-auto shadow-2xl border border-slate-200">
        <div className="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex justify-between items-center">
          <h3 className="text-lg font-extrabold text-slate-900">Claim {detail.claim_id}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X size={20} /></button>
        </div>
        <div className="p-6 space-y-5 text-xs">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={Users} title="Customer" value={detail.customer?.name || '—'} />
            <StatCard icon={Flag} title="Product" value={detail.claim_type || '—'} />
            <StatCard icon={DollarSign} title="Amount" value={money(detail.amount)} />
            <StatCard icon={ShieldAlert} title="Status" value={detail.status || '—'} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={ShieldCheck} title="AI Risk Score" value={a.risk_score != null ? `${a.risk_score}/100` : '—'} subtitle={a.risk_category || 'Unassessed'} />
            <StatCard icon={Activity} title="Investigation" value={inv ? `#${inv.id}` : 'None'} subtitle={inv?.status || 'open'} />
            <StatCard icon={BarChart3} title="Submitted" value={iso(detail.submission_date)} />
            <StatCard icon={Star} title="Priority" value={a.risk_category === 'Critical' ? 'CRITICAL' : a.risk_category === 'High' ? 'HIGH' : 'NORMAL'} colorCls="border-t-red-600" />
          </div>
          {a.explanation && (
            <div className="bg-slate-50 rounded-xl p-4 border-l-4 border-amber-500">
              <p className="text-[10px] font-extrabold text-slate-500 uppercase mb-1">AI Assessment Narrative</p>
              <p className="text-slate-700">{a.explanation}</p>
              {Array.isArray(a.indicators) && a.indicators.slice(0, 5).map((ind, i) => (
                <div key={i} className="mt-1 text-[10px] text-slate-600"><strong>{ind.code}:</strong> {ind.detail}</div>
              ))}
            </div>
          )}
          {evidenceDocs.length > 0 && (
            <div>
              <h3 className="text-sm font-extrabold text-slate-700 mb-2 flex items-center gap-2"><FileText size={14} className="text-red-500" /> Review Supporting Evidence ({evidenceDocs.length})</h3>
              <Table headers={['Document', 'Type', 'Status', 'Uploaded']} rows={evidenceDocs.map(d => [
                <td key="f" className="py-2 px-4 font-bold text-slate-800">{d.filename}</td>,
                <td key="t" className="py-2 px-4">{d.document_type || '—'}</td>,
                <td key="s" className="py-2 px-4"><span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase">{d.processing_status || '—'}</span></td>,
                <td key="d" className="py-2 px-4">{iso(d.uploaded_at)}</td>,
              ])} emptyText="No evidence documents attached to this claim." />
            </div>
          )}
          <div>
            <h3 className="text-sm font-extrabold text-slate-700 mb-2 flex items-center gap-2"><ClipboardList size={14} className="text-blue-500" /> Investigation Progress & Notes</h3>
            <Table headers={['When', 'User', 'Note']} rows={notes.map(n => [
              <td key="w" className="py-2 px-4 font-mono text-[10px] text-slate-400">{iso(n.created_at)}</td>,
              <td key="u" className="py-2 px-4 font-semibold text-slate-800">{n.created_by}</td>,
              <td key="n" className="py-2 px-4">{n.note}</td>,
            ])} emptyText="No investigation notes recorded." />
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
            <h3 className="text-sm font-extrabold text-slate-700">Management Actions</h3>
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => { inv?.id ? onClose() : null; }} className="px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-bold rounded-lg">View Investigation #{inv?.id || '—'}</button>
              <button onClick={() => setUpdateNotes('')} className="px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-bold rounded-lg">Review Evidence</button>
              <button onClick={() => {}} className="px-3 py-1.5 bg-slate-100 text-slate-600 text-xs font-bold rounded-lg">Monitor Progress</button>
              <button onClick={() => setUpdateNotes('')} className="px-3 py-1.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-lg">{updating ? 'Updating…' : 'Request Update'}</button>
              <button onClick={doEscalate} disabled={escalating} className="px-3 py-1.5 bg-red-600 text-white text-xs font-bold rounded-lg hover:bg-red-700 disabled:opacity-50">{escalating ? 'Escalating…' : 'Escalate Case'}</button>
            </div>
            <div className="flex gap-2">
              <input
                placeholder="Request update / investigation note (optional)…"
                value={updateNotes}
                onChange={e => setUpdateNotes(e.target.value)}
                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-xs"
                onKeyDown={e => e.key === 'Enter' && doUpdate()}
              />
              <button onClick={doUpdate} disabled={updating} className="px-3 py-2 bg-[#0F2744] text-white rounded-lg text-xs font-bold">Save Update</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// AI Fraud Intelligence (data-driven insights)
// ─────────────────────────────────────────────

function AIInsights({ insights }) {
  const items = insights || [];
  const SEV = { WARNING: { cls: 'bg-amber-100 text-amber-700', label: 'High' }, SUSPICION: { cls: 'bg-red-100 text-red-700', label: 'Critical' }, NOTICE: { cls: 'bg-blue-100 text-blue-700', label: 'Notice' } };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><Star size={16} className="text-amber-500" /><span>AI Fraud Intelligence Insights</span></h3>
        <p className="text-xs text-slate-500">Generated from live system data — AI suspicions are flagged distinctly from confirmed fraud.</p>
      </div>
      {items.length === 0 ? (
        <EmptyState icon={Star} title="No AI insights" note="No significant trends or patterns were detected in the current data set." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map(ins => {
            const sev = SEV[ins.severity] || SEV.NOTICE;
            const basis = ins.basis === 'ai_detected' ? 'AI suspicion (requires human review)' : 'Verified from investigation data';
            return (
              <div key={ins.insight_id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${sev.cls}`}>{sev.label}</span>
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">{ins.type.replace(/_/g, ' ')}</span>
                  </div>
                  <span className="text-[9px] text-slate-400">{basis}</span>
                </div>
                <h4 className="font-extrabold text-slate-800 text-sm mb-1.5">{ins.title}</h4>
                <p className="text-xs text-slate-600 leading-relaxed mb-3">{ins.description}</p>
                {Object.keys(ins.data || {}).length > 0 && (
                  <div className="bg-slate-50 rounded-lg p-3 mb-3">
                    <p className="text-[9px] font-extrabold uppercase text-slate-500 mb-1">Supporting data</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(ins.data).map(([k, v]) => (
                        <span key={k} className="px-2 py-1 bg-white rounded border border-slate-200 text-[10px] font-mono text-slate-600">
                          {k}: {Array.isArray(v) ? `${v.length} items` : typeof v === 'object' ? num(v) : v}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <p className="text-xs font-semibold text-slate-700"><strong>Recommended action:</strong> {ins.recommended_action}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Priority Suspicious Claims Queue
// ─────────────────────────────────────────────

function PriorityQueue({ queue, total, onOpen }) {
  const sev = {
    CRITICAL: { cls: 'bg-red-100 text-red-700', label: 'CRITICAL', icon: AlertTriangle },
    HIGH: { cls: 'bg-orange-100 text-orange-700', label: 'HIGH', icon: AlertTriangle },
    NORMAL: { cls: 'bg-slate-100 text-slate-500', label: 'NORMAL', icon: Flag },
  };
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><AlertTriangle size={16} className="text-red-500" /><span>Priority Suspicious Claims Queue</span></h3>
        <p className="text-xs text-slate-500 font-bold">{total} flagged claims awaiting review</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
            <tr>
              <th className="py-3 px-4">Claim ID</th>
              <th className="py-3 px-4">Claimant</th>
              <th className="py-3 px-4">Product</th>
              <th className="py-3 px-4">Amount</th>
              <th className="py-3 px-4">AI Risk Score</th>
              <th className="py-3 px-4">Risk</th>
              <th className="py-3 px-4">Fraud Indicators</th>
              <th className="py-3 px-4">Investigation</th>
              <th className="py-3 px-4">Submitted</th>
              <th className="py-3 px-4">Priority</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {queue.length === 0 ? (
              <tr><td colSpan={10} className="py-10 text-center text-slate-400">No suspicious claims recorded.</td></tr>
            ) : queue.map(q => {
              const s = sev[q.priority] || sev.NORMAL;
              const SIcon = s.icon;
              return (
                <tr key={q.claim_id} className="hover:bg-slate-50 transition cursor-pointer" onClick={() => onOpen(q.claim_id)}>
                  <td className="py-3 px-4 font-mono font-bold text-red-600">{q.claim_id}</td>
                  <td className="py-3 px-4 font-semibold text-slate-800">{q.customer_name}</td>
                  <td className="py-3 px-4">{q.claim_type}</td>
                  <td className="py-3 px-4 font-mono font-bold text-slate-900">{money(q.amount)}</td>
                  <td className="py-3 px-4 font-mono font-black text-slate-900">{q.risk_score}/100</td>
                  <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${q.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : q.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-amber-100 text-amber-800'}`}>{q.risk_category}</span></td>
                  <td className="py-3 px-4"><div className="flex flex-wrap gap-1 max-w-xs">{(q.top_indicators || []).slice(0, 3).map(i => <span key={i} className="px-2 py-0.5 bg-red-50 text-red-700 rounded text-[9px] font-bold">{i}</span>)}</div></td>
                  <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${q.investigation_status === 'open' ? 'bg-red-100 text-red-700' : q.investigation_status === 'in_review' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>{q.investigation_status}</span></td>
                  <td className="py-3 px-4 font-mono text-slate-500">{fmtYmd(q.submitted_date)}</td>
                  <td className="py-3 px-4"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${s.cls}`}><SIcon size={10} />{s.label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Financial Loss Prevention
// ─────────────────────────────────────────────

function FinancialLossPrevention({ kpis, productAnalysis }) {
  const preventedClaims = (productAnalysis || []).flatMap(p => p.confirmed_fraud_claims || []);
  const totalPrevented = kpis?.total_losses_prevented;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard icon={ShieldCheck} title="Verified Losses Prevented" value={money(totalPrevented)} subtitle="claims stopped/rejected through authorised intervention" colorCls="border-t-emerald-600" />
        <KpiCard icon={DollarSign} title="Total Confirmed Fraud Losses" value={money(kpis?.total_confirmed_fraud_losses)} subtitle="value of confirmed fraud claims" colorCls="border-t-blue-600" />
        <KpiCard icon={Star} title="Recovered Funds" value={money(kpis?.recovered_funds)} subtitle="no recovered-fund records exist in the current system" colorCls="border-t-amber-600" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={DollarSign} title="Suspected Exposure" value={money(kpis?.total_financial_exposure)} subtitle="all claims at risk" />
        <StatCard icon={ShieldCheck} title="Prevented Share of Exposure" value={fmtPct(totalPrevented && kpis?.total_financial_exposure ? totalPrevented / kpis.total_financial_exposure * 100 : 0)} subtitle="of total exposure" />
        <StatCard icon={CheckCircle} title="High-Risk Claims" value={num(kpis?.high_risk_claims)} subtitle={`${fmtPct(kpis?.overall_fraud_risk_percentage)} of assessed claims`} />
        <StatCard icon={Activity} title="Under Investigation" value={num(kpis?.claims_under_investigation)} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2"><ShieldCheck size={16} className="text-emerald-600" />Verified Losses Prevented by Product</h3>
          <Table
            headers={['Product', 'Confirmed Fraud', 'Losses Prevented', 'Product Share']}
            rows={(productAnalysis || []).filter(p => p.confirmed_fraud_losses).map(p => [
              <td key="p" className="py-3 px-4 font-bold text-slate-800">{p.product_name}</td>,
              <td key="c" className="py-3 px-4 text-right font-mono text-slate-900">{num(p.confirmed_fraud)}</td>,
              <td key="e" className="py-3 px-4 text-right font-mono font-bold text-emerald-700">{money(p.confirmed_fraud_losses)}</td>,
              <td key="s" className="py-3 px-4 text-right"><ProgressBar pct={p.prevented_share_pct} colorCls="bg-emerald-500" /></td>,
            ])}
            emptyText="No prevented claims recorded by product."
          />
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2"><DollarSign size={16} className="text-red-600" />Suspected Unmitigated Exposure by Product</h3>
          <Table
            headers={['Product', 'Suspected Claims', 'Total Exposure', 'Suspected Share']}
            rows={(productAnalysis || []).map(p => [
              <td key="p" className="py-3 px-4 font-bold text-slate-800">{p.product_name}</td>,
              <td key="c" className="py-3 px-4 text-right font-mono text-amber-700">{num(p.suspected_risk)}</td>,
              <td key="e" className="py-3 px-4 text-right font-mono font-bold text-red-600">{money(p.total_exposure)}</td>,
              <td key="s" className="py-3 px-4 text-right"><ProgressBar pct={p.suspected_share_pct} colorCls="bg-red-500" /></td>,
            ])}
            emptyText="No exposure data recorded by product."
          />
        </div>
      </div>
      <Table
        headers={['Claim ID', 'Customer', 'Amount', 'Product', 'Status', 'Confirmed Fraud', 'Risk Score']}
        rows={preventedClaims.map(c => [
          <td key="id" className="py-3 px-4 font-mono font-bold text-red-600">{c.claim_id}</td>,
          <td key="c" className="py-3 px-4 text-slate-800">{c.customer_name}</td>,
          <td key="a" className="py-3 px-4 font-mono font-bold text-slate-900">{money(c.amount)}</td>,
          <td key="p" className="py-3 px-4">{c.claim_type}</td>,
          <td key="s" className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-100 text-red-700">{c.status}</span></td>,
          <td key="f" className="py-3 px-4">{c.confirmed ? 'Yes' : 'Pending'}</td>,
          <td key="r" className="py-3 px-4 font-mono text-slate-700">{c.risk_score != null ? `${c.risk_score}/100` : '—'}</td>,
        ])}
        emptyText="No confirmed fraud claims recorded."
      />
    </div>
  );
}

// ─────────────────────────────────────────────
// Management Reports (generate / list / export)
// ─────────────────────────────────────────────

const REPORT_TYPES = [
  { value: 'MONTHLY_FRAUD_REPORT', label: 'Monthly Fraud Report' },
  { value: 'QUARTERLY_FRAUD_REPORT', label: 'Quarterly Fraud Report' },
  { value: 'ANNUAL_FRAUD_REPORT', label: 'Annual Fraud Report' },
  { value: 'EXECUTIVE_FINANCIAL_EXPOSURE_REPORT', label: 'Executive Financial Exposure Report' },
  { value: 'FRAUD_INVESTIGATIONS_REPORT', label: 'Fraud Investigations Report' },
  { value: 'CONFIRMED_FRAUD_CASES_REPORT', label: 'Confirmed Fraud Cases Report' },
  { value: 'LOSSES_PREVENTED_REPORT', label: 'Losses Prevented Report' },
  { value: 'DEPARTMENTAL_PERFORMANCE_REPORT', label: 'Departmental Performance Report' },
  { value: 'PRODUCT_FRAUD_TRENDS_REPORT', label: 'Product Fraud Trends Report' },
];

function exportCsv(filename, rows) {
  const list = rows || [];
  if (!list.length) { alert('No data to export.'); return; }
  const cols = Object.keys(list[0]);
  const csv = cols.join(',') + '\n' + list.map(r => Object.values(r).map(v => (v == null ? '' : String(v).replace(/,/g, ';'))).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function ReportsSection({ reportsList, generating, generate, filterType, setFilterType, openReport, selectedReport }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="nexa-report text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><FileText size={16} className="text-blue-600" /><span>Executive Reports</span></h3>
          <p className="nexa-report text-xs text-slate-500 mt-0.5">Reports contain company/report identification, reporting period, executive summary, statistical findings, financial analysis, fraud trends, recommendations and generation date.</p>
        </div>
        <select
          value={filterType || ''}
          onChange={e => setFilterType(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-2 text-xs bg-white font-semibold"
        >
          <option value="">All report types</option>
          {REPORT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {REPORT_TYPES.map(t => (
          <button key={t.value} onClick={() => generate(t.value)} disabled={generating === t.value}
            className="p-3 border border-slate-200 rounded-xl text-left text-[11px] font-bold bg-white hover:bg-slate-50 transition-colors disabled:opacity-50">
            {generating === t.value ? <Loader2 className="w-3.5 h-3.5 animate-spin inline-block" /> : 'Generate'} — {t.label}
          </button>
        ))}
      </div>

      <Table
        headers={['ID', 'Report Type', 'Generated By', 'Generated At', 'Actions']}
        rows={reportsList.map(r => [
          <td key="i" className="py-3 px-4 font-mono font-bold text-slate-600">#{r.id}</td>,
          <td key="t" className="py-3 px-4 font-semibold text-slate-800">{r.report_type}</td>,
          <td key="b" className="py-3 px-4 text-slate-600">{r.generated_by}</td>,
          <td key="a" className="py-3 px-4 font-mono text-[10px] text-slate-500">{iso(r.generated_at)}</td>,
          <td key="c" className="py-3 px-4 text-right flex gap-1.5">
            <button onClick={() => openReport(r.id)} className="px-2 py-1 bg-blue-50 text-blue-700 text-[10px] font-bold rounded-lg hover:bg-blue-100">View</button>
            <button onClick={() => exportCsv(`nexa_${r.report_type}_#${r.id}.csv`, flattenCsvRows(r.summary))} className="px-2 py-1 bg-emerald-50 text-emerald-700 text-[10px] font-bold rounded-lg hover:bg-emerald-100 flex items-center gap-0.5"><Download size={10} />Excel</button>
            <button onClick={() => window.print()} className="px-2 py-1 bg-red-50 text-red-700 text-[10px] font-bold rounded-lg hover:bg-red-100">PDF</button>
          </td>,
        ])}
        emptyText="No generated reports yet."
      />
      {selectedReport && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
            <div><p className="nexa-report text-base font-extrabold text-slate-900">{selectedReport.report_type}</p><p className="nexa-report text-xs text-slate-500">#{selectedReport.id} · {selectedReport.generated_by}</p></div>
            <div className="flex gap-2">
              <button onClick={() => exportCsv(`nexa_${selectedReport.report_type}.csv`, flattenCsvRows(selectedReport.summary))} className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-bold rounded-lg hover:bg-emerald-700"><Download size={13} /> Export Excel (CSV)</button>
              <button onClick={() => window.print()} className="px-3 py-1.5 bg-red-600 text-white text-xs font-bold rounded-lg hover:bg-red-700"><FileText size={13} /> Print to PDF</button>
            </div>
          </div>
          <ReportDetail report={selectedReport} />
        </div>
      )}
    </div>
  );
}

function flattenCsvRows(summary) {
  if (!summary) return [];
  const rows = [];
  const walk = (prefix, obj) => Object.entries(obj || {}).forEach(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') { if (!Array.isArray(v)) walk(key, v); }
    else if (Array.isArray(v) && v.length) { v.slice(0, 50).forEach((it, i) => walk(`${key}[${i}]`, it)); }
    else rows.push({ [key]: typeof v === 'object' ? JSON.stringify(v) : (v == null ? '' : String(v)) });
  });
  walk('', summary);
  return rows;
}

function ReportDetail({ report }) {
  const s = report.summary || {};
  const { executive_summary, statistical_findings, financial_analysis, fraud_trends, recommendations, reporting_period } = s;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs nexa-report">
      <div>
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Executive Summary</h4>
        <p className="text-slate-700 leading-relaxed mb-3">{executive_summary || '—'}</p>
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Reporting Period</h4>
        <p className="font-mono text-[10px]">{iso(reporting_period?.start)} → {iso(reporting_period?.end)}</p>
      </div>
      <div>
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Statistical Findings</h4>
        <div className="space-y-1 mb-3">{Object.entries(statistical_findings || {}).map(([k, v]) => (
          <div key={k} className="flex justify-between"><span className="text-slate-600">{k.replace(/_/g, ' ')}</span><span className="font-mono font-bold">{num(v) || v}</span></div>
        ))}</div>
      </div>
      <div className="lg:col-span-2">
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Financial Analysis</h4>
        <pre className="bg-slate-50 rounded-lg p-3 font-mono text-[10px] whitespace-pre-wrap overflow-x-auto">{JSON.stringify(financial_analysis, null, 1)?.slice(0, 2000)}</pre>
      </div>
      <div className="lg:col-span-2">
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Fraud Trends</h4>
        <pre className="bg-slate-50 rounded-lg p-3 font-mono text-[10px] whitespace-pre-wrap overflow-x-auto h-48 overflow-y-auto">{JSON.stringify(fraud_trends, null, 1)?.slice(0, 2000)}</pre>
      </div>
      <div className="lg:col-span-2">
        <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Recommendations</h4>
        <ul className="space-y-1">{(recommendations || []).map((r, i) => <li key={i} className="text-slate-600">• {r}</li>)}</ul>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main ExecutiveDashboard
// ─────────────────────────────────────────────

export default function ExecutiveDashboard({ activeTab }) {
  const [tab, setTab] = useState(activeTab || 'executive-overview');
  useEffect(() => { if (activeTab) setTab(activeTab); }, [activeTab]);

  const [exec, setExec] = useState(null);
  const [monthly, setMonthly] = useState([]);
  const [yearly, setYearly] = useState([]);
  const [products, setProducts] = useState([]);
  const [riskDist, setRiskDist] = useState([]);
  const [dept, setDept] = useState([]);
  const [suspicions, setSuspicions] = useState([]);
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const [reportsList, setReportsList] = useState([]);
  const [reportsFilterType, setReportsFilterType] = useState('');
  const [reportsGenerating, setReportsGenerating] = useState('');
  const [selectedReport, setSelectedReport] = useState(null);
  const [viewedClaimId, setViewedClaimId] = useState(null);
  const [claimModalOpen, setClaimModalOpen] = useState(false);

  const [periodStart, setPeriodStart] = useState('2026-01-01');
  const [periodEnd, setPeriodEnd] = useState('2026-11-30');

  const loadExec = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await api.executiveDashboard();
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const d = await res.json();
      setExec(d);
      setRiskDist(d.risk_distribution || []);
      setDept(d.departmental_performance || []);
    } catch (e) { setError(e.message || 'Could not load executive data'); }
    finally { setLoading(false); }
  }, []);

  const loadMonthly = useCallback(async () => {
    try {
      const q = `?months=24&period_start=${encodeURIComponent(periodStart)}&period_end=${encodeURIComponent(periodEnd)}`;
      const res = await api.executiveMonthlyTrends(q);
      if (res.ok) setMonthly(await res.json().then(d => d.trends || []));
    } catch (e) { console.error(e); }
  }, [periodStart, periodEnd]);

  const loadYearly = useCallback(async () => {
    try {
      const res = await api.executiveYearlyExposure();
      if (res.ok) setYearly(await res.json().then(d => d.rows || []));
    } catch (e) { console.error(e); }
  }, []);

  const loadProducts = useCallback(async () => {
    try {
      const res = await api.executiveProductAnalysis();
      if (res.ok) setProducts(await res.json().then(d => d.rows || []));
    } catch (e) { console.error(e); }
  }, []);

  const loadSuspicions = useCallback(async () => {
    try {
      const res = await api.executiveSuspicions('?limit=25');
      if (res.ok) setSuspicions(await res.json().then(d => d.queue || []));
    } catch (e) { console.error(e); }
  }, []);

  const loadInsights = useCallback(async () => {
    try {
      const res = await api.executiveAiInsights();
      if (res.ok) setInsights(await res.json().then(d => d.insights || []));
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadExec(); }, [loadExec, retryKey]);
  useEffect(() => { loadMonthly(); }, [loadMonthly]);
  useEffect(() => { loadYearly(); }, [loadYearly]);
  useEffect(() => { loadProducts(); }, [loadProducts]);
  useEffect(() => { loadSuspicions(); }, [loadSuspicions]);
  useEffect(() => { loadInsights(); }, [loadInsights]);

  const loadReports = useCallback(async () => {
    try {
      const res = await api.getManagementReports(reportsFilterType ? `?type=${encodeURIComponent(reportsFilterType)}` : '');
      if (res.ok) setReportsList(await res.json());
    } catch (e) { console.error(e); }
  }, [reportsFilterType]);

  useEffect(() => { loadReports(); }, [loadReports]);

  const generateReport = async (reportType) => {
    setReportsGenerating(reportType);
    try {
      const res = await api.generateManagementReport(reportType, 12);
      const data = await res.json();
      if (res.ok) { setSelectedReport(data); alert(`Report #${data.id} generated successfully.`); }
      else { alert('Report generation failed: ' + (data.detail || 'unknown')); }
    } catch (e) { console.error(e); alert('Report generation failed'); }
    finally { setReportsGenerating(''); }
    loadReports();
  };

  const openReport = async (id) => {
    try {
      const res = await api.getManagementReport(id);
      if (res.ok) setSelectedReport(await res.json());
    } catch (e) { console.error(e); }
  };

  if (loading && !exec) return <Loading />;
  if (error) return <ErrorBlock error={error} retry={() => setRetryKey(k => k + 1)} />;

  const kpis = exec?.kpis || {};
  const preventShare = kpis.total_financial_exposure && kpis.total_losses_prevented ? (kpis.total_losses_prevented / kpis.total_financial_exposure * 100).toFixed(1) : '0.0';

  const renderTab = () => {
    if (tab === 'fraud-analytics') {
      return (
        <div className="space-y-8">
          <section>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><LineChart size={16} className="text-red-500" /><span>Monthly Fraud Trends</span></h2>
              <p className="text-xs text-slate-500">Compare submissions vs suspected/confirmed claims vs exposure — month-over-month changes.</p>
            </div>
            <div className="flex gap-3 mb-4 flex-wrap">
              <input type="date" value={periodStart} onChange={e => setPeriodStart(e.target.value)} className="px-3 py-2 border border-slate-200 rounded-lg text-xs bg-white font-semibold" />
              <span className="text-xs text-slate-400">→</span>
              <input type="date" value={periodEnd} onChange={e => setPeriodEnd(e.target.value)} className="px-3 py-2 border border-slate-200 rounded-lg text-xs bg-white font-semibold" />
            </div>
            <MonthlyTrendsChart trends={monthly} />
            <div className="grid grid-cols-4 gap-3 mt-4">
              <KpiCard icon={TrendingUp} title="Total Suspected" value={num(monthly.reduce((a, m) => a + (m.suspected || 0), 0))} subtitle={`${monthly.length} months`} colorCls="border-t-orange-600" />
              <KpiCard icon={AlertTriangle} title="Total Confirmed" value={num(monthly.reduce((a, m) => a + (m.confirmed || 0), 0))} colorCls="border-t-red-600" />
              <KpiCard icon={DollarSign} title="Total Exposure" value={money(monthly.reduce((a, m) => a + (m.exposure_amount || 0), 0))} colorCls="border-t-blue-600" />
              <KpiCard icon={Flag} title="Largest Month Spike" value={maxMonthSpike(monthly)} colorCls="border-t-amber-600" />
            </div>
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><TrendingUp size={16} className="text-red-500" /><span>Year-over-Year Financial Exposure</span></h2>
            </div>
            <YoYExposureChart rows={yearly} />
            {yearly.length === 0 && <EmptyState icon={TrendingUp} title="No yearly exposure data" note="Annual exposure is derived from claim submission dates." />}
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><Flag size={16} className="text-red-500" /><span>Insurance Product Fraud Analysis</span></h2>
            </div>
            <ProductAnalysisChart rows={products} />
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><ShieldAlert size={16} className="text-red-500" /><span>Fraud Risk Distribution</span></h2>
            </div>
            <RiskDistributionChart riskDist={riskDist} />
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><Activity size={16} className="text-red-500" /><span>Departmental Fraud Performance</span></h2>
            </div>
            <Table
              headers={['Department', 'Active Claims', 'Investigations', 'Open', 'In Review', 'Confirmed Fraud', 'Cleared']}
              rows={dept.map(d => [
                <td key="d" className="py-3 px-4 font-semibold text-slate-800">{d.department}</td>,
                <td key="c" className="py-3 px-4 text-right font-mono">{num(d.claims)}</td>,
                <td key="i" className="py-3 px-4 text-right font-mono font-bold text-slate-700">{num(d.investigation_count)}</td>,
                <td key="o" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.open, d.investigation_count)} colorCls="bg-red-500" /></td>,
                <td key="r" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.in_review, d.investigation_count)} colorCls="bg-amber-500" /></td>,
                <td key="f" className="py-3 px-4 text-right font-mono font-bold text-red-600">{num(d.confirmed_fraud)}</td>,
                <td key="x" className="py-3 px-4 text-right font-mono text-emerald-700">{num(d.cleared)}</td>,
              ])}
              emptyText="No department data available."
            />
          </section>
        </div>
      );
    }

    if (tab === 'ai-fraud-intelligence') {
      return <AIInsights insights={insights} />;
    }

    if (tab === 'financial-exposure') {
      return (
        <div className="space-y-8">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <KpiCard icon={DollarSign} title="Total Financial Exposure" value={money(kpis?.total_financial_exposure)} subtitle="all claims — risk-adjusted" colorCls="border-t-blue-600" />
            <KpiCard icon={ShieldCheck} title="Total Confirmed Fraud Losses" value={money(kpis?.total_confirmed_fraud_losses)} colorCls="border-t-red-600" />
            <KpiCard icon={ShieldCheck} title="Losses Prevented (Verified)" value={money(kpis?.total_losses_prevented)} subtitle={`${preventShare}% of exposure`} colorCls="border-t-emerald-600" />
            <KpiCard icon={DollarSign} title="Recovered Funds" value={money(kpis?.recovered_funds)} colorCls="border-t-amber-500" />
          </div>
          <FinancialLossPrevention kpis={kpis} productAnalysis={products} />
        </div>
      );
    }

    if (tab === 'department-performance') {
      return (
        <div className="space-y-8">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 text-xs font-extrabold uppercase tracking-wider text-slate-600">Departmental Fraud Performance</div>
            <Table
              headers={['Department', 'Active Claims', 'Users', 'Open', 'In Review', 'Confirmed Fraud', 'Cleared']}
              rows={dept.map(d => [
                <td key="d" className="py-3 px-4 font-semibold text-slate-800">{d.department}</td>,
                <td key="c" className="py-3 px-4 text-right font-mono">{num(d.claims)}</td>,
                <td key="u" className="py-3 px-4 text-right font-mono">{num(d.users)}</td>,
                <td key="o" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.open, d.investigation_count)} colorCls="bg-red-500" /></td>,
                <td key="r" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.in_review, d.investigation_count)} colorCls="bg-amber-500" /></td>,
                <td key="f" className="py-3 px-4 text-right font-mono font-bold text-red-600">{num(d.confirmed_fraud)}</td>,
                <td key="x" className="py-3 px-4 text-right font-mono text-emerald-700">{num(d.cleared)}</td>,
              ])}
              emptyText="No department data available."
            />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-2">
            <Table
              headers={['Department', 'Open Investigations']}
              rows={dept.map(d => [
                <td key="d" className="py-3 px-4 font-semibold text-slate-800">{d.department}</td>,
                <td key="o" className="py-3 px-4 text-right font-mono">{num(d.open)}</td>,
              ])}
              emptyText="No open investigation data."
            />
            <Table
              headers={['Department', 'In Review']}
              rows={dept.map(d => [
                <td key="d" className="py-3 px-4 font-semibold text-slate-800">{d.department}</td>,
                <td key="r" className="py-3 px-4 text-right font-mono">{num(d.in_review)}</td>,
              ])}
              emptyText="No in-review investigation data."
            />
          </div>
        </div>
      );
    }

    if (tab === 'management-reports') {
      return <ReportsSection reportsList={reportsList} generating={reportsGenerating} generate={generateReport} filterType={reportsFilterType} setFilterType={setReportsFilterType} openReport={openReport} selectedReport={selectedReport} />;
    }

    if (tab === 'claims-performance') {
      const perf = exec?.processing_performance || {};
      return (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard icon={CheckCircle} title="Claims Processed" value={num(perf.claims_processed)} colorCls="border-t-emerald-600" />
            <KpiCard icon={AlertTriangle} title="Claims Pending" value={num(perf.claims_pending)} colorCls="border-t-amber-600" />
            <KpiCard icon={ShieldCheck} title="Pending Processing Rate" value={fmtPct(perf.pending_ratio_percent)} colorCls="border-t-slate-500" />
            <KpiCard icon={ShieldCheck} title="AI Coverage Rate" value={fmtPct(perf.ai_coverage_rate)} colorCls="border-t-purple-500" />
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center gap-2"><AlertTriangle size={15} className="text-amber-500" /><h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider">Claims Performance Breakdown</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-3 px-4">Claim ID</th><th className="py-3 px-4">Policyholder</th><th className="py-3 px-4">Product</th><th className="py-3 px-4">Amount</th><th className="py-3 px-4">Risk Assessment</th><th className="py-3 px-4">Primary Anomaly</th></tr></thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {(exec?.recent_suspicious_claims || []).map(c => (
                    <tr key={c.claim_id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
                      <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
                      <td className="py-3 px-4">{c.claim_type}</td>
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">{money(c.amount)}</td>
                      <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${c.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : c.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>{c.risk_category} ({c.risk_score})</span></td>
                      <td className="py-3 px-4 text-slate-600 truncate max-w-xs">{c.top_indicator || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    // executive-overview (default)
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-8 gap-4">
          <KpiCard icon={DollarSign} title="Total Financial Exposure" value={money(kpis?.total_financial_exposure)} colorCls="border-t-blue-600" />
          <KpiCard icon={CheckCircle} title="Total Confirmed Fraud Losses" value={money(kpis?.total_confirmed_fraud_losses)} colorCls="border-t-red-600" />
          <KpiCard icon={ShieldCheck} title="Losses Prevented (Verified)" value={money(kpis?.total_losses_prevented)} subtitle={`${preventShare}% of exposure`} colorCls="border-t-emerald-600" />
          <KpiCard icon={Activity} title="Claims Under Investigation" value={num(kpis?.claims_under_investigation)} colorCls="border-t-red-600" />
          <KpiCard icon={AlertTriangle} title="Confirmed Fraud Cases" value={num(kpis?.confirmed_fraud_cases)} colorCls="border-t-amber-600" />
          <KpiCard icon={ShieldAlert} title="High-Risk Claims" value={num(kpis?.high_risk_claims)} colorCls="border-t-red-600" />
          <KpiCard icon={MapPinned} title="Active Insurance Portfolio" value={num(kpis?.active_insurance_portfolio)} colorCls="border-t-slate-500" />
          <KpiCard icon={PieChart} title="Overall Fraud Risk %" value={fmtPct(kpis?.overall_fraud_risk_percentage)} colorCls="border-t-amber-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider flex items-center gap-2"><AlertTriangle size={15} className="text-red-500" />Priority Suspicious Claims Queue</h3>
              <span className="text-xs text-slate-500 font-bold">{suspicions.length} queued</span>
            </div>
            <PriorityQueue queue={suspicions} total={suspicions.length} onOpen={(id) => { setViewedClaimId(id); setClaimModalOpen(true); }} />
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider flex items-center gap-2"><ShieldCheck size={15} className="text-red-500" />AI Fraud Intelligence Snapshot</h3>
              <button onClick={loadInsights} className="text-xs text-slate-400 hover:text-slate-700"><RotateCw size={13} /></button>
            </div>
            <div className="space-y-2">
              {insights.slice(0, 6).map(ins => (
                <div key={ins.insight_id} className="px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 text-xs">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${ins.severity === 'WARNING' ? 'bg-amber-100 text-amber-700' : ins.severity === 'SUSPICION' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{ins.severity}</span>
                  <p className="text-slate-700 font-semibold mt-1">{ins.title}</p>
                </div>
              ))}
              {insights.length === 0 && <EmptyState icon={Star} title="No AI insights yet" note="Insights appear as the system collects data." />}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RiskDistributionChart riskDist={riskDist} />
          <Table
            headers={['Department', 'Active Claims', 'Users', 'Open', 'In Review', 'Confirmed Fraud', 'Cleared']}
            rows={dept.map(d => [
              <td key="d" className="py-3 px-4 font-semibold text-slate-800">{d.department}</td>,
              <td key="c" className="py-3 px-4 text-right font-mono">{num(d.claims)}</td>,
              <td key="u" className="py-3 px-4 text-right font-mono">{num(d.users)}</td>,
              <td key="o" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.open, d.investigation_count)} colorCls="bg-red-500" /></td>,
              <td key="r" className="py-3 px-4 text-right"><ProgressBar pct={pctOf(d.in_review, d.investigation_count)} colorCls="bg-amber-500" /></td>,
              <td key="f" className="py-3 px-4 text-right font-mono font-bold text-red-600">{num(d.confirmed_fraud)}</td>,
              <td key="x" className="py-3 px-4 text-right font-mono text-emerald-700">{num(d.cleared)}</td>,
            ])}
            emptyText="No department data available."
          />
        </div>

        <section>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><LineChart size={16} className="text-red-500" /><span>Monthly Fraud Trends</span></h2>
            <p className="text-xs text-slate-500">Submissions vs suspected/confirmed claims — month-over-month change.</p>
          </div>
          <MonthlyTrendsChart trends={monthly} />
          <div className="grid grid-cols-4 gap-3 mt-4">
            <KpiCard icon={TrendingUp} title="Total Suspected" value={num(monthly.reduce((a, m) => a + (m.suspected || 0), 0))} subtitle={`${monthly.length} months`} colorCls="border-t-orange-600" />
            <KpiCard icon={AlertTriangle} title="Total Confirmed" value={num(monthly.reduce((a, m) => a + (m.confirmed || 0), 0))} colorCls="border-t-red-600" />
            <KpiCard icon={DollarSign} title="Total Exposure" value={money(monthly.reduce((a, m) => a + (m.exposure_amount || 0), 0))} colorCls="border-t-blue-600" />
            <KpiCard icon={Flag} title="Largest Month Spike" value={maxMonthSpike(monthly)} colorCls="border-t-amber-600" />
          </div>
        </section>

        <section>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><TrendingUp size={16} className="text-red-500" /><span>Year-over-Year Financial Exposure</span></h2>
          </div>
          <YoYExposureChart rows={yearly} />
          {yearly.length === 0 && <EmptyState icon={TrendingUp} title="No yearly exposure data" note="Annual exposure is derived from claim submission dates." />}
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2"><Flag size={16} className="text-red-500" /><span>Insurance Product Fraud Analysis</span></h2>
            </div>
            <ProductAnalysisChart rows={products} />
          </div>
        </div>

        {claimModalOpen && viewedClaimId && (
          <ClaimDetailModal
            claimId={viewedClaimId}
            onClose={() => setClaimModalOpen(false)}
            onEscalate={async (claimId) => {
              try {
                const res = await api.updateInvestigation(claimId, { status: 'escalated' });
                if (res.ok) { alert('Case escalated to SIU / investigative workflow.'); }
              } catch (e) { alert('Could not escalate: ' + e.message); }
              await loadSuspicions(); await loadInsights();
            }}
            onUpdate={async (claimId, data) => {
              try {
                const res = await api.updateInvestigation(claimId, data);
                if (res.ok) { alert('Investigation updated.'); }
              } catch (e) { alert('Could not update: ' + e.message); }
              await loadSuspicions(); await loadInsights();
            }}
          />
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Executive Management Suite — Fraud Intelligence & Decision Support</h1>
          <p className="text-xs text-slate-500 mt-0.5">High-level organisational intelligence — fraud trends, financial exposure, product risk, AI insights, loss prevention & executive reporting</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {[
            { id: 'executive-overview', label: 'Dashboard', icon: MapPinned },
            { id: 'claims-performance', label: 'Claims Performance', icon: TrendingUp },
            { id: 'fraud-analytics', label: 'Fraud Analytics', icon: ShieldCheck },
            { id: 'financial-exposure', label: 'Financial Exposure & Loss Prevention', icon: DollarSign },
            { id: 'department-performance', label: 'Department Performance', icon: Building2 },
            { id: 'ai-fraud-intelligence', label: 'AI Fraud Intelligence', icon: Star },
            { id: 'management-reports', label: 'Executive Reports', icon: FileText },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5 ${tab === t.id ? 'bg-[#0F2744] text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>
              <t.icon size={13} className={tab === t.id ? '' : 'opacity-50'} /> {t.label}
            </button>
          ))}
        </div>
      </div>
      {renderTab()}
    </div>
  );
}

// ─────────────────────────────────────────────
// Small helpers
// ─────────────────────────────────────────────

function pctOf(value, total) {
  const denom = Number(total) || 0;
  if (!denom) return 0;
  return Math.min(100, Math.round((Number(value || 0) / denom) * 1000) / 10);
}
function maxMonthSpike(trends) {
  if (!trends || !trends.length) return '—';
  const s = Math.max(...trends.map(t => t.suspected || 0), 0);
  return num(s);
}
