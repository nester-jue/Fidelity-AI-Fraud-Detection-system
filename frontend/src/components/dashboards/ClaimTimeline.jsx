import { useCallback, useEffect, useState } from 'react';
import { Clock, FileText, ScanEye } from 'lucide-react';
import { api } from '../../api/apiClient.js';

// ---------------------------------------------------------------------------
// Claim Timeline — chronological history of a claim from real records, with
// anomalies and missing steps highlighted.
// ---------------------------------------------------------------------------

function EventCard({ e }) {
  const [expanded, setExpanded] = useState(false);
  const icons = {
    customer_registered: 'UserCheck', incident_occurred: 'AlertTriangle',
    beneficiary_changed: 'Users', claim_submitted: 'FilePlus', documents_submitted: 'Upload',
    ocr_processed: 'ScanEye', fraud_assessed: 'ShieldAlert', investigation_opened: 'ShieldPlus',
    investigation_actions: 'ListChecks', investigation_closed: 'CheckCheck', claim_decided: 'Gavel',
    policy_activated: 'FileBarChart',
  };
  const label = e.display_label || e.event_type;
  return (
    <div className="relative flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`w-4 h-4 rounded-full border-2 border-[#0F2744] ${expanded ? 'bg-[#0F2744]' : 'bg-white'} z-10`} />
      </div>
      <div className="flex-1 bg-white rounded-xl border border-slate-200 px-4 py-3">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-extrabold text-[#0F2744] uppercase tracking-wide">{label}</p>
            <p className="text-[11px] text-slate-500">{new Date(e.timestamp).toLocaleString()}</p>
          </div>
          <button onClick={() => setExpanded(!expanded)} title="Show details" className="text-slate-400 hover:text-slate-700">
            <ScanEye size={14} />
          </button>
        </div>
        <p className="text-sm text-slate-700 mt-1">{e.description}</p>
        {e.source && <p className="text-[10px] font-mono text-slate-400 mt-1">Source: {e.source}</p>}
        {e.is_fabricated && <p className="text-[10px] font-semibold text-amber-700 mt-1">Derived event (not observed in records)</p>}
        {expanded && e.sequence_order != null && <p className="text-[10px] text-slate-400 mt-1">Sequence: {e.sequence_order}</p>}
      </div>
    </div>
  );
}

export default function ClaimTimeline({ user }) {
  const [claimId, setClaimId] = useState('');
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState('');
  const [recentClaims, setRecentClaims] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchTimeline = useCallback(async (ref) => {
    const id = (ref || claimId || '').trim();
    if (!id) { setTimeline(null); return; }
    setLoading(true);
    try {
      const res = await api.claimTimeline(id);
      if (res.ok) {
        setTimeline(await res.json());
        setError('');
      } else {
        const b = await res.json().catch(() => ({}));
        setError(b.detail || 'Claim not found.');
        setTimeline(null);
      }
    } catch {
      setError('Could not fetch timeline.');
      setTimeline(null);
    } finally {
      setLoading(false);
    }
  }, [claimId]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.listClaims({ limit: 25 });
        if (res.ok) setRecentClaims((await res.json()).map(c => ({ id: c.claim_id, value: c.claim_id, label: `${c.claim_id} — ${c.customer_name} (${c.claim_type})` })));
      } catch { /* best effort */ }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-2xl font-extrabold text-[#0F2744] flex items-center gap-3"><Clock size={22} className="text-amber-500" /> Claim Timeline Intelligence</h1>
          <p className="text-xs text-slate-500 font-medium">Chronological reconstruction of claim events from real records — never fabricated.</p>
        </div>
        <div className="flex gap-2">
          <select
            value={claimId}
            onChange={e => setClaimId(e.target.value)}
            className="px-4 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-400"
          >
            <option value="">— select claim —</option>
            {recentClaims.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <button onClick={() => fetchTimeline()} className="px-5 py-2.5 rounded-xl bg-[#0F2744] text-white font-bold text-sm" disabled={!claimId || loading}>Load Timeline</button>
        </div>
      </div>

      {error && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      {timeline && (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-3">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider">Event Timeline — {timeline.claim_id}</h3>
            <div className="relative ml-1">
              <div className="absolute left-2 top-2 bottom-2 w-px bg-slate-200" />
              {timeline.events.length === 0 && <p className="text-sm text-slate-400">No events recorded.</p>}
              {timeline.events.map((e, i) => (
                <EventCard key={i} e={{ ...e, display_label: e.display_label || e.event_type }} />
              ))}
            </div>
            {timeline.notes && timeline.notes.length > 0 && (
              <div className="mt-4">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">Investigation Notes</h4>
                {timeline.notes.map(n => (
                  <div key={n.id} className="text-sm text-slate-700 bg-slate-50 rounded-xl px-4 py-2 mb-2 border-l-4 border-amber-400"><p className="text-xs font-bold text-slate-500">{n.created_by} · {n.created_at}</p>{n.text}</div>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Summary</h4>
              <p className="text-sm">Events: <span className="font-black">{timeline.summary.total_events}</span></p>
              <p className="text-sm mt-1">Span: <span className="font-black">{timeline.summary.span_days ?? '—'}</span> days</p>
              {timeline.summary.missing_steps?.length && <p className="text-xs text-red-600 font-semibold mt-2">Missing steps: {timeline.summary.missing_steps.join(', ')}</p>}
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h4 className="text-xs font-extrabold uppercase text-slate-500 mb-2">Anomalies & inconsistencies</h4>
              {timeline.anomalies.length === 0 && <p className="text-xs text-slate-400">None detected.</p>}
              {timeline.anomalies.map((a, i) => (
                <div key={i} className="text-sm mb-2 bg-amber-50/60 border border-amber-200 rounded-xl px-3 py-2">
                  <p className="font-semibold text-amber-800">{a.type}</p>
                  <p className="text-xs text-slate-600">{a.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
