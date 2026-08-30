import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CircleMarker, MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { dashboardApi } from '../api/apiClient';

const RISK_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const RISK_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#facc15',
  LOW: '#22c55e',
};

const markerStyle = document.createElement('style');
markerStyle.innerHTML = `
  .risk-marker { width: 18px; height: 18px; border-radius: 999px; border: 2px solid white; box-shadow: 0 0 0 3px rgba(15, 23, 42, .55), 0 10px 24px rgba(0,0,0,.35); }
  .risk-marker-critical { animation: riskPulse 1.4s infinite; }
  .ghost-marker { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 999px; border: 2px solid #fecaca; background: #7f1d1d; color: white; font-weight: 900; box-shadow: 0 0 0 4px rgba(239, 68, 68, .24); }
  @keyframes riskPulse { 0% { box-shadow: 0 0 0 0 rgba(239,68,68,.55), 0 10px 24px rgba(0,0,0,.35); } 70% { box-shadow: 0 0 0 14px rgba(239,68,68,0), 0 10px 24px rgba(0,0,0,.35); } 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0), 0 10px 24px rgba(0,0,0,.35); } }
`;
if (typeof document !== 'undefined' && !document.getElementById('geo-risk-marker-style')) {
  markerStyle.id = 'geo-risk-marker-style';
  document.head.appendChild(markerStyle);
}

const createRiskIcon = (level) => L.divIcon({
  className: '',
  html: `<div class="risk-marker ${level === 'CRITICAL' ? 'risk-marker-critical' : ''}" style="background:${RISK_COLORS[level] || '#64748b'}"></div>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
  popupAnchor: [0, -10],
});

const ghostIcon = L.divIcon({
  className: '',
  html: '<div class="ghost-marker">X</div>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -12],
});

const getWorkType = (project) => project.work_type || project.metadata_json?.work_type || 'General';
const getGeoStatus = (project) => String(project.geo_status || project.geo_verification_status || 'PENDING').toUpperCase();
const amountLakhs = (project) => Number(project.amount || project.sanctioned_amount || project.allocated_amount || 0) / 1e5;

function Legend() {
  return (
    <div className="absolute right-4 top-4 z-[500] rounded-lg border border-white/10 bg-slate-950/90 p-4 text-xs text-slate-300 shadow-2xl backdrop-blur-xl">
      <p className="mb-3 font-black uppercase tracking-wider text-white">Legend</p>
      <div className="space-y-2">
        {RISK_LEVELS.map((level) => (
          <div key={level} className="flex items-center gap-2">
            <span className="h-3.5 w-3.5 rounded-full border border-white" style={{ background: RISK_COLORS[level] }} />
            {level}
          </div>
        ))}
        <div className="flex items-center gap-2"><span className="grid h-4 w-4 place-items-center rounded-full bg-red-900 text-[10px] font-black text-white">X</span> Ghost Project</div>
      </div>
    </div>
  );
}

function HeatmapLayer({ projects }) {
  const clusters = useMemo(() => {
    const grouped = new Map();
    projects.forEach((project) => {
      const lat = Number(project.latitude);
      const lng = Number(project.longitude);
      const key = `${Math.round(lat * 2) / 2}:${Math.round(lng * 2) / 2}`;
      const current = grouped.get(key) || { lat: 0, lng: 0, count: 0, riskSum: 0, amount: 0 };
      current.lat += lat;
      current.lng += lng;
      current.count += 1;
      current.riskSum += Number(project.risk_score || 0);
      current.amount += amountLakhs(project);
      grouped.set(key, current);
    });

    return Array.from(grouped.values()).map((cluster) => ({
      ...cluster,
      lat: cluster.lat / cluster.count,
      lng: cluster.lng / cluster.count,
      avgRisk: cluster.riskSum / cluster.count,
    }));
  }, [projects]);

  return clusters.map((cluster) => (
    <CircleMarker
      key={`${cluster.lat}-${cluster.lng}`}
      center={[cluster.lat, cluster.lng]}
      radius={Math.min(42, 10 + cluster.count * 5)}
      pathOptions={{
        color: cluster.avgRisk >= 70 ? '#ef4444' : cluster.avgRisk >= 45 ? '#f97316' : '#22c55e',
        fillColor: cluster.avgRisk >= 70 ? '#ef4444' : cluster.avgRisk >= 45 ? '#f97316' : '#22c55e',
        fillOpacity: 0.35,
        weight: 2,
      }}
    >
      <Popup>
        <div className="space-y-1 text-slate-900">
          <p className="font-bold">{cluster.count} projects</p>
          <p>Avg risk: {cluster.avgRisk.toFixed(0)}</p>
          <p>Amount: ₹{cluster.amount.toFixed(2)} L</p>
        </div>
      </Popup>
    </CircleMarker>
  ));
}

export default function GeoMap() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [riskLevels, setRiskLevels] = useState(RISK_LEVELS);
  const [state, setState] = useState('');
  const [workType, setWorkType] = useState('');
  const [viewMode, setViewMode] = useState('markers');
  const [ghostOnly, setGhostOnly] = useState(false);

  useEffect(() => {
    const loadMap = async () => {
      try {
        setLoading(true);
        const response = await dashboardApi.getMap();
        setProjects((response.data || []).filter((project) => project.latitude && project.longitude));
      } catch (err) {
        console.error('Failed to load geo map', err);
      } finally {
        setLoading(false);
      }
    };

    loadMap();
  }, []);

  const states = useMemo(() => Array.from(new Set(projects.map((project) => project.state).filter(Boolean))).sort(), [projects]);
  const workTypes = useMemo(() => Array.from(new Set(projects.map(getWorkType).filter(Boolean))).sort(), [projects]);

  const filteredProjects = useMemo(() => {
    return projects
      .filter((project) => riskLevels.includes(project.risk_level))
      .filter((project) => !state || project.state === state)
      .filter((project) => !workType || getWorkType(project) === workType)
      .filter((project) => !ghostOnly || getGeoStatus(project) === 'NOT_FOUND');
  }, [ghostOnly, projects, riskLevels, state, workType]);

  const toggleRisk = (level) => {
    setRiskLevels((current) => current.includes(level) ? current.filter((item) => item !== level) : [...current, level]);
  };

  return (
    <div className="relative h-[calc(100vh-9rem)] min-h-[680px] overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-2xl shadow-black/30">
      <div className="absolute left-4 top-4 z-[500] w-[min(92vw,720px)] rounded-lg border border-white/10 bg-slate-950/90 p-4 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="min-w-44">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-300">Geo Verification</p>
            <h1 className="mt-1 text-xl font-black text-white">India Project Map</h1>
          </div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            State
            <select value={state} onChange={(event) => setState(event.target.value)} className="mt-2 h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400">
              <option value="">All States</option>
              {states.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Work Type
            <select value={workType} onChange={(event) => setWorkType(event.target.value)} className="mt-2 h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400">
              <option value="">All Types</option>
              {workTypes.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Risk Level
            <div className="mt-2 flex flex-wrap gap-2">
              {RISK_LEVELS.map((level) => (
                <label key={level} className="flex h-9 items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-2 text-[11px] normal-case tracking-normal text-slate-200">
                  <input type="checkbox" checked={riskLevels.includes(level)} onChange={() => toggleRisk(level)} className="rounded border-slate-600 bg-slate-900 accent-cyan-400" />
                  {level}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <button type="button" onClick={() => setViewMode('markers')} className={`rounded-lg border px-3 py-2 font-bold ${viewMode === 'markers' ? 'border-cyan-400/30 bg-cyan-400/15 text-cyan-100' : 'border-slate-700 text-slate-300'}`}>Marker View</button>
          <button type="button" onClick={() => setViewMode('heatmap')} className={`rounded-lg border px-3 py-2 font-bold ${viewMode === 'heatmap' ? 'border-cyan-400/30 bg-cyan-400/15 text-cyan-100' : 'border-slate-700 text-slate-300'}`}>Cluster Heatmap</button>
          <label className={`flex items-center gap-2 rounded-lg border px-3 py-2 font-bold ${ghostOnly ? 'border-red-400/30 bg-red-500/15 text-red-100' : 'border-slate-700 text-slate-300'}`}>
            <input type="checkbox" checked={ghostOnly} onChange={(event) => setGhostOnly(event.target.checked)} className="rounded border-slate-600 bg-slate-900 accent-red-400" />
            Ghost Projects
          </label>
          <span className="ml-auto text-slate-400">{filteredProjects.length} shown</span>
        </div>
      </div>

      <Legend />

      {loading ? (
        <div className="grid h-full place-items-center">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" />
        </div>
      ) : (
        <MapContainer center={[20.5937, 78.9629]} zoom={5} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {viewMode === 'heatmap' ? (
            <HeatmapLayer projects={filteredProjects} />
          ) : (
            filteredProjects.map((project) => (
              <Marker
                key={project.id}
                position={[project.latitude, project.longitude]}
                icon={ghostOnly || getGeoStatus(project) === 'NOT_FOUND' ? ghostIcon : createRiskIcon(project.risk_level)}
              >
                <Popup>
                  <div className="w-56 space-y-2 text-slate-900">
                    <p className="text-sm font-black">{project.work_name || project.title}</p>
                    <p className="text-xs"><b>MP:</b> {project.mp_name || 'N/A'}</p>
                    <p className="text-xs"><b>Risk:</b> {Number(project.risk_score || 0).toFixed(0)} / 100</p>
                    <p className="text-xs"><b>Amount:</b> ₹{amountLakhs(project).toFixed(2)} L</p>
                    <p className="text-xs"><b>Status:</b> {project.status || 'N/A'}</p>
                    <p className="text-xs"><b>Geo:</b> {getGeoStatus(project)}</p>
                    <Link to={`/projects/${project.id}`} className="inline-flex rounded bg-slate-900 px-3 py-1.5 text-xs font-bold text-white">
                      View Details
                    </Link>
                  </div>
                </Popup>
              </Marker>
            ))
          )}
        </MapContainer>
      )}
    </div>
  );
}
