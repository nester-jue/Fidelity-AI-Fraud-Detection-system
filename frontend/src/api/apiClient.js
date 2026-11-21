/**
 * Centralised API client for NEXA Fraud Detection Platform.
 * All API calls should use this module to ensure consistent
 * authentication header injection and error handling.
 */

const getToken = () => sessionStorage.getItem('fide_token');

export const apiCall = async (path, options = {}) => {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  if (!(options.body instanceof FormData) && options.method && options.method !== 'GET') {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    sessionStorage.removeItem('fide_token');
    window.location.reload();
    throw new Error('Session expired. Please sign in again.');
  }
  return res;
};

export const api = {
  // Auth
  login: (formData) => apiCall('/auth/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: formData }),
  register: (data) => apiCall('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  me: () => apiCall('/auth/me'),
  forgotPassword: (email) => apiCall('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),

  // Profile
  myProfile: () => apiCall('/departmental/my-profile'),

  // Departmental dashboards
  claimsOfficerDashboard: () => apiCall('/departmental/claims-officer'),
  executiveDashboard: () => apiCall('/departmental/executive'),
  complianceDashboard: () => apiCall('/departmental/compliance'),
  fraudInvestigatorDashboard: () => apiCall('/departmental/fraud-investigator'),
  adminDashboard: () => apiCall('/departmental/admin'),

  // Claims
  listClaims: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/claims/${q ? '?' + q : ''}`);
  },
  getClaim: (id) => apiCall(`/claims/${id}`),
  submitClaim: (formData) => apiCall('/claims/submit', { method: 'POST', body: formData }),
  updateClaim: (id, formData) => apiCall(`/claims/${id}`, { method: 'PUT', body: formData }),
  rescoreClaim: (id) => apiCall(`/claims/${id}/score`, { method: 'POST' }),
  listFnol: () => apiCall('/claims/fnol/list'),
  submitFnol: (formData) => apiCall('/claims/fnol', { method: 'POST', body: formData }),

  // Fraud Assessments
  listAssessments: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/fraud/assessments${q ? '?' + q : ''}`);
  },
  getAssessment: (claimId) => apiCall(`/fraud/assessments/${claimId}`),
  highRiskClaims: () => apiCall('/fraud/high-risk'),

  // Forensics
  forensicsOverview: () => apiCall('/forensics/overview'),
  listForensicClaims: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/forensics/claims${q ? '?' + q : ''}`);
  },
  getForensicDetail: (claimId) => apiCall(`/forensics/claims/${claimId}`),
  highRiskForensicQueue: () => apiCall('/forensics/high-risk-queue'),

  // OCR
  ocrOverview: () => apiCall('/ocr/overview'),
  uploadDocument: (formData) => apiCall('/ocr/upload', { method: 'POST', body: formData }),
  listOcrDocuments: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/ocr/documents${q ? '?' + q : ''}`);
  },
  getOcrDocument: (id) => apiCall(`/ocr/documents/${id}`),
  correctOcrField: (id, data) => apiCall(`/ocr/documents/${id}/correct`, { method: 'POST', body: JSON.stringify(data) }),
  verifyOcrDocument: (id) => apiCall(`/ocr/documents/${id}/verify`, { method: 'POST' }),

  // Investigations
  listInvestigations: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/investigations/${q ? '?' + q : ''}`);
  },
  createInvestigation: (data) => apiCall('/investigations/', { method: 'POST', body: JSON.stringify(data) }),
  updateInvestigation: (id, data) => apiCall(`/investigations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Users (admin)
  listUsers: () => apiCall('/users/'),
  createUser: (data) => apiCall('/users/', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id, data) => apiCall(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deactivateUser: (id) => apiCall(`/users/${id}`, { method: 'DELETE' }),

  // Dashboard (executive/legacy)
  dashboardOverview: () => apiCall('/dashboard/overview'),
  networkGraph: () => apiCall('/dashboard/network-graph'),
  modelGovernance: () => apiCall('/dashboard/model-governance'),

  // Audit logs
  auditLogs: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/audit-logs/${q ? '?' + q : ''}`);
  },

  // Lookup
  customers: () => apiCall('/customers'),
  policies: () => apiCall('/policies'),
  notifications: () => apiCall('/notifications'),
  notificationUnreadCount: () => apiCall('/notifications/unread-count'),

  // Claims Officer actions
  requestMissingDocuments: (claimId, reason) => apiCall(`/claims/${claimId}/request-documents`, { method: 'POST', body: JSON.stringify({ reason }) }),
  forwardToInvestigation: (claimId, notes) => apiCall(`/claims/${claimId}/forward-to-investigation`, { method: 'POST', body: JSON.stringify({ notes }) }),
  claimNotes: (claimId) => apiCall(`/claims/${claimId}/notes`),
  addClaimNote: (claimId, note) => apiCall(`/claims/${claimId}/notes`, { method: 'POST', body: JSON.stringify({ note }) }),

  // Management reports (Executive)
  getManagementReports: () => apiCall('/management-reports/'),
  generateManagementReport: (type = 'EXECUTIVE_KPI_SNAPSHOT') => apiCall('/management-reports/', { method: 'POST', body: JSON.stringify({ report_type: type }) }),
  getManagementReport: (id) => apiCall(`/management-reports/${id}`),

  // Compliance reports (Compliance/Admin)
  listComplianceReports: () => apiCall('/compliance-reports/'),
  generateComplianceReport: () => apiCall('/compliance-reports/', { method: 'POST', body: JSON.stringify({ report_type: 'FRAUD_COMPLIANCE_REVIEW' }) }),
  getComplianceReport: (id) => apiCall(`/compliance-reports/${id}`),
  listComplianceExceptions: () => apiCall('/compliance-reports/exceptions'),

  // Fraud risk thresholds (Admin)
  getForensicsRiskThresholds: () => apiCall('/forensics/risk-thresholds'),
  updateForensicsRiskThresholds: (updates) => apiCall('/forensics/risk-thresholds', { method: 'PUT', body: JSON.stringify(updates) }),

  // Investigation details & notes
  investigationDetail: (id) => apiCall(`/investigations/${id}`),
  addInvestigationNote: (id, note) => apiCall(`/investigations/${id}/notes`, { method: 'POST', body: JSON.stringify({ note }) }),
  attachEvidence: (id, documentIds) => apiCall(`/investigations/${id}/`, { method: 'PUT', body: JSON.stringify({ evidence_documents: documentIds }) }).catch(() => null),

  // NEXA AI Intelligence Assistant (role-aware conversational chatbot)
  chatSuggestedQuestions: () => apiCall('/chatbot/suggested-questions'),
  chatSendMessage: (message) => apiCall('/chatbot/messages', { method: 'POST', body: JSON.stringify({ message }) }),
  chatHistory: () => apiCall('/chatbot/history'),
  chatResetHistory: () => apiCall('/chatbot/history', { method: 'DELETE' }),

  // NEXA Sample Claim Forms & Document Forensics (Phase 8)
  listSampleDocuments: () => apiCall('/ocr/sample-documents/'),
  getSampleDocument: (id) => apiCall(`/ocr/sample-documents/${id}`),
  getForensicAnalysis: () => apiCall('/forensics/document-analysis'),

  // Advanced NEXA Intelligence (enterprise upgrade)
  fraudNetworkGraph: () => apiCall('/fraud-network/graph'),
  fraudNetworkInsights: () => apiCall('/fraud-network/insights'),
  claimNetwork: (claimId) => apiCall(`/fraud-network/claim/${claimId}`),
  claimTimeline: (claimId) => apiCall(`/timeline/${claimId}`),
  timelineAll: (claimIds = []) => apiCall(`/timeline/all?claim_ids=${encodeURIComponent(claimIds.join(','))}`),
  evidenceList: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/evidence/${q ? '?' + q : ''}`);
  },
  evidenceTypes: () => apiCall('/evidence/types'),
  evidenceById: (id) => apiCall(`/evidence/${id}`),
  evidenceReport: (invId) => apiCall(`/evidence/report/${invId}`),
  updateEvidenceStatus: (id, status, notes) => apiCall(`/evidence/${id}/status`, { method: 'PUT', body: JSON.stringify({ status, notes }) }),
  historicalClaimAnalysis: (claimId) => apiCall(`/historical/claim/${claimId}`),
  historicalCustomerStats: (customerId) => apiCall(`/historical/customer/${customerId}/stats`),
  predictiveAlerts: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiCall(`/predictive/alerts${q ? '?' + q : ''}`);
  },
  predictiveSummary: () => apiCall('/predictive/summary'),
  predictiveScan: () => apiCall('/predictive/scan', { method: 'POST' }),
  acknowledgeAlert: (id) => apiCall(`/predictive/alerts/${id}/acknowledge`, { method: 'PUT' }),
  resolveAlert: (id, note) => apiCall(`/predictive/alerts/${id}/resolve`, { method: 'PUT', body: JSON.stringify({ resolution_note: note }) }),
  dismissAlert: (id) => apiCall(`/predictive/alerts/${id}/dismiss`, { method: 'PUT' }),
  modelPerformanceDashboard: () => apiCall('/model-performance/dashboard'),
  modelPerformanceVersions: () => apiCall('/model-performance/versions'),
  modelPerformanceHistory: () => apiCall('/model-performance/history'),
  modelPerformanceDataRetention: () => apiCall('/model-performance/data-retention'),
  openRetrainingRequest: (data) => apiCall('/model-performance/requests', { method: 'POST', body: JSON.stringify(data) }),
  listRetrainingRequests: (status = '') => apiCall(`/model-performance/requests?status=${encodeURIComponent(status)}`),
  approveRetraining: (id) => apiCall(`/model-performance/requests/${id}/approve`, { method: 'PUT' }),
  deployRetraining: (id) => apiCall(`/model-performance/requests/${id}/deploy`, { method: 'PUT' }),
  rejectRetraining: (id, reason = '') => apiCall(`/model-performance/requests/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: 'PUT' }),
  zimConfig: () => apiCall('/zim/config'),
  zimRegulatoryRules: () => apiCall('/zim/regulatory-rules'),
  zimValidateNationalId: (value) => apiCall('/zim/validate/national-id', { method: 'POST', body: JSON.stringify({ value }) }),
  zimValidateDate: (value) => apiCall('/zim/normalize-date', { method: 'POST', body: JSON.stringify({ value }) }),
  zimValidateCurrency: (currency) => apiCall('/zim/validate-currency', { method: 'POST', body: JSON.stringify({ currency }) }),
};
