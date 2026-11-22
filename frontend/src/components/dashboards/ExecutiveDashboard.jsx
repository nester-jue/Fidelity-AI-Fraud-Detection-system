/**
 * ExecutiveDashboard.jsx
 * NEXA AI Fraud Detection Platform — Executive Management workspace.
 * Tabs: executive-overview | claims-performance | fraud-analytics | financial-exposure | department-performance | management-reports
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  DollarSign, ShieldCheck, Building2, RefreshCw, RotateCw, TrendingUp, TrendingDown,
  ArrowUpRight, FileText, AlertTriangle, Users, MapPinned, AlertCircle, Eye,
  Loader2, CheckCircle, Settings2,
} from 'lucide-react';
import { api } from '../../api/apiClient';

const fmtCurrency = (v) => (v != null ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v) : '—');
const fmtPct = (v) => `${(v ?? 0).toFixed(1)}%`;
const fmtNum = (v) => (v != null ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v) : '—');

function Card({ icon: Icon, title, value, subtitle, color, colorCls, trend }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 flex items-center gap-4 border-t-4 ${colorCls}`}>
      <div className="p-3 rounded-xl bg-slate-50 text-slate-900">
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>
        <p className="text-2xl font-extrabold text-slate-900 mt-0.5">{value}</p>
        {subtitle && <p className={`text-[11px] font-semibold mt-1 ${color}`}>{subtitle}</p>}
      </div>
      {trend && <div className="ml-auto text-right">{trend}</div>}
    </div>
  );
}

function TrendBar({ trend }) {
  if (!trend || trend.length === 0) return null;
  const max = Math.max(...trend.map(t => t.claims_received || 0), 1);
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Fraud Trends — Monthly</p>
      {trend.map(t => (
        <div key={t.period} className="flex items-center gap-2 text-xs font-medium text-slate-700">
          <span className="font-mono w-12 text-slate-400">{t.period}</span>
          <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-red-500 rounded-full" style={{ width: `${Math.max(3, (t.claims_received / max) * 100)}%` }} />
          </div>
          <span className="font-mono w-10 text-right">{t.claims_received}</span>
          <span className="font-mono w-14 text-right">{fmtCurrency(t.exposure_amount)}</span>
        </div>
      ))}
    </div>
  );
}

function YearlyTrend({ trends }) {
  if (!trends || trends.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-500 mb-3 flex items-center space-x-2">
        <TrendingUp size={14} className="text-red-500" />
        <span>Year-Over-Year Claim Exposure Trend</span>
      </h3>
      <div className="flex items-end gap-3 h-32">
        {trends.map(t => {
          const h = Math.max(t.count, 1) / Math.max(...trends.map(x => x.count), 1) * 24;
          return (
            <div key={t.period} className="flex-1 flex flex-col items-center gap-1.5">
              <div className="w-full flex flex-col items-center justify-end h-32">
                <div className="w-full rounded-t-lg bg-red-500" style={{ height: `${Math.max(2, h) * (1.5)}px` }} />
              </div>
              <span className="text-[10px] font-mono font-semibold text-slate-500">{t.period}</span>
              <span className="text-[9px] font-black text-slate-700">{t.count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, title, value, trendText }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5">
      <div className="flex items-start justify-between">
        <div className="p-3 rounded-xl bg-slate-50 text-slate-900"><Icon className="w-5 h-5" /></div>
        <div className="text-right text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</div>
      </div>
      <p className="text-3xl font-extrabold text-slate-900 mt-2">{value}</p>
      {trendText && <p className={`text-xs mt-1 ${trendText.startsWith('+') ? 'text-red-600' : 'text-emerald-600'}`}>{trendText}</p>}
    </div>
  );
}

function ReportGenerator({ user }) {
  const [reports, setReports] = useState([]);
  const [type, setType] = useState('EXECUTIVE_KPI_SNAPSHOT');
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await api.getManagementReports();
      if (res.ok) setReports(await res.json());
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setGenerating(true); setMessage('');
    try {
      const res = await api.postManagementReport(type);
      const data = await res.json();
      setMessage(`Report #${data.id} generated successfully and is downloadable.`);
      load();
    } catch (e) { setMessage(`Error: ${e.message}`); }
    finally { setGenerating(false); }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-3 flex items-center space-x-2">
        <FileText size={14} className="text-blue-600" />
        <span>Management Reports &amp; Downloadable Summaries</span>
      </h3>
      <div className="flex items-center gap-2 mb-4">
        <select value={type} onChange={e => setType(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-slate-50">
          <option>EXECUTIVE_KPI_SNAPSHOT</option>
          <option>FRAUD_TREND_REVIEW</option>
          <option>FINANCIAL_EXPOSURE_REVIEW</option>
        </select>
        <button onClick={generate} disabled={generating} className="px-4 py-1.5 text-xs font-bold bg-[#0F2744] text-white rounded-lg hover:bg-[#1B3A57] transition-colors flex items-center space-x-1.5 disabled:opacity-50">
          {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw size={13} />}
          <span>Generate Report</span>
        </button>
      </div>
      {message && <p className="text-xs text-emerald-600 font-semibold mb-3">{message}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
            <tr><th className="py-2.5 px-3">ID</th><th className="py-2.5 px-3">Type</th><th className="py-2.5 px-3">Generated By</th><th className="py-2.5 px-3">Generated At</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {reports.map(r => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="py-2.5 px-3 font-mono font-bold text-slate-600">#{r.id}</td>
                <td className="py-2.5 px-3 font-semibold">{r.report_type}</td>
                <td className="py-2.5 px-3">{r.generated_by}</td>
                <td className="py-2.5 px-3 font-mono">{r.generated_at ? new Date(r.generated_at).toLocaleString('en-ZA') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ExecutiveDashboard({ activeTab }) {
  // The workspace is routed by the parent App via activeTab — mirror it into
  // the internal view so each sidebar item shows its own section.
  const [tab, setTab] = useState(activeTab || 'executive-overview');
  useEffect(() => { if (activeTab) setTab(activeTab); }, [activeTab]);
  const [kpis, setKpis] = useState(null);
  const [trends, setTrends] = useState([]);
  const [riskDist, setRiskDist] = useState([]);
  const [yearly, setYearly] = useState([]);
  const [deptPerf, setDeptPerf] = useState([]);
  const [procPerf, setProcPerf] = useState(null);
  const [suspicious, setSuspicious] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.executiveDashboard();
      if (!res.ok) return;
      const d = await res.json();
      setKpis(d.kpis);
      setTrends(d.monthly_fraud_trends || []);
      setRiskDist(d.risk_distribution || []);
      setYearly(d.yearly_fraud_trends || []);
      setDeptPerf(d.departmental_performance || []);
      setProcPerf(d.processing_performance || null);
      setSuspicious(d.recent_suspicious_claims || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !kpis) return <div className="flex justify-center py-24"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;

  const renderTab = () => {
    if (tab === 'claims-performance') {
      const perf = procPerf || {};
      return (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card icon={CheckCircle} title="Claims Processed" value={perf.claims_processed ?? '—'} color="text-emerald-700" colorCls="border-t-emerald-600" />
            <Card icon={AlertTriangle} title="Claims Pending" value={perf.claims_pending ?? '—'} color="text-amber-600" colorCls="border-t-amber-500" />
            <Card icon={ShieldCheck} title="Pending Processing Rate" value={fmtPct(perf.pending_ratio_percent)} color="text-slate-600" colorCls="border-t-slate-500" />
            <Card icon={ShieldCheck} title="AI Coverage Rate" value={fmtPct(perf.ai_coverage_rate)} color="text-purple-600" colorCls="border-t-purple-500" />
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Claims Performance Breakdown</h3>
              <span className="text-xs text-slate-400 font-bold">Total: {kpis?.total_claims_received ?? 0}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                  <tr><th className="py-3 px-4">Claim ID</th><th className="py-3 px-4">Policyholder</th><th className="py-3 px-4">Product</th><th className="py-3 px-4">Amount</th><th className="py-3 px-4">Risk Assessment</th><th className="py-3 px-4">Primary Anomaly</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {suspicious.map((c, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
                      <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
                      <td className="py-3 px-4">{c.claim_type}</td>
                      <td className="py-3 px-4 font-mono font-bold">${fmtNum(c.amount)}</td>
                      <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${c.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : c.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>{c.risk_category} ({c.risk_score})</span></td>
                      <td className="py-3 px-4 text-slate-600 truncate max-w-xs">{c.top_indicator || 'No indicator'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }
    if (tab === 'fraud-analytics') {
      const alertRates = [
        { label: 'High-Risk Claims', value: kpis?.high_risk ?? '—' },
        { label: 'Critical Risk', value: kpis?.critical_risk_claims ?? '—' },
        { label: 'Under Investigation', value: kpis?.claims_under_investigation ?? '—' },
        { label: 'Confirmed Fraud', value: kpis?.confirmed_fraud_cases ?? '—' },
        { label: 'Fraud Alerts Rate', value: fmtPct(procPerf?.fraud_detection_rate) },
      ];
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {alertRates.map(c => (
            <div key={c.label} className="bg-white border border-slate-200 rounded-2xl p-5 border-t-4 border-t-red-600">
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{c.label}</p>
              <p className="text-3xl font-extrabold text-red-600 mt-1">{c.value}</p>
            </div>
          ))}
          <div className="col-span-2 lg:col-span-2 bg-white border border-slate-200 rounded-2xl p-5">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-2 flex items-center space-x-2"><TrendingUp size={13} className="text-red-500" /><span>Fraud Risk Distribution</span></h3>
            <div className="space-y-2 mt-3">
              {riskDist.map((item, idx) => (
                <div key={idx}>
                  <div className="flex justify-between text-xs font-semibold mb-1"><span className="text-slate-700">{item.name}</span><span className="font-mono">{item.percentage}% ({item.count})</span></div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${item.percentage}%`, backgroundColor: item.color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }
    if (tab === 'financial-exposure') {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card icon={DollarSign} title="Total Financial Exposure" value={fmtCurrency(kpis?.total_financial_exposure)} subtitle={`All claims — risk-adjusted`} color="text-slate-900" colorCls="border-t-blue-600" />
          <Card icon={ShieldCheck} title="Potential Fraud Losses Prevented" value={fmtCurrency(kpis?.potential_fraud_prevented)} subtitle="Holds and confirmed fraud" color="text-emerald-700" colorCls="border-t-emerald-600" />
          <Card icon={AlertTriangle} title="Critical Payment Holds" value={kpis?.claims_flagged ?? '—'} subtitle="Pending review" color="text-red-600" colorCls="border-t-red-600" />
        </div>
      );
    }
    if (tab === 'department-performance') {
      return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200"><h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Departmental Performance</h3></div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                <tr><th className="py-3 px-4">Department</th><th className="py-3 px-4 text-right">Active Claims</th><th className="py-3 px-4 text-right">Users</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {deptPerf.map(d => (
                  <tr key={d.department}>
                    <td className="py-3 px-4 font-semibold">{d.department}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold">{d.claims.toLocaleString()}</td>
                    <td className="py-3 px-4 text-right font-mono">{d.users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }
    if (tab === 'management-reports') {
      return <ReportGenerator />;
    }
    // Default executive overview
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiCard icon={CheckCircle} title="Total Claims" value={kpis?.total_claims_received?.toLocaleString() ?? '—'} />
          <KpiCard icon={CheckCircle} title="Claims Processed" value={(kpis?.total_claims_processed ?? 0).toLocaleString()} trendText={kpis?.ai_coverage_rate ? `${fmtPct(kpis.ai_coverage_rate)} AI coverage` : null} />
          <KpiCard icon={ShieldCheck} title="High-Risk Claims" value={(kpis?.high_risk ?? 0).toLocaleString()} />
          <KpiCard icon={AlertTriangle} title="Critical Risk Claims" value={(kpis?.critical_risk_claims ?? 0).toLocaleString()} trendText="Payment holds" />
          <KpiCard icon={CheckCircle} title="Confirmed Fraud" value={(kpis?.confirmed_fraud_cases ?? 0).toLocaleString()} />
          <KpiCard icon={DollarSign} title="Financial Exposure" value={fmtCurrency(kpis?.total_financial_exposure)} />
          <KpiCard icon={ShieldCheck} title="Losses Prevented" value={fmtCurrency(kpis?.potential_fraud_prevented)} />
          <KpiCard icon={TrendingDown} title="Open Under Investigation" value={(kpis?.claims_under_investigation ?? 0).toLocaleString()} />
          <KpiCard icon={MapPinned} title="Active Portfolio" value={(kpis?.total_claims_received ?? 0).toLocaleString()} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Monthly Fraud Trends</h3>
              <span className="text-xs text-slate-400 font-bold">Last 12 months</span>
            </div>
            <TrendBar trend={trends} />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4">Year-Over-Year Exposure</h3>
            <YearlyTrend trends={yearly} />
            {(!yearly || yearly.length === 0) && <p className="text-xs text-slate-400 mt-4">Insufficient data for trend visualization.</p>}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Priority Suspicious Claims Queue</h3>
            {suspicious.slice(0, 8).map((c, i) => (
              <div key={i} className="border-b border-slate-100 pb-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-mono font-bold text-slate-900 text-xs">{c.claim_id}</span>
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${c.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : c.risk_category === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>{c.risk_category} — {c.risk_score}/100</span>
                </div>
                <p className="text-xs text-slate-600">{c.customer_name} &bull; {c.claim_type}</p>
                <p className="text-xs font-mono text-slate-500 mt-0.5">{fmtCurrency(c.amount)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Executive Management Suite</h1>
          <p className="text-xs text-slate-500 mt-0.5">High-level organisational intelligence — fraud trends, financial exposure & processing performance</p>
        </div>
        <div className="flex gap-2">
          {[
            { id: 'executive-overview', label: 'Overview', icon: MapPinned },
            { id: 'claims-performance', label: 'Claims Performance', icon: TrendingUp },
            { id: 'fraud-analytics', label: 'Fraud Analytics', icon: ShieldCheck },
            { id: 'financial-exposure', label: 'Financial Exposure', icon: DollarSign },
            { id: 'department-performance', label: 'Department Performance', icon: Building2 },
            { id: 'management-reports', label: 'Management Reports', icon: FileText },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 text-xs font-bold rounded-xl transition-colors ${tab === t.id ? 'bg-[#0F2744] text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {renderTab()}
      <ReadOnlyNotice />
    </div>
  );
}

function ReadOnlyNotice() {
  return (
    <div className="flex items-center space-x-2 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500">
      <AlertCircle size={14} />
      <span>Executive workspace provides read-only access to sensitive operational data by default.</span>
    </div>
  );
}
