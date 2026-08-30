import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toUpperCase();
    console.info(`[API] ${method} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.message;
    console.error(`[API ERROR] ${status || 'NETWORK'}: ${detail}`);
    return Promise.reject(error);
  }
);

export const fetchDashboardSummary = async () => {
  const response = await api.get('/dashboard/summary');
  return response.data;
};

export const fetchProjects = async (filters = {}) => {
  const response = await api.get('/projects', { params: filters });
  return response.data;
};

export const fetchProjectDetail = async (id) => {
  const response = await api.get(`/projects/${id}`);
  return response.data;
};

export const fetchVendorNetwork = async () => {
  const response = await api.get('/dashboard/network');
  return response.data;
};

export const fetchMapData = async () => {
  const response = await api.get('/dashboard/map');
  return response.data;
};

export const triggerSurvey = async (projectId) => {
  const response = await api.post(`/survey/trigger/${projectId}`);
  return response.data;
};

export const fetchSurveyResults = async (projectId) => {
  const response = await api.get(`/survey/${projectId}/results`);
  return response.data;
};

export const uploadDataset = async (file) => {
  const formData = file instanceof FormData ? file : new FormData();
  if (!(file instanceof FormData)) {
    formData.append('file', file);
  }
  const response = await api.post('/ingest/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const useSampleData = async () => {
  const response = await api.post('/ingest/use-sample');
  return response.data;
};

export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats'),
  getRiskDistribution: () => api.get('/dashboard/risk-distribution'),
  getStateWise: () => api.get('/dashboard/state-wise'),
  getRecentFlags: (limit = 10) => api.get('/dashboard/recent-flags', { params: { limit } }),
  getNetwork: () => api.get('/dashboard/network'),
  getMap: () => api.get('/dashboard/map'),
};

export const projectsApi = {
  list: (params) => api.get('/projects', { params }),
  get: (id) => api.get(`/projects/${id}`),
  search: (q) => api.get('/projects/search', { params: { q } }),
  analyze: (id) => api.post(`/projects/${id}/analyze`),
  getFlags: (id) => api.get(`/projects/${id}/flags`),
};

export const vendorsApi = {
  list: (params) => api.get('/vendors', { params }),
  get: (id) => api.get(`/vendors/${id}`),
  getNetwork: () => api.get('/vendors/network'),
};

export const surveysApi = {
  list: (params) => api.get('/survey', { params }),
  getForProject: (projectId) => api.get(`/survey/${projectId}/results`),
  submitPublic: (projectId, data) => api.post(`/survey/${projectId}/respond`, data),
  trigger: (projectId) => api.post(`/survey/trigger/${projectId}`),
  link: (projectId) => api.get(`/survey/link/${projectId}`),
};

export const ingestionApi = {
  uploadCsv: (formData) => api.post('/ingest/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  seedDemo: () => api.post('/ingest/use-sample'),
};

export const demoApi = {
  startDemo: () => api.post('/demo/start'),
};

export const getWebSocketUrl = (path = '/ws/live-flags') => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'localhost:8000'
    : window.location.host;
  return `${protocol}//${host}${path.startsWith('/') ? path : `/${path}`}`;
};

export default api;
