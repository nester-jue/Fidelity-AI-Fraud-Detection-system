import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Network, RefreshCw, AlertCircle, ServerOff } from 'lucide-react';
import { api } from '../../api/apiClient.js';

// ---------------------------------------------------------------------------
// Fraud Network Intelligence — real fraud relationship graph from the backend.
// Nodes: customers, policies, claims, documents, beneficiaries, payment refs.
// Edges: real relationships with strength + evidence. Suspicious ones flagged.
// Note: the platform surfaces suspicion for review; it never labels anyone
// confirmed fraud by itself.
// ---------------------------------------------------------------------------

const TYPE_COLORS = {
  customer: '#3B82F6', policy: '#10B981', claim: '#8B5CF6',
  document: '#F59E0B', beneficiary: '#EF4444', payment_ref: '#6B72BE',
  default: '#6B7280',
};
const TYPE_LABELS = {
  customer: 'Customer', policy: 'Policy', claim: 'Claim',
  document: 'Document', beneficiary: 'Beneficiary', payment_ref: 'Account Ref',
};

const API_TIMEOUT_MS = 10000;

function forceLayout(nodes, edges, width = 760, height = 420) {
  const pos = new Map();
  const cx = width / 2, cy = height / 2;
  const r = Math.min(width, height) * 0.35;
  nodes.forEach((n, i) => {
    const a = (i / Math.max(1, nodes.length)) * 2 * Math.PI;
    pos.set(n.id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
  });
  for (let it = 0; it < 80; it++) {
    for (const e of edges) {
      const a = pos.get(e.node_a_id), b = pos.get(e.node_b_id);
      if (!a || !b) continue;
      let dx = b.x - a.x, dy = b.y - a.y;
      let d = Math.sqrt(dx * dx + dy * dy) || 1;
      const target = (1 - e.strength) * 3 + 1.5;
      const fx = (dx / d) * (target - d) * 0.5;
      const fy = (dy / d) * (target - d) * 0.5;
      a.x += fx; a.y += fy; b.x -= fx; b.y -= fy;
    }
    for (const n of nodes) {
      const p = pos.get(n.id);
      if (!p) continue;
      if (n.is_suspicious) { p.x += (cx - p.x) * 0.02; p.y += (cy - p.y) * 0.02; }
    }
  }
  return pos;
}

export default function FraudNetworkGraph({ user }) {
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedEdge, setExpandedEdge] = useState(null);
  const abortRef = useRef(null);

  const refresh = useCallback(async () => {
    const controller = new AbortController();
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = controller;
    setLoading(true);
    setError('');
    try {
      const res = await api.fraudNetworkGraph({ signal: controller.signal });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data && Array.isArray(data.nodes)) setGraph(data);
      else setGraph({ nodes: [], edges: [], summary: { total_nodes: 0, total_edges: 0, clusters: 0 }, suspicious_nodes: [], suspicious_edges: [] });
    } catch (err) {
      if (err?.name === 'AbortError') return; // superseded by a newer request or unmount
      setError(err.message || 'Could not fetch fraud network data.');
    } finally {
      if (abortRef.current === controller) setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const positions = useMemo(
    () => (graph ? forceLayout(graph.nodes, graph.edges) : new Map()),
    [graph]
  );

  const hasEmpty = !graph?.nodes || graph.nodes.length === 0;
  const suspiciousCount = (graph?.suspicious_nodes?.length || 0) + (graph?.suspicious_edges?.length || 0);

  if (loading && !graph) {
    return <div className="flex items-center justify-center h-64 text-slate-400"><Network size={20} className="animate-pulse mr-2" /> Loading fraud network…</div>;
  }
  if (error) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center space-x-2 mb-2"><ServerOff size={18} className="text-red-500" /><span className="font-bold text-red-700">Fraud Network Intelligence — Data Unavailable</span></div>
          <p className="text-xs text-slate-600 mb-4">{error}</p>
          <button onClick={refresh} className="px-4 py-2 rounded-xl bg-red-600 text-white font-bold text-xs hover:bg-red-700 shadow-md flex items-center space-x-2"><RefreshCw size={14} /><span>Retry Fetching Network</span></button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total entities analysed</p>
          <p className="text-3xl font-black text-[#0F2744] mt-2">{graph.summary?.total_nodes ?? 0}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total relationships identified</p>
          <p className="text-3xl font-black text-slate-600 mt-2">{graph.summary?.total_edges ?? 0}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-red-500">Suspicious relationships</p>
          <p className="text-3xl font-black text-red-600 mt-2">{suspiciousCount}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Connected claim clusters</p>
          <p className="text-3xl font-black text-slate-800 mt-2">{graph.summary?.clusters ?? 0}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 bg-[#0F2744] text-white flex items-center justify-between">
          <div className="flex items-center space-x-2 font-bold">
            <Network size={16} className="text-amber-400" />
            <span>Fraud Relationship Network (live graph)</span>
          </div>
          <button onClick={refresh} className="text-white/60 hover:text-white text-xs" title="Refresh network">
            Refresh
          </button>
        </div>
        {hasEmpty ? (
          <div className="p-8 text-center">
            <AlertCircle size={28} className="text-slate-300 mx-auto" />
            <p className="text-sm text-slate-500 font-medium mt-2">No fraud network relationships are currently available.</p>
            <p className="text-xs text-slate-400 mt-1">Network intelligence generates from repeated customer claims, shared contact details, identical document hashes, repeated beneficiaries and shared payment references across multiple claims.</p>
          </div>
        ) : (
          <>
            <div className="relative bg-slate-950">
              <svg viewBox="0 0 760 420" className="w-full h-[420px]">
                {(graph.edges || []).map(e => {
                  const a = positions.get(e.node_a_id), b = positions.get(e.node_b_id);
                  if (!a || !b) return null;
                  return (
                    <g key={e.id}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                        stroke={e.is_suspicious ? '#F87171' : '#334155'}
                        strokeWidth={e.strength * 2.5} strokeOpacity={e.is_suspicious ? 0.85 : 0.35}
                        strokeDasharray={e.is_suspicious ? '4,3' : undefined}
                        className={e.is_suspicious ? 'animate-pulse' : ''}
                        onClick={() => setExpandedEdge(e)}
                        cursor={e.is_suspicious ? 'pointer' : 'default'} />
                      {e.is_suspicious && (
                        <circle cx={(a.x + b.x) / 2} cy={(a.y + b.y) / 2} r="4" fill="#F87171" stroke="#1E3A8A" strokeWidth="1.5" />
                      )}
                    </g>
                  );
                })}
                {(graph.nodes || []).map(n => {
                  const p = positions.get(n.id);
                  if (!p) return null;
                  const color = TYPE_COLORS[n.entity_type] || TYPE_COLORS.default;
                  const label = (n.name || n.id).slice(0, 14);
                  return (
                    <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
                      {n.is_suspicious && <circle r="18" fill="none" stroke="#F87171" strokeWidth="1.5" className="animate-ping opacity-40" />}
                      <circle r="10" fill={color} stroke={n.is_suspicious ? '#F87171' : '#0F2744'} strokeWidth={n.is_suspicious ? 2 : 1} />
                      <text textAnchor="middle" y="-14" fill="#CBD5E1" fontSize="8" fontWeight="bold">{label}</text>
                      <text textAnchor="middle" y="17" fill="white" fontSize="7" fontWeight="bold" fontFamily="monospace">{n.entity_type === 'claim' ? (n.amount ? `${Number(n.amount).toLocaleString()}` : '') : ''}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <div className="px-6 py-4 grid sm:grid-cols-3 gap-4 border-t border-slate-200 bg-slate-50">
              <div>
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Suspicious nodes</h4>
                {(graph.suspicious_nodes || []).slice(0, 6).map(n => (
                  <div key={n.id} className="text-xs mb-1">
                    <span className="font-semibold">{n.name || n.id}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] ml-1 ${n.risk_score >= 80 ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'}`}>{n.risk_score?.toFixed(0)}/100</span>
                    <span className="text-[10px] text-slate-400 block">{TYPE_LABELS[n.entity_type]}{n.claim_id ? ` — claim ${n.claim_id}` : ''}</span>
                  </div>
                ))}
                {!graph.suspicious_nodes?.length && <p className="text-xs text-slate-400">None.</p>}
              </div>
              <div>
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Suspicious relationships</h4>
                {(graph.suspicious_edges || []).slice(0, 8).map((e, i) => (
                  <div key={i} className="text-xs mb-1">
                    <span className="font-semibold">{(e.relationship_type || 'relationship').replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-slate-500 block">{e.evidence}</span>
                  </div>
                ))}
                {!graph.suspicious_edges?.length && <p className="text-xs text-slate-400">None.</p>}
              </div>
              <div>
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Clusters (review candidates)</h4>
                {(graph.clusters || []).slice(0, 5).map(c => (
                  <div key={c.cluster_id} className="text-xs mb-1">
                    <span className="font-semibold">{c.claim_ids?.length || 0} claims · {c.member_count} entities</span>
                    <span className="text-[10px] text-red-600 font-semibold block">{(c.relationship_evidence || []).slice(0, 2).join(' ; ')}</span>
                  </div>
                ))}
                {!graph.clusters?.length && <p className="text-xs text-slate-400">No suspicious clusters detected.</p>}
              </div>
            </div>
          </>
        )}
      </div>

      {expandedEdge && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Relationship Detail</h3>
            <button onClick={() => setExpandedEdge(null)} className="text-slate-400 hover:text-slate-700"><span className="text-xl">&times;</span></button>
          </div>
          <p className="text-xs font-bold">{expandedEdge.relationship_type?.replace(/_/g, ' ')}</p>
          <p className="text-[11px] text-slate-600 mt-1">{expandedEdge.evidence}</p>
          <div className="mt-2 flex gap-4 text-[11px] text-slate-500">
            <span>Strength: {expandedEdge.strength?.toFixed?.(2)}</span>
            <span>Suspicious: {expandedEdge.is_suspicious ? 'Yes' : 'No'}</span>
            <span>Claims: {(expandedEdge.claim_ids || []).join(', ')}</span>
          </div>
          {expandedEdge.is_suspicious && (
            <p className="mt-2 text-[10px] text-red-600 font-semibold">
              Honesty note: connected entities may have legitimate explanations. NEXA flags possible relationships for human review; no individual is labelled confirmed fraud automatically.
            </p>
          )}
        </div>
      )}

      <div className="text-[10px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-3">
        Honesty note: connected entities may have legitimate explanations. NEXA flags possible relationships for human review; no individual is labeled confirmed fraud automatically.
      </div>
    </div>
  );
}
