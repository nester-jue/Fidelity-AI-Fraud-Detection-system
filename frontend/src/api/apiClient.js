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
};
