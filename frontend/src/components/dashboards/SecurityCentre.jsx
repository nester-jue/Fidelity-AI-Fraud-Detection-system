import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Activity, Database, LockKeyhole, RefreshCw, ShieldAlert, ShieldCheck, Clock } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const num = (v) => (v == null ? '—' : Number(v).toLocaleString());
const statusClass = (status) => {
  const s = String(status || '').toUpperCase();
  if (['ENFORCED', 'CONNECTED', 'ENABLED', 'REQUIRED', 'VERIFIED'].includes(s)) return 'bg-emerald-50 text-emerald-800 border-emerald-200';
  if (['UNAVAILABLE', 'UNKNOWN'].includes(s)) return 'bg-red-50 text-red-800 border-red-200';
  return 'bg-amber-50 text-amber-800 border-amber-200';
};

function Card({ label, value, note, icon: Icon, tone = 'text-slate-900' }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
        {Icon && <Icon size={15} className="text-amber-700" />} {label}
      </div>
      <p className={`text-nexaFigure mt-2 ${tone}`}>{num(value)}</p>
      {note && <p className="text-[12px] text-slate-500 mt-1">{note}</p>}
    </div>
  );
}

export default function SecurityCentre() {
  const [data, setData] = useState(null);
  const [events, setEvents] = useState([]);
  const [days, setDays] = useState(30);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [overview, eventRes] = await Promise.all([
        api.securityOverview(days),
        api.securityEvents({ days, limit: 40 }),
      ]);
      if (!overview.ok) {
        const detail = await overview.json().catch(() => ({}));
        throw new Error(detail.detail || `Security overview unavailable (${overview.status})`);
      }
      setData(await overview.json());
      if (eventRes.ok) {
        const d = await eventRes.json();
        setEvents(Array.isArray(d) ? d : []);
      }
    } catch (err) {
      setError(err.message || 'Could not load security information.');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const auth = data?.authentication || {};
  const audit = data?.audit || {};
  const trend = data?.authentication_trend || [];
  const maxTrend = Math.max(1, ...trend.flatMap(t => [t.successful || 0, t.failed || 0]));

  if (loading && !data) return <div className="p-10 text-center text-slate-500"><RefreshCw className="inline animate-spin mr-2" size={18} />Loading security centre…</div>;

  if (error && !data) return (
    <div className="bg-white rounded-2xl border border-red-200 p-8 max-w-2xl mx-auto text-center">
      <AlertCircle className="mx-auto text-red-500" size={30} />
      <h2 className="nexa-suite-section text-red-800 mt-3">Security information unavailable</h2>
      <p className="text-sm text-red-700 mt-2">{error}</p>
      <button onClick={load} className="mt-4 px-4 py-2 bg-red-600 text-white text-sm font-bold rounded-lg">Retry</button>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="nexa-suite-heading text-slate-900 flex items-center gap-3"><ShieldCheck size={24} className="text-amber-700" /> Enterprise Security Centre</h1>
          <p className="text-[13px] text-slate-600 mt-2">
            Reporting period {data?.reporting_period?.from || '—'} to {data?.reporting_period?.to || '—'}. Figures are derived from recorded system activity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={days} onChange={e => setDays(Number(e.target.value))} className="rounded-lg border border-slate-300 p-2 text-sm">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={load} className="rounded-lg border border-slate-300 p-2 text-slate-700 hover:bg-slate-50" title="Refresh"><RefreshCw size={16} /></button>
        </div>
      </div>

      {error && <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-xl px-4 py-2">{error}</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Successful sign-ins" value={auth.successful_logins} icon={LockKeyhole} />
        <Card label="Failed sign-ins" value={auth.failed_logins} icon={AlertCircle} tone="text-red-700" />
        <Card label="Audit events" value={audit.events_in_period} icon={Activity} />
        <Card label="Recently authenticated" value={auth.recently_authenticated_users} icon={Clock} note="Distinct users within one token lifetime" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm lg:col-span-2">
          <h2 className="nexa-suite-section text-slate-900">Authentication activity</h2>
          <p className="text-[12px] text-slate-500 mt-1">Successful and failed sign-ins by day, from audit records.</p>
          {trend.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">No authentication activity recorded in this period.</p>
          ) : (
            <div className="mt-5 space-y-2">
              {trend.map(t => (
                <div key={t.date} className="grid grid-cols-[90px_1fr] items-center gap-3">
                  <span className="text-[12px] font-mono text-slate-500">{t.date.slice(5)}</span>
                  <div className="flex gap-1">
                    <div className="h-3 rounded bg-emerald-500" style={{ width: `${Math.max(2, ((t.successful || 0) / maxTrend) * 100)}%` }} title={`${t.successful || 0} successful`} />
                    <div className="h-3 rounded bg-red-500" style={{ width: `${Math.max(2, ((t.failed || 0) / maxTrend) * 100)}%` }} title={`${t.failed || 0} failed`} />
                  </div>
                </div>
              ))}
              <div className="flex gap-4 pt-2 text-[11px] text-slate-500"><span className="flex items-center gap-1"><i className="w-3 h-3 bg-emerald-500 inline-block rounded" /> Successful</span><span className="flex items-center gap-1"><i className="w-3 h-3 bg-red-500 inline-block rounded" /> Failed</span></div>
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h2 className="nexa-suite-section text-slate-900">System status</h2>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 text-sm">
              <span className="flex items-center gap-2 text-slate-600"><Database size={16} /> Database ({data?.database?.dialect || '—'})</span>
              <span className={`px-2 py-0.5 rounded-full border text-[11px] font-bold ${statusClass(data?.database?.status)}`}>{data?.database?.status || '—'}</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 text-sm">
              <span className="flex items-center gap-2 text-slate-600"><ShieldAlert size={16} /> Backup verification</span>
              <span className={`px-2 py-0.5 rounded-full border text-[11px] font-bold ${statusClass(data?.backup?.status)}`}>{data?.backup?.status || '—'}</span>
            </div>
            <p className="text-[12px] text-slate-500">{data?.backup?.detail || (data?.backup?.last_verified_at ? `Last verified ${data.backup.last_verified_at}` : '')}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
        <h2 className="nexa-suite-section text-slate-900">Configured controls</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(data?.controls || []).map(c => (
            <div key={c.name} className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-bold text-slate-800">{c.name}</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded-full border text-[11px] font-bold ${statusClass(c.status)}`}>{c.status}</span>
              <p className="text-[12px] text-slate-500 mt-2">{c.basis}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/60">
          <h2 className="nexa-suite-section text-slate-900">Recent security-relevant events</h2>
          <p className="text-[12px] text-slate-500 mt-1">Read-only view of the audit trail. {auth.recent_users_note}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-[12px] uppercase font-bold border-b border-slate-200">
              <tr><th className="py-2.5 px-4">Time</th><th className="py-2.5 px-4">User</th><th className="py-2.5 px-4">Action</th><th className="py-2.5 px-4">Target</th><th className="py-2.5 px-4">Type</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-slate-400">No events recorded.</td></tr>}
              {events.map(e => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="py-2.5 px-4 font-mono text-[12px] text-slate-500">{e.timestamp ? new Date(e.timestamp).toLocaleString('en-ZA') : '—'}</td>
                  <td className="py-2.5 px-4 font-semibold">{e.user}</td>
                  <td className="py-2.5 px-4 font-mono text-[12px]">{e.action}</td>
                  <td className="py-2.5 px-4 text-slate-600">{e.target || '—'}</td>
                  <td className="py-2.5 px-4"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${e.classification === 'SECURITY' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'}`}>{e.classification}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-[12px] text-slate-500">No green status is shown unless the corresponding database check or explicit configuration record exists. This view does not claim regulatory certification.</p>
    </div>
  );
}
