import React from 'react';
import {
  ShieldCheck, LogOut,
  LayoutDashboard, FileText, Plus, Upload,
  ScanText, Brain, AlertTriangle, FileCheck,
  Users, Settings, Activity, BarChart3,
  ClipboardCheck, Scale, Search, Eye,
  Briefcase, TrendingUp, Shield, Server,
  Database, Cpu, List, ChevronRight, Bell, User
} from 'lucide-react';

/* ══════════════════════════════════════════════════════════════════════════
   FIDE AI FRAUD DETECTION — FIDELITY LIFE ASSURANCE ZIMBABWE
   Corporate dashboard layout. WHITE surfaces + Fidelity red (#C8102E),
   black headings, subtle #EEEEEE borders. Role-based navigation and
   permissions are preserved exactly; only the presentation is restyled.
   ══════════════════════════════════════════════════════════════════════════ */

const FIDELITY_RED = '#C8102E';

// Role-based navigation configuration (unchanged items & permissions;
// `color` retained for API compatibility, now uniformly corporate).
const NAV_CONFIG = {
  claims_officer: {
    label: 'Claims Officer',
    color: '',
    accent: FIDELITY_RED,
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
    color: '',
    accent: FIDELITY_RED,
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
    color: '',
    accent: FIDELITY_RED,
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
    color: '',
    accent: FIDELITY_RED,
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
    color: '',
    accent: FIDELITY_RED,
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
    color: '',
    accent: FIDELITY_RED,
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
    <div className="min-h-screen bg-white flex flex-col font-sans text-[#222222]">
      {/* Top corporate navigation — white, Fidelity branding left, red accents */}
      <header className="bg-white text-[#222222] border-b border-[#EEEEEE] sticky top-0 z-50 shadow-sm">
        <div className="px-4 sm:px-6 h-16 flex items-center justify-between gap-3 flex-wrap min-w-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-md bg-[#C8102E] flex items-center justify-center shadow-sm shrink-0">
              <ShieldCheck size={22} className="text-white" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-extrabold tracking-wide text-sm text-[#222222]">FIDELITY LIFE</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-[#FCEBED] border border-[#EEEEEE] text-[#8B0000] font-black tracking-widest uppercase">ASSURANCE</span>
              </div>
              <p className="text-[10px] text-[#222222] font-semibold tracking-wide hidden sm:block">NEXA AI Fraud Detection Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full bg-[#FCEBED] border border-[#EEEEEE] text-[#8B0000]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#C8102E]" aria-hidden="true" />
              <span>AI: <strong>v1.2-hybrid</strong></span>
            </div>

            <div className="flex items-center gap-2 pl-3 border-l border-[#EEEEEE]">
              <div className="w-8 h-8 rounded-md bg-[#FCEBED] border border-[#EEEEEE] flex items-center justify-center font-bold text-xs text-[#8B0000]">
                {(user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase()}
              </div>
              <div className="hidden lg:block text-left">
                <p className="text-xs font-bold text-[#222222] leading-tight">{user?.full_name || user?.username}</p>
                <p className="text-[10px] text-[#C8102E] font-semibold">{roleLabels[user?.role] || user?.role}</p>
              </div>
            </div>

            <button
              onClick={onLogout}
              className="p-2 text-[#C8102E] hover:bg-[#FCEBED] rounded-md transition"
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — white corporate, black text, red icons, light-red active */}
        <aside className="w-56 bg-white border-r border-[#EEEEEE] flex flex-col flex-shrink-0 overflow-y-auto min-w-0">
          <div className="px-4 py-4 border-b border-[#EEEEEE]">
            <span className="text-[10px] text-[#222222] uppercase font-black tracking-widest">Department</span>
            <p className="text-xs font-bold text-[#222222] mt-0.5">{navConfig.label}</p>
          </div>

          <nav className="flex-1 py-3 px-2 space-y-0.5">
            {navConfig.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`relative w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition text-xs font-semibold ${
                    isActive ? 'bg-[#FCEBED] text-[#222222]' : 'text-[#222222] hover:bg-[#FCEBED] hover:text-[#C8102E]'
                  }`}
                >
                  {isActive && <span aria-hidden="true" className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-full bg-[#C8102E]" />}
                  <Icon size={15} className="text-[#C8102E] shrink-0" />
                  <span className="truncate">{item.label}</span>
                  {isActive && <ChevronRight size={12} className="ml-auto text-[#C8102E]" />}
                </button>
              );
            })}
          </nav>

          <div className="px-4 py-3 border-t border-[#EEEEEE]">
            <p className="text-[10px] text-[#222222] font-semibold">
              © 2026 Fidelity Life Assurance Zimbabwe<br />FIDE AI Fraud Detection
            </p>
          </div>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto bg-white p-5 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export { getDashboardType, NAV_CONFIG };
