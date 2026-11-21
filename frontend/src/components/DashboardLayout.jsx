import React from 'react';
import {
  ShieldCheck, LogOut, Bell, User,
  LayoutDashboard, FileText, Plus, Upload,
  ScanText, Brain, AlertTriangle, FileCheck,
  Users, Settings, Activity, BarChart3,
  ClipboardCheck, Scale, Search, Eye,
  Briefcase, TrendingUp, Shield, Server,
  Database, Cpu, List, ChevronRight
} from 'lucide-react';

// Role-based navigation configuration
const NAV_CONFIG = {
  claims_officer: {
    label: 'Claims Officer',
    color: 'from-blue-700 to-blue-900',
    accent: '#3B82F6',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'my-claims', label: 'My Claims', icon: FileText },
      { id: 'new-claim', label: 'New Claim', icon: Plus },
      { id: 'fnol', label: 'FNOL Intake', icon: FileCheck },
      { id: 'ocr-upload', label: 'Document Upload', icon: Upload },
      { id: 'ocr-results', label: 'OCR Results', icon: ScanText },
      { id: 'ocr-samples', label: 'Genuine Claim Forms', icon: FileCheck },
      { id: 'ai-assessment', label: 'AI Risk Assessment', icon: Brain },
      { id: 'notifications', label: 'Notifications', icon: Bell },
      { id: 'profile', label: 'My Profile', icon: User },
    ],
  },
  claims_manager: {
    label: 'Claims Manager',
    color: 'from-indigo-700 to-indigo-900',
    accent: '#6366F1',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'my-claims', label: 'Claims Register', icon: FileText },
      { id: 'new-claim', label: 'New Claim', icon: Plus },
      { id: 'fnol', label: 'FNOL Intake', icon: FileCheck },
      { id: 'ocr-upload', label: 'Document Upload', icon: Upload },
      { id: 'ocr-results', label: 'OCR Results', icon: ScanText },
      { id: 'ocr-samples', label: 'Genuine Claim Forms', icon: FileCheck },
      { id: 'ai-assessment', label: 'AI Risk Assessment', icon: Brain },
      { id: 'investigations', label: 'Investigations', icon: Search },
      { id: 'profile', label: 'My Profile', icon: User },
    ],
  },
  executive: {
    label: 'Executive',
    color: 'from-slate-800 to-slate-950',
    accent: '#F59E0B',
    items: [
      { id: 'dashboard', label: 'Executive Overview', icon: LayoutDashboard },
      { id: 'claims-performance', label: 'Claims Performance', icon: BarChart3 },
      { id: 'fraud-analytics', label: 'Fraud Analytics', icon: TrendingUp },
      { id: 'network', label: 'Fraud Network', icon: Activity },
      { id: 'financial-exposure', label: 'Financial Exposure', icon: Briefcase },
      { id: 'governance', label: 'AI Model Governance', icon: Cpu },
      { id: 'reports', label: 'Management Reports', icon: FileText },
      { id: 'profile', label: 'My Profile', icon: User },
    ],
  },
  compliance: {
    label: 'Compliance Officer',
    color: 'from-purple-800 to-purple-950',
    accent: '#8B5CF6',
    items: [
      { id: 'dashboard', label: 'Compliance Overview', icon: LayoutDashboard },
      { id: 'alerts', label: 'Compliance Alerts', icon: AlertTriangle },
      { id: 'claims-review', label: 'Claims Under Review', icon: Eye },
      { id: 'ocr-forensics', label: 'Document Forensics', icon: AlertTriangle },
      { id: 'investigations', label: 'Investigations', icon: Search },
      { id: 'audit', label: 'Audit Trails', icon: ClipboardCheck },
      { id: 'reports', label: 'Regulatory Reports', icon: Scale },
      { id: 'profile', label: 'My Profile', icon: User },
    ],
  },
  fraud_investigator: {
    label: 'Fraud Investigator',
    color: 'from-red-800 to-red-950',
    accent: '#EF4444',
    items: [
      { id: 'dashboard', label: 'Investigation Overview', icon: LayoutDashboard },
      { id: 'fraud-alerts', label: 'Fraud Alerts', icon: AlertTriangle },
      { id: 'assigned-cases', label: 'Assigned Cases', icon: Briefcase },
      { id: 'forensics', label: 'AI Forensic Analysis', icon: Brain },
      { id: 'ocr-evidence', label: 'OCR Evidence', icon: ScanText },
      { id: 'ocr-samples', label: 'Genuine Claim Forms', icon: FileCheck },
      { id: 'ocr-forensics', label: 'Document Forensics', icon: AlertTriangle },
      { id: 'investigation-reports', label: 'Investigation Reports', icon: FileText },
      { id: 'profile', label: 'My Profile', icon: User },
    ],
  },
  admin: {
    label: 'System Administrator',
    color: 'from-emerald-800 to-emerald-950',
    accent: '#10B981',
    items: [
      { id: 'dashboard', label: 'Admin Overview', icon: LayoutDashboard },
      { id: 'users', label: 'User Management', icon: Users },
      { id: 'roles', label: 'Roles & Permissions', icon: Shield },
      { id: 'system-health', label: 'System Monitoring', icon: Server },
      { id: 'ai-monitoring', label: 'AI Model Monitor', icon: Cpu },
      { id: 'ocr-monitoring', label: 'OCR Monitoring', icon: Database },
      { id: 'audit', label: 'Audit Logs', icon: List },
      { id: 'config', label: 'System Configuration', icon: Settings },
    ],
  },
};

function getDashboardType(role) {
  if (role === 'management') return 'executive';
  if (role === 'claims_manager') return 'claims_manager';
  if (role === 'claims_officer') return 'claims_officer';
  if (role === 'compliance_officer') return 'compliance';
  if (role === 'fraud_investigator') return 'fraud_investigator';
  if (role === 'system_admin') return 'admin';
  return 'claims_officer';
}

export default function DashboardLayout({ user, activeTab, setActiveTab, onLogout, children }) {
  const dashType = getDashboardType(user?.role);
  const navConfig = NAV_CONFIG[dashType] || NAV_CONFIG.claims_officer;

  const roleLabels = {
    system_admin: 'System Administrator',
    claims_officer: 'Claims Officer',
    claims_manager: 'Claims Manager',
    fraud_investigator: 'Fraud Investigator',
    compliance_officer: 'Compliance Officer',
    management: 'Executive / CRO',
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-[#0A192F] text-white border-b border-slate-700/80 sticky top-0 z-50 shadow-lg">
        <div className="px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-md">
              <ShieldCheck size={22} className="text-slate-950" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold tracking-wider text-sm text-white">FIDELITY LIFE</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500 text-slate-950 font-black tracking-widest uppercase">ASSURANCE</span>
              </div>
              <p className="text-[10px] text-slate-400 font-semibold tracking-wide hidden sm:block">NEXA AI Fraud Detection Platform</p>
            </div>
          </div>

          {/* Right side: AI status + user */}
          <div className="flex items-center space-x-3">
            <div className="hidden md:flex items-center space-x-1.5 text-[11px] bg-slate-800/80 px-2.5 py-1 rounded-full border border-slate-700 text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>AI: <strong className="text-amber-300">v1.2-hybrid</strong></span>
            </div>

            <div className="flex items-center space-x-2 pl-3 border-l border-slate-700">
              <div className="w-8 h-8 rounded-lg bg-slate-800 border-2 border-amber-500 flex items-center justify-center font-bold text-xs text-amber-400">
                {(user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase()}
              </div>
              <div className="hidden lg:block text-left">
                <p className="text-xs font-bold text-white leading-tight">{user?.full_name || user?.username}</p>
                <p className="text-[10px] text-amber-400 font-semibold">{roleLabels[user?.role] || user?.role}</p>
              </div>
            </div>

            <button
              onClick={onLogout}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`w-56 bg-gradient-to-b ${navConfig.color} flex flex-col flex-shrink-0 overflow-y-auto`}>
          {/* Department label */}
          <div className="px-4 py-4 border-b border-white/10">
            <span className="text-[10px] text-white/50 uppercase font-black tracking-widest">Department</span>
            <p className="text-xs font-bold text-white mt-0.5">{navConfig.label}</p>
          </div>

          {/* Nav items */}
          <nav className="flex-1 py-3 px-2 space-y-0.5">
            {navConfig.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center space-x-2.5 px-3 py-2.5 rounded-lg text-left transition text-xs font-semibold ${
                    isActive
                      ? 'bg-white/20 text-white shadow-sm'
                      : 'text-white/60 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <Icon size={15} className={isActive ? 'text-white' : 'text-white/50'} />
                  <span>{item.label}</span>
                  {isActive && <ChevronRight size={12} className="ml-auto text-white/70" />}
                </button>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-white/10">
            <p className="text-[10px] text-white/40 font-semibold">
              © 2026 Fidelity Life<br />NEXA AI Suite v2.0
            </p>
          </div>
        </aside>

        {/* Main content area */}
        <main className="flex-1 overflow-y-auto bg-slate-50 p-5 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export { getDashboardType, NAV_CONFIG };
