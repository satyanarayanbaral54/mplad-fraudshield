import React from 'react';

export default function RiskGauge({ score }) {
  const normalizedScore = Math.min(Math.max(score || 0, 0), 100);
  
  let color = '#10b981'; // green
  if (normalizedScore > 70) color = '#f43f5e'; // red
  else if (normalizedScore > 45) color = '#f97316'; // orange
  else if (normalizedScore > 20) color = '#f59e0b'; // yellow

  return (
    <div className="flex flex-col items-center justify-center p-4 bg-slate-900/50 rounded-2xl border border-slate-800">
      <div className="relative w-32 h-32 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
          <path
            className="text-slate-800"
            strokeWidth="3.8"
            stroke="currentColor"
            fill="none"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            strokeDasharray={`${normalizedScore}, 100`}
            strokeWidth="3.8"
            strokeLinecap="round"
            stroke={color}
            fill="none"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="text-3xl font-extrabold tracking-tight text-white">{normalizedScore.toFixed(0)}</span>
          <span className="text-[10px] uppercase font-semibold text-slate-400">Risk Index</span>
        </div>
      </div>
    </div>
  );
}
