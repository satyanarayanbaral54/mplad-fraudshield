import React from 'react';
import RiskBadge from './RiskBadge';

export default function FlagList({ flags = [] }) {
  if (!flags || flags.length === 0) {
    return (
      <div className="p-6 text-center text-slate-500 bg-slate-900/30 rounded-xl border border-slate-800/50">
        No anomaly flags recorded for this asset.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {flags.map((flag, idx) => (
        <div key={flag.id || idx} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-sm text-slate-200">{flag.flag_type}</span>
              <RiskBadge level={flag.severity} />
              {flag.engine_source && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                  {flag.engine_source}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">{flag.description}</p>
            {flag.evidence && (
              <pre className="mt-2 p-2 rounded bg-slate-950 text-[11px] text-blue-300 font-mono overflow-x-auto">
                {JSON.stringify(flag.evidence, null, 2)}
              </pre>
            )}
          </div>
          {flag.created_at && (
            <span className="text-[10px] text-slate-500 whitespace-nowrap ml-4">
              {new Date(flag.created_at).toLocaleDateString()}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
