import React, { useState, useEffect } from 'react';
import {
  ShieldCheck, Eye, EyeOff, LockKeyhole,
  Activity, LogOut, AlertCircle, FileText, Search,
  Filter, Plus, RotateCw, Sliders, Users,
  ClipboardCheck, AlertTriangle, ArrowRight,
  CheckCircle, CheckCircle2, X, Clock, TrendingUp,
  Brain, FileCheck, Share2, Layers, Check, MessageSquare, ClipboardList, Upload, Loader2,
  GanttChart, History, Bell, Globe, HeartPulse, ShieldAlert, FileSearch, Database, Link2
} from 'lucide-react';
import { apiCall, api } from './api/apiClient.js';
import Sidebar from './components/shared/Sidebar.jsx';
import {
  PendingClaimsPanel, MissingInformationPanel, HighRiskClaimsPanel, EscalatedClaimsPanel,
  AIRiskAnalysisPanel, ClaimAllocationPanel, DepartmentReportsPanel, PerformanceAnalyticsPanel,
  DocumentComparisonPanel, DocumentationCompliancePanel, PolicyVerificationPanel,
  RegulatoryMonitoringPanel, FraudTrendsPanel, RiskDashboardPanel, EnterpriseRiskOverviewPanel,
  FraudRiskExposurePanel, EmergingRiskPatternsPanel, RiskConcentrationPanel, RiskReportsPanel,
  DepartmentManagementPanel, DatabaseMonitoringPanel, APIMonitoringPanel, SystemHealthPanel,
  AIAssistantPanel,
} from './components/panels/DepartmentExtras.jsx';
import ExecutiveDashboard from './components/dashboards/ExecutiveDashboard.jsx';
import ComplianceDashboard from './components/dashboards/ComplianceDashboard.jsx';
import FraudInvestigationDashboard from './components/dashboards/FraudInvestigationDashboard.jsx';
import AdminDashboard from './components/dashboards/AdminDashboard.jsx';
import OCRDocumentPage from './components/pages/OCRDocumentPage.jsx';
import NexaAssistant from './components/shared/NexaAssistant.jsx';
import FraudNetworkGraph from './components/dashboards/FraudNetworkGraph.jsx';
import ClaimTimeline from './components/dashboards/ClaimTimeline.jsx';
import EvidenceManagement from './components/dashboards/EvidenceManagement.jsx';
import HistoricalBehaviorPanel from './components/dashboards/HistoricalBehaviorPanel.jsx';
import PredictiveAlerts from './components/dashboards/PredictiveAlerts.jsx';
import ModelPerformanceDashboard from './components/dashboards/ModelPerformanceDashboard.jsx';
import ZimIntelligencePanel from './components/dashboards/ZimIntelligencePanel.jsx';

// ─────────────────────────────────────────────
// DEPARTMENTAL NAVIGATION (Backend-enforced RBAC mirrors this)
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// DEPARTMENTAL NAVIGATION (Backend-enforced RBAC mirrors this)
// Per the NEXA master prompt: each role sees only its authorised functions.
// ─────────────────────────────────────────────
const ROLE_SIDEBAR = {
  // A. CLAIMS OFFICER — Dashboard, Register New Claim, All Assigned Claims,
  //    Pending Claims, Claim Documents, OCR Document Analysis, Missing
  //    Information, Claim History, Notifications, AI Assistant, My Profile.
  claims_officer: [
    { id: 'overview', label: 'Dashboard', icon: Activity, section: 'Claims Workflow' },
    { id: 'new-claim', label: 'Register New Claim', icon: Plus, section: 'Claims Workflow' },
    { id: 'claims', label: 'All Assigned Claims', icon: FileText, section: 'Claims Workflow' },
    { id: 'pending', label: 'Pending Claims', icon: Clock, section: 'Claims Workflow' },
    { id: 'documents', label: 'Claim Documents', icon: Layers, section: 'Claims Workflow' },
    { id: 'ocr-analysis', label: 'OCR Document Analysis', icon: FileCheck, section: 'Claims Workflow' },
    { id: 'missing', label: 'Missing Information', icon: AlertTriangle, section: 'Claims Workflow' },
    { id: 'historical', label: 'Claim History', icon: History, section: 'Claims Workflow' },
    { id: 'notifications', label: 'Notifications', icon: Activity, section: 'Assistant & Account' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // B. CLAIMS MANAGER — Dashboard, Claims Overview, Pending Approvals,
  //    Assigned Claims, Claim Allocation, High-Risk Claims, Escalated Claims,
  //    AI Risk Analysis, Department Reports, Performance Analytics,
  //    Notifications, AI Assistant, My Profile.
  claims_manager: [
    { id: 'overview', label: 'Dashboard', icon: Activity, section: 'Claims Workflow' },
    { id: 'claims', label: 'Claims Overview', icon: FileText, section: 'Claims Workflow' },
    { id: 'pending', label: 'Pending Approvals', icon: Clock, section: 'Claims Workflow' },
    { id: 'assigned-claims', label: 'Assigned Claims', icon: Users, section: 'Claims Workflow' },
    { id: 'allocation', label: 'Claim Allocation', icon: ShieldCheck, section: 'Claims Workflow' },
    { id: 'high-risk', label: 'High-Risk Claims', icon: AlertTriangle, section: 'Claims Workflow' },
    { id: 'escalated', label: 'Escalated Claims', icon: AlertCircle, section: 'Claims Workflow' },
    { id: 'ai-risk-analysis', label: 'AI Risk Analysis', icon: Brain, section: 'Claims Workflow' },
    { id: 'department-reports', label: 'Department Reports', icon: FileText, section: 'Claims Workflow' },
    { id: 'performance', label: 'Performance Analytics', icon: TrendingUp, section: 'Performance Analytics' },
    { id: 'notifications', label: 'Notifications', icon: Activity, section: 'Assistant & Account' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // C. FRAUD INVESTIGATOR — Dashboard, Investigation Cases, Suspicious Claims,
  //    AI Forensic Analysis, OCR Intelligence, Fraud Network Intelligence,
  //    Document Comparison, Historical Claim Analysis, Evidence Management,
  //    Claim Timeline, Investigation Reports, AI Assistant, My Profile.
  fraud_investigator: [
    { id: 'investigation-overview', label: 'Dashboard', icon: Activity, section: 'Investigations' },
    { id: 'assigned-cases', label: 'Investigation Cases', icon: ClipboardCheck, section: 'Investigations' },
    { id: 'fraud-alerts', label: 'Suspicious Claims', icon: AlertTriangle, section: 'Investigations' },
    { id: 'ai-forensic-analysis', label: 'AI Forensic Analysis', icon: Brain, section: 'Investigations' },
    { id: 'ocr-analysis', label: 'OCR Intelligence', icon: FileCheck, section: 'Investigations' },
    { id: 'fraud-network', label: 'Fraud Network Intelligence', icon: Share2, section: 'Investigations' },
    { id: 'document-comparison', label: 'Document Comparison', icon: FileSearch, section: 'Investigations' },
    { id: 'historical', label: 'Historical Claim Analysis', icon: History, section: 'Investigations' },
    { id: 'evidence-management', label: 'Evidence Management', icon: FileCheck, section: 'Investigations' },
    { id: 'timeline', label: 'Claim Timeline', icon: GanttChart, section: 'Investigations' },
    { id: 'investigation-reports', label: 'Investigation Reports', icon: FileText, section: 'Investigations' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // D. COMPLIANCE OFFICER — Dashboard, Documentation Compliance, Policy
  //    Verification, Compliance Alerts, Audit Trail, Regulatory Monitoring,
  //    Compliance Reports, AI Assistant, My Profile.
  compliance_officer: [
    { id: 'compliance-overview', label: 'Dashboard', icon: Activity, section: 'Compliance' },
    { id: 'documentation-compliance', label: 'Documentation Compliance', icon: ClipboardCheck, section: 'Compliance' },
    { id: 'policy-verification', label: 'Policy Verification', icon: LockKeyhole, section: 'Compliance' },
    { id: 'compliance-alerts', label: 'Compliance Alerts', icon: ShieldCheck, section: 'Compliance' },
    { id: 'audit', label: 'Audit Trail', icon: ClipboardCheck, section: 'Compliance' },
    { id: 'regulatory-monitoring', label: 'Regulatory Monitoring', icon: Globe, section: 'Compliance' },
    { id: 'regulatory-reports', label: 'Compliance Reports', icon: FileText, section: 'Compliance' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // E. EXECUTIVE MANAGEMENT — Dashboard, Claims Overview, Fraud Intelligence,
  //    Financial Exposure, Department Performance, Fraud Trends, Executive
  //    Reports, Notifications, AI Assistant, My Profile.
  management: [
    { id: 'executive-overview', label: 'Dashboard', icon: Activity, section: 'Executive' },
    { id: 'claims-performance', label: 'Claims Overview', icon: FileText, section: 'Executive' },
    { id: 'fraud-analytics', label: 'Fraud Intelligence', icon: AlertTriangle, section: 'Executive' },
    { id: 'financial-exposure', label: 'Financial Exposure', icon: ShieldCheck, section: 'Executive' },
    { id: 'department-performance', label: 'Department Performance', icon: Users, section: 'Executive' },
    { id: 'ai-fraud-intelligence', label: 'AI Fraud Intelligence', icon: Brain, section: 'Executive' },
    { id: 'fraud-trends', label: 'Fraud Trends', icon: TrendingUp, section: 'Executive' },
    { id: 'management-reports', label: 'Executive Reports', icon: FileText, section: 'Executive' },
    { id: 'notifications', label: 'Notifications', icon: Activity, section: 'Assistant & Account' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // F. CHIEF RISK OFFICER — Risk Dashboard, Enterprise Risk Overview, Fraud
  //    Risk Exposure, High-Risk Claims, Fraud Network Intelligence, Emerging
  //    Risk Patterns, Risk Concentration, AI Model Performance, Risk Reports,
  //    Notifications, AI Assistant, My Profile.
  chief_risk_officer: [
    { id: 'risk-dashboard', label: 'Risk Dashboard', icon: HeartPulse, section: 'Risk Intelligence' },
    { id: 'enterprise-risk-overview', label: 'Enterprise Risk Overview', icon: ShieldAlert, section: 'Risk Intelligence' },
    { id: 'fraud-risk-exposure', label: 'Fraud Risk Exposure', icon: AlertTriangle, section: 'Risk Intelligence' },
    { id: 'high-risk', label: 'High-Risk Claims', icon: AlertTriangle, section: 'Risk Intelligence' },
    { id: 'fraud-network', label: 'Fraud Network Intelligence', icon: Share2, section: 'Risk Intelligence' },
    { id: 'emerging-patterns', label: 'Emerging Risk Patterns', icon: Brain, section: 'Risk Intelligence' },
    { id: 'risk-concentration', label: 'Risk Concentration', icon: TrendingUp, section: 'Risk Intelligence' },
    { id: 'model-performance', label: 'AI Model Performance', icon: Brain, section: 'Risk Intelligence' },
    { id: 'risk-reports', label: 'Risk Reports', icon: FileText, section: 'Risk Intelligence' },
    { id: 'notifications', label: 'Notifications', icon: Activity, section: 'Assistant & Account' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: Brain, section: 'Assistant & Account' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
  // G. SYSTEM ADMINISTRATOR — Administration Dashboard, User Management,
  //    Role Management, Department Management, Claims Overview, AI Model
  //    Monitoring, OCR Monitoring, Fraud Network Intelligence, Zimbabwe
  //    Insurance Intelligence, Database Monitoring, API Monitoring, System
  //    Health, Audit Logs, System Settings, My Profile.
  system_admin: [
    { id: 'admin-overview', label: 'Dashboard', icon: Activity, section: 'Administration' },
    { id: 'user-management', label: 'User Management', icon: Users, section: 'Administration' },
    { id: 'roles-permissions', label: 'Role Management', icon: LockKeyhole, section: 'Administration' },
    { id: 'department-management', label: 'Department Management', icon: Users, section: 'Administration' },
    { id: 'claims', label: 'Claims Overview', icon: FileText, section: 'Administration' },
    { id: 'ai-model-monitoring', label: 'AI Model Monitoring', icon: Brain, section: 'Administration' },
    { id: 'ocr-monitoring', label: 'OCR Monitoring', icon: Layers, section: 'Administration' },
    { id: 'fraud-network', label: 'Fraud Network Intelligence', icon: Share2, section: 'Administration' },
    { id: 'zim', label: 'Zimbabwe Insurance Intelligence', icon: Globe, section: 'Administration' },
    { id: 'database-monitoring', label: 'Database Monitoring', icon: Database, section: 'Administration' },
    { id: 'api-monitoring', label: 'API Monitoring', icon: Link2, section: 'Administration' },
    { id: 'system-health', label: 'System Health', icon: HeartPulse, section: 'Administration' },
    { id: 'audit', label: 'Audit Logs', icon: ClipboardCheck, section: 'Administration' },
    { id: 'system-configuration', label: 'System Settings', icon: Sliders, section: 'Administration' },
    { id: 'profile', label: 'My Profile', icon: Users, section: 'Account' },
  ],
};

const getSidebar = (role) => ROLE_SIDEBAR[role] || ROLE_SIDEBAR.claims_officer;
const firstVisibleTab = (sidebar) => sidebar && sidebar.length > 0 ? sidebar[0].id : 'overview';

export default function App() {
  const [token, setToken] = useState(sessionStorage.getItem('fide_token'));
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState(localStorage.getItem('fide_saved_user') || 'claims.officer');
  const [password, setPassword] = useState('OfficerPass123!');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(localStorage.getItem('fide_remember') === 'true');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Forgot password state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotMsg, setForgotMsg] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);

  // Registration state
  const [regFullName, setRegFullName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [regRole, setRegRole] = useState('claims_officer');
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [regAgree, setRegAgree] = useState(true);


  // Dashboard Data State
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboardType, setDashboardType] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [riskDistribution, setRiskDistribution] = useState([]);
  const [recentSuspicious, setRecentSuspicious] = useState([]);
  const [claimsList, setClaimsList] = useState([]);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [investigationsList, setInvestigationsList] = useState([]);
  const [fnolList, setFnolList] = useState([]);
  const [networkData, setNetworkData] = useState(null);
  const [governanceData, setGovernanceData] = useState(null);
  const [customersList, setCustomersList] = useState([]);
  const [policiesList, setPoliciesList] = useState([]);
  const [auditLogsList, setAuditLogsList] = useState([]);
  const [claimNotesList, setClaimNotesList] = useState([]);
  const [newClaimNote, setNewClaimNote] = useState('');
  const [notesLoading, setNotesLoading] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);

  // ── Fixed collapsible LEFT sidebar (persisted across sessions) ──
  const [sidebarExpanded, setSidebarExpanded] = useState(() => {
    try { return window.localStorage.getItem('nexa_sidebar_expanded') !== 'false'; } catch { return true; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleSidebar = () => setSidebarExpanded(p => {
    const n = !p;
    try { window.localStorage.setItem('nexa_sidebar_expanded', String(n)); } catch { /* ignore */ }
    return n;
  });
  const toggleMobile = () => setMobileOpen(p => !p);

  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Modals
  const [showClaimModal, setShowClaimModal] = useState(false);
  const [showFnolModal, setShowFnolModal] = useState(false);
  const [showInvModal, setShowInvModal] = useState(false);
  const [invCaseData, setInvCaseData] = useState({ id: null, claim_id: '', status: 'in_review', notes: '' });

  // Claim Form State
  const [claimForm, setClaimForm] = useState({
    policy_number: 'POL-LIF-801294',
    claim_type: 'Death Benefit',
    claim_amount: '35000',
    incident_date: new Date().toISOString().slice(0, 10),
    beneficiary_name: 'Simbarashe Mpofu Jr.',
    description: 'Submitted for expedited review following loss event.',
  });

  // FNOL Form State
  const [fnolForm, setFnolForm] = useState({
    policy_number: 'POL-FUN-302199',
    claimant_name: 'Tendai Moyo',
    event_type: 'Funeral Expense',
    incident_date: new Date().toISOString().slice(0, 10),
    estimated_amount: '10000',
    reporting_channel: 'Branch Walk-In',
    initial_notes: 'Walk-in notification at First Street Harare branch.',
  });

  // Validate or fetch profile
  useEffect(() => {
    if (!token) return;

    fetch('/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(async res => {
        if (!res.ok) throw new Error('Session expired');
        return res.json();
      })
      .then(setUser)
      .catch(() => {
        sessionStorage.removeItem('fide_token');
        setToken(null);
        setUser(null);
      });
  }, [token]);

  // Redirect users to their departmental dashboard on login
  useEffect(() => {
    if (!user || !token) return;
    fetch('/departmental/my-profile', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(profile => {
        if (profile) {
          setDashboardType(profile.dashboard_type);
          const sidebar = getSidebar(profile.role);
          const first = firstVisibleTab(sidebar);
          setActiveTab(sidebar.some(t => t.id === activeTab) ? activeTab : first);
        }
      })
      .catch(() => {});
  }, [user, token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Enforce role-based sidebar guard: users cannot access other departments'
  // dashboards even via manual navigation. 'detail' is a claim-view state (not
  // a sidebar item) and is allowed through.
  useEffect(() => {
    if (!user) return;
    const sidebar = getSidebar(user.role);
    if (activeTab !== 'detail' && !sidebar.some(t => t.id === activeTab)) {
      setActiveTab(firstVisibleTab(sidebar));
    }
  }, [user, activeTab]);

  // Load All System Data Once Authenticated
  useEffect(() => {
    if (!user || !token) return;
    refreshAllData();
  }, [user, token]);

  // Load claim notes for the detail view
  useEffect(() => {
    if (activeTab !== 'detail' || !selectedClaim) return;
    setNotesLoading(true);
    fetch(`/claims/${selectedClaim.claim_id}/notes`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(setClaimNotesList)
      .catch(() => setClaimNotesList([]))
      .finally(() => setNotesLoading(false));
  }, [activeTab, selectedClaim?.claim_id]);

  // Unread notification count
  const refreshUnreadCount = () => {
    fetch('/notifications/unread-count', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setNotificationCount(d.unread_count))
      .catch(() => {});
  };

  const refreshAllData = () => {
    const headers = { Authorization: `Bearer ${token}` };

    // Overview KPIs
    fetch('/dashboard/overview', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setKpis(d.kpis);
          setRiskDistribution(d.risk_distribution || []);
          setRecentSuspicious(d.recent_suspicious_claims || []);
        }
      })
      .catch(console.error);

    // Claims Register
    fetch('/claims/', { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => {
        setClaimsList(d);
        if (d.length > 0 && !selectedClaim) {
          fetchClaimDetail(d[0].claim_id);
        }
      })
      .catch(console.error);

    // FNOL List
    fetch('/claims/fnol/list', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setFnolList(d.fnol_intakes || []))
      .catch(console.error);

    // Investigations
    fetch('/investigations/', { headers })
      .then(r => r.ok ? r.json() : [])
      .then(setInvestigationsList)
      .catch(console.error);

    // Network Graph
    fetch('/dashboard/network-graph', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setNetworkData(d))
      .catch(console.error);

    // Model Governance
    fetch('/dashboard/model-governance', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setGovernanceData(d))
      .catch(console.error);

    // Registries
    fetch('/customers', { headers }).then(r => r.ok ? r.json() : []).then(setCustomersList).catch(console.error);
    fetch('/policies', { headers }).then(r => r.ok ? r.json() : []).then(setPoliciesList).catch(console.error);
    fetch('/audit-logs/', { headers }).then(r => r.ok ? r.json() : []).then(setAuditLogsList).catch(console.error);

    // Unread notification count
    refreshUnreadCount();
  };

  const fetchClaimDetail = (claimId) => {
    fetch(`/claims/${claimId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) setSelectedClaim(d);
      })
      .catch(console.error);
  };

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMsg('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', username.trim());
      formData.append('password', password);

      const response = await fetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Invalid username or password');
      }

      if (rememberMe) {
        localStorage.setItem('fide_saved_user', username.trim());
        localStorage.setItem('fide_remember', 'true');
      } else {
        localStorage.removeItem('fide_saved_user');
        localStorage.removeItem('fide_remember');
      }

      sessionStorage.setItem('fide_token', data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } catch (err) {
      setError(err.message || 'Unable to connect to the server');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (regPassword !== regConfirmPassword) {
      setError('Passwords do not match. Please verify your password entry.');
      return;
    }
    if (!regAgree) {
      setError('Please acknowledge compliance with the Data Protection Act and Fraud Governance Policy.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: regFullName.trim(),
          email: regEmail.trim(),
          username: regUsername.trim(),
          password: regPassword,
          role: regRole,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed.');
      }

      setSuccessMsg(`Account created for ${data.username}! You can now sign in.`);
      setUsername(data.username);
      setPassword('');
      setAuthMode('login');
    } catch (err) {
      setError(err.message || 'Unable to create account');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setForgotLoading(true);
    try {
      const response = await fetch('/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail.trim() }),
      });
      const data = await response.json();
      setForgotMsg(data.message || 'Password reset link sent to your corporate email.');
    } catch (err) {
      setForgotMsg('Password reset instructions dispatched to your corporate inbox.');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('fide_token');
    setToken(null);
    setUser(null);
    setKpis(null);
  };


  const switchRole = async (targetUser, targetPass) => {
    setUsername(targetUser);
    setPassword(targetPass);
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append('username', targetUser);
      formData.append('password', targetPass);

      const response = await fetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      const data = await response.json();
      if (response.ok) {
        sessionStorage.setItem('fide_token', data.access_token);
        setToken(data.access_token);
        setUser(data.user);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Submit Claim
  const submitClaim = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('policy_number', claimForm.policy_number);
    formData.append('claim_type', claimForm.claim_type);
    formData.append('claim_amount', claimForm.claim_amount);
    formData.append('incident_date', claimForm.incident_date);
    formData.append('beneficiary_name', claimForm.beneficiary_name);
    formData.append('description', claimForm.description);

    try {
      const res = await fetch('/claims/submit', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setShowClaimModal(false);
        alert(`Claim ${data.claim_id} registered and evaluated by AI!`);
        refreshAllData();
        fetchClaimDetail(data.claim_id);
        setActiveTab('detail');
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Failed to submit'}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Submit FNOL
  const submitFnol = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('policy_number', fnolForm.policy_number);
    formData.append('claimant_name', fnolForm.claimant_name);
    formData.append('event_type', fnolForm.event_type);
    formData.append('incident_date', fnolForm.incident_date);
    formData.append('estimated_amount', fnolForm.estimated_amount);
    formData.append('reporting_channel', fnolForm.reporting_channel);
    formData.append('initial_notes', fnolForm.initial_notes);

    try {
      const res = await fetch('/claims/fnol', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setShowFnolModal(false);
        alert(`FNOL Notice Registered!\nReference: ${data.fnol_reference}\nTriage: ${data.triage_queue}`);
        refreshAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Update Investigation
  const updateInvestigation = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`/investigations/${invCaseData.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ status: invCaseData.status, notes: invCaseData.notes })
      });
      if (res.ok) {
        setShowInvModal(false);
        alert('Investigation case updated successfully!');
        refreshAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Recalculate AI Score
  const rescoreClaim = async (claimId) => {
    try {
      const res = await fetch(`/claims/${claimId}/score`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert(`AI score recalculated for ${claimId}`);
        fetchClaimDetail(claimId);
        refreshAllData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Request missing documents (Claims Officer)
  const requestMissingDocuments = async (claimId) => {
    try {
      const fd = new FormData();
      fd.append('reason', 'Requesting supporting documents to complete adjudication.');
      const res = await fetch(`/claims/${claimId}/request-documents`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (res.ok) {
        alert(`Documentation request sent for ${claimId}. Status: pending_documents.`);
        refreshAllData();
        fetchClaimDetail(claimId);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Error: ${err.detail || 'Request failed'}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Forward suspicious claim to Fraud Investigation Department (Claims Officer)
  const forwardToInvestigation = async (claimId) => {
    try {
      const fd = new FormData();
      fd.append('notes', selectedClaim?.assessment?.explanation || `Forwarded: AI fraud risk detected on ${claimId}.`);
      const res = await fetch(`/claims/${claimId}/forward-to-investigation`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (res.ok) {
        alert(`Claim ${claimId} forwarded to Fraud Investigation Department.`);
        refreshAllData();
        fetchClaimDetail(claimId);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Error: ${err.detail || 'Forward failed'}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Add internal note to claim
  const addClaimNote = async () => {
    if (!selectedClaim || !newClaimNote.trim()) return;
    try {
      const res = await fetch(`/claims/${selectedClaim.claim_id}/notes`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: newClaimNote.trim() }),
      });
      if (res.ok) {
        setNewClaimNote('');
        const notes = await fetch(`/claims/${selectedClaim.claim_id}/notes`, { headers: { Authorization: `Bearer ${token}` } });
        if (notes.ok) setClaimNotesList(await notes.json());
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Error: ${err.detail || 'Note failed'}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Filtered claims
  const filteredClaims = claimsList.filter(c => {
    const matchesSearch = !searchQuery ||
      c.claim_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.customer_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.policy_number?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRisk = !riskFilter || c.risk_category?.toLowerCase() === riskFilter.toLowerCase();
    const matchesStatus = !statusFilter || c.status?.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesRisk && matchesStatus;
  });

  // Claims currently assigned to the logged-in user (Claims Manager view)
  const assignedToMe = user?.id
    ? claimsList.filter(c => c.assigned_officer_id === user.id)
    : [];

  // Status-filtered claims fetched from the backend. The claims list is
  // paginated (limit 200) and older claims (e.g. approved/under-investigation
  // ones) may sit beyond the first page, so filtering by status client-side
  // on claimsList shows nothing for them. The backend supports the `status`
  // query param — use it when a status filter is active.
  const [statusFilteredClaims, setStatusFilteredClaims] = useState([]);
  useEffect(() => {
    if (!statusFilter) {
      setStatusFilteredClaims([]);
      return;
    }
    let cancelled = false;
    apiCall(`/claims/?status=${encodeURIComponent(statusFilter)}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) setStatusFilteredClaims(Array.isArray(d) ? d : []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [statusFilter, token, user?.id]);

  const claimsTableList = activeTab === 'assigned-claims' ? assignedToMe
    : (statusFilter ? statusFilteredClaims : filteredClaims);

  const getRiskBadge = (category, score) => {
    const cat = (category || '').toLowerCase();
    let color = 'bg-slate-100 text-slate-800 border-slate-200';
    if (cat === 'critical') color = 'bg-red-50 text-red-800 border-red-300 font-black';
    else if (cat === 'high') color = 'bg-orange-50 text-orange-800 border-orange-300 font-extrabold';
    else if (cat === 'medium') color = 'bg-amber-50 text-amber-800 border-amber-300 font-bold';
    else if (cat === 'low') color = 'bg-emerald-50 text-emerald-800 border-emerald-300 font-bold';

    return (
      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs border ${color}`}>
        {score !== undefined && score !== null ? `${score} • ` : ''}{category || 'Unassessed'}
      </span>
    );
  };

  // ==========================================
  // VIEW: LOGIN SCREEN
  // ==========================================
  if (!user) {
    return (
      <div className="login-page">
        <div className="login-brand-panel">
          <div className="brand-logo">
            <ShieldCheck size={36} />
          </div>

          <div className="brand-content">
            <span className="brand-label">FIDELITY LIFE ASSURANCE OF ZIMBABWE</span>

            <h1>
              Intelligence.<br />
              Integrity.<br />
              <span>Trust.</span>
            </h1>

            <p>
              Next-generation AI fraud surveillance, automated OCR forensics,
              collusion network intelligence, and Special Investigation Unit workflow.
            </p>

            <div className="brand-feature">
              <Activity size={20} />
              <span>Real-Time Inception & Duplicate Fraud Analysis</span>
            </div>

            <div className="brand-feature">
              <ShieldCheck size={20} />
              <span>Multi-Agent Forensic Verification & SHA-256 Hashing</span>
            </div>
          </div>

          <div className="brand-footer">
            NEXA AI FRAUD SUITE &bull; FIDELITY LIFE ASSURANCE &bull; VERSION 2.0
          </div>
        </div>

        <div className="login-form-panel">
          <div className="login-card">
            <div className="mobile-logo">
              <ShieldCheck size={32} />
              <span>FIDELITY LIFE ASSURANCE</span>
            </div>

            {/* Top Auth Mode Tabs */}
            <div className="flex border-b border-slate-200 mb-6">
              <button
                type="button"
                onClick={() => { setAuthMode('login'); setError(''); setSuccessMsg(''); }}
                className={`flex-1 py-3 text-xs font-extrabold uppercase tracking-wider border-b-2 transition ${
                  authMode === 'login'
                    ? 'border-amber-500 text-slate-900'
                    : 'border-transparent text-slate-400 hover:text-slate-700'
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => { setAuthMode('register'); setError(''); setSuccessMsg(''); }}
                className={`flex-1 py-3 text-xs font-extrabold uppercase tracking-wider border-b-2 transition ${
                  authMode === 'register'
                    ? 'border-amber-500 text-slate-900'
                    : 'border-transparent text-slate-400 hover:text-slate-700'
                }`}
              >
                Create Account
              </button>
            </div>

            <span className="welcome-label">{authMode === 'login' ? 'ENTERPRISE ACCESS' : 'NEW OFFICER REGISTRATION'}</span>
            <h2>{authMode === 'login' ? 'Sign In to NEXA AI' : 'Create System Account'}</h2>
            <p className="login-description">
              {authMode === 'login'
                ? 'Access the Fraud Detection, FNOL Intake, and Claims Risk Assessment Platform.'
                : 'Register your employee profile and request role-based platform clearance.'}
            </p>

            {error && (
              <div className="login-error mb-4">
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-3 mb-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold flex items-center space-x-2">
                <CheckCircle2 size={18} className="text-emerald-600" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* ==================================================== */}
            {/* MODE 1: SIGN IN / LOG IN FORM                        */}
            {/* ==================================================== */}
            {authMode === 'login' && (
              <form onSubmit={handleLogin}>
                <label>Email or Username</label>
                <input
                  type="text"
                  placeholder="name@fidelitylife.co.zw or username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                />

                <label>Password</label>
                <div className="password-field">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your secure password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                  </button>
                </div>

                {/* Remember Me and Forgot Password Row */}
                <div className="flex items-center justify-between mt-3 mb-4 text-xs">
                  <label className="flex items-center space-x-2 cursor-pointer select-none m-0 font-medium text-slate-600">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={e => setRememberMe(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-amber-500 focus:ring-amber-400 cursor-pointer"
                    />
                    <span>Remember me</span>
                  </label>

                  <button
                    type="button"
                    onClick={() => { setShowForgotModal(true); setForgotMsg(''); }}
                    className="text-amber-700 hover:text-amber-900 font-bold hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>

                <button
                  type="submit"
                  className="login-button"
                  disabled={loading}
                >
                  {loading ? 'Authenticating...' : 'Sign In Securely'}
                </button>

                {/* Switch to Register link */}
                <div className="text-center mt-4 text-xs text-slate-500">
                  Don't have an account?{' '}
                  <button
                    type="button"
                    onClick={() => { setAuthMode('register'); setError(''); }}
                    className="font-bold text-blue-900 hover:underline"
                  >
                    Sign in if you don't have account
                  </button>
                </div>
              </form>
            )}

            {/* ==================================================== */}
            {/* MODE 2: CREATE ACCOUNT / REGISTER FORM              */}
            {/* ==================================================== */}
            {authMode === 'register' && (
              <form onSubmit={handleRegister} className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Full Legal Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Tendai Moyo"
                    value={regFullName}
                    onChange={e => setRegFullName(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Corporate Email Address *</label>
                  <input
                    type="email"
                    required
                    placeholder="tmoyo@fidelitylife.co.zw"
                    value={regEmail}
                    onChange={e => setRegEmail(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg text-xs"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Username *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. tmoyo"
                      value={regUsername}
                      onChange={e => setRegUsername(e.target.value)}
                      className="w-full p-3 border border-slate-300 rounded-lg text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Requested Role *</label>
                    <select
                      value={regRole}
                      onChange={e => setRegRole(e.target.value)}
                      className="w-full p-3 border border-slate-300 rounded-lg text-xs bg-white font-semibold"
                    >
                      <option value="claims_officer">Claims Officer</option>
                      <option value="claims_manager">Claims Manager</option>
                      <option value="fraud_investigator">Fraud Investigator</option>
                      <option value="compliance_officer">Compliance Officer</option>
                      <option value="management">Executive / CRO</option>
                      <option value="system_admin">System Admin</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Password *</label>
                  <div className="password-field">
                    <input
                      type={showRegPassword ? 'text' : 'password'}
                      required
                      placeholder="Minimum 6 characters"
                      value={regPassword}
                      onChange={e => setRegPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowRegPassword(!showRegPassword)}
                      aria-label="Toggle password visibility"
                    >
                      {showRegPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Confirm Password *</label>
                  <input
                    type="password"
                    required
                    placeholder="Re-enter password"
                    value={regConfirmPassword}
                    onChange={e => setRegConfirmPassword(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg text-xs"
                    autoComplete="new-password"
                  />
                </div>

                <div className="pt-1">
                  <label className="flex items-start space-x-2 text-[11px] text-slate-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={regAgree}
                      onChange={e => setRegAgree(e.target.checked)}
                      className="mt-0.5 rounded border-slate-300 text-amber-500 focus:ring-amber-400"
                    />
                    <span>I confirm official Fidelity Life Assurance employment and agree to Zimbabwean Data Protection Act guidelines.</span>
                  </label>
                </div>

                <button
                  type="submit"
                  className="login-button mt-3"
                  disabled={loading}
                >
                  {loading ? 'Creating Account...' : 'Register & Request Access'}
                </button>

                <div className="text-center mt-3 text-xs text-slate-500">
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => { setAuthMode('login'); setError(''); }}
                    className="font-bold text-blue-900 hover:underline"
                  >
                    Sign in
                  </button>
                </div>
              </form>
            )}

            {/* 1-Click Fast Demo Credentials (For Examiners & Testing) */}
            <div className="mt-6 pt-4 border-t border-slate-100">
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">1-Click Demo Profiles:</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button type="button" onClick={() => switchRole('claims.officer', 'OfficerPass123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">Claims Officer</button>
                <button type="button" onClick={() => switchRole('investigator', 'Investigate123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">Fraud Investigator</button>
                <button type="button" onClick={() => switchRole('claims.manager', 'ManagerPass123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">Claims Manager</button>
                <button type="button" onClick={() => switchRole('compliance', 'Compliance123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">Compliance Officer</button>
                <button type="button" onClick={() => switchRole('executive', 'Executive123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">Executive / CRO</button>
                <button type="button" onClick={() => switchRole('admin', 'AdminPass123!')} className="p-2 border rounded-lg text-left hover:bg-slate-50 font-semibold text-slate-700">System Admin</button>
              </div>
            </div>

            <div className="secure-notice mt-5">
              <LockKeyhole size={14} className="text-emerald-600" />
              <span>Protected by PBKDF2 Encryption & Zimbabwean Data Protection Act</span>
            </div>

            <div className="login-bottom">
              &copy; 2026 Fidelity Life Assurance of Zimbabwe
              <br />
              NEXA AI Claims Detection Platform
            </div>
          </div>
        </div>

        {/* Modal: Forgot Password */}
        {showForgotModal && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-4">
              <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                <div>
                  <h3 className="text-base font-black text-slate-900">Reset Your Password</h3>
                  <p className="text-xs text-slate-500">Enter your corporate email to receive reset instructions</p>
                </div>
                <button onClick={() => setShowForgotModal(false)} className="text-slate-400 hover:text-slate-700">
                  <X size={20} />
                </button>
              </div>

              {forgotMsg ? (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 space-y-2">
                  <p className="font-bold flex items-center space-x-1.5"><CheckCircle2 size={16} className="text-emerald-600" /><span>Instructions Dispatched</span></p>
                  <p>{forgotMsg}</p>
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="w-full mt-2 py-2 bg-emerald-600 text-white rounded-lg font-bold text-xs"
                  >
                    Return to Sign In
                  </button>
                </div>
              ) : (
                <form onSubmit={handleForgotPassword} className="space-y-4 text-xs">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Corporate Email Address *</label>
                    <input
                      type="email"
                      required
                      placeholder="e.g. tmoyo@fidelitylife.co.zw"
                      value={forgotEmail}
                      onChange={e => setForgotEmail(e.target.value)}
                      className="w-full p-3 border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div className="pt-2 flex justify-end space-x-2">
                    <button
                      type="button"
                      onClick={() => setShowForgotModal(false)}
                      className="px-4 py-2 border rounded-xl text-slate-600 font-bold"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={forgotLoading}
                      className="px-4 py-2 bg-[#0F2744] text-white rounded-xl font-bold"
                    >
                      {forgotLoading ? 'Dispatching...' : 'Send Reset Link'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }


  // ==========================================
  // VIEW: MAIN ENTERPRISE DASHBOARD
  // ==========================================
  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-[#0A192F] text-white border-b border-slate-700/80 sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center font-black text-slate-950 text-2xl shadow-md">
              <ShieldCheck size={28} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold tracking-wider text-lg text-white">FIDELITY LIFE</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 font-black tracking-widest uppercase">ASSURANCE</span>
              </div>
              <p className="text-xs text-slate-300 font-semibold tracking-wide">NEXA AI Fraud Detection & Enterprise Claims Suite</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>AI Engine: <strong className="text-amber-300">v1.2-ensemble-hybrid</strong></span>
            </div>

            <div className="flex items-center space-x-2 bg-slate-800/90 border border-slate-700 rounded-xl px-3 py-1.5 text-xs">
              <span className="text-slate-400">Role:</span>
              <select
                value={user?.username || 'claims.officer'}
                onChange={(e) => {
                  const passMap = {
                    'admin': 'AdminPass123!',
                    'claims.officer': 'OfficerPass123!',
                    'claims.manager': 'ManagerPass123!',
                    'investigator': 'Investigate123!',
                    'compliance': 'Compliance123!',
                    'executive': 'Executive123!',
                  };
                  switchRole(e.target.value, passMap[e.target.value] || 'AdminPass123!');
                }}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="claims.officer" className="bg-slate-900">Claims Officer</option>
                <option value="claims.manager" className="bg-slate-900">Claims Manager</option>
                <option value="investigator" className="bg-slate-900">Fraud Investigator</option>
                <option value="compliance" className="bg-slate-900">Compliance Officer</option>
                <option value="executive" className="bg-slate-900">Executive / CRO</option>
                <option value="admin" className="bg-slate-900">System Admin</option>
              </select>
            </div>

            <div className="flex items-center space-x-2 pl-3 border-l border-slate-700">
              <div className="w-9 h-9 rounded-xl bg-slate-800 border-2 border-amber-500 flex items-center justify-center font-bold text-xs text-amber-400">
                {(user.full_name || user.username).slice(0, 2).toUpperCase()}
              </div>
              <div className="hidden lg:block text-left">
                <p className="text-xs font-bold text-white leading-tight">{user.full_name || user.username}</p>
                <p className="text-[10px] text-amber-400 font-semibold">{user.role}</p>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="p-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-xl transition"
              title="Sign Out"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>

        {/* Fixed collapsible LEFT sidebar — role-based, backend-enforced */}
        <Sidebar
          user={user}
          sidebar={getSidebar(user?.role || 'claims_officer')}
          activeTab={activeTab}
          onTab={setActiveTab}
          expanded={sidebarExpanded}
          onToggle={toggleSidebar}
          mobileOpen={mobileOpen}
          onMobileClose={toggleMobile}
        />
      </header>

      {/* Main Container — shifts right with the collapsible sidebar */}
      <main
        className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-8 md:transition-all md:duration-200"
        style={{ marginLeft: sidebarExpanded ? '264px' : '56px' }}
      >

        {/* ========================================================= */}
        {/* TAB 1: EXECUTIVE OVERVIEW */}
        {/* ========================================================= */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Commanding Hero Banner */}
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-amber-50/50 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-900/10 border border-blue-900/20 text-blue-900 text-xs font-black tracking-widest uppercase mb-3">
                    <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                    <span>FIDELITY LIFE ASSURANCE &bull; EXECUTIVE FRAUD SURVEILLANCE</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    Executive Claims & Fraud Intelligence Suite
                  </h1>
                  <div className="mt-3 flex items-center space-x-2">
                    <div className="h-1.5 w-20 bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"></div>
                    <div className="h-1.5 w-6 bg-blue-900 rounded-full"></div>
                    <div className="h-1.5 w-2 bg-slate-300 rounded-full"></div>
                  </div>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed font-medium">
                    Continuous AI evaluation of policy inception proximity, duplicate claims, OCR forensic validation, and network collusion tracking.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => setShowFnolModal(true)}
                    className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs sm:text-sm font-black shadow-md transition flex items-center space-x-2"
                  >
                    <Plus size={16} />
                    <span>Intake FNOL Notice</span>
                  </button>
                  <button
                    onClick={() => setShowClaimModal(true)}
                    className="px-4 py-2.5 rounded-xl bg-[#0F2744] hover:bg-[#1B3A57] text-white text-xs sm:text-sm font-bold shadow-md transition flex items-center space-x-2"
                  >
                    <Plus size={16} />
                    <span>Submit Formal Claim</span>
                  </button>
                  <button
                    onClick={refreshAllData}
                    className="p-2.5 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition shadow-sm"
                    title="Refresh Live Data"
                  >
                    <RotateCw size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-[#0F2744]">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Claims</span>
                <p className="text-3xl font-black text-slate-900 mt-2">{kpis?.total_claims_received ?? '—'}</p>
                <div className="text-[11px] text-emerald-600 font-bold mt-2 flex items-center space-x-1">
                  <TrendingUp size={13} />
                  <span>Active Portfolio</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-purple-600">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">AI Analysed</span>
                <p className="text-3xl font-black text-purple-700 mt-2">{kpis?.claims_analysed_by_ai ?? '—'}</p>
                <div className="text-[11px] text-slate-500 font-bold mt-2">
                  <span>{kpis?.ai_coverage_rate ?? 100}% Coverage</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-t-red-600">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Critical Risk</span>
                <p className="text-3xl font-black text-red-600 mt-2">{kpis?.critical_risk_claims ?? '—'}</p>
                <div className="text-[11px] text-red-700 font-extrabold mt-2 uppercase">Payment Hold</div>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-amber-200 shadow-sm border-t-4 border-t-amber-500 bg-gradient-to-br from-white to-amber-50/40">
                <span className="text-[11px] font-bold uppercase tracking-wider text-amber-800">Losses Prevented</span>
                <p className="text-2xl sm:text-3xl font-black text-slate-950 mt-2">
                  ${kpis ? Number(kpis.prevented_fraud_losses_usd).toLocaleString() : '0'}
                </p>
                <div className="text-[11px] text-emerald-700 font-extrabold mt-2 flex items-center space-x-1">
                  <ShieldCheck size={13} />
                  <span>Saved Capital</span>
                </div>
              </div>
            </div>

            {/* Risk Distribution and Recent Suspicious */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                  <div>
                    <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Claims Risk Distribution</h2>
                    <p className="text-xs text-slate-500 font-medium">Calibrated Multi-Layer Score (0-100)</p>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 font-bold">Live</span>
                </div>

                <div className="space-y-4 mt-2">
                  {riskDistribution.map((item, idx) => (
                    <div key={idx}>
                      <div className="flex justify-between text-xs font-bold mb-1">
                        <span className="text-slate-700">{item.name}</span>
                        <span className="font-mono">{item.percentage}% ({item.count})</span>
                      </div>
                      <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${item.percentage}%`, backgroundColor: item.color }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm lg:col-span-2 space-y-4">
                <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                  <div>
                    <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                      <AlertTriangle size={17} className="text-amber-500" />
                      <span>Priority Suspicious Claims Surveillance Queue</span>
                    </h2>
                    <p className="text-xs text-slate-500 font-medium">Requires SIU investigation or payment hold review</p>
                  </div>
                  <button
                    onClick={() => setActiveTab('claims')}
                    className="text-xs font-bold text-blue-900 hover:text-blue-700 flex items-center space-x-1"
                  >
                    <span>View All</span>
                    <ArrowRight size={14} />
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                      <tr>
                        <th className="py-2.5 px-3">Claim ID</th>
                        <th className="py-2.5 px-3">Policyholder</th>
                        <th className="py-2.5 px-3">Product</th>
                        <th className="py-2.5 px-3">Amount</th>
                        <th className="py-2.5 px-3">Risk Assessment</th>
                        <th className="py-2.5 px-3">Primary Anomaly</th>
                        <th className="py-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {recentSuspicious.length === 0 ? (
                        <tr><td colSpan="7" className="py-6 text-center text-slate-400">No suspicious claims recorded.</td></tr>
                      ) : (
                        recentSuspicious.map((c, i) => (
                          <tr key={i} className="hover:bg-slate-50 transition cursor-pointer" onClick={() => { fetchClaimDetail(c.claim_id); setActiveTab('detail'); }}>
                            <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{c.claim_id}</td>
                            <td className="py-2.5 px-3 font-semibold text-slate-800">{c.customer_name}</td>
                            <td className="py-2.5 px-3">{c.claim_type}</td>
                            <td className="py-2.5 px-3 font-mono font-bold">${Number(c.amount).toLocaleString()}</td>
                            <td className="py-2.5 px-3">{getRiskBadge(c.risk_category, c.risk_score)}</td>
                            <td className="py-2.5 px-3 text-slate-600 truncate max-w-xs">{c.top_indicator}</td>
                            <td className="py-2.5 px-3 text-right">
                              <button className="px-2.5 py-1 rounded bg-[#0F2744] text-white text-[11px] font-bold hover:bg-[#1B3A57]">Inspect</button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 2: FNOL INTAKE */}
        {/* ========================================================= */}
        {activeTab === 'fnol' && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-amber-50/50 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-800 text-xs font-black tracking-widest uppercase mb-3">
                    <Layers size={14} className="text-amber-600" />
                    <span>SECTION 4.4 &bull; FIRST NOTICE OF LOSS (FNOL) INTAKE</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    First Notice of Loss (FNOL) Intake & Triage
                  </h1>
                  <div className="mt-3 flex items-center space-x-2">
                    <div className="h-1.5 w-20 bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"></div>
                    <div className="h-1.5 w-6 bg-blue-900 rounded-full"></div>
                    <div className="h-1.5 w-2 bg-slate-300 rounded-full"></div>
                  </div>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed font-medium">
                    Capture initial notification of loss, validate policy coverage schedules, and assign intelligent triage priority.
                  </p>
                </div>
                <button
                  onClick={() => setShowFnolModal(true)}
                  className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs sm:text-sm font-black shadow-md transition flex items-center space-x-2"
                >
                  <Plus size={16} />
                  <span>Log New Loss Notice</span>
                </button>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Preliminary Loss Notifications Queue</h3>
                <span className="text-xs text-slate-500">Total Notifications: <strong className="text-slate-900 font-bold">{fnolList.length}</strong></span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-4">FNOL Ref #</th>
                      <th className="py-3 px-4">Associated Claim</th>
                      <th className="py-3 px-4">Policy #</th>
                      <th className="py-3 px-4">Claimant Name</th>
                      <th className="py-3 px-4">Event Type</th>
                      <th className="py-3 px-4">Incident Date</th>
                      <th className="py-3 px-4">Channel</th>
                      <th className="py-3 px-4">Estimated Loss</th>
                      <th className="py-3 px-4">Initial Triage</th>
                      <th className="py-3 px-4">Intake Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {fnolList.map((f, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition">
                        <td className="py-3 px-4 font-mono font-bold text-amber-700">{f.fnol_reference}</td>
                        <td className="py-3 px-4 font-mono font-bold text-blue-900 cursor-pointer hover:underline" onClick={() => { fetchClaimDetail(f.claim_id); setActiveTab('detail'); }}>{f.claim_id}</td>
                        <td className="py-3 px-4 font-mono text-slate-600">{f.policy_number}</td>
                        <td className="py-3 px-4 font-bold text-slate-800">{f.claimant_name}</td>
                        <td className="py-3 px-4">{f.event_type}</td>
                        <td className="py-3 px-4 font-mono text-slate-500">{f.incident_date}</td>
                        <td className="py-3 px-4"><span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-bold">{f.reporting_channel}</span></td>
                        <td className="py-3 px-4 font-mono font-bold">${Number(f.estimated_amount).toLocaleString()}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${f.initial_triage?.includes('SIU') ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'}`}>
                            {f.initial_triage}
                          </span>
                        </td>
                        <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">{f.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 3: CLAIMS REGISTER */}
        {/* ========================================================= */}
        {['claims', 'assigned-claims'].includes(activeTab) && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-blue-50/40 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-900/10 border border-blue-900/20 text-blue-900 text-xs font-black tracking-widest uppercase mb-3">
                    <FileText size={14} className="text-blue-900" />
                    <span>CLAIMS LIFECYCLE & RISK REGISTER</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    Claims Processing & Comprehensive Risk Register
                  </h1>
                  <div className="mt-3 flex items-center space-x-2">
                    <div className="h-1.5 w-20 bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"></div>
                    <div className="h-1.5 w-6 bg-blue-900 rounded-full"></div>
                    <div className="h-1.5 w-2 bg-slate-300 rounded-full"></div>
                  </div>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed font-medium">
                    Search and filter claims across all life, funeral, and pension portfolios. Review real-time automated fraud scores.
                  </p>
                </div>
                <button
                  onClick={() => setShowClaimModal(true)}
                  className="px-5 py-2.5 rounded-xl bg-[#0F2744] hover:bg-[#1B3A57] text-white text-xs sm:text-sm font-bold shadow-md transition flex items-center space-x-2"
                >
                  <Plus size={16} />
                  <span>Submit Formal Claim</span>
                </button>
              </div>
            </div>

            {/* Filter toolbar */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col lg:flex-row gap-3 items-center justify-between">
              <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                <div className="relative w-full sm:w-72">
                  <Search size={15} className="absolute left-3.5 top-3.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search Claim ID, Policy, Name..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 font-medium"
                  />
                </div>

                <select
                  value={riskFilter}
                  onChange={e => setRiskFilter(e.target.value)}
                  className="px-3 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none bg-white font-semibold"
                >
                  <option value="">All Risk Categories</option>
                  <option value="Critical">Critical Risk (80-100)</option>
                  <option value="High">High Risk (60-79)</option>
                  <option value="Medium">Medium Risk (30-59)</option>
                  <option value="Low">Low Risk (0-29)</option>
                </select>

                <select
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  className="px-3 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none bg-white font-semibold"
                >
                  <option value="">All Statuses</option>
                  <option value="submitted">Submitted</option>
                  <option value="flagged">Flagged</option>
                  <option value="under_investigation">Under Investigation</option>
                  <option value="in_review">In Review</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>

              <div className="text-xs text-slate-500 font-bold">
                Showing <span className="text-slate-900 font-black">{claimsTableList.length}</span> claims
              </div>
            </div>

            {/* Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                    <tr>
                      <th className="py-3.5 px-4">Claim ID</th>
                      <th className="py-3.5 px-4">Policy #</th>
                      <th className="py-3.5 px-4">Policyholder</th>
                      <th className="py-3.5 px-4">Claim Type</th>
                      <th className="py-3.5 px-4">Amount</th>
                      <th className="py-3.5 px-4">Incident Date</th>
                      <th className="py-3.5 px-4">AI Risk Score</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {claimsTableList.map((c, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition cursor-pointer" onClick={() => { fetchClaimDetail(c.claim_id); setActiveTab('detail'); }}>
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.claim_id}</td>
                        <td className="py-3 px-4 font-mono text-slate-600">{c.policy_number}</td>
                        <td className="py-3 px-4 font-semibold text-slate-800">{c.customer_name}</td>
                        <td className="py-3 px-4">{c.claim_type}</td>
                        <td className="py-3 px-4 font-mono font-bold">${Number(c.amount).toLocaleString()}</td>
                        <td className="py-3 px-4 text-slate-500 font-mono">{c.incident_date?.slice(0, 10)}</td>
                        <td className="py-3 px-4">{getRiskBadge(c.risk_category, c.risk_score)}</td>
                        <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{c.status}</span></td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={(e) => { e.stopPropagation(); fetchClaimDetail(c.claim_id); setActiveTab('detail'); }}
                            className="px-3 py-1 rounded-xl bg-[#0F2744] text-white text-[11px] font-bold hover:bg-[#1B3A57] shadow-sm"
                          >
                            Review AI
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 4: AI FORENSICS & OCR DETAIL */}
        {/* ========================================================= */}
        {activeTab === 'detail' && selectedClaim && (
          <div className="space-y-8">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center space-x-3.5">
                <button
                  onClick={() => setActiveTab('claims')}
                  className="p-2.5 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition"
                >
                  <ArrowRight size={16} className="rotate-180" />
                </button>
                <div>
                  <div className="flex items-center space-x-3">
                    <h1 className="text-xl sm:text-2xl font-black text-slate-900">{selectedClaim.claim_id}</h1>
                    {getRiskBadge(selectedClaim.assessment?.risk_category, selectedClaim.assessment?.risk_score)}
                  </div>
                  <p className="text-xs text-slate-500 font-semibold mt-1">
                    Policy: {selectedClaim.policy?.policy_number} &bull; Customer: {selectedClaim.customer?.name} ({selectedClaim.customer?.national_id})
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2.5">
                <button
                  onClick={() => rescoreClaim(selectedClaim.claim_id)}
                  className="px-4 py-2 rounded-xl border border-slate-300 text-slate-700 text-xs font-bold hover:bg-slate-50 flex items-center space-x-2 shadow-sm"
                >
                  <RotateCw size={14} className="text-amber-500" />
                  <span>Recalculate AI Score</span>
                </button>
                <button
                  onClick={() => {
                    setInvCaseData({
                      id: selectedClaim.id,
                      claim_id: selectedClaim.claim_id,
                      status: 'in_review',
                      notes: selectedClaim.assessment?.explanation || ''
                    });
                    setShowInvModal(true);
                  }}
                  className="px-4 py-2 rounded-xl bg-[#0F2744] text-white text-xs font-bold hover:bg-[#1B3A57] flex items-center space-x-2 shadow-md"
                >
                  <ShieldCheck size={16} className="text-amber-400" />
                  <span>Manage Investigation</span>
                </button>
              </div>
            </div>

            {/* Claim Management Actions (Claims Officer) */}
            {(user?.role === 'claims_officer' || user?.role === 'claims_manager') && (
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-500 mb-3 flex items-center space-x-2"><ShieldCheck size={14} className="text-amber-600" /><span>Claim Management Actions</span></h3>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => requestMissingDocuments(selectedClaim.claim_id)}
                    className="px-4 py-2 rounded-xl border-2 border-amber-500 text-amber-800 hover:bg-amber-50 font-bold text-xs transition-colors flex items-center space-x-2"
                  >
                    <FileText size={13} />
                    <span>Request Missing Documents</span>
                  </button>
                  <button
                    onClick={() => forwardToInvestigation(selectedClaim.claim_id)}
                    className="px-4 py-2 rounded-xl border-2 border-red-600 text-red-800 hover:bg-red-50 font-bold text-xs transition-colors flex items-center space-x-2"
                  >
                    <ShieldCheck size={13} />
                    <span>Forward to Fraud Investigation Dept</span>
                  </button>
                </div>
                <div className="mt-4">
                  <div className="flex items-center space-x-2 mb-2">
                    <MessageSquare size={13} className="text-blue-600" />
                    <span className="text-xs font-extrabold uppercase tracking-wider text-slate-500">Claim History & Notes ({claimNotesList.length})</span>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-3 mb-3 max-h-44 overflow-y-auto space-y-2">
                    {claimNotesList.length === 0 && <p className="text-xs text-slate-400">No notes recorded yet.</p>}
                    {claimNotesList.map((n, i) => (
                      <div key={n.id ?? i} className="text-xs text-slate-600 border-b border-slate-100 pb-1.5 last:border-0">
                        <span className="font-semibold text-slate-800">{n.created_by}</span>
                        <span className="text-slate-400 mx-1">·</span>
                        <span className="text-[10px] font-mono text-slate-400">{n.created_at ? new Date(n.created_at).toLocaleString('en-ZA') : ''}</span>
                        <p className="mt-0.5">{n.note}</p>
                      </div>
                    ))}
                  </div>
                  <div className="flex space-x-2">
                    <textarea
                      rows={2}
                      placeholder="Add an internal note to this claim..."
                      value={newClaimNote}
                      onChange={e => setNewClaimNote(e.target.value)}
                      className="flex-1 px-3 py-2 text-xs border border-slate-200 rounded-xl resize-none"
                      disabled={notesLoading}
                    />
                    <button onClick={addClaimNote} disabled={notesLoading || !newClaimNote.trim()}
                      className="px-3.5 py-2 bg-[#0F2744] text-white rounded-xl hover:bg-[#1B3A57] font-bold text-xs transition-colors disabled:opacity-50">
                      <Plus size={13} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Score Column */}
              <div className="space-y-6">
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm text-center border-t-4 border-t-amber-500">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-4">Calibrated Fraud Risk Score</h3>
                  <div className="w-36 h-36 mx-auto rounded-full border-8 border-red-500 flex flex-col items-center justify-center">
                    <span className="text-4xl font-black text-slate-900">{selectedClaim.assessment?.risk_score ?? '--'}</span>
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">out of 100</span>
                  </div>
                  <p className="text-base font-extrabold text-slate-800 mt-4">{selectedClaim.assessment?.risk_category} Fraud Risk</p>
                  <p className="text-xs text-slate-500 font-mono mt-1">Model: {selectedClaim.assessment?.model_version || 'v1.2-ensemble-hybrid'}</p>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3 text-xs">
                  <h3 className="font-extrabold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2">Claim & Policy Profile</h3>
                  <div className="flex justify-between py-1.5 border-b border-slate-50"><span className="text-slate-500">Amount:</span><strong className="text-slate-900 font-mono text-sm">${Number(selectedClaim.amount).toLocaleString()}</strong></div>
                  <div className="flex justify-between py-1.5 border-b border-slate-50"><span className="text-slate-500">Product:</span><span className="font-bold">{selectedClaim.claim_type}</span></div>
                  <div className="flex justify-between py-1.5 border-b border-slate-50"><span className="text-slate-500">Incident Date:</span><span className="font-mono">{selectedClaim.incident_date?.slice(0, 10)}</span></div>
                  <div className="flex justify-between py-1.5 border-b border-slate-50"><span className="text-slate-500">National ID:</span><span className="font-mono font-bold">{selectedClaim.customer?.national_id}</span></div>
                  <div className="flex justify-between py-1.5"><span className="text-slate-500">Status:</span><span className="font-black text-red-600 uppercase">{selectedClaim.status}</span></div>
                </div>
              </div>

              {/* Right Breakdown Column */}
              <div className="space-y-6 lg:col-span-2">
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2.5 flex items-center space-x-2">
                    <Activity size={15} className="text-amber-500" />
                    <span>AI Assessment Narrative & Adjudication Rationale</span>
                  </h3>
                  <div className="p-4 bg-slate-50 border-l-4 border-amber-500 rounded-xl text-xs leading-relaxed text-slate-700 font-medium">
                    {selectedClaim.assessment?.explanation || 'Evaluation completed. No major anomalies triggered.'}
                  </div>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-3.5 flex items-center space-x-2">
                    <AlertTriangle size={15} className="text-red-500" />
                    <span>Identified Suspicious Indicators</span>
                  </h3>
                  <div className="space-y-3">
                    {selectedClaim.assessment?.indicators?.map((ind, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex items-start justify-between">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-red-600 text-white">{ind.severity}</span>
                            <strong className="text-xs text-slate-800">{ind.code}</strong>
                          </div>
                          <p className="text-xs text-slate-600 mt-1">{ind.detail}</p>
                        </div>
                        <span className="text-xs font-mono font-bold text-slate-500">+{ind.weight} pts</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-3 flex items-center space-x-2">
                    <FileCheck size={15} className="text-emerald-600" />
                    <span>OCR Supporting Document Forensics</span>
                  </h3>
                  <div className="space-y-3">
                    {selectedClaim.documents?.map((doc, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl border border-slate-200 bg-white">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-bold text-slate-900">{doc.filename}</span>
                          <span className="text-[11px] px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-bold">OCR Verified</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">Cross-matched against incident date: {selectedClaim.incident_date?.slice(0, 10)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 5: SIU INVESTIGATION WORKSPACE */}
        {/* ========================================================= */}
        {activeTab === 'investigations' && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-red-50/40 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-800 text-xs font-black tracking-widest uppercase mb-3">
                    <ShieldCheck size={14} className="text-red-600" />
                    <span>SPECIAL INVESTIGATION UNIT (SIU) &bull; CASE WORKSPACE</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    Fraud Investigation Case Management Workspace
                  </h1>
                  <div className="mt-3 flex items-center space-x-2">
                    <div className="h-1.5 w-20 bg-gradient-to-r from-red-600 to-amber-500 rounded-full"></div>
                    <div className="h-1.5 w-6 bg-blue-900 rounded-full"></div>
                    <div className="h-1.5 w-2 bg-slate-300 rounded-full"></div>
                  </div>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed font-medium">
                    Review assigned cases, record investigative findings, document verification evidence, and enter formal loss prevention decisions.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                    <tr>
                      <th className="py-3.5 px-4">Case #</th>
                      <th className="py-3.5 px-4">Target Claim</th>
                      <th className="py-3.5 px-4">Claimant / Policy</th>
                      <th className="py-3.5 px-4">Amount</th>
                      <th className="py-3.5 px-4">AI Risk</th>
                      <th className="py-3.5 px-4">Investigator</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4">Notes</th>
                      <th className="py-3.5 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {investigationsList.map((inv, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">INV-{inv.id}</td>
                        <td className="py-3 px-4 font-mono font-bold text-blue-900 cursor-pointer hover:underline" onClick={() => { fetchClaimDetail(inv.claim_id); setActiveTab('detail'); }}>{inv.claim_id}</td>
                        <td className="py-3 px-4 font-semibold text-slate-800">{inv.customer_name}</td>
                        <td className="py-3 px-4 font-mono font-bold">${Number(inv.claim_amount).toLocaleString()}</td>
                        <td className="py-3 px-4">{getRiskBadge(inv.risk_category, inv.risk_score)}</td>
                        <td className="py-3 px-4 text-slate-600 font-medium">{inv.investigator}</td>
                        <td className="py-3 px-4"><span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">{inv.status}</span></td>
                        <td className="py-3 px-4 text-slate-600 truncate max-w-xs">{inv.notes}</td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => {
                              setInvCaseData({
                                id: inv.id,
                                claim_id: inv.claim_id,
                                status: inv.status,
                                notes: inv.notes || ''
                              });
                              setShowInvModal(true);
                            }}
                            className="px-3 py-1 rounded-xl bg-slate-800 text-white text-[11px] font-bold hover:bg-slate-700 shadow-sm"
                          >
                            Update Case
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 6: FRAUD NETWORK INTELLIGENCE */}
        {/* ========================================================= */}
        {activeTab === 'network' && <FraudNetworkGraph user={user} />}

        {/* ========================================================= */}
        {/* TAB 7: AI MODEL GOVERNANCE */}
        {/* ========================================================= */}
        {activeTab === 'governance' && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-emerald-50/40 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-800 text-xs font-black tracking-widest uppercase mb-3">
                    <Sliders size={14} className="text-emerald-600" />
                    <span>SECTION 10 & 11 &bull; MODEL GOVERNANCE & FALSE-POSITIVE DRIFT</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    AI Model Governance & False-Positive Monitoring
                  </h1>
                  <div className="mt-3 flex items-center space-x-2">
                    <div className="h-1.5 w-20 bg-gradient-to-r from-emerald-500 to-teal-600 rounded-full"></div>
                    <div className="h-1.5 w-6 bg-blue-900 rounded-full"></div>
                    <div className="h-1.5 w-2 bg-slate-300 rounded-full"></div>
                  </div>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed font-medium">
                    Controlled model lineage, version registries, offline retraining validation, and population stability monitoring.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Model Precision</span>
                <p className="text-3xl font-black text-emerald-600 mt-2">94.6%</p>
              </div>
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Model Recall</span>
                <p className="text-3xl font-black text-blue-600 mt-2">92.1%</p>
              </div>
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">F1 Score</span>
                <p className="text-3xl font-black text-purple-600 mt-2">93.3%</p>
              </div>
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">False Positive Rate</span>
                <p className="text-3xl font-black text-amber-600 mt-2">2.3%</p>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 8: POLICYHOLDER REGISTRY */}
        {/* ========================================================= */}
        {activeTab === 'registry' && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-amber-50/40 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                Policyholder & Insurance Policy Registry
              </h1>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed">
                Registered policyholders, Zimbabwean National ID verification, and active coverage schedules.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Registered Policyholders</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                      <tr>
                        <th className="py-2.5 px-3">Customer ID</th>
                        <th className="py-2.5 px-3">Name</th>
                        <th className="py-2.5 px-3">National ID</th>
                        <th className="py-2.5 px-3">Policies</th>
                        <th className="py-2.5 px-3">Claims</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {customersList.map((c, i) => (
                        <tr key={i}>
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{c.customer_id}</td>
                          <td className="py-2.5 px-3 font-semibold text-slate-800">{c.name}</td>
                          <td className="py-2.5 px-3 font-mono text-slate-500">{c.national_id}</td>
                          <td className="py-2.5 px-3 font-bold">{c.policies_count}</td>
                          <td className="py-2.5 px-3 font-bold">{c.claims_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Active Insurance Policies</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                      <tr>
                        <th className="py-2.5 px-3">Policy #</th>
                        <th className="py-2.5 px-3">Product Type</th>
                        <th className="py-2.5 px-3">Policyholder</th>
                        <th className="py-2.5 px-3">Effective</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {policiesList.map((p, i) => (
                        <tr key={i}>
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{p.policy_number}</td>
                          <td className="py-2.5 px-3 font-semibold">{p.policy_type}</td>
                          <td className="py-2.5 px-3">{p.customer_name}</td>
                          <td className="py-2.5 px-3 text-slate-500 font-mono">{p.effective_date?.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 9: COMPLIANCE & AUDIT LOG */}
        {/* ========================================================= */}
        {activeTab === 'audit' && (
          <div className="space-y-8">
            <div className="relative overflow-hidden bg-gradient-to-r from-white via-slate-50 to-blue-50/40 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
                Regulatory Compliance & Immutable Audit Trail
              </h1>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed">
                Tamper-evident activity logs recording employee actions, risk adjudications, and system operations.
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-4">Timestamp (UTC)</th>
                      <th className="py-3 px-4">User</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Target Entity</th>
                      <th className="py-3 px-4">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                    {auditLogsList.map((l, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="py-2.5 px-4 text-slate-500">{l.timestamp?.replace('T', ' ').slice(0, 19)}</td>
                        <td className="py-2.5 px-4 font-bold text-slate-900">{l.user}</td>
                        <td className="py-2.5 px-4 uppercase text-slate-500 font-bold">{l.user_role}</td>
                        <td className="py-2.5 px-4 font-bold text-blue-900">{l.action}</td>
                        <td className="py-2.5 px-4 text-slate-700">{l.target || '--'}</td>
                        <td className="py-2.5 px-4 text-slate-500 truncate max-w-xs">{JSON.stringify(l.detail || {})}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* NEW: DEPARTMENTAL WORKSPACES */}
        {/* ========================================================= */}
        {['executive-overview', 'claims-performance', 'fraud-analytics', 'financial-exposure', 'department-performance', 'ai-fraud-intelligence', 'management-reports'].includes(activeTab) && (
          <ExecutiveDashboard activeTab={activeTab} />
        )}
        {['compliance-overview', 'compliance-alerts', 'claims-under-review', 'regulatory-reports'].includes(activeTab) && (
          <ComplianceDashboard activeTab={activeTab} />
        )}
        {['investigation-overview', 'fraud-alerts', 'assigned-cases', 'ai-forensic-analysis', 'evidence-management', 'investigation-reports'].includes(activeTab) && (
          <FraudInvestigationDashboard activeTab={activeTab} />
        )}
        {['admin-overview', 'user-management', 'roles-permissions', 'system-monitoring', 'ai-model-monitoring', 'ocr-monitoring', 'system-configuration'].includes(activeTab) && (
          <AdminDashboard activeTab={activeTab} />
        )}
        {activeTab === 'ocr' && <OCRDocumentPage activeTab="ocr-results" user={user} />}
        {activeTab === 'ocr-results' && <OCRDocumentPage activeTab="ocr-results" user={user} />}
        {activeTab === 'ocr-upload' && <OCRDocumentPage activeTab="ocr-upload" user={user} />}
        {activeTab === 'ocr-samples' && <OCRDocumentPage activeTab="ocr-samples" user={user} />}
        {activeTab === 'ocr-forensics' && <OCRDocumentPage activeTab="ocr-forensics" user={user} />}
        {activeTab === 'notifications' && <NotificationsPanel user={user} token={token} onCountChange={(n) => setNotificationCount(n)} />}
        {activeTab === 'profile' && <ProfilePanel user={user} onExit={handleLogout} />}
        {activeTab === 'new-claim' && <NewClaimPanel user={user} />}

        {/* ========================================================= */}
        {/* Advanced NEXA Intelligence Workspaces (enterprise upgrade) */}
        {/* ========================================================= */}
        {activeTab === 'fraud-network' && <FraudNetworkGraph user={user} />}
        {activeTab === 'timeline' && <ClaimTimeline user={user} />}
        {activeTab === 'evidence-management' && <EvidenceManagement user={user} />}
        {activeTab === 'historical' && <HistoricalBehaviorPanel user={user} />}
        {activeTab === 'predictive' && <PredictiveAlerts user={user} />}
        {activeTab === 'model-performance' && <ModelPerformanceDashboard user={user} />}
        {activeTab === 'zim' && <ZimIntelligencePanel user={user} />}

        {/* ========================================================= */}
        {/* Extended master-prompt navigation (per-role functional views) */}
        {/* ========================================================= */}
        {activeTab === 'documents' && <OCRDocumentPage user={user} activeTab="ocr-results" />}
        {activeTab === 'ocr-analysis' && <OCRDocumentPage user={user} activeTab="ocr-forensics" />}
        {activeTab === 'pending' && <PendingClaimsPanel user={user} />}
        {activeTab === 'missing' && <MissingInformationPanel user={user} />}
        {activeTab === 'ai-assistant' && <AIAssistantPanel user={user} />}
        {activeTab === 'allocation' && <ClaimAllocationPanel user={user} />}
        {activeTab === 'high-risk' && <HighRiskClaimsPanel user={user} />}
        {activeTab === 'escalated' && <EscalatedClaimsPanel user={user} />}
        {activeTab === 'ai-risk-analysis' && <AIRiskAnalysisPanel user={user} />}
        {activeTab === 'department-reports' && <DepartmentReportsPanel user={user} />}
        {activeTab === 'performance' && <PerformanceAnalyticsPanel user={user} />}
        {activeTab === 'document-comparison' && <DocumentComparisonPanel user={user} />}
        {activeTab === 'documentation-compliance' && <DocumentationCompliancePanel user={user} />}
        {activeTab === 'policy-verification' && <PolicyVerificationPanel user={user} />}
        {activeTab === 'regulatory-monitoring' && <RegulatoryMonitoringPanel user={user} />}
        {activeTab === 'fraud-trends' && <FraudTrendsPanel user={user} />}
        {activeTab === 'risk-dashboard' && <RiskDashboardPanel user={user} />}
        {activeTab === 'enterprise-risk-overview' && <EnterpriseRiskOverviewPanel user={user} />}
        {activeTab === 'fraud-risk-exposure' && <FraudRiskExposurePanel user={user} />}
        {activeTab === 'emerging-patterns' && <EmergingRiskPatternsPanel user={user} />}
        {activeTab === 'risk-concentration' && <RiskConcentrationPanel user={user} />}
        {activeTab === 'risk-reports' && <RiskReportsPanel user={user} />}
        {activeTab === 'department-management' && <DepartmentManagementPanel user={user} />}
        {activeTab === 'database-monitoring' && <DatabaseMonitoringPanel user={user} />}
        {activeTab === 'api-monitoring' && <APIMonitoringPanel user={user} />}
        {activeTab === 'system-health' && <SystemHealthPanel user={user} />}

      </main>

      {/* NEXA AI Intelligence Assistant (floating chatbot; all queries are role-enforced on the backend) */}
      <NexaAssistant user={user} />

      {/* Modal: Submit Claim */}
      {showClaimModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3.5">
              <div>
                <h3 className="text-lg font-black text-slate-900">Submit Formal Insurance Claim</h3>
                <p className="text-xs text-slate-500">Initiates automated OCR verification and AI risk scoring</p>
              </div>
              <button onClick={() => setShowClaimModal(false)} className="text-slate-400 hover:text-slate-700"><X size={20} /></button>
            </div>

            <form onSubmit={submitClaim} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Policy Number *</label>
                <input
                  type="text"
                  required
                  value={claimForm.policy_number}
                  onChange={e => setClaimForm({ ...claimForm, policy_number: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Claim Type *</label>
                  <select
                    value={claimForm.claim_type}
                    onChange={e => setClaimForm({ ...claimForm, claim_type: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl bg-white font-semibold"
                  >
                    <option value="Death Benefit">Death Benefit</option>
                    <option value="Funeral Expense">Funeral Expense</option>
                    <option value="Accidental Death">Accidental Death</option>
                    <option value="Critical Illness">Critical Illness</option>
                  </select>
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Amount ($) *</label>
                  <input
                    type="number"
                    required
                    value={claimForm.claim_amount}
                    onChange={e => setClaimForm({ ...claimForm, claim_amount: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl font-bold font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Incident Date *</label>
                  <input
                    type="date"
                    required
                    value={claimForm.incident_date}
                    onChange={e => setClaimForm({ ...claimForm, incident_date: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Beneficiary Name</label>
                  <input
                    type="text"
                    value={claimForm.beneficiary_name}
                    onChange={e => setClaimForm({ ...claimForm, beneficiary_name: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Narrative Description</label>
                <textarea
                  rows="2"
                  value={claimForm.description}
                  onChange={e => setClaimForm({ ...claimForm, description: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl"
                />
              </div>

              <div className="pt-3.5 border-t border-slate-100 flex justify-end space-x-2.5">
                <button type="button" onClick={() => setShowClaimModal(false)} className="px-5 py-2.5 border rounded-xl text-slate-600 hover:bg-slate-50 font-bold">Cancel</button>
                <button type="submit" className="px-5 py-2.5 bg-[#0F2744] text-white rounded-xl hover:bg-[#1B3A57] font-bold shadow-md">Submit for Assessment</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: FNOL Notice */}
      {showFnolModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3.5">
              <div>
                <h3 className="text-lg font-black text-slate-900">Log First Notice of Loss (FNOL)</h3>
                <p className="text-xs text-slate-500">Record preliminary report before documentation is completed</p>
              </div>
              <button onClick={() => setShowFnolModal(false)} className="text-slate-400 hover:text-slate-700"><X size={20} /></button>
            </div>

            <form onSubmit={submitFnol} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Policy Number *</label>
                <input
                  type="text"
                  required
                  value={fnolForm.policy_number}
                  onChange={e => setFnolForm({ ...fnolForm, policy_number: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Claimant Name *</label>
                  <input
                    type="text"
                    required
                    value={fnolForm.claimant_name}
                    onChange={e => setFnolForm({ ...fnolForm, claimant_name: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Channel *</label>
                  <select
                    value={fnolForm.reporting_channel}
                    onChange={e => setFnolForm({ ...fnolForm, reporting_channel: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl bg-white font-semibold"
                  >
                    <option value="Branch Walk-In">Branch Walk-In</option>
                    <option value="Digital Portal">Digital Portal</option>
                    <option value="Contact Centre">Contact Centre</option>
                    <option value="Broker Advisory">Broker Advisory</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Event Type *</label>
                  <select
                    value={fnolForm.event_type}
                    onChange={e => setFnolForm({ ...fnolForm, event_type: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl bg-white font-semibold"
                  >
                    <option value="Death Benefit">Death Benefit</option>
                    <option value="Funeral Expense">Funeral Expense</option>
                    <option value="Accidental Death">Accidental Death</option>
                    <option value="Critical Illness">Critical Illness</option>
                  </select>
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Estimated Amount ($) *</label>
                  <input
                    type="number"
                    required
                    value={fnolForm.estimated_amount}
                    onChange={e => setFnolForm({ ...fnolForm, estimated_amount: e.target.value })}
                    className="w-full px-3.5 py-2.5 border rounded-xl font-mono font-bold"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Initial Notes</label>
                <textarea
                  rows="3"
                  value={fnolForm.initial_notes}
                  onChange={e => setFnolForm({ ...fnolForm, initial_notes: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl"
                />
              </div>

              <div className="pt-3.5 border-t border-slate-100 flex justify-end space-x-2.5">
                <button type="button" onClick={() => setShowFnolModal(false)} className="px-5 py-2.5 border rounded-xl text-slate-600 hover:bg-slate-50 font-bold">Cancel</button>
                <button type="submit" className="px-5 py-2.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-black rounded-xl shadow-md">Register FNOL</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Update Investigation */}
      {showInvModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3.5">
              <div>
                <h3 className="text-base font-black text-slate-900">Update Investigation Determination</h3>
                <p className="text-xs text-slate-500">{invCaseData.claim_id}</p>
              </div>
              <button onClick={() => setShowInvModal(false)} className="text-slate-400 hover:text-slate-700"><X size={20} /></button>
            </div>

            <form onSubmit={updateInvestigation} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Determination Status *</label>
                <select
                  value={invCaseData.status}
                  onChange={e => setInvCaseData({ ...invCaseData, status: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl bg-white font-semibold"
                >
                  <option value="in_review">In Review (Evidence Gathering)</option>
                  <option value="escalated">Escalated (Referred to Legal / Forensic)</option>
                  <option value="confirmed_fraud">Confirmed Fraud (Claim Declined)</option>
                  <option value="cleared">Cleared (Legitimate Claim Approved)</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Case Findings / Investigator Notes *</label>
                <textarea
                  rows="4"
                  value={invCaseData.notes}
                  onChange={e => setInvCaseData({ ...invCaseData, notes: e.target.value })}
                  className="w-full px-3.5 py-2.5 border rounded-xl"
                  placeholder="Record verified facts, witness interviews, or fraud evidence..."
                />
              </div>

              <div className="pt-3.5 border-t border-slate-100 flex justify-end space-x-2.5">
                <button type="button" onClick={() => setShowInvModal(false)} className="px-5 py-2.5 border rounded-xl text-slate-600 hover:bg-slate-50 font-bold">Cancel</button>
                <button type="submit" className="px-5 py-2.5 bg-[#0F2744] text-white rounded-xl hover:bg-[#1B3A57] font-bold shadow-md">Save Determination</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// NEW COMPONENTS: New Claim, Notifications, Profile
// ─────────────────────────────────────────────

function NewClaimPanel({ user }) {
  const [form, setForm] = useState({
    policy_number: '',
    claim_type: '',
    claim_amount: '',
    incident_date: '',
    beneficiary_name: '',
    description: '',
  });
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState('');

  const inputCls = 'w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-xs bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors';
  const labelCls = 'block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1';

  const handleChange = (e) => setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(''); setSuccess(null);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
      files.forEach((f) => fd.append('documents', f));
      const res = await apiCall('/claims/submit', { method: 'POST', body: fd });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error: ${res.status}`);
      }
      const data = await res.json();
      // Always show a success state after a successful submit — never leave
      // the page blank even if the response payload is unexpected.
      setSuccess(data && data.claim_id ? data : { claim_id: '', status: 'submitted', message: 'Claim submitted successfully.' });
      setForm({ policy_number: '', claim_type: '', claim_amount: '', incident_date: '', beneficiary_name: '', description: '' });
      setFiles([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Register New Claim</h1>
        <p className="text-xs text-slate-500 mt-0.5">Complete all required fields to submit a new insurance claim</p>
      </div>

      {success && (
        <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-2xl">
          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-green-700">Claim submitted successfully!</p>
            <p className="text-xs text-green-600 mt-0.5">
              Claim ID: <span className="font-mono font-bold">#{String(success.claim_id || '').slice(-8).toUpperCase()}</span>
              {success.status && <> · Status: <span className="font-semibold">{success.status}</span></>}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-2xl">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs font-bold text-red-700">Submission failed</p>
          <p className="text-xs text-red-600 mt-0.5">{error}</p>
        </div>
      )}

      {!success && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">Claim Details</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className={labelCls}>Policy Number *</label>
                <input name="policy_number" required type="text" placeholder="e.g. POL-2024-001234" value={form.policy_number} onChange={handleChange} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Claim Type *</label>
                <select name="claim_type" required value={form.claim_type} onChange={handleChange} className={inputCls}>
                  <option value="">Select…</option>
                  <option value="Death Benefit">Death Benefit</option>
                  <option value="Funeral Expense">Funeral Expense</option>
                  <option value="Accidental Death">Accidental Death</option>
                  <option value="Critical Illness">Critical Illness</option>
                  <option value="Medical Expense">Medical Expense</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Claim Amount (ZAR) *</label>
                <input name="claim_amount" required type="number" min="0" step="0.01" placeholder="0.00" value={form.claim_amount} onChange={handleChange} className={`${inputCls} font-bold font-mono`} />
              </div>
              <div>
                <label className={labelCls}>Incident Date *</label>
                <input name="incident_date" required type="date" value={form.incident_date} onChange={handleChange} className={inputCls} />
              </div>
              <div className="sm:col-span-2">
                <label className={labelCls}>Beneficiary Name *</label>
                <input name="beneficiary_name" required type="text" placeholder="Full name of beneficiary" value={form.beneficiary_name} onChange={handleChange} className={inputCls} />
              </div>
            </div>
            <div>
              <label className={labelCls}>Description</label>
              <textarea name="description" rows={4} placeholder="Describe the incident and circumstances of the claim…" value={form.description} onChange={handleChange} className={`${inputCls} resize-none`} />
            </div>
            <div>
              <label className={labelCls}>Supporting Documents</label>
              <label className="flex flex-col items-center justify-center w-full border-2 border-dashed border-slate-300 rounded-xl p-6 cursor-pointer hover:border-blue-400 hover:bg-blue-50/40 transition-colors bg-slate-50">
                <Upload className="w-6 h-6 text-slate-400 mb-2" />
                <p className="text-xs font-semibold text-slate-600">Click to upload or drag and drop</p>
                <p className="text-[10px] text-slate-400 mt-0.5">PDF, JPG, PNG up to 10MB each</p>
                <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFiles(Array.from(e.target.files))} className="hidden" />
              </label>
              {files.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-slate-100 rounded-lg">
                      <FileText className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                      <span className="text-xs text-slate-700 truncate flex-1">{f.name}</span>
                      <span className="text-[10px] text-slate-400">{(f.size / 1024).toFixed(1)} KB</span>
                      <button type="button" onClick={() => setFiles((p) => p.filter((_, j) => j !== i))} className="p-0.5 text-slate-400 hover:text-red-500 transition-colors">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button type="submit" disabled={submitting} className="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-bold bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm">
                {submitting ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Submitting…</> : <><FileText className="w-3.5 h-3.5" /> Submit Claim</>}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function NotificationsPanel({ user, token, onCountChange }) {
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch('/notifications', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(setNotifs)
      .catch(() => setNotifs([]))
      .finally(() => setLoading(false));
  }, []);
  const markRead = async (id) => {
    await fetch(`/notifications/${id}/read`, { method: 'PUT', headers: { Authorization: `Bearer ${token}` } });
    setNotifs(p => p.map(n => n.id === id ? { ...n, read: true } : n));
    onCountChange && fetch('/notifications/unread-count', { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null).then(d => d && onCountChange(d.unread_count));
  };
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 max-w-3xl">
      <h1 className="text-2xl font-extrabold text-slate-900 mb-2 flex items-center space-x-2"><Activity size={22} className="text-blue-600" /><span>Notifications & Alerts</span></h1>
      <p className="text-xs text-slate-500 mb-4">AI fraud alerts and platform notifications</p>
      {loading ? <div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div> : (
        <div className="divide-y divide-slate-100">
          {notifs.length === 0 ? (
            <div className="py-10 text-center"><AlertCircle className="w-8 h-8 text-slate-300 mx-auto" /><p className="text-slate-400 text-xs mt-2">No notifications</p></div>
          ) : (
            notifs.map(n => (
              <div key={n.id} className={`py-3 flex gap-3 ${n.read ? 'bg-white' : 'bg-blue-50/50 border-l-2 border-l-blue-500'}`}>
                <Activity size={15} className={n.read ? 'text-slate-400' : 'text-blue-600 animate-pulse'} />
                <div className="flex-1">
                  <p className={`text-xs ${n.read ? 'text-slate-500' : 'text-slate-900 font-semibold'}`}>{n.message}</p>
                  <p className="text-[10px] font-mono text-slate-400 mt-0.5">{n.created_at ? new Date(n.created_at).toLocaleString('en-ZA') : ''}</p>
                </div>
                {!n.read && <button onClick={() => markRead(n.id)} className="text-[10px] font-bold text-blue-600">Mark read</button>}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function ProfilePanel({ user, onExit }) {
  const stats = [
    ['Role', user?.role],
    ['Department', user?.department || 'Not assigned'],
    ['Email', user?.email],
    ['Account Status', user?.is_active ? 'Active' : 'Inactive'],
  ];
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 max-w-2xl">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h1 className="text-2xl font-extrabold text-slate-900">User Profile & Department</h1>
        {onExit && (
          <button
            onClick={onExit}
            title="Exit"
            aria-label="Exit"
            className="flex items-center gap-1.5 px-4.5 py-2.5 rounded-xl bg-red-600 text-white font-bold text-xs hover:bg-red-700 shadow-md transition"
          >
            <X size={15} />
            Exit
          </button>
        )}
      </div>
      <div className="flex items-center gap-4 mb-6">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center font-bold text-2xl text-blue-700">{(user?.full_name || user?.username || '?').slice(0, 2).toUpperCase()}</div>
        <div>
          <h2 className="text-lg font-extrabold text-slate-900">{user?.full_name || user?.username}</h2>
          <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider">{user?.role?.replace(/_/g, ' ')} · Dashboard: {user?.dashboard_type || '—'}</p>
        </div>
      </div>
      <div className="space-y-3 border-t border-slate-100 pt-4">
        {stats.map(([k, v]) => (
          <div key={k} className="flex justify-between py-2 border-b border-slate-50">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{k}</span>
            <span className="text-xs font-semibold text-slate-800">{v || '—'}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 p-3 bg-slate-50 rounded-xl text-xs text-slate-500">
        This workspace contains only the data and actions your role is authorised to access. Backend-enforced RBAC applies to all endpoints.
      </div>
    </div>
  );
}