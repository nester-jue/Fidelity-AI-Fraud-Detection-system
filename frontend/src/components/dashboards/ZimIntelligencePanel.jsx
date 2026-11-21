import { useCallback, useEffect, useState } from 'react';
import { Globe, ShieldAlert, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../../api/apiClient.js';

const CURRENCY_STYLE = (ok) => (ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700');

function RuleGroup({ group }) {
  return (
    <div className="mb-5">
      <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">{group.group_id.replace(/_/g, ' ')} — {group.description}</h4>
      {group.rules.map(rule => (
        <div key={rule.rule_id} className="text-xs bg-slate-50 rounded-xl px-3 py-2 mb-1.5 border border-slate-100">
          <p className="font-semibold text-slate-700">{rule.rule_id}</p>
          <p className="text-slate-600">{rule.description}</p>
          <p className="text-[10px] font-black text-slate-500 mt-1">Default: {String(rule.value)}</p>
        </div>
      ))}
    </div>
  );
}

export default function ZimIntelligencePanel({ user }) {
  const [config, setConfig] = useState(null);
  const [rules, setRules] = useState(null);
  const [nidTest, setNidTest] = useState('');
  const [nidResult, setNidResult] = useState(null);
  const [dateTest, setDateTest] = useState('');
  const [dateResult, setDateResult] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [c, r] = await Promise.allSettled([api.zimConfig(), api.zimRegulatoryRules()]);
      if (c.status === 'fulfilled' && c.value.ok) setConfig(await c.value.json());
      if (r.status === 'fulfilled' && r.value.ok) setRules(await r.value.json());
    } catch { setError('Could not fetch Zimbabwe intelligence data.'); }
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

  if (!config) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Loading Zimbabwe intelligence…{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h1 className="text-2xl font-extrabold text-[#0F2744] flex items-center gap-3"><Globe size={22} className="text-amber-500" /> Zimbabwe Insurance Intelligence</h1>
        <p className="text-xs text-slate-500 font-medium mt-1">Zimbabwean operating environment: formats, currencies, regulatory rules. Configurable defaults — verify against current legislation with legal counsel.</p>
      </div>

      {error && <div className="bg-red-50 border-l-4 border-red-600 text-red-800 px-4 py-2.5 rounded-xl text-sm font-bold">{error}</div>}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Accepted Claim Currencies</h3>
            <div className="flex flex-wrap gap-2">
              {config.accepted_currencies.map(c => (
                <span key={c} className={`px-3 py-1.5 rounded-full text-xs font-black ${c === config.mandatory_currency ? 'bg-[#0F2744] text-white' : 'bg-slate-100 text-slate-600'}`}>
                  {c}{c === config.mandatory_currency ? ' (mandatory)' : ''}
                </span>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">National ID Formats</h3>
            {config.national_id_formats.map(f => (
              <div key={f.format_id} className="text-sm mb-2">
                <p className="font-semibold">{f.format_id}</p>
                <p className="text-[11px] font-mono text-slate-500">{f.regex}</p>
                <p className="text-[10px] text-slate-400">{f.description}</p>
              </div>
            ))}
            <div className="mt-3 flex gap-2">
              <input value={nidTest} onChange={e => setNidTest(e.target.value)} placeholder="e.g. 63-1234567-A-01" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-44" />
              <button onClick={validateNid} className="px-3 py-2 text-sm font-bold bg-[#0F2744] text-white rounded-md">Validate ID</button>
            </div>
            {nidResult && (
              <div className="mt-3 text-xs bg-slate-50 rounded-xl px-3 py-2">
                <p className={`font-bold ${nidResult.valid ? 'text-emerald-700' : 'text-red-700'}`}><span className="inline-block w-4"><CheckCircle2 size={14} className={nidResult.valid ? 'text-emerald-600' : 'text-red-600'} /><span className="w-1" /></span>{nidResult.valid ? 'Valid format' : 'Invalid format'}</p>
                {nidResult.normalized && <p className="font-mono">Normalized: {nidResult.normalized}</p>}
                {nidResult.errors?.map((e, i) => <p key={i} className="text-red-600">⚠ {e}</p>)}
              </div>
            )}
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider mb-3">Date Format Normalisation</h3>
            <div className="flex gap-2">
              <input value={dateTest} onChange={e => setDateTest(e.target.value)} placeholder="e.g. 15/03/2026 (DD/MM/YYYY)" className="px-3 py-2 text-sm border border-slate-200 rounded-md w-48" />
              <button onClick={normalizeDate} className="px-3 py-2 text-sm font-bold bg-[#0F2744] text-white rounded-md">Normalize</button>
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
          {rules?.rule_groups?.map(g => <RuleGroup key={g.group_id} group={g} />)}
        </div>
      </div>
    </div>
  );
}
