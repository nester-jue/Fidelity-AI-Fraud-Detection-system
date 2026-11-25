import { useCallback, useEffect, useState } from 'react';
import { History, Activity, ShieldAlert } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const SEV_STYLES = {
  high: 'bg-red-50 text-red-800', medium: 'bg-amber-50 text-amber-800', low: 'bg-blue-50 text-blue-700',
};

export default function HistoricalBehaviorPanel({ user }) {
  const [data, setData] = useState(null);
  const [customerId, setCustomerId] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      // Pick a claim (officer/manager scope or any authenticated user).
      const claimsRes = await api.listClaims({ limit: 10 });
      let claimId = null;
      if (claimsRes.ok) {
        const claims = await claimsRes.json();
        claimId = claims[0]?.claim_id || null;
      }
      if (claimId) {
        const res = await api.historicalClaimAnalysis(claimId);
        if (res.ok) {
          const body = await res.json();
          setData(body);
          setCustomerId(body.claim?.customer_id || '');
          return;
        }
      }
      // Fallback: customer stats overview
      if (customerId) {
        const res2 = await api.historicalCustomerStats(customerId);
        if (res2.ok) setData({ claim: { claim_id: '(customer overview)', claim_type: '', amount: 0 }, ...await res2.json() });
      }
    } catch {
      setError('Could not load historical behaviour data.');
    }
  }, [customerId]);

  useEffect(() => { load(); }, [load]);

  const anomalies = data?.history_anomalies || [];
  const comparisons = data?.comparisons || [];
  const prevClaims = data?.previous_claims || [];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h1 className="nexa-suite-heading text-[#0F2744] flex items-center gap-3"><History size={22} className="text-amber-500" /> Historical Claim Behaviour Intelligence</h1>
        <p className="text-xs text-slate-500 font-medium mt-1">Comparisons of the current claim against policyholder history, similar historical claims and policy information — all real records.</p>
      </div>

      {error && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Policyholder Statistics</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <p>Prior claims: <span className="font-black">{data.stats?.claim_count ?? '—'}</span></p>
                <p>Total amount: <span className="font-black">{data.stats?.total_amount != null ? `$${data.stats.total_amount.toLocaleString()}` : '—'}</span></p>
                <p>Avg claim amount: <span className="font-black">{data.stats?.avg_amount != null ? `$${data.stats.avg_amount.toLocaleString()}` : '—'}</span></p>
                <p>Peak claims/30d: <span className="font-black">{data.stats?.claims_per_30d ?? '—'}</span></p>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Current Claim</h3>
              <div className="text-sm">
                <p><span className="font-bold">{data.claim?.claim_id}</span> — {data.claim?.claim_type}</p>
                <p className="mt-1">Amount: <span className="font-black">${(data.claim?.amount || 0).toLocaleString()}</span></p>
                <p className="mt-1">Policy: <span className="font-semibold">{data.policy?.policy_number}</span></p>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase flex items-center gap-2"><ShieldAlert size={14} /> Anomalies</h3>
              {anomalies.length === 0 && <p className="text-xs text-slate-400">No anomalies found in historical patterns.</p>}
              {anomalies.map((a, i) => (
                <div key={i} className="text-xs mb-2 bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                  <p className="font-semibold text-[#0F2744]">{a.type} <span className={`px-1.5 py-0.5 rounded text-[9px] ${SEV_STYLES[a.severity] || ''}`}>{a.severity}</span></p>
                  <p className="text-slate-600">{a.evidence}</p>
                  <p className="text-slate-500">Reason: {a.reason}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Previous Claims ({prevClaims.length})</h3>
              <table className="w-full text-left text-xs">
                <thead><tr className="border-b border-slate-100 text-slate-400"><th className="py-1 font-semibold">Claim</th><th className="py-1 font-semibold">Type</th><th className="py-1 font-semibold">Amount</th><th className="py-1 font-semibold">Incident</th><th className="py-1 font-semibold">Δ days</th></tr></thead>
                <tbody>
                  {prevClaims.slice(0, 8).map((c, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-1 font-mono">{c.claim_id}</td>
                      <td className="py-1">{c.claim_type}</td>
                      <td className="py-1 font-black">${c.amount ? c.amount.toLocaleString() : '—'}</td>
                      <td className="py-1">{c.incident_date ? c.incident_date.slice(0, 10) : '—'}</td>
                      <td className="py-1 text-slate-500">{c.days_since_incident != null ? `${Math.abs(c.days_since_incident)}d` : '—'}</td>
                    </tr>
                  ))}
                  {prevClaims.length === 0 && <tr><td colSpan={5} className="py-2 text-center text-slate-400">No prior claims.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Similar Historical Claims ({(data.similar_historical_claims || []).length})</h3>
              {(data.similar_historical_claims || []).slice(0, 5).map((c, i) => (
                <div key={i} className="text-xs mb-2 bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                  <p className="font-semibold text-slate-600">{c.claim_id} · {c.claim_type}</p>
                  <p className="text-black font-black">${c.amount ? c.amount.toLocaleString() : '—'} · {c.submission_date ? c.submission_date.slice(0, 10) : '—'}</p>
                  <p className="text-slate-500">Similarity: <span className="font-semibold">{(c.similarity_score * 100).toFixed(0)}%</span> ({c.matching_strength})</p>
                </div>
              ))}
              {(data.similar_historical_claims || []).length === 0 && <p className="text-xs text-slate-400">No similar claims found.</p>}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Comparisons — Current Claim vs History</h3>
              {comparisons.length === 0 && <p className="text-xs text-slate-400">No notable comparisons found.</p>}
              {comparisons.map((c, i) => (
                <div key={i} className="text-xs mb-2 bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                  <p className="font-semibold text-[#0F2744]">{c.topic}</p>
                  <p className="text-slate-700">{c.detail}</p>
                  {c.evidence && <p className="text-[10px] text-slate-400">{c.evidence}</p>}
                </div>
              ))}
            </div>
            <div className="text-[10px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-3">
              Historical intelligence evaluates the current claim against legitimate policy conditions and customer circumstances — anomalies are indicators for review, not confirmed fraud.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
