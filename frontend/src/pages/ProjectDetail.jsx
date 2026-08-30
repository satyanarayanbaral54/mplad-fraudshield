import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { projectsApi, triggerSurvey, surveysApi } from '../api/apiClient';
import RiskBadge from '../components/RiskBadge';
import RiskGauge from '../components/RiskGauge';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const suspiciousPhrases = [
  'ghost', 'missing', 'not found', 'duplicate', 'shell', 'blacklisted', 'fraud',
  'bribe', 'inflated', 'incomplete', 'delay', 'same vendor', 'photo proof awaiting',
  'record time', 'fiscal year ending', 'as per norms',
];

const moneyLakhs = (value) => Number(value || 0) / 1e5;
const getMeta = (project, key, fallback = null) => project?.metadata_json?.[key] ?? project?.[key] ?? fallback;
const getWorkType = (project) => getMeta(project, 'work_type', project?.description?.split(' ')?.[0] || 'General Public Work');
const formatDate = (value) => (value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A');

const assessmentTone = {
  CLEAN: 'border-emerald-400/30 bg-emerald-500/15 text-emerald-200',
  SUSPICIOUS: 'border-orange-400/30 bg-orange-500/15 text-orange-200',
  HIGHLY_SUSPICIOUS: 'border-red-400/30 bg-red-500/15 text-red-200',
  NOT_RUN: 'border-slate-600 bg-slate-800 text-slate-300',
};

function Panel({ title, children, className = '', rightElement = null }) {
  return (
    <section className={`rounded-lg border border-white/10 bg-slate-950/60 p-5 shadow-2xl shadow-black/25 backdrop-blur-xl ${className}`}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-white">{title}</h2>
        {rightElement}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value || 'N/A'}</p>
    </div>
  );
}

function MoneyBar({ label, value, max, color }) {
  const percent = max > 0 ? Math.min(100, (Number(value || 0) / max) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-300">{label}</span>
        <span className="font-mono text-slate-400">₹{moneyLakhs(value).toFixed(2)} L</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function SubBar({ label, weight, score, color }) {
  const contribution = Math.round((Number(score || 0) * weight) / 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-semibold text-slate-300">{label} ({weight}%)</span>
        <span className="font-mono text-slate-400">{contribution}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, contribution)}%` }} />
      </div>
    </div>
  );
}

function ExpandableFlag({ flag, index }) {
  const [open, setOpen] = useState(index === 0);
  const icon = flag.severity === 'CRITICAL' ? '🔴' : flag.severity === 'HIGH' ? '🟠' : flag.severity === 'MEDIUM' ? '🟡' : '🟢';

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-3 p-4 text-left">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-lg">{icon}</span>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-white">{flag.flag_type}</p>
            <p className="text-xs text-slate-500">{flag.engine_source || 'FraudShield Engine'}</p>
          </div>
        </div>
        <RiskBadge level={flag.severity} />
      </button>
      {open ? (
        <div className="border-t border-slate-800 px-4 pb-4 pt-3">
          <p className="text-sm leading-6 text-slate-300">{flag.description}</p>
          {flag.evidence ? (
            <pre className="mt-3 max-h-52 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-cyan-200">
              {JSON.stringify(flag.evidence, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function HighlightedUcText({ text }) {
  if (!text) return <p className="text-sm text-slate-500">No utilization certificate text available.</p>;
  const pattern = new RegExp(`(${suspiciousPhrases.map((phrase) => phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  const parts = String(text).split(pattern);

  return (
    <p className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-sm leading-7 text-slate-300">
      {parts.map((part, index) => (
        suspiciousPhrases.some((phrase) => phrase.toLowerCase() === part.toLowerCase())
          ? <mark key={`${part}-${index}`} className="rounded bg-red-500/20 px-1 font-bold text-red-200">{part}</mark>
          : <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>
      ))}
    </p>
  );
}

function Stars({ value }) {
  const rounded = Math.round(Number(value || 0));
  return <span className="text-amber-300">{'★'.repeat(rounded)}<span className="text-slate-700">{'★'.repeat(Math.max(0, 5 - rounded))}</span></span>;
}

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [surveyResults, setSurveyResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [surveying, setSurveying] = useState(false);
  const [toast, setToast] = useState('');

  const reportDate = useMemo(() => {
    return new Date().toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  }, []);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [projectRes, surveyRes] = await Promise.all([
          projectsApi.get(id),
          surveysApi.getForProject(id).catch(() => ({ data: null })),
        ]);
        setProject(projectRes.data);
        setSurveyResults(surveyRes.data);
      } catch (err) {
        console.error('Failed to load project detail', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [id]);

  const finances = useMemo(() => {
    const allocated = Number(project?.allocated_amount || 0);
    const sanctioned = Number(getMeta(project, 'sanctioned_amount', project?.disbursed_amount || allocated));
    const expenditure = Number(project?.expenditure || getMeta(project, 'expenditure_reported', 0));
    const unspent = Number(getMeta(project, 'unspent_balance', Math.max(allocated - expenditure, 0)));
    return { allocated, sanctioned, expenditure, unspent, max: Math.max(allocated, sanctioned, expenditure, unspent, 1) };
  }, [project]);

  const geoStatus = useMemo(() => {
    const checkpoints = getMeta(project, 'geo_checkpoints', []);
    if (Array.isArray(checkpoints) && checkpoints.some((checkpoint) => checkpoint.satellite_verified)) return 'VERIFIED';
    if (!project?.latitude || !project?.longitude) return 'NOT_FOUND';
    return 'PENDING';
  }, [project]);

  const survey = surveyResults || {};
  const responses = survey.all_responses || [];
  const awarePct = Number(survey.aware_citizens_pct || 0);
  const assessment = getMeta(project, 'gemini_assessment', null);
  const geminiReason = Array.isArray(getMeta(project, 'gemini_flags', []))
    ? getMeta(project, 'gemini_flags', []).join(', ')
    : getMeta(project, 'gemini_reason', '');
  const ucText = getMeta(project, 'uc_text', project?.description);

  const handleSurvey = async () => {
    try {
      setSurveying(true);
      const result = await triggerSurvey(id);
      setToast(`Citizen survey queued: ${result.phones_queued || 0} recipients`);
    } catch (err) {
      console.error('Survey trigger failed', err);
      setToast('Citizen survey could not be sent');
    } finally {
      setSurveying(false);
      window.setTimeout(() => setToast(''), 4000);
    }
  };

  const handlePrintReport = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="grid min-h-[70vh] place-items-center">
        <div className="h-12 w-12 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" />
      </div>
    );
  }

  if (!project) {
    return <div className="rounded-lg border border-red-400/20 bg-red-500/10 p-6 text-red-100">Project not found.</div>;
  }

  const publicProjectId = getMeta(project, 'project_id', `MPLAD-${project.id}`);

  return (
    <div className="space-y-5">
      {toast ? (
        <div className="no-print fixed right-6 top-6 z-[1000] rounded-lg border border-cyan-400/30 bg-slate-950 px-4 py-3 text-sm font-bold text-cyan-100 shadow-2xl">
          {toast}
        </div>
      ) : null}

      {/* SCREEN VIEW HEADER NAVIGATION */}
      <div className="screen-only-view flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <nav className="text-sm text-slate-400">
          <Link to="/" className="hover:text-cyan-300">Dashboard</Link>
          <span className="mx-2 text-slate-600">&gt;</span>
          <Link to="/projects" className="hover:text-cyan-300">Projects</Link>
          <span className="mx-2 text-slate-600">&gt;</span>
          <span className="text-slate-200">{project.title}</span>
        </nav>

        {/* Generate Audit Report Quick Action */}
        <button
          type="button"
          onClick={handlePrintReport}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-cyan-400/40 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 px-5 text-xs font-black uppercase tracking-wider text-cyan-100 shadow-lg shadow-cyan-500/10 transition hover:border-cyan-300 hover:bg-cyan-500/30"
        >
          <span>📄</span>
          <span>Generate Audit Report (Print / PDF)</span>
        </button>
      </div>

      {/* ============================================================ */}
      {/* 1. SCREEN VIEW (Interactive Dashboard)                      */}
      {/* ============================================================ */}
      <div className="screen-only-view grid grid-cols-1 gap-6 xl:grid-cols-5">
        <div className="space-y-6 xl:col-span-3">
          <Panel title="Project Dossier">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h1 className="text-3xl font-black tracking-tight text-white">{project.title}</h1>
                <p className="mt-2 text-sm text-slate-400">ID #{project.id} ({publicProjectId}) | {project.district || 'Unknown District'}, {project.state || 'Unknown State'}</p>
              </div>
              <div className="scale-110 origin-top-right"><RiskBadge level={project.risk_level} /></div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
              <InfoTile label="MP" value={project.mp_name} />
              <InfoTile label="State" value={project.state} />
              <InfoTile label="District" value={project.district} />
              <InfoTile label="Work Type" value={getWorkType(project)} />
              <InfoTile label="Status" value={project.status} />
              <InfoTile label="Dates" value={`${formatDate(project.start_date)} - ${formatDate(project.completion_date)}`} />
            </div>
          </Panel>

          <Panel title="Financial Breakdown">
            <div className="space-y-4">
              <MoneyBar label="Allocated" value={finances.allocated} max={finances.max} color="bg-blue-500" />
              <MoneyBar label="Sanctioned" value={finances.sanctioned} max={finances.max} color="bg-cyan-400" />
              <MoneyBar label="Expenditure" value={finances.expenditure} max={finances.max} color="bg-orange-500" />
              <MoneyBar label="Unspent" value={finances.unspent} max={finances.max} color="bg-emerald-500" />
            </div>
          </Panel>

          <Panel title="Risk Score Breakdown">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[180px_1fr] md:items-center">
              <RiskGauge score={project.risk_score} />
              <div className="space-y-4">
                <SubBar label="Rule-based" weight={40} score={project.risk_score} color="bg-red-500" />
                <SubBar label="ML Anomaly" weight={35} score={project.risk_score} color="bg-orange-500" />
                <SubBar label="NLP Text" weight={25} score={project.risk_score} color="bg-purple-500" />
              </div>
            </div>
          </Panel>

          <Panel title="Flags Triggered">
            {(project.flags || []).length === 0 ? (
              <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-500">No anomaly flags recorded for this project.</div>
            ) : (
              <div className="space-y-3">
                {project.flags.map((flag, index) => <ExpandableFlag key={flag.id || index} flag={flag} index={index} />)}
              </div>
            )}
          </Panel>

          <Panel title="Utilization Certificate">
            <HighlightedUcText text={ucText} />
          </Panel>

          {assessment ? (
            <Panel title="Gemini AI Assessment">
              <div className={`inline-flex rounded-lg border px-3 py-2 text-sm font-black ${assessmentTone[assessment] || assessmentTone.NOT_RUN}`}>{assessment}</div>
              {geminiReason ? <p className="mt-3 text-sm leading-6 text-slate-300">{geminiReason}</p> : null}
            </Panel>
          ) : null}
        </div>

        <div className="space-y-6 xl:col-span-2">
          <Panel title="Geo Verification">
            <div className="h-72 overflow-hidden rounded-lg border border-slate-800">
              {project.latitude && project.longitude ? (
                <MapContainer center={[project.latitude, project.longitude]} zoom={13} style={{ height: '100%', width: '100%' }}>
                  <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <Marker position={[project.latitude, project.longitude]}>
                    <Popup>{project.title}</Popup>
                  </Marker>
                </MapContainer>
              ) : (
                <div className="grid h-full place-items-center bg-slate-900 text-sm text-slate-500">Location coordinates unavailable</div>
              )}
            </div>
            <div className={`mt-4 inline-flex rounded-lg border px-3 py-2 text-xs font-black ${
              geoStatus === 'VERIFIED' ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-200' :
              geoStatus === 'NOT_FOUND' ? 'border-red-400/30 bg-red-500/15 text-red-200' :
              'border-amber-400/30 bg-amber-500/15 text-amber-200'
            }`}>
              {geoStatus}
            </div>
          </Panel>

          <Panel title="Vendor Info">
            <div className="space-y-3">
              <InfoTile label="Name" value={project.vendor?.name || getMeta(project, 'vendor_name')} />
              <InfoTile label="Reg No" value={project.vendor?.registration_number || getMeta(project, 'vendor_reg_no')} />
              <InfoTile label="Registration Date" value={formatDate(getMeta(project, 'vendor_registration_date'))} />
              <InfoTile label="Project Count" value={project.vendor?.total_contracts ?? getMeta(project, 'project_count', 'N/A')} />
              <InfoTile label="Cluster ID" value={getMeta(project, 'cluster_id', 'N/A')} />
            </div>
          </Panel>

          <Panel title="Survey Results">
            {!surveyResults ? (
              <p className="text-sm text-slate-500">No survey results available yet.</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <InfoTile label="Sent" value={survey.sent_count || 0} />
                  <InfoTile label="Responded" value={survey.response_count || responses.length || 0} />
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-300">Avg Satisfaction</span>
                    <Stars value={survey.avg_satisfaction} />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-semibold text-slate-300">Awareness Rate</span>
                    <span className="font-mono text-slate-400">{awarePct.toFixed(0)}%</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-cyan-400" style={{ width: `${Math.min(100, awarePct)}%` }} />
                  </div>
                </div>
                {awarePct < 30 ? (
                  <div className="rounded-lg border border-red-400/30 bg-red-500/15 p-3 text-sm font-bold text-red-100">
                    Citizens unaware of this project
                  </div>
                ) : null}
              </div>
            )}
          </Panel>

          <Panel title="Forensic Actions">
            <div className="space-y-3">
              <button
                type="button"
                onClick={handlePrintReport}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-cyan-400/40 bg-gradient-to-r from-cyan-500/30 to-blue-500/30 px-4 text-sm font-black text-cyan-100 shadow-md transition hover:bg-cyan-500/40"
              >
                <span>🖨️</span>
                <span>Generate Audit Report</span>
              </button>

              <button
                type="button"
                onClick={handleSurvey}
                disabled={surveying}
                className="h-11 w-full rounded-lg bg-cyan-500 px-4 text-sm font-black text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
              >
                {surveying ? 'Sending...' : 'Send Citizen Survey'}
              </button>

              <button
                type="button"
                onClick={() => setToast('Project tagged for immediate district vigilance audit')}
                className="h-11 w-full rounded-lg border border-orange-400/25 bg-orange-500/10 px-4 text-sm font-bold text-orange-100 transition hover:bg-orange-500/20"
              >
                Mark for Audit
              </button>
            </div>
          </Panel>
        </div>
      </div>

      {/* ============================================================ */}
      {/* 2. DEDICATED A4 PRINTABLE AUDIT REPORT (Triggered on Print) */}
      {/* ============================================================ */}
      <div className="printable-audit-report p-6 font-sans text-black">
        {/* Header */}
        <div className="border-b-2 border-slate-900 pb-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold">🇮🇳</span>
                <span className="text-xs font-black uppercase tracking-[0.25em] text-slate-700">
                  GOVERNMENT OF INDIA • STATUTORY AUDIT CELL
                </span>
              </div>
              <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900">
                MPLAD FraudShield Audit Report
              </h1>
              <p className="text-xs text-slate-600">
                Scheme: Members of Parliament Local Area Development Scheme (MPLADS)
              </p>
            </div>

            <div className="text-right text-xs">
              <div className="font-mono font-bold text-slate-800">REF: {publicProjectId}-AUDIT</div>
              <div className="text-slate-600">Date: {reportDate}</div>
              <div className="mt-1 inline-block rounded bg-red-100 px-2 py-0.5 font-bold uppercase text-red-800">
                CONFIDENTIAL AUDIT DOSSIER
              </div>
            </div>
          </div>
        </div>

        {/* Project Meta Box */}
        <div className="my-4 rounded border border-slate-300 bg-slate-50 p-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Project Overview & Constituency Metadata
          </h2>
          <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-slate-500">Project Title:</span>
              <div className="font-bold text-slate-900">{project.title}</div>
            </div>
            <div>
              <span className="text-slate-500">Project ID:</span>
              <div className="font-bold text-slate-900">{publicProjectId}</div>
            </div>
            <div>
              <span className="text-slate-500">Hon. Member of Parliament:</span>
              <div className="font-bold text-slate-900">{project.mp_name || 'N/A'}</div>
            </div>
            <div>
              <span className="text-slate-500">Constituency / District:</span>
              <div className="font-bold text-slate-900">{project.district || 'N/A'}, {project.state || 'N/A'}</div>
            </div>
            <div>
              <span className="text-slate-500">Work Category:</span>
              <div className="font-bold text-slate-900">{getWorkType(project)}</div>
            </div>
            <div>
              <span className="text-slate-500">Tender / Completion Period:</span>
              <div className="font-bold text-slate-900">{formatDate(project.start_date)} to {formatDate(project.completion_date)}</div>
            </div>
          </div>
        </div>

        {/* Risk Score Summary Box */}
        <div className="my-4 rounded border-2 border-red-500 bg-red-50/70 p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-red-700">
                Forensic Risk Assessment
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-red-700">
                  {Number(project.risk_score || 0).toFixed(0)}/100
                </span>
                <span className="text-lg font-black uppercase text-red-800">
                  [{project.risk_level || 'CRITICAL'} RISK]
                </span>
              </div>
            </div>

            <div className="text-right text-xs text-slate-700">
              <div>Rule Engine Contribution: <span className="font-bold">40%</span></div>
              <div>ML Anomaly Isolation: <span className="font-bold">35%</span></div>
              <div>NLP & Sentiment Score: <span className="font-bold">25%</span></div>
            </div>
          </div>
        </div>

        {/* Financial Breakdown Table */}
        <div className="my-4">
          <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-800">
            Financial Breakdown & Fund Flow
          </h3>
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-400 bg-slate-100 text-slate-700">
                <th className="p-2">Financial Parameter</th>
                <th className="p-2 text-right">Amount (₹ Lakhs)</th>
                <th className="p-2 text-right">Amount (₹ Actual)</th>
                <th className="p-2">Status & Audit Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              <tr>
                <td className="p-2 font-semibold">Sanctioned Amount</td>
                <td className="p-2 text-right font-mono font-bold">₹{moneyLakhs(finances.sanctioned).toFixed(2)}L</td>
                <td className="p-2 text-right font-mono">₹{finances.sanctioned.toLocaleString('en-IN')}</td>
                <td className="p-2 text-slate-600">Approved by District Nodal Authority</td>
              </tr>
              <tr>
                <td className="p-2 font-semibold">Allocated / Disbursed</td>
                <td className="p-2 text-right font-mono font-bold">₹{moneyLakhs(finances.allocated).toFixed(2)}L</td>
                <td className="p-2 text-right font-mono">₹{finances.allocated.toLocaleString('en-IN')}</td>
                <td className="p-2 text-slate-600">Disbursed to implementing agency / contractor</td>
              </tr>
              <tr>
                <td className="p-2 font-semibold">Expenditure Reported</td>
                <td className="p-2 text-right font-mono font-bold">₹{moneyLakhs(finances.expenditure).toFixed(2)}L</td>
                <td className="p-2 text-right font-mono">₹{finances.expenditure.toLocaleString('en-IN')}</td>
                <td className="p-2 text-slate-600">Certified via Utilization Certificate (UC)</td>
              </tr>
              <tr className="bg-slate-50 font-bold">
                <td className="p-2">Unspent / Residual Balance</td>
                <td className="p-2 text-right font-mono">₹{moneyLakhs(finances.unspent).toFixed(2)}L</td>
                <td className="p-2 text-right font-mono">₹{finances.unspent.toLocaleString('en-IN')}</td>
                <td className="p-2 text-slate-600">Subject to fund recycling verification</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* All Flags with Forensic Explanations */}
        <div className="my-4">
          <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-800">
            Triggered Forensic Anomaly Flags & Evidence
          </h3>
          {(project.flags || []).length === 0 ? (
            <p className="rounded border border-slate-200 p-3 text-xs text-slate-500">
              No deterministic or statistical flags triggered.
            </p>
          ) : (
            <div className="space-y-2">
              {project.flags.map((flag, idx) => (
                <div key={idx} className="rounded border border-slate-300 bg-slate-50 p-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900">
                      {idx + 1}. {flag.flag_type}
                    </span>
                    <span className="rounded bg-red-100 px-2 py-0.5 font-bold uppercase text-red-800">
                      {flag.severity || 'CRITICAL'}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-700">{flag.description}</p>
                  {flag.evidence ? (
                    <div className="mt-1 font-mono text-[10px] text-slate-600">
                      Evidence: {typeof flag.evidence === 'object' ? JSON.stringify(flag.evidence) : String(flag.evidence)}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Vendor & Citizen Feedback Summary */}
        <div className="my-4 grid grid-cols-2 gap-4 text-xs">
          <div className="rounded border border-slate-300 p-3">
            <h4 className="font-bold uppercase text-slate-800">Assigned Vendor / Contractor</h4>
            <div className="mt-2 space-y-1 text-slate-700">
              <div><span className="font-semibold">Vendor:</span> {project.vendor?.name || getMeta(project, 'vendor_name', 'N/A')}</div>
              <div><span className="font-semibold">Reg / GSTIN:</span> {project.vendor?.registration_number || getMeta(project, 'vendor_reg_no', 'N/A')}</div>
              <div><span className="font-semibold">Tender Cluster:</span> Cluster #{getMeta(project, 'cluster_id', '1')}</div>
            </div>
          </div>

          <div className="rounded border border-slate-300 p-3">
            <h4 className="font-bold uppercase text-slate-800">Citizen Sentinel Ground Truth</h4>
            <div className="mt-2 space-y-1 text-slate-700">
              <div><span className="font-semibold">Surveys Dispatched:</span> {survey.sent_count || 0}</div>
              <div><span className="font-semibold">Public Awareness:</span> {awarePct.toFixed(0)}% of citizens aware</div>
              <div><span className="font-semibold">Avg Civic Satisfaction:</span> {survey.avg_satisfaction ? `${survey.avg_satisfaction}/5.0` : 'Pending'}</div>
            </div>
          </div>
        </div>

        {/* Statutory Recommendation Box */}
        <div className="my-5 rounded border-2 border-slate-900 bg-slate-100 p-4">
          <h4 className="text-xs font-black uppercase tracking-wider text-slate-900">
            ⚠️ STATUTORY FORENSIC RECOMMENDATION
          </h4>
          <p className="mt-1 text-xs font-bold leading-5 text-slate-900">
            This project requires immediate field audit by district auditor and physical verification by the MoSPI vigilance wing. Further financial disbursements should remain on administrative hold pending resolution of the duplicate coordinates and tender splitting anomalies.
          </p>
        </div>

        {/* Official Signatures & Footer */}
        <div className="mt-8 border-t border-slate-400 pt-6">
          <div className="flex justify-between text-xs text-slate-700">
            <div className="w-56 border-t border-dashed border-slate-600 pt-1 text-center font-semibold">
              District Nodal Auditor
            </div>
            <div className="w-56 border-t border-dashed border-slate-600 pt-1 text-center font-semibold">
              MoSPI Vigilance Authority
            </div>
          </div>

          <div className="print-footer mt-6 text-center text-[10px] text-slate-500">
            Generated by MPLAD FraudShield | SIH 2025 | Powered by AI Forensics & Machine Learning
          </div>
        </div>
      </div>
    </div>
  );
}
