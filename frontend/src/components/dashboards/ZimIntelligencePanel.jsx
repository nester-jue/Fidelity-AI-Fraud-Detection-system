import { useCallback, useEffect, useState } from 'react';
import { Globe, ShieldAlert, CheckCircle2, XCircle, RefreshCw, AlertCircle, Database } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const CURRENCY_STYLE = (ok) => (ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700');

function RuleGroup({ group }) {
  return (
    <div className="mb-5">
      <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">{group.group_id.replace(/_/g, ' ')} — {group.description}</h4>
      {(group.rules || []).map(rule => (
        <div key={rule.rule_id} className="text-xs bg-slate-50 rounded-xl px-3 py-2 mb-1.5 border border-slate-100">
          <p className="font-semibold text-slate-700">{rule.rule_id}</p>
          <p className="text-slate-600">{rule.description}</p>
          <p className="text-[10px] font-black text-slate-500 mt-1">Default: {String(rule.value)}</p>
        </div>
      ))}
      {!group.rules?.length && (
        <p className="text-[11px] text-slate-400 italic">No configurable rules defined in this group.</p>
      )}
    </div>
  );
}

export default function ZimIntelligencePanel({ user }) {
  const [config, setConfig] = useState(null);
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState('');
  const [nidTest, setNidTest] = useState('');
  const [nidResult, setNidResult] = useState(null);
  const [dateTest, setDateTest] = useState('');
  const [dateResult, setDateResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [c, r] = await Promise.all([api.zimConfig(), api.zimRegulatoryRules()]);
      if (c.ok) setConfig(await c.json());
      if (r.ok) setRules(await r.json());
      setLastUpdated(new Date().toLocaleString('en-ZA'));
    } catch {
      setError('Could not fetch Zimbabwe intelligence data. The service is temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const validateNid = async () => {
    setNidResult(null);
    const res = await api.zimValidateNationalId(nidTest.trim());
    if (res.ok) setNidResult(await res.json());
  };

  const normalizeDate = async () => {
    setDateResult(null);
    const res = await api.zimValidateDate(dateTest.trim());
    if (res.ok) setDateResult(await res.json());
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400"><Database size={20} className="animate-pulse mr-2" /> Loading Zimbabwe intelligence…</div>;
  }
  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-6 flex flex-col items-center text-center">
          <AlertCircle size={32} className="text-red-400 mb-3" />
          <h2 className="text-lg font-black text-slate-900 mb-2">Zimbabwe Insurance Intelligence — Service Unavailable</h2>
          <p className="text-xs text-slate-600 mb-4">{error}</p>
          <button onClick={load} className="px-5 py-2.5 rounded-xl bg-red-600 text-white font-bold text-xs hover:bg-red-700 shadow-md flex items-center space-x-2"><RefreshCw size={14} /><span>Retry</span></button>
          {lastUpdated && <p className="text-[10px] text-slate-400 mt-3">Last verified update: {lastUpdated}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-extrabold text-[#0F2744] flex items-center gap-3"><Globe size={22} className="text-amber-500" /> Zimbabwe Insurance Intelligence</h1>
          {lastUpdated && <span className="text-[11px] text-slate-400">Last verified information update: {lastUpdated}</span>}
        </div>
        <p className="text-xs text-slate-500 font-medium mt-1">
          Zimbabwean operating environment: formats, currencies, regulatory rules. Configurable defaults — verify against current legislation with legal counsel.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Accepted Claim Currencies</h3>
            {(config?.accepted_currencies || []).length === 0 ? (
              <p className="text-xs text-slate-400">No regulated currencies accepted currently.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {config.accepted_currencies.map(c => (
                  <span key={c} className={`px-3 py-1.5 rounded-full text-xs font-black ${c === config.mandatory_currency ? 'bg-[#0F2744] text-white' : 'bg-slate-100 text-slate-600'}`}>
                    {c}{c === config.mandatory_currency ? ' (mandatory)' : ''}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">National ID Formats</h3>
            {(config?.national_id_formats || []).length === 0 ? (
              <p className="text-xs text-slate-400">No national ID formats defined.</p>
            ) : (
              <>
                {config.national_id_formats.map(f => (
                  <div key={f.format_id} className="text-sm mb-2">
                    <p className="font-semibold">{f.format_id}</p>
                    <p className="text-[11px] font-mono text-slate-500">{f.regex}</p>
                    <p className="text-[10px] text-slate-400">{f.description}</p>
                  </div>
                ))}
                <div className="mt-3 flex gap-2">
                  <input value={nidTest} onChange={e => setNidTest(e.target.value)} placeholder="e.g. 63-1234567-A-01" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-44" />
                  <button onClick={validateNid} disabled={!nidTest.trim()} className="px-3 py-2 text-sm font-bold bg-[#0F2744] text-white rounded-md disabled:opacity-50">Validate ID</button>
                </div>
                {nidResult && (
                  <div className="mt-3 text-xs bg-slate-50 rounded-xl px-3 py-2">
                    <p className={`font-bold ${nidResult.valid ? 'text-emerald-700' : 'text-red-700'}`}><span className={`inline-block w-4 mr-1`}><span className={nidResult.valid ? 'text-emerald-600' : 'text-red-600'}><CheckCircle2 size={14} /></span><span className="w-1" /></span>{nidResult.valid ? 'Format valid' : 'Format invalid'}</p>
                    {nidResult.normalized && <p className="font-mono">Normalized: {nidResult.normalized}</p>}
                    {nidResult.errors?.map((e, i) => <p key={i} className="text-red-600">⚠ {e}</p>)}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Date Format Normalisation</h3>
            <div className="flex gap-2">
              <input value={dateTest} onChange={e => setDateTest(e.target.value)} placeholder="e.g. 15/03/2026 (DD/MM/YYYY)" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-48" />
              <button onClick={normalizeDate} disabled={!dateTest.trim()} className="px-3 py-2 text-sm font-bold bg-[#0F2744] text-white rounded-md disabled:opacity-50">Normalize</button>
            </div>
            {dateResult && (
              <p className="mt-3 text-xs">{dateResult.ok ? `→ ISO: ${dateResult.iso}` : `✗ ${(dateResult.errors || ['No match']).join(' ')}`}</p>
            )}
          </div>

          <div className="text-[10px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-3">
            Formats encode verifiable public formats; regulatory values are configurable defaults — verify against current legislation with legal counsel.
          </div>
        </div>

        <div>
          <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Regulatory & Compliance Rules</h3>
          {(rules?.rule_groups || []).length === 0 ? (
            <p className="text-xs text-slate-400">No regulatory rules defined at present.</p>
          ) : (
            rules.rule_groups.map(g => <RuleGroup key={g.group_id} group={g} />)
          )}
          {rules && (
            <p className="text-[10px] text-slate-400 mt-4">
              Source: /zim/regulatory-rules endpoint — Fidelity Life Assurance AI Fraud Suite regulatory rules data. Verified against Zimbabwean insurance legislation on the platform's configuration snapshot; values marked "configurable" may be adjusted by administrators under legal/compliance guidance. Information requiring formal legal confirmation is flagged in the UI.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
