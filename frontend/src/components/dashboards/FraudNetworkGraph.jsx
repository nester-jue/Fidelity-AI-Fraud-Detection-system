/**
 * FraudNetworkGraph.jsx — Fraud Network Intelligence (new implementation).
 *
 * A live fraud-relationship graph + review panels. All data comes from the
 * backend (no fabricated data): /fraud-network/graph.
 *
 * Design:
 * - Summary cards: total nodes, relationships, suspicious relationships, clusters.
 * - Live graph: edges (normal + suspicious), nodes by entity type, labels.
 * - "Review" emphasis: suspicious nodes get ping markers + red borders;
 *   suspicious edges get midpoint markers.
 * - Always renders something — loading, error (with Retry) or a clear empty
 *   state ("No fraud network relationships are currently available.").
 * - Node repulsion keeps dense graphs readable.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Network, RefreshCw, AlertCircle, ServerOff, ShieldCheck, Users, FileWarning, Eye, Plus } from 'lucide-react';
import { api } from '../../api/apiClient.js';

// ---------------------------------------------------------------------------
// Styling / formatting helpers
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
const EDGE_STROKE = '#334155';
const EDGE_STRONG = '#F87171';
const EDGE_SUSPICIOUS_MID = '#F87171';

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

function forceLayout(nodes, edges, width = 760, height = 480) {
  const pos = new Map();
  const cx = width / 2, cy = height / 2;
  const r = Math.min(width, height) * 0.40;
  nodes.forEach((n, i) => {
    const a = (i / Math.max(1, nodes.length)) * 2 * Math.PI;
    pos.set(n.id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
  });
  for (let it = 0; it < 100; it++) {
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
    // Mutual node repulsion so the graph doesn't become unreadable.
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = pos.get(nodes[i].id), b = pos.get(nodes[j].id);
        if (!a || !b) continue;
        let dx = a.x - b.x, dy = a.y - b.y;
        let d = Math.sqrt(dx * dx + dy * dy) || 1;
        const minDist = 22;
        if (d < minDist) {
          const f = (minDist - d) * 0.6;
          const fx = (dx / d) * f, fy = (dy / d) * f;
          a.x += fx; a.y += fy; b.x -= fx; b.y -= fy;
        }
      }
    }
    // Suspicious nodes gravitate toward the centre for visibility.
    for (const n of nodes) {
      const p = pos.get(n.id);
      if (!p) continue;
      if (n.is_suspicious) { p.x += (cx - p.x) * 0.03; p.y += (cy - p.y) * 0.03; }
    }
  }
  return pos;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function FraudNetworkGraph({ user }) {
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);
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
      // Always store a usable graph — never leave it null.
      setGraph(data || {
        nodes: [], edges: [], clusters: [],
        summary: { total_nodes: 0, total_edges: 0, clusters: 0 },
        suspicious_nodes: [], suspicious_edges: [],
      });
    } catch (err) {
      if (err?.name === 'AbortError') return;
      setError(err.message || 'Could not fetch fraud network data.');
    } finally {
      if (abortRef.current === controller) setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh, retryKey]);
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const g = graph || {
    nodes: [], edges: [], clusters: [],
    summary: { total_nodes: 0, total_edges: 0, clusters: 0 },
    suspicious_nodes: [], suspicious_edges: [],
  };
  const positions = useMemo(() => forceLayout(g.nodes, g.edges), [g.nodes, g.edges]);
  const hasEmpty = !g.nodes || g.nodes.length === 0;
  const suspiciousCount = (g.suspicious_nodes?.length || 0) + (g.suspicious_edges?.length || 0);

  const KpiMini = ({ icon: Icon, label, value, sub, accent = '#334155' }) => (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <div className="flex items-start justify-between">
        <div><p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{label}</p><p className="text-2xl font-extrabold text-slate-900 mt-1">{value}</p></div>
        <div className="p-2 rounded-lg bg-slate-50 text-slate-600"><Icon className="w-5 h-5" /></div>
      </div>
      {sub && <p className="text-[11px] text-slate-500 font-medium mt-1">{sub}</p>}
    </div>
  );

  const nodeLabel = (n) => (n?.name || n?.id || '').slice(0, 16);
  const fmtNum = (v) => (v == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v));

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Fraud Network Intelligence — Live Relationship Graph</h1>
          <p className="text-base text-slate-500 mt-1">Entities, relationships and suspicious connections — for human review. Entities are displayed as found by the analysis engine; suspicions are flagged for review.</p>
        </div>
        <button onClick={refresh} className="px-5 py-2.5 text-sm font-bold bg-white text-slate-600 border border-slate-200 rounded-xl hover:bg-slate-50 shadow-sm flex items-center gap-2"><RefreshCw size={15} /> Refresh</button>
      </div>

      {loading && !graph ? (
        <div className="flex justify-center py-24"><Network size={24} className="w-6 h-6 animate-pulse text-blue-500 mr-2" />Loading fraud network…</div>
      ) : error ? (
        <div className="max-w-3xl mx-auto p-8">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 flex flex-col items-center text-center">
            <ServerOff size={36} className="text-red-400 mb-4" />
            <p className="text-base font-bold text-slate-700 mb-2">Fraud Network Intelligence — Data Unavailable</p>
            <p className="text-sm text-slate-600 mb-4">{error}</p>
            <button onClick={() => setRetryKey(k => k + 1)} className="px-5 py-2.5 bg-red-600 text-white text-sm font-bold rounded-xl hover:bg-red-700 shadow-md"><RefreshCw size={15} /> Retry Fetching Network</button>
          </div>
        </div>
      ) : hasEmpty ? (
        <div className="max-w-4xl mx-auto p-8">
          <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
            <AlertCircle size={36} className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-lg font-bold text-slate-500 mt-3">No fraud network relationships are currently available.</p>
            <p className="text-sm text-slate-400 mt-1">The analysis engine finds relationships from repeated customer claims, shared contact details, identical document hashes, repeated beneficiaries and shared payment references across multiple claims.</p>
          </div>
        </div>
      ) : (
        <>
          {/* ── Summary ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiMini icon={Network} label="Total entities analysed" value={fmtNum(g.summary?.total_nodes)} />
            <KpiMini icon={Plus} label="Total relationships identified" value={fmtNum(g.summary?.total_edges)} />
            <KpiMini icon={ShieldCheck} label="Suspicious relationships for review" value={fmtNum(suspiciousCount)} accent="#EF4444" />
            <KpiMini icon={FileWarning} label="Connected claim clusters" value={fmtNum(g.summary?.clusters)} />
          </div>

          {/* ── Live Graph ── */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-[#0F2744] text-white flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold">
                <Network size={16} className="text-amber-400" />
                <span>Fraud Relationship Network (live graph)</span>
              </div>
              <span className="text-xs text-white/60 font-bold uppercase tracking-wide">
                {fmtNum(g.summary?.total_nodes)} entities · {fmtNum(g.summary?.total_edges)} relationships · {fmtNum(g.summary?.clusters)} clusters
              </span>
            </div>
            <div className="relative bg-slate-950">
              <svg viewBox="0 0 760 480" className="w-full h-[480px]" role="img" aria-label="Fraud relationship network graph">
                {/* Edges */}
                {(g.edges || []).map((e, i) => {
                  const a = positions.get(e.node_a_id), b = positions.get(e.node_b_id);
                  if (!a || !b) return null;
                  const isS = e.is_suspicious;
                  return (
                    <g key={e.id || `edge-${i}`}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                        stroke={isS ? EDGE_SUSPICIOUS_MID : EDGE_STRONG}
                        strokeWidth={Math.max((e.strength || 0.3) * 3, 0.8)}
                        strokeOpacity={isS ? 0.85 : 0.35}
                        strokeDasharray={isS ? '5 3' : undefined}
                        className={isS ? 'animate-pulse' : ''}
                        cursor="default" />
                      {isS && (
                        <circle cx={(a.x + b.x) / 2} cy={(a.y + b.y) / 2} r="4.5" fill="#F87171" stroke="#1E3A8A" strokeWidth="2" />
                      )}
                    </g>
                  );
                })}
                {/* Nodes */}
                {(g.nodes || []).map(n => {
                  const p = positions.get(n.id);
                  if (!p) return null;
                  const color = TYPE_COLORS[n.entity_type] || TYPE_COLORS.default;
                  const label = nodeLabel(n);
                  return (
                    <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
                      {n.is_suspicious && <circle r="22" fill="none" stroke="#F87171" strokeWidth="2" className="animate-ping opacity-45" />}
                      <circle r="12" fill={color} stroke={n.is_suspicious ? '#F87171' : '#0F2744'} strokeWidth={n.is_suspicious ? 3 : 1.5} />
                      <text textAnchor="middle" y="-15" fill="#CBD5E1" fontSize="8" fontWeight="bold">{label}</text>
                      <text textAnchor="middle" y="18" fill="white" fontSize="7" fontWeight="bold" fontFamily="monospace">
                        {n.entity_type === 'claim' ? (n.amount ? `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n.amount)}` : '') : ''}
                      </text>
                    </g>
                  );
                })}
                {/* Legend */}
                <g transform="translate(14, 14)">
                  {Object.entries(TYPE_COLORS).filter(([k]) => k !== 'default').map(([k, color], i) => (
                    <g key={k} transform={`translate(0, ${i * 16})`}>
                      <circle cx="5" cy="5" r="5" fill={color} />
                      <text x="16" y="9" fontSize="9" fontWeight="bold" fill="#CBD5E1">{TYPE_LABELS[k] || k}</text>
                    </g>
                  ))}
                </g>
              </svg>
            </div>

            {/* Legend note */}
            <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 text-xs text-slate-500 font-medium space-y-1">
              <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-slate-500 inline-block"></span><span>Relationship strength (weak → strong)</span></div>
              <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-red-400 dashed inline-block"></span><span>Suspicious relationship (pulsing, midpoint marker)</span></div>
              <div className="flex items-center gap-2"><span className="w-4 h-4 rounded-full border-2 border-red-400 animate-ping opacity-40 inline-block"></span><span>Suspicious node (red ring, pulsing)</span></div>
            </div>
          </div>

          {/* ── Review lists ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Suspicious nodes */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h4 className="text-sm font-extrabold uppercase tracking-wider text-red-600 mb-3 flex items-center gap-2"><ShieldCheck size={15} /><span>Suspicious Nodes ({g.suspicious_nodes?.length || 0})</span></h4>
              <div className="space-y-2">
                {(g.suspicious_nodes || []).slice(0, 8).map((n, i) => (
                  <div key={n.id} className="text-sm bg-red-50/50 border border-red-100 rounded-xl p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{nodeLabel(n)}</span>
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-black uppercase bg-red-600 text-white">{n.risk_score >= 80 ? 'CRITICAL' : 'HIGH'}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{TYPE_LABELS[n.entity_type]}{n.claim_id ? ` — Claim ${n.claim_id}` : ''}</p>
                  </div>
                ))}
                {(!g.suspicious_nodes || g.suspicious_nodes.length === 0) && <p className="text-sm text-slate-400">None.</p>}
              </div>
            </div>

            {/* Suspicious relationships */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h4 className="text-sm font-extrabold uppercase tracking-wider text-red-600 mb-3 flex items-center gap-2"><Users size={15} /><span>Suspicious Relationships ({g.suspicious_edges?.length || 0})</span></h4>
              <div className="space-y-2">
                {(g.suspicious_edges || []).slice(0, 8).map((e, i) => (
                  <div key={i} className="text-sm bg-red-50/50 border border-red-100 rounded-xl p-3">
                    <p className="font-semibold">{(e.relationship_type || 'relationship').replace(/_/g, ' ')}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Strength {e.strength?.toFixed?.(2)}</p>
                    <p className="text-xs text-slate-500 mt-0.5 line-through">{e.evidence}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Claims: {(e.claim_ids || []).join(', ')}</p>
                  </div>
                ))}
                {(!g.suspicious_edges || g.suspicious_edges.length === 0) && <p className="text-sm text-slate-400">None.</p>}
              </div>
            </div>

            {/* Clusters */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h4 className="text-sm font-extrabold uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-2"><FileWarning size={15} /><span>Clusters (Review Candidates, {g.clusters?.length || 0})</span></h4>
              <div className="space-y-2">
                {(g.clusters || []).slice(0, 5).map((c, i) => (
                  <div key={c.cluster_id || i} className="text-sm bg-amber-50/50 border border-amber-100 rounded-xl p-3">
                    <p className="font-semibold">{(c.claim_ids || []).length} claims · {c.member_count} entities</p>
                    {(c.relationship_evidence || []).slice(0, 2).map((ev, j) => (
                      <p key={j} className="text-xs text-red-600 font-semibold mt-0.5">{ev}</p>
                    ))}
                  </div>
                ))}
                {(!g.clusters || g.clusters.length === 0) && <p className="text-sm text-slate-400">No suspicious clusters detected.</p>}
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 bg-amber-50 border border-amber-200 rounded-xl p-4">
            Honesty note: connected entities may have legitimate explanations. NEXA flags possible relationships for human review; no individual is labeled confirmed fraud automatically.
          </div>
        </>
      )}
    </div>
  );
}
