import { useCallback, useEffect, useState } from 'react';
import { FileCheck, ShieldCheck, AlertTriangle } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const STATUS_STYLES = {
  collected: 'bg-slate-100 text-slate-600',
  pending_review: 'bg-amber-50 text-amber-800',
  under_review: 'bg-blue-50 text-blue-700',
  verified: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-red-50 text-red-700',
};

function EvidenceRow({ e, updating, onUpdate }) {
  const [note, setNote] = useState('');
  return (
    <tr className="hover:bg-slate-50">
      <td className="p-3 border-b border-slate-100 text-xs font-mono text-slate-500">#{e.id}</td>
      <td className="p-3 border-b border-slate-100 text-xs font-extrabold text-[#0F2744]">{e.title}</td>
      <td className="p-3 border-b border-slate-100 text-xs"><span className="font-semibold uppercase">{e.evidence_type}</span></td>
      <td className="p-3 border-b border-slate-100 text-xs">{e.claim_id ? `Claim ${e.claim_id}` : ''}{e.investigation_id ? ` (Inv ${e.investigation_id})` : ''}</td>
      <td className="p-3 border-b border-slate-100 text-xs">
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${STATUS_STYLES[e.status] || ''}`}>{e.status}</span>
        {e.integrity_verified ? <span className="ml-2 text-emerald-600"><ShieldCheck size={13} className="inline" /></span> : null}
      </td>
      <td className="p-3 border-b border-slate-100 text-[10px] font-mono text-slate-400">{e.sha256_hash || '—'}</td>
      <td className="p-3 border-b border-slate-100 text-[11px] text-slate-500">{new Date(e.collected_at).toLocaleDateString()} — {e.collected_by}</td>
      <td className="p-3 border-b border-slate-100">
        <div className="flex gap-2">
          <input value={note} onChange={ev => setNote(ev.target.value)} placeholder="note" className="px-2 py-1.5 text-[11px] border border-slate-200 rounded-md" disabled={updating} />
          <button onClick={() => onUpdate(e.id, 'pending_review', note || 'sent for review')} className="text-[10px] px-2 py-1 bg-amber-500 text-amber-950 font-bold rounded-md disabled:opacity-40" disabled={updating}>Review</button>
          <button onClick={() => onUpdate(e.id, 'verified', note || 'verified')} className="text-[10px] px-2 py-1 bg-emerald-500 text-emerald-950 font-bold rounded-md disabled:opacity-40" disabled={updating}>Verify</button>
          <button onClick={() => onUpdate(e.id, 'rejected', note || 'rejected by investigator')} className="text-[10px] px-2 py-1 bg-red-100 text-red-700 font-bold rounded-md disabled:opacity-40" disabled={updating}>Reject</button>
        </div>
      </td>
    </tr>
  );
}

export default function EvidenceManagement({ user }) {
  const [evidence, setEvidence] = useState([]);
  const [integrity, setIntegrity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [updating, setUpdating] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.evidenceList({ limit: 100 });
      if (res.ok) setEvidence(await res.json());
      const res2 = await api.evidenceReport(0).catch(() => null);
      const integ = await fetch('/evidence/integrity/all');
      if (integ.ok) setIntegrity(await integ.json());
    } catch { setError('Could not fetch evidence data.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  const allVerified = integrity.length > 0 && integrity.every(r => r.integrity_ok);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-[#0F2744] flex items-center gap-3"><FileCheck size={22} className="text-amber-500" /> Digital Evidence & Audit Trail</h1>
          <p className="text-xs text-slate-500 font-medium mt-1">SHA-256 fingerprinted records — integrity is re-verified on demand; evidence updates are audited.</p>
        </div>
        <div className="flex gap-2">
          <span className={`px-3 py-1.5 rounded-full text-xs font-bold ${allVerified ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}>
            {integrity.filter(r => r.integrity_ok).length}/{integrity.length} integrity verified
          </span>
          <button onClick={() => setRefreshKey(k => k + 1)} className="px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 font-bold text-sm">Refresh</button>
        </div>
      </div>

      {loading && <div className="text-center text-slate-400 py-12">Loading evidence…</div>}
      {error && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-[#0F2744] text-white">
            <tr className="text-[10px] font-extrabold uppercase tracking-wide">
              <th className="p-4">ID</th><th className="p-4">Title</th><th className="p-4">Type</th>
              <th className="p-4">Link</th><th className="p-4">Status</th><th className="p-4">SHA-256</th>
              <th className="p-4">Collected</th><th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {evidence.length === 0 && <tr><td colSpan={8} className="p-6 text-center text-sm text-slate-400">No evidence records available for your scope.</td></tr>}
            {evidence.map(e => <EvidenceRow key={e.id} e={e} updating={updating} onUpdate={async (id, status, note) => {
              setUpdating(true);
              await api.updateEvidenceStatus(id, status, note);
              await load(); setUpdating(false);
            }} />)}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-3">
        Digital evidence actions (review/verify/reject) append to the append-only audit trail. Modifications and deletions of verified evidence are restricted.
      </div>
    </div>
  );
}
