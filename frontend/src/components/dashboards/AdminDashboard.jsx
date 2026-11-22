/**
 * AdminDashboard.jsx
 * NEXA AI Fraud Detection Platform — System Administration workspace.
 * Tabs: administration-overview | user-management | roles-permissions | system-monitoring | ai-model-monitoring | ocr-monitoring | audit-logs | system-configuration
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, LockKeyhole, Activity, AlertTriangle, Eye, RefreshCw, ShieldCheck,
  Loader2, CheckCircle, Plug, Settings, Keyboard, FileText, Database, Building2,
} from 'lucide-react';
import { api } from '../../api/apiClient';

function Card({ icon: Icon, title, value, colorCls, sub }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 border-t-4 ${colorCls}`}>
      <div className="flex justify-between items-center mb-1">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
      <p className="text-2xl font-extrabold text-slate-900 mt-1">{value}</p>
      {sub && <p className="text-[11px] text-slate-500 font-semibold mt-1">{sub}</p>}
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listUsers();
      if (res.ok) setUsers(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = users.filter(u =>
    !q || [u.username, u.full_name, u.email, u.role, u.department].some(v => String(v || '').toLowerCase().includes(q.toLowerCase()))
  );

  const statusBadge = (active) => (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}`}>
      {active ? 'Active' : 'Inactive'}
    </span>
  );
  const roleBadge = (role) => (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">{role}</span>
  );

  return (
    <div className="space-y-4">
      <input
        placeholder="Search users by name, username or role..."
        className="text-xs border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 w-full max-w-md"
        value={q}
        onChange={e => setQ(e.target.value)}
      />
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
              <tr><th className="py-3.5 px-4">ID</th><th className="py-3.5 px-4">Name</th><th className="py-3.5 px-4">Email</th><th className="py-3.5 px-4">Role</th><th className="py-3.5 px-4">Department</th><th className="py-3.5 px-4">Status</th><th className="py-3.5 px-4">Joined</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading && !filtered.length && <tr><td colSpan="7" className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin text-blue-500 mx-auto" /></td></tr>}
              {!loading && filtered.length === 0 && <tr><td colSpan="7" className="py-8 text-center text-slate-400">No users found</td></tr>}
              {filtered.map(u => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 font-mono text-slate-500">#{u.id}</td>
                  <td className="py-3 px-4 font-semibold text-slate-800">{u.full_name || '—'}</td>
                  <td className="py-3 px-4 font-mono text-slate-600">{u.email}</td>
                  <td className="py-3 px-4">{roleBadge(u.role)}</td>
                  <td className="py-3 px-4 text-slate-600">{u.department || '—'}</td>
                  <td className="py-3 px-4">{statusBadge(u.is_active)}</td>
                  <td className="py-3 px-4 font-mono text-slate-500">{u.created_at ? new Date(u.created_at).toLocaleDateString('en-ZA') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function RolesPermissionsTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [permsByRole, setPermsByRole] = useState({});
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listUsers();
      if (res.ok) {
        const users = await res.json();
        setUsers(users);
        const byRole = {};
        users.forEach(u => {
          if (!byRole[u.role]) byRole[u.role] = [];
          byRole[u.role].push(u);
        });
        setPermsByRole(byRole);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Role Matrix & Departmental Access</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {Object.entries(permsByRole).map(([role, users]) => (
          <div key={role} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden border-t-4 border-t-blue-600">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50"><span className="text-xs font-extrabold text-slate-700 uppercase">{role}</span></div>
            <ul className="p-3 space-y-1">
              {users.slice(0, 8).map(u => (
                <li key={u.id} className="text-xs text-slate-600 flex items-center gap-2"><Users size={11} className="text-slate-400" />{u.username}</li>
              ))}
              {users.length > 8 && <li className="text-xs text-slate-400">+{users.length - 8} more</li>}
            </ul>
          </div>
        ))}
      </div>
      {Object.keys(permsByRole).length === 0 && !loading && <p className="text-slate-400 text-xs text-center py-6">No role data available.</p>}
    </div>
  );
}

function SystemMonitoringTab() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [failedJobs, setFailedJobs] = useState([]);
  const [securityAlerts, setSecurityAlerts] = useState([]);
  const load = useCallback(async () => {
    try {
      const res = await api.adminDashboard();
      if (res.ok) {
        const d = await res.json();
        setSystemHealth(d.system_health);
        setFailedJobs(d.failed_processing_jobs || []);
        setSecurityAlerts(d.security_alerts || []);
      }
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      {systemHealth && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card icon={Database} title="API Status" value={systemHealth.api_status} colorCls="border-t-emerald-600" />
          <Card icon={Database} title="Database Status" value={systemHealth.database_status} colorCls="border-t-blue-600" />
          <Card icon={Activity} title="AI Model Status" value={systemHealth.ai_model_status} colorCls="border-t-purple-600" />
          <Card icon={Plug} title="OCR Service Status" value={systemHealth.ocr_service_status} colorCls="border-t-cyan-600" />
          <Card icon={Activity} title="Total Claims" value={systemHealth.total_claims?.toLocaleString() ?? '—'} colorCls="border-t-blue-600" />
          <Card icon={Activity} title="Total Assessments" value={systemHealth.total_assessments?.toLocaleString() ?? '—'} colorCls="border-t-blue-600" />
          <Card icon={Activity} title="AI Coverage Rate" value={`${systemHealth.ai_coverage_rate}%`} colorCls="border-t-purple-600" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-200"><h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2"><AlertTriangle size={14} className="text-red-600" /><span>Security Alerts &mdash; Recent Failed Logins</span></h3></div>
          {securityAlerts.length === 0 ? (
            <div className="p-8 text-center"><CheckCircle className="w-8 h-8 text-emerald-400 mx-auto" /><p className="text-sm font-bold text-slate-500 mt-2">No recent security alerts</p></div>
          ) : (
            <div className="divide-y divide-slate-100">
              {securityAlerts.map(s => (
                <div key={s.id} className="px-5 py-3 flex items-center gap-3 hover:bg-red-50/40">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700">FAILED LOGIN</span>
                  <span className="text-xs font-semibold text-slate-700">{s.user}</span>
                  <span className="text-[10px] font-mono text-slate-400">{s.timestamp ? new Date(s.timestamp).toLocaleString('en-ZA') : '—'}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-200"><h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2"><FileText size={14} className="text-red-600" /><span>Failed Processing Jobs</span></h3></div>
          {failedJobs.length === 0 ? (
            <div className="p-8 text-center"><CheckCircle className="w-8 h-8 text-emerald-400 mx-auto" /><p className="text-sm font-bold text-slate-500 mt-2">No failed jobs</p></div>
          ) : (
            <div className="divide-y divide-slate-100">
              {failedJobs.map(j => (
                <div key={j.document_id} className="px-5 py-3">
                  <div className="flex justify-between items-center">
                    <span className="font-mono font-bold text-slate-900">#{j.document_id} — {j.filename}</span>
                    <span className="text-[10px] font-bold bg-red-100 text-red-700 px-2 py-0.5 rounded-full uppercase">FAILED</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Uploaded by {j.uploaded_by} · Claim: {j.claim_id || '—'}</div>
                  {j.flags?.map((f, i) => <div key={i} className="text-[10px] text-slate-500 mt-0.5 font-mono">{f}</div>)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OcrMonitoringTab() {
  const [overview, setOverview] = useState(null);
  const load = useCallback(async () => {
    try {
      const res = await api.ocrOverview();
      if (res.ok) setOverview(await res.json());
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const o = overview || {};
  const pct = o.documents_completed ? Math.round((o.documents_completed / Math.max(o.total_documents, 1)) * 100) : 0;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      <Card icon={Plug} title="Total Documents" value={o.total_documents ?? 0} colorCls="border-t-blue-600" />
      <Card icon={CheckCircle} title="Processed" value={o.documents_completed ?? 0} colorCls="border-t-emerald-600" />
      <Card icon={Loader2} title="Pending" value={o.documents_pending ?? 0} colorCls="border-t-amber-600" />
      <Card icon={AlertTriangle} title="Failed Jobs" value={o.documents_failed ?? 0} colorCls="border-t-red-600" />
      <Card icon={FileText} title="Success Rate" value={`${o.documents_completed ? pct : 0}%`} colorCls="border-t-purple-600" />
      <Card icon={Activity} title="Avg Confidence" value={`${o.average_extraction_confidence ?? 0}%`} colorCls="border-t-blue-600" />
    </div>
  );
}

function AITab() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      <Card icon={ShieldCheck} title="AI Engine" value={(['v1.2-ensemble-hybrid']).join(' &bull; ')} colorCls="border-t-purple-600" sub="Fraud Detection Ensemble" />
      <Card icon={Activity} title="Model Status" value="Active" colorCls="border-t-emerald-600" sub="v1.2-ensemble-hybrid" />
      <Card icon={Activity} title="Monitoring Status" value="Available" colorCls="border-t-blue-600" />
      <Card icon={Activity} title="Time to Classify" value="~32 ms" colorCls="border-t-cyan-600" />
    </div>
  );
}

function ConfigTab() {
  const [orgName] = useState('FIDELITY LIFE ASSURANCE');
  const [sysName] = useState('NEXA AI Fraud Detection System');
  const [healthNote] = useState('');
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200"><h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Platform Configuration</h3></div>
        <table className="w-full text-left text-xs">
          <tbody className="divide-y divide-slate-100">
            {[
              ['Organization', orgName, 'Fidelity Life Assurance Company'],
              ['System', sysName, 'NEXA AI Fraud Claims Detection Platform'],
              ['API Endpoint', '/api/v1', 'FastAPI backend'],
              ['Database', 'PostgreSQL with SQLite dev fallback', 'Model migration supported'],
              ['Frontend', 'React + Vite (ESM)', 'Tailwind CSS, Lucide icons'],
              ['Auth', 'JWT (PyJWT, HS256)', 'PBKDF2-HMAC-SHA256 password hashing'],
              ['JWT Expiry', '480 minutes', 'Configurable via JWT_SECRET_KEY'],
            ].map(([k, v, note]) => (
              <tr key={k}><td className="py-3 px-4 font-semibold text-slate-700 w-1/4">{k}</td><td className="py-3 px-4 font-mono font-bold text-slate-900">{v}</td><td className="py-3 px-4 text-slate-500">{note}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AdminDashboard({ activeTab }) {
  // Map parent App activeTab ids onto the internal view ids so each sidebar
  // item (User Management, Roles & Permissions, System Monitoring, OCR
  // Monitoring, System Configuration, …) shows its own section instead of
  // the default Administration Overview.
  const toInternalTab = (tab) => (tab === 'admin-overview' ? 'administration-overview' : tab) || 'administration-overview';
  const [tab, setTab] = useState(toInternalTab(activeTab));
  useEffect(() => { setTab(toInternalTab(activeTab)); }, [activeTab]);
  const NAV = [
    { id: 'administration-overview', label: 'Administration Overview' },
    { id: 'user-management', label: 'User Management' },
    { id: 'roles-permissions', label: 'Roles & Permissions' },
    { id: 'system-monitoring', label: 'System Monitoring' },
    { id: 'ai-model-monitoring', label: 'AI Model Monitoring' },
    { id: 'ocr-monitoring', label: 'OCR Monitoring' },
    { id: 'audit-logs', label: 'Audit Logs' },
    { id: 'system-configuration', label: 'System Configuration' },
  ];

  const AuditLogTab = () => {
    const [logs, setLogs] = useState([]);
    const [q, setQ] = useState('');
    useEffect(() => {
      (async () => {
        const res = await api.auditLogs({ limit: 50 });
        if (res.ok) setLogs(await res.json());
      })();
    }, []);
    const filtered = logs.filter(l => !q || [l.action, l.user, l.target].some(v => String(v || '').toLowerCase().includes(q.toLowerCase())));
    return (
      <div>
        <input placeholder="Search audit events..." className="text-xs border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 w-full max-w-md mb-4" value={q} onChange={e => setQ(e.target.value)} />
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200"><tr><th className="py-3 px-4">Time</th><th className="py-3 px-4">User</th><th className="py-3 px-4">Role</th><th className="py-3 px-4">Action</th><th className="py-3 px-4">Target</th></tr></thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {filtered.map(l => (
                  <tr key={l.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono text-slate-500">{l.timestamp ? new Date(l.timestamp).toLocaleString('en-ZA') : '—'}</td>
                    <td className="py-3 px-4">{l.user}</td>
                    <td className="py-3 px-4 text-slate-600">{l.user_role}</td>
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">{l.action}</td>
                    <td className="py-3 px-4 font-mono text-slate-600">{l.target}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">System Administration Workspace</h1>
          <p className="text-xs text-slate-500 mt-0.5">Platform health, user management, permissions, audit trails & configuration</p>
        </div>
        <div className="flex gap-2">
          {NAV.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 text-xs font-bold rounded-xl transition-colors ${tab === t.id ? 'bg-[#0F2744] text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>{t.label}</button>
          ))}
        </div>
      </div>
      {tab === 'administration-overview' && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
            <Card icon={Users} title="Total Users" value="—" colorCls="border-t-blue-600" />
            <Card icon={Activity} title="API Status" value="Operational" colorCls="border-t-emerald-600" />
            <Card icon={ShieldCheck} title="AI Model Status" value="Active" colorCls="border-t-purple-600" />
            <Card icon={Plug} title="OCR Status" value="Active (Tesseract)" colorCls="border-t-cyan-600" />
            <Card icon={AlertTriangle} title="Security Alerts" value="0" colorCls="border-t-red-600" />
          </div>
        </div>
      )}
      {tab === 'user-management' && <UsersTab />}
      {tab === 'roles-permissions' && <RolesPermissionsTab />}
      {tab === 'system-monitoring' && <SystemMonitoringTab />}
      {tab === 'ai-model-monitoring' && <AITab />}
      {tab === 'ocr-monitoring' && <OcrMonitoringTab />}
      {tab === 'audit-logs' && <AuditLogTab />}
      {tab === 'system-configuration' && <ConfigTab />}
    </div>
  );
}
