import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Label,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { dashboardApi, demoApi, getWebSocketUrl, projectsApi, uploadDataset, useSampleData } from '../api/apiClient';
import RiskBadge from '../components/RiskBadge';

const RISK_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#facc15',
  LOW: '#22c55e',
  UNKNOWN: '#64748b',
};

const riskLevelForScore = (score = 0) => {
  if (score >= 75) return 'CRITICAL';
  if (score >= 55) return 'HIGH';
  if (score >= 30) return 'MEDIUM';
  return 'LOW';
};

const formatNumber = (value) => new Intl.NumberFormat('en-IN').format(Math.round(value || 0));

const chartTooltipStyle = {
  background: 'rgba(2, 6, 23, 0.94)',
  border: '1px solid rgba(148, 163, 184, 0.22)',
  borderRadius: '8px',
  color: '#e2e8f0',
  boxShadow: '0 18px 45px rgba(0, 0, 0, 0.35)',
};

function StatCard({ title, value, subtitle, tone, icon, pulse }) {
  const tones = {
    blue: 'from-blue-500/18 to-cyan-500/5 text-blue-300 border-blue-400/25 shadow-blue-500/10',
    red: 'from-red-500/20 to-rose-500/5 text-red-300 border-red-400/30 shadow-red-500/15',
    orange: 'from-orange-500/18 to-amber-500/5 text-orange-300 border-orange-400/25 shadow-orange-500/10',
    purple: 'from-purple-500/18 to-fuchsia-500/5 text-purple-300 border-purple-400/25 shadow-purple-500/10',
  };

  return (
    <div className={`relative overflow-hidden rounded-lg border bg-gradient-to-br ${tones[tone]} bg-slate-950/70 p-5 shadow-2xl backdrop-blur-xl`}>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/45 to-transparent" />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{title}</p>
          <p className="mt-3 text-3xl font-black text-white">{value}</p>
          {subtitle ? <p className="mt-2 text-xs font-medium text-slate-400">{subtitle}</p> : null}
        </div>
        <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.08] text-lg font-black ${pulse ? 'animate-pulse' : ''}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

function GlassPanel({ title, subtitle, children, className = '', rightElement = null }) {
  return (
    <section className={`rounded-lg border border-white/10 bg-slate-950/58 p-5 shadow-2xl shadow-black/25 backdrop-blur-xl ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-white">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-slate-400">{subtitle}</p> : null}
        </div>
        {rightElement}
      </div>
      {children}
    </section>
  );
}

function SkeletonBlock({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-slate-800/70 ${className}`} />;
}

function LoadingDashboard() {
  return (
    <div className="space-y-6">
      <SkeletonBlock className="h-20" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => <SkeletonBlock key={item} className="h-36" />)}
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <SkeletonBlock className="h-96 xl:col-span-3" />
        <SkeletonBlock className="h-96 xl:col-span-2" />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <SkeletonBlock className="h-96" />
        <SkeletonBlock className="h-96" />
      </div>
    </div>
  );
}

function CenterLabel({ viewBox, total }) {
  const { cx, cy } = viewBox;
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
      <tspan x={cx} dy="-0.1em" className="fill-white text-3xl font-black">{total}</tspan>
      <tspan x={cx} dy="1.7em" className="fill-slate-400 text-[11px] font-semibold uppercase tracking-widest">Projects</tspan>
    </text>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const wsRef = useRef(null);

  const [stats, setStats] = useState(null);
  const [riskDist, setRiskDist] = useState([]);
  const [stateWise, setStateWise] = useState([]);
  const [recentFlags, setRecentFlags] = useState([]);
  const [projects, setProjects] = useState([]);
  const [lastAnalyzed, setLastAnalyzed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);

  // WebSocket & Demo Mode state
  const [wsConnected, setWsConnected] = useState(false);
  const [demoActive, setDemoActive] = useState(false);
  const [demoStep, setDemoStep] = useState(0);
  const [demoTotalSteps, setDemoTotalSteps] = useState(10);
  const [anomaliesDetected, setAnomaliesDetected] = useState(0);
  const [liveToasts, setLiveToasts] = useState([]);
  const [liveStreamFeed, setLiveStreamFeed] = useState([]);
  const [analysisCompleteData, setAnalysisCompleteData] = useState(null);

  const fetchDashboardData = async ({ quiet = false } = {}) => {
    try {
      quiet ? setRefreshing(true) : setLoading(true);
      const [statsRes, distRes, stateRes, flagsRes, projectsRes] = await Promise.all([
        dashboardApi.getStats(),
        dashboardApi.getRiskDistribution(),
        dashboardApi.getStateWise(),
        dashboardApi.getRecentFlags(20),
        projectsApi.list({ limit: 500 }),
      ]);

      setStats(statsRes.data);
      setRiskDist(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((name) => ({ name, value: Number(distRes.data?.[name] || 0) })));
      setStateWise((stateRes.data || []).sort((a, b) => (b.avg_risk_score || 0) - (a.avg_risk_score || 0)).slice(0, 15));
      setRecentFlags(flagsRes.data || []);
      setProjects(projectsRes.data || []);
      setLastAnalyzed(new Date());
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Connect WebSocket for Live Telemetry
  useEffect(() => {
    let reconnectTimeout = null;

    const connectWS = () => {
      try {
        const wsUrl = getWebSocketUrl('/ws/live-flags');
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'CONNECTED') {
              setWsConnected(true);
            } else if (data.type === 'DEMO_STARTED') {
              setDemoActive(true);
              setDemoStep(0);
              setDemoTotalSteps(data.total_steps || 10);
              setAnalysisCompleteData(null);
            } else if (data.type === 'NEW_FLAG') {
              setDemoActive(true);
              setDemoStep(data.step || ((prev) => prev + 1));
              setAnomaliesDetected((prev) => prev + 1);

              // Add toast notification
              const toastId = `${Date.now()}-${Math.random()}`;
              const toastItem = {
                id: toastId,
                ...data,
              };

              setLiveToasts((prev) => [toastItem, ...prev.slice(0, 3)]);

              // Auto-remove toast after 5 seconds
              setTimeout(() => {
                setLiveToasts((prev) => prev.filter((t) => t.id !== toastId));
              }, 5000);

              // Prepend to Live Feed with slide-in
              setLiveStreamFeed((prev) => [
                {
                  id: `live-${Date.now()}-${Math.random()}`,
                  project_id: data.project_id,
                  title: data.title || `MPLAD Project ${data.project_id}`,
                  mp_name: data.mp || 'Hon. MP',
                  topFlag: `${data.flag}: ${data.detail || data.amount}`,
                  risk_level: data.risk_level || 'CRITICAL',
                  risk_score: data.score || 92,
                  amount: data.amount,
                  location: data.location,
                  isLiveStream: true,
                },
                ...prev.slice(0, 14),
              ]);
            } else if (data.type === 'ANALYSIS_COMPLETE') {
              setDemoActive(false);
              setAnalysisCompleteData(data);
              // Refresh background stats
              fetchDashboardData({ quiet: true });
            }
          } catch (err) {
            console.error('Error handling WebSocket message', err);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWS, 4000);
        };

        ws.onerror = () => {
          setWsConnected(false);
          ws.close();
        };
      } catch (e) {
        console.error('WebSocket connection initialization failed', e);
        reconnectTimeout = setTimeout(connectWS, 5000);
      }
    };

    connectWS();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Trigger Demo Mode
  const triggerDemoMode = useCallback(async () => {
    try {
      setDemoActive(true);
      setDemoStep(0);
      setAnomaliesDetected(0);
      setAnalysisCompleteData(null);

      // If WS is ready, send action; otherwise trigger via HTTP
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: 'start_demo' }));
      }
      await demoApi.startDemo();
    } catch (err) {
      console.error('Failed to trigger demo mode', err);
    }
  }, []);

  // Keyboard shortcut: Press 'D' on dashboard
  useEffect(() => {
    const handleKeyDown = (e) => {
      const targetTag = e.target?.tagName?.toUpperCase();
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(targetTag)) return;

      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault();
        triggerDemoMode();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [triggerDemoMode]);

  useEffect(() => {
    fetchDashboardData();
    const interval = window.setInterval(() => fetchDashboardData({ quiet: true }), 30000);
    return () => window.clearInterval(interval);
  }, []);

  const topMps = useMemo(() => {
    const grouped = new Map();
    projects.forEach((project) => {
      const name = project.mp_name || 'Unknown MP';
      const current = grouped.get(name) || { mp_name: name, total: 0, scoreSum: 0, critical: 0, high: 0 };
      const score = Number(project.risk_score || 0);
      current.total += 1;
      current.scoreSum += score;
      current.critical += project.risk_level === 'CRITICAL' ? 1 : 0;
      current.high += project.risk_level === 'HIGH' ? 1 : 0;
      grouped.set(name, current);
    });

    return Array.from(grouped.values())
      .map((mp) => ({
        ...mp,
        avg_risk_score: Number((mp.scoreSum / Math.max(mp.total, 1)).toFixed(1)),
      }))
      .sort((a, b) => b.avg_risk_score - a.avg_risk_score)
      .slice(0, 10);
  }, [projects]);

  const derivedStats = useMemo(() => {
    const critical = riskDist.find((item) => item.name === 'CRITICAL')?.value || 0;
    const fundsAtRisk = projects
      .filter((project) => ['HIGH', 'CRITICAL'].includes(project.risk_level))
      .reduce((sum, project) => sum + Number(project.allocated_amount || project.sanctioned_amount || 0), 0) / 1e7;

    return {
      criticalCount: stats?.critical_count ?? critical,
      fundsAtRisk: stats?.funds_at_risk ?? Number(fundsAtRisk.toFixed(2)),
      avgRiskScore: stats?.avg_risk_score ?? 0,
      totalProjects: stats?.dashboard_stats?.total_projects ?? stats?.total_projects ?? projects.length,
    };
  }, [projects, riskDist, stats]);

  const timelineData = useMemo(() => {
    const buckets = new Map();
    recentFlags.forEach((flag) => {
      const day = flag.created_at ? new Date(flag.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : null;
      if (day) buckets.set(day, (buckets.get(day) || 0) + 1);
    });

    if (buckets.size > 1) {
      return Array.from(buckets.entries()).map(([date, count]) => ({ date, count })).slice(-10);
    }

    return Array.from({ length: 10 }, (_, index) => {
      const date = new Date();
      date.setDate(date.getDate() - (9 - index));
      return {
        date: date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
        count: Math.max(1, Math.round(4 + Math.sin(index * 0.9) * 3 + index * 0.7)),
      };
    });
  }, [recentFlags]);

  // Combined live feed: stream items + DB projects
  const liveFeed = useMemo(() => {
    const flagByProject = new Map();
    recentFlags.forEach((flag) => {
      if (!flagByProject.has(flag.project_id)) flagByProject.set(flag.project_id, flag);
    });

    const staticTop = projects
      .filter((project) => ['CRITICAL', 'HIGH'].includes(project.risk_level))
      .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      .slice(0, 5)
      .map((project) => ({
        id: project.id,
        title: project.title || `Project #${project.id}`,
        mp_name: project.mp_name || 'Unknown MP',
        topFlag: flagByProject.get(project.id)?.flag_type || flagByProject.get(project.id)?.description || 'Composite anomaly score breach',
        risk_level: project.risk_level,
        risk_score: project.risk_score,
        isLiveStream: false,
      }));

    // Prepend live stream items
    return [...liveStreamFeed, ...staticTop].slice(0, 10);
  }, [projects, recentFlags, liveStreamFeed]);

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      await uploadDataset(file);
      await fetchDashboardData();
    } catch (err) {
      console.error('Dataset upload failed', err);
      window.alert('Dataset upload failed.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleSampleData = async () => {
    try {
      setUploading(true);
      await useSampleData();
      await fetchDashboardData();
    } catch (err) {
      console.error('Sample data load failed', err);
      window.alert('Could not load sample data.');
    } finally {
      setUploading(false);
    }
  };

  if (loading && !stats) return <LoadingDashboard />;

  return (
    <div className="space-y-6">
      {/* Real-time Toast Notifications (Bottom Right) */}
      <div className="toast-container pointer-events-none fixed bottom-6 right-6 z-[1000] flex max-w-md flex-col gap-3">
        {liveToasts.map((toast) => (
          <div
            key={toast.id}
            className="animate-toast-slide pointer-events-auto rounded-xl border border-red-500/60 bg-slate-950/95 p-4 shadow-2xl shadow-red-950/50 backdrop-blur-2xl"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="flex h-2.5 w-2.5 rounded-full bg-red-500 animate-ping" />
                <span className="text-[10px] font-black uppercase tracking-widest text-red-400">
                  CRITICAL SIGNAL #{toast.step || 1}
                </span>
              </div>
              <span className="rounded bg-red-500/20 px-2 py-0.5 font-mono text-[11px] font-bold text-red-300">
                Score: {toast.score}
              </span>
            </div>
            <h4 className="mt-2 text-sm font-black text-white">{toast.flag}</h4>
            <p className="mt-1 line-clamp-2 text-xs text-slate-300">{toast.title}</p>
            <div className="mt-2 flex items-center justify-between border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
              <span>{toast.mp}</span>
              <span className="font-bold text-cyan-300">{toast.amount}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Live Analysis / Demo Mode Top Banner */}
      {demoActive ? (
        <div className="relative overflow-hidden rounded-xl border border-red-500/40 bg-gradient-to-r from-red-950/90 via-slate-950/90 to-red-950/90 p-5 shadow-2xl shadow-red-950/50 backdrop-blur-xl">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-red-500/10 via-transparent to-transparent pointer-events-none" />
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3.5">
              <div className="relative flex h-4 w-4 items-center justify-center">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black uppercase tracking-[0.25em] text-red-400">🔴 LIVE TELEMETRY SCANNING ACTIVE</span>
                  <span className="rounded bg-red-500/20 px-2 py-0.5 text-[10px] font-mono font-bold text-red-200">
                    EVENT {demoStep}/{demoTotalSteps}
                  </span>
                </div>
                <p className="mt-0.5 text-sm font-semibold text-slate-200">
                  Scanning 847 national projects across 543 constituencies for fiscal anomalies & collusion
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-2 text-right">
                <div className="text-[10px] font-bold uppercase tracking-wider text-red-300">Live Anomalies</div>
                <div className="font-mono text-xl font-black text-white">{anomaliesDetected} Detected</div>
              </div>
              <button
                type="button"
                onClick={() => setDemoActive(false)}
                className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-xs font-bold text-slate-300 hover:bg-slate-800"
              >
                Dismiss
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-900">
            <div
              className="h-full bg-gradient-to-r from-red-500 via-orange-500 to-amber-400 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(8, (demoStep / demoTotalSteps) * 100))}%` }}
            />
          </div>
        </div>
      ) : null}

      {/* Analysis Complete Modal / Banner */}
      {analysisCompleteData ? (
        <div className="relative overflow-hidden rounded-xl border border-emerald-500/50 bg-gradient-to-r from-emerald-950/90 via-slate-950/95 to-teal-950/90 p-6 shadow-2xl shadow-emerald-950/40 backdrop-blur-2xl">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-4">
              <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-emerald-500/20 text-2xl">
                ✅
              </div>
              <div>
                <span className="text-xs font-black uppercase tracking-[0.25em] text-emerald-400">
                  SIH 2025 • COMPLIANCE AUDIT AUDITING COMPLETE
                </span>
                <h3 className="mt-1 text-xl font-black text-white">
                  {analysisCompleteData.message || 'Analysis Complete — 847 projects scanned, 23 CRITICAL flags raised'}
                </h3>
                <p className="mt-1 text-xs text-slate-300">
                  Full forensic triage executed: Deterministic Rules (₹49L threshold) + Isolation Forest ML + NLP Sentence Plagiarism + OSM Satellite Cross-Check.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-center">
                <div className="text-[10px] font-bold uppercase text-emerald-300">Est. Funds Protected</div>
                <div className="text-base font-black text-white">{analysisCompleteData.funds_saved_estimate || '₹14.8 Cr'}</div>
              </div>
              <button
                type="button"
                onClick={() => setAnalysisCompleteData(null)}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-black text-slate-950 transition hover:bg-emerald-400"
              >
                Close Summary
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Header bar */}
      <div className="flex flex-col gap-4 rounded-lg border border-white/10 bg-slate-950/60 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-cyan-300">MPLAD FraudShield</p>
            {wsConnected ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                LIVE STREAM
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[10px] font-medium text-slate-400">
                OFFLINE CACHE
              </span>
            )}
          </div>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white sm:text-4xl">Integrity Command Center</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Real-time forensic telemetry across 543 parliamentary constituencies with multi-engine anomaly triangulation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Pitch Demo Mode Button */}
          <button
            type="button"
            onClick={triggerDemoMode}
            disabled={demoActive}
            title="Press 'D' on keyboard for instant demo"
            className="group relative inline-flex h-11 items-center justify-center gap-2 overflow-hidden rounded-xl border border-red-500/50 bg-gradient-to-r from-red-600 via-rose-600 to-orange-600 px-5 text-xs font-black uppercase tracking-wider text-white shadow-lg shadow-red-600/30 transition-all duration-300 hover:scale-105 hover:border-red-400 hover:shadow-red-500/50 disabled:opacity-50"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
            </span>
            <span>{demoActive ? 'Analysis Running...' : '🚀 Live Demo Mode'}</span>
            <span className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-[10px] font-bold text-red-200">
              Press D
            </span>
          </button>

          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleUpload} />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-blue-400/30 bg-blue-500/15 px-4 text-xs font-bold text-blue-100 transition hover:bg-blue-500/25 disabled:opacity-60"
          >
            {uploading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-100 border-t-transparent" /> : <span className="text-base">↑</span>}
            Upload Dataset
          </button>
          <button
            type="button"
            onClick={handleSampleData}
            disabled={uploading}
            className="inline-flex h-10 items-center justify-center rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 text-xs font-bold text-emerald-100 transition hover:bg-emerald-500/25 disabled:opacity-60"
          >
            Use Sample Data
          </button>

          <div className="text-xs text-slate-400 sm:text-right">
            <div>Last analyzed</div>
            <div className="font-semibold text-slate-200">{lastAnalyzed ? lastAnalyzed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Pending'}</div>
            {refreshing ? <div className="text-cyan-300">Refreshing...</div> : null}
          </div>
        </div>
      </div>

      {/* Primary KPI stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Total Projects" value={formatNumber(derivedStats.totalProjects)} subtitle="Projects under watch" tone="blue" icon="DB" />
        <StatCard title="CRITICAL Risk" value={formatNumber(derivedStats.criticalCount)} subtitle="Immediate Audit Needed" tone="red" icon="!" pulse />
        <StatCard title="Funds at Risk" value={`₹${derivedStats.fundsAtRisk} Cr`} subtitle="HIGH + CRITICAL projects" tone="orange" icon="₹" />
        <StatCard title="Avg Risk Score" value={`${Number(derivedStats.avgRiskScore || 0).toFixed(1)}/100`} subtitle="Portfolio mean score" tone="purple" icon="∿" />
      </div>

      {/* Top MPs and Risk Distribution */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <GlassPanel title="Top 10 Riskiest MPs" subtitle="Click any bar to open filtered project records" className="xl:col-span-3">
          <div className="h-[390px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topMps} layout="vertical" margin={{ top: 8, right: 36, left: 20, bottom: 8 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#94a3b8" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis type="category" dataKey="mp_name" width={145} stroke="#cbd5e1" tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} />
                <Bar
                  dataKey="avg_risk_score"
                  radius={[0, 8, 8, 0]}
                  name="Avg Risk Score"
                  cursor="pointer"
                  onClick={(data) => navigate(`/projects?mp_name=${encodeURIComponent(data.mp_name)}`)}
                >
                  {topMps.map((entry) => <Cell key={entry.mp_name} fill={RISK_COLORS[riskLevelForScore(entry.avg_risk_score)]} />)}
                  <LabelList dataKey="avg_risk_score" position="right" className="fill-slate-200 text-[11px] font-bold" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>

        <GlassPanel title="Risk Distribution" subtitle="Current project severity mix" className="xl:col-span-2">
          <div className="h-[390px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={riskDist} dataKey="value" nameKey="name" innerRadius={82} outerRadius={128} paddingAngle={3} labelLine={false} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {riskDist.map((entry) => <Cell key={entry.name} fill={RISK_COLORS[entry.name]} />)}
                  <Label content={(props) => <CenterLabel {...props} total={formatNumber(derivedStats.totalProjects)} />} position="center" />
                </Pie>
                <Tooltip contentStyle={chartTooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>
      </div>

      {/* State Wise and Timeline */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <GlassPanel title="State-wise Risk Heatmap" subtitle="Top 15 states by average risk score">
          <div className="h-[390px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stateWise} layout="vertical" margin={{ top: 6, right: 34, left: 22, bottom: 6 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#94a3b8" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis type="category" dataKey="state" width={132} stroke="#cbd5e1" tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} />
                <Bar dataKey="avg_risk_score" name="Avg Risk Score" radius={[0, 8, 8, 0]}>
                  {stateWise.map((entry) => <Cell key={entry.state} fill={RISK_COLORS[riskLevelForScore(entry.avg_risk_score)]} />)}
                  <LabelList dataKey="avg_risk_score" position="right" className="fill-slate-200 text-[11px] font-bold" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>

        <GlassPanel title="Recent Flags Timeline" subtitle="Flags raised per day">
          <div className="h-[390px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timelineData} margin={{ top: 16, right: 24, left: 2, bottom: 8 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke="#94a3b8" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Line type="monotone" dataKey="count" name="Flags" stroke="#38bdf8" strokeWidth={3} dot={{ r: 4, fill: '#0f172a', stroke: '#38bdf8', strokeWidth: 2 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>
      </div>

      {/* Live Feed Panel with Telemetry indicator & Slide-in Animation */}
      <GlassPanel
        title="Live Analysis Feed"
        subtitle="Recent projects flagged by risk engines & real-time telemetry"
        rightElement={
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-red-400 animate-live-dot" />
            <span className="text-[11px] font-bold text-slate-400">
              {anomaliesDetected > 0 ? `${anomaliesDetected} real-time alerts` : 'Listening on live stream'}
            </span>
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {liveFeed.length === 0 ? (
            <div className="col-span-full rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-400">
              No high-risk projects are currently flagged.
            </div>
          ) : (
            liveFeed.map((project, idx) => (
              <button
                key={project.id || idx}
                type="button"
                onClick={() => {
                  if (typeof project.id === 'number' || (typeof project.id === 'string' && !project.id.startsWith('live-'))) {
                    navigate(`/projects/${project.id}`);
                  } else {
                    navigate(`/projects?search=${encodeURIComponent(project.project_id || project.title)}`);
                  }
                }}
                className={`animate-feed-slide relative overflow-hidden rounded-xl border p-4 text-left transition hover:scale-[1.02] ${
                  project.isLiveStream
                    ? 'border-red-500/60 bg-gradient-to-br from-red-950/60 to-slate-950/80 shadow-lg shadow-red-950/40 hover:border-red-400'
                    : 'border-white/10 bg-white/[0.04] hover:border-cyan-300/35 hover:bg-cyan-300/[0.07]'
                }`}
              >
                {project.isLiveStream ? (
                  <div className="absolute right-2 top-2 flex items-center gap-1 rounded bg-red-500/30 px-1.5 py-0.5 text-[9px] font-black uppercase text-red-200">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-pulse" />
                    LIVE
                  </div>
                ) : null}

                <div className="flex items-center justify-between gap-2">
                  <RiskBadge level={project.risk_level} />
                  <span className="font-mono text-xs font-black text-slate-300">{Number(project.risk_score || 0).toFixed(0)}</span>
                </div>
                <h3 className="mt-3 line-clamp-2 min-h-10 text-sm font-bold text-white">{project.title || `Project #${project.id}`}</h3>
                <p className="mt-1 truncate text-xs font-medium text-slate-400">{project.mp_name || 'Unknown MP'}</p>
                <p className="mt-2.5 line-clamp-2 text-xs font-semibold text-orange-300">{project.topFlag}</p>
              </button>
            ))
          )}
        </div>
      </GlassPanel>
    </div>
  );
}
