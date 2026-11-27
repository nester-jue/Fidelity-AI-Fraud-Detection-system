import { useCallback, useEffect, useState } from 'react';
import { BarChart3, Settings, ShieldAlert } from 'lucide-react';
import { api } from '../../api/apiClient.js';

export default function ModelPerformanceDashboard({ user }) {
  const [data, setData] = useState(null);
  const [versions, setVersions] = useState([]);
  const [history, setHistory] = useState([]);
  const [requests, setRequests] = useState([]);
  const [newVersion, setNewVersion] = useState('');
  const [datasetVersion, setDatasetVersion] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [d, v, h, r] = await Promise.allSettled([
        api.modelPerformanceDashboard(), api.modelPerformanceVersions(), api.modelPerformanceHistory(), api.listRetrainingRequests(),
      ]);
      if (d.status === 'fulfilled' && d.value.ok) setData(await d.value.json());
      if (v.status === 'fulfilled' && v.value.ok) setVersions(await v.value.json());
      if (h.status === 'fulfilled' && h.value.ok) setHistory(await h.value.json());
      if (r.status === 'fulfilled' && r.value.ok) setRequests(await r.value.json());
    } catch { setError('Could not fetch model performance data.'); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const metrics = data?.metrics || {};
  const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
  const isAdmin = ['system_admin', 'admin'].includes(user?.role);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h1 className="text-2xl font-extrabold text-[#C8102E] flex items-center gap-3"><BarChart3 size={22} className="text-amber-500" /> AI Model Performance Dashboard</h1>
        <p className="text-xs text-slate-500 font-medium mt-1">Fraud detection metrics from validated records — metrics use confirmed investigations as labelled signal.</p>
      </div>

      {error && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 border-t-4 border-t-[#C8102E]">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Claims assessed</p>
              <p className="text-3xl font-black mt-2">{data.claims_assessed}</p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5 border-t-4 border-t-red-600">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Flagged for review</p>
              <p className="text-3xl font-black text-red-600 mt-2">{data.claims_flagged}</p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5 border-t-4 border-t-amber-500">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Confirmed fraud</p>
              <p className="text-3xl font-black mt-2">{data.confirmed_fraud_cases}</p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5 border-t-4 border-t-emerald-600">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Fraud exposure (score sum)</p>
              <p className="text-3xl font-black text-emerald-600 mt-2">{metrics.true_positives + metrics.false_positives || 0}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Core Metrics</h3>
              <div className="space-y-2 text-sm">
                <p>Accuracy proxy: <span className="font-black">{pct(metrics.accuracy_proxy_flagged_confirmed_or_clear)}</span> (TP/TN vs confirmed investigations)</p>
                <p>Precision: <span className="font-black">{pct(metrics.precision)}</span></p>
                <p>Recall: <span className="font-black">{pct(metrics.recall)}</span></p>
                <p>F1 Score: <span className="font-black">{pct(metrics.f1_score)}</span></p>
                <p>False positive rate: <span className="font-black">{pct(metrics.false_positive_rate)}</span></p>
                <p>False negative rate: <span className="font-black">{pct(metrics.false_negative_rate)}</span></p>
              </div>
              <p className="text-[10px] text-slate-400 mt-3">{data.honesty_note}</p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Risk Distribution</h3>
              <div className="space-y-2">
                <div className="flex items-center"><span className="w-24 text-sm text-slate-600">Low</span><div className="flex-1 bg-emerald-100 rounded-full h-3"><div className="bg-emerald-500 h-3 rounded-full" style={{ width: `${data.risk_distribution.low ? (data.risk_distribution.low / Math.max(1, data.claims_assessed)) * 100 : 0}%` }} /></div><span className="w-10 text-center text-sm font-black">{data.risk_distribution.low}</span></div>
                <div className="flex items-center"><span className="w-24 text-sm text-slate-600">Medium</span><div className="flex-1 bg-amber-100 rounded-full h-3"><div className="bg-amber-500 h-3 rounded-full" style={{ width: `${data.risk_distribution.medium ? (data.risk_distribution.medium / Math.max(1, data.claims_assessed)) * 100 : 0}%` }} /></div><span className="w-10 text-center text-sm font-black">{data.risk_distribution.medium}</span></div>
                <div className="flex items-center"><span className="w-24 text-sm text-slate-600">High</span><div className="flex-1 bg-orange-100 rounded-full h-3"><div className="bg-orange-500 h-3 rounded-full" style={{ width: `${data.risk_distribution.high ? (data.risk_distribution.high / Math.max(1, data.claims_assessed)) * 100 : 0}%` }} /></div><span className="w-10 text-center text-sm font-black">{data.risk_distribution.high}</span></div>
                <div className="flex items-center"><span className="w-24 text-sm text-slate-600">Critical</span><div className="flex-1 bg-red-100 rounded-full h-3"><div className="bg-red-500 h-3 rounded-full" style={{ width: `${data.risk_distribution.critical ? (data.risk_distribution.critical / Math.max(1, data.claims_assessed)) * 100 : 0}%` }} /></div><span className="w-10 text-center text-sm font-black">{data.risk_distribution.critical}</span></div>
              </div>
              <p className="text-[10px] text-amber-700 mt-3">Model risk categories are informational indicators for review; they never establish fraud. Data quality: {metrics.total ? `${data.data_quality?.assessments_with_explanation || 0}/${metrics.total} assessments have explanations` : '—'}</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Model Versions</h3>
            <table className="w-full text-left text-sm">
              <thead><tr className="text-[10px] uppercase text-slate-400 border-b border-slate-100"><th className="py-1 font-semibold">Model</th><th className="py-1 font-semibold">Version</th><th className="py-1 font-semibold">Precision</th><th className="py-1 font-semibold">Recall</th><th className="py-1 font-semibold">F1</th><th className="py-1 font-semibold">Evaluated</th></tr></thead>
              <tbody>
                {versions.map((v, i) => (
                  <tr key={i}><td className="py-1 font-semibold">{v.model_name}</td><td className="py-1 font-mono">{v.version}</td>
                    <td className="py-1">{pct(v.precision)}</td><td className="py-1">{pct(v.recall)}</td><td className="py-1">{pct(v.f1_score)}</td>
                    <td className="py-1 text-xs text-slate-400">{v.evaluated_at ? new Date(v.evaluated_at).toLocaleDateString() : '—'}</td></tr>
                ))}
                {versions.length === 0 && <tr><td colSpan={6} className="py-2 text-center text-slate-400 text-xs">No historical versions — current engine version: {data.model_versions?.[0]?.version || '—'}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {isAdmin && (
        <>
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2"><Settings size={14} /> Controlled Retraining Requests</h3>
            <div className="flex gap-2 mb-3">
              <input value={newVersion} onChange={e => setNewVersion(e.target.value)} placeholder="new model version, e.g. v2.0-test" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-1/3" />
              <input value={datasetVersion} onChange={e => setDatasetVersion(e.target.value)} placeholder="dataset version, e.g. ds-2026-01" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-1/3" />
              <button
                disabled={!newVersion.trim() || !datasetVersion.trim() || submitting}
                onClick={async () => {
                  setSubmitting(true);
                  try {
                    await api.openRetrainingRequest({ new_model_version: newVersion, dataset_version: datasetVersion, notes: 'entered from NEXA Learning Centre' });
                    setNewVersion(''); setDatasetVersion(''); await load();
                  } catch (err) {
                    setError(err.message || 'Could not submit the retraining request.');
                  } finally {
                    setSubmitting(false);
                  }
                }}
                className="px-4 py-2 text-sm font-bold bg-[#C8102E] text-white rounded-md disabled:opacity-40"
              >Request Retrain</button>
            </div>
            <table className="w-full text-left text-sm">
              <thead><tr className="text-[10px] uppercase text-slate-400 border-b border-slate-100"><th className="py-1 font-semibold">Version</th><th className="py-1 font-semibold">Status</th><th className="py-1 font-semibold">Dataset</th><th className="py-1 font-semibold">Requested by</th><th className="py-1 font-semibold">Actions</th></tr></thead>
              <tbody>
                {requests.map(r => (
                  <tr key={r.id} className="border-b border-slate-50">
                    <td className="py-2 font-mono text-xs">{r.new_model_version}</td>
                    <td className="py-2 font-semibold text-[11px]"><span className={`px-2 py-0.5 rounded-full text-[10px] ${r.status === 'deployed' ? 'bg-emerald-50 text-emerald-700' : r.status === 'rejected' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'}`}>{r.status}</span></td>
                    <td className="py-2 text-xs">{r.dataset_version} · {r.dataset_records} records</td>
                    <td className="py-2 text-xs">{r.requested_by}</td>
                    <td className="py-2">
                      <div className="flex gap-1">
                        {r.status === 'requested' && <button onClick={() => api.approveRetraining(r.id).then(load)} className="text-[10px] px-2 py-1 bg-blue-100 text-blue-700 rounded font-bold">Approve</button>}
                        {r.status === 'approved' && <button onClick={() => api.deployRetraining(r.id).then(load)} className="text-[10px] px-2 py-1 bg-emerald-100 text-emerald-700 rounded font-bold">Deploy</button>}
                        {r.status === 'requested' && <button onClick={() => api.rejectRetraining(r.id, 'test').then(load)} className="text-[10px] px-2 py-1 bg-red-100 text-red-700 rounded font-bold">Reject</button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {requests.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-xs text-slate-400">No retraining requests.</td></tr>}
              </tbody>
            </table>
            <p className="text-[10px] text-slate-400 mt-2">Retraining deploys only after explicit admin approval. Unverified fraud allegations are never used for retraining automatically.</p>
          </div>
          <div className="text-[10px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-3">
            {data?.data_quality?.assessments_missing_model_version != null && `${data.data_quality.assessments_missing_model_version} assessments lack model version attribution. `}Data retention: evidence 5 years, audit 10 years, assessments 365 days.
          </div>
        </>
      )}
    </div>
  );
}
