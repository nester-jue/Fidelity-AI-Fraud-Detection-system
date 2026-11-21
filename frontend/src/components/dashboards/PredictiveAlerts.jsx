import { useCallback, useEffect, useState } from 'react';
import { Bell, ShieldAlert, Play, CheckCheck, XCircle } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const SEV_STYLES = {
  CRITICAL: 'bg-red-50 text-red-800', HIGH: 'bg-orange-50 text-orange-800',
  WARNING: 'bg-amber-50 text-amber-800', INFO: 'bg-blue-50 text-blue-700',
};
const SEV_ICONS = { CRITICAL: ShieldAlert, HIGH: XCircle, WARNING: Bell, INFO: Play };

function AlertRow({ alert, onAction }) {
  const Icon = SEV_ICONS[alert.severity] || Bell;
  return (
    <tr className="hover:bg-slate-50">
      <td className="p-3 border-b border-slate-100 text-xs font-black text-slate-500">#{alert.id}</td>
      <td className="p-3 border-b border-slate-100 text-xs font-extrabold text-[#0F2744]">{alert.alert_type.replace(/_/g, ' ')}</td>
      <td className="p-3 border-b border-slate-100 text-xs">
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${SEV_STYLES[alert.severity] || ''}`}>{alert.severity}</span>
        <Icon size={12} className="text-slate-300 ml-1" />
      </td>
      <td className="p-3 border-b border-slate-100 text-xs font-black">{(alert.risk_score || 0).toFixed(0)}</td>
      <td className="p-3 border-b border-slate-100 text-xs text-slate-600">{alert.description}</td>
      <td className="p-3 border-b border-slate-100 text-[10px] text-slate-400 block max-w-xs truncate">{alert.evidence_summary}</td>
      <td className="p-3 border-b border-slate-100 text-[11px] text-slate-500">{alert.status} · {alert.generated_at ? new Date(alert.generated_at).toLocaleDateString() : ''}</td>
      <td className="p-3 border-b border-slate-100 align-top">
        <div className="flex gap-1 flex-wrap justify-end">
          {alert.status !== 'acknowledged' && alert.status !== 'resolved' && <button onClick={() => onAction('ack', alert.id)} className="text-[10px] px-2 py-1 bg-blue-100 text-blue-700 rounded-md font-bold">Ack</button>}
          {alert.status !== 'resolved' && alert.status !== 'dismissed' && <button onClick={() => onAction('resolve', alert.id)} className="text-[10px] px-2 py-1 bg-emerald-100 text-emerald-700 rounded-md font-bold">Resolve</button>}
          {alert.status !== 'dismissed' && <button onClick={() => onAction('dismiss', alert.id)} className="text-[10px] px-2 py-1 bg-slate-100 text-slate-600 rounded-md font-bold">Dismiss</button>}
        </div>
      </td>
    </tr>
  );
}

export default function PredictiveAlerts({ user }) {
  const [alerts, setAlerts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    const [a, s] = await Promise.allSettled([api.predictiveAlerts({ limit: 100 }), api.predictiveSummary()]);
    if (a.status === 'fulfilled' && a.value.ok) setAlerts(await a.value.json());
    if (s.status === 'fulfilled' && s.value.ok) setSummary(await s.value.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  const runScan = async () => {
    setScanning(true);
    const res = await api.predictiveScan();
    if (res.ok) setError('Scan completed — new predictive alerts generated.');
    await load();
    setScanning(false);
  };

  const onAction = async (action, id) => {
    if (action === 'ack') await api.acknowledgeAlert(id);
    else if (action === 'resolve') { const note = window.prompt('Resolution note:', '') ?? ''; await api.resolveAlert(id, note); }
    else await api.dismissAlert(id);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-[#0F2744] flex items-center gap-3"><Bell size={22} className="text-amber-500" /> Predictive Fraud Risk Monitoring</h1>
          <p className="text-xs text-slate-500 font-medium mt-1">Proactive risk indicators from live claim data — these are indicators for review, NOT confirmed fraud.</p>
        </div>
        <button onClick={runScan} disabled={scanning} className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-sm disabled:opacity-40">
          {scanning ? 'Scanning…' : 'Run Predictive Scan'}
        </button>
      </div>

      {error && error.startsWith('Scan') && <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2.5 rounded-xl text-xs font-bold">{error}</div>}
      {error && !error.startsWith('Scan') && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 text-center"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Total</p><p className="text-xl font-black">{summary.total}</p></div>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 text-center"><p className="text-xs font-bold uppercase tracking-wider text-amber-700">New</p><p className="text-xl font-black text-amber-800">{summary.new}</p></div>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 text-center"><p className="text-xs font-bold uppercase tracking-wider text-blue-700">Acknowledged</p><p className="text-xl font-black text-blue-800">{summary.acknowledged}</p></div>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 text-center"><p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Resolved</p><p className="text-xl font-black text-emerald-800">{summary.resolved}</p></div>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 text-center"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Dismissed</p><p className="text-xl font-black">{summary.dismissed}</p></div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-[#0F2744] text-white text-[10px]">
            <tr className="uppercase tracking-wide font-extrabold">
              <th className="p-3">ID</th><th className="p-3">Type</th><th className="p-3">Severity</th><th className="p-3 text-center">Risk</th>
              <th className="p-3">Description</th><th className="p-3">Evidence</th><th className="p-3">Status</th><th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {alerts.length === 0 && <tr><td colSpan={8} className="p-6 text-center text-sm text-slate-400">No predictive alerts currently.</td></tr>}
            {alerts.map(a => <AlertRow key={a.id} alert={a} onAction={onAction} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
