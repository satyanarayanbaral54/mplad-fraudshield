import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { dashboardApi } from '../api/apiClient';

const formatCrore = (value) => {
  const num = Number(value || 0);
  const crores = num > 50000 ? num / 1e7 : num / 100;
  return `₹${crores.toFixed(2)} Cr`;
};
const riskColor = d3.scaleLinear().domain([0, 45, 100]).range(['#22c55e', '#facc15', '#ef4444']).clamp(true);

function Legend() {
  return (
    <div className="absolute right-4 top-4 z-10 rounded-lg border border-white/10 bg-slate-950/85 p-4 text-xs text-slate-300 shadow-2xl backdrop-blur-xl">
      <p className="mb-3 font-black uppercase tracking-wider text-white">Legend</p>
      <div className="space-y-2">
        <div className="flex items-center gap-2"><span className="h-5 w-5 rounded-full bg-red-500" /> High-risk MP</div>
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-orange-500" /> Flagged vendor</div>
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-slate-500" /> Clean vendor</div>
        <div className="flex items-center gap-2"><span className="h-0 w-8 border-t-2 border-dashed border-red-400" /> Collusion cluster</div>
      </div>
    </div>
  );
}

export default function VendorNetwork() {
  const svgRef = useRef(null);
  const wrapperRef = useRef(null);
  const [network, setNetwork] = useState({ nodes: [], links: [], clusters: [], cluster_count: 0 });
  const [loading, setLoading] = useState(true);
  const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    const loadNetwork = async () => {
      try {
        setLoading(true);
        const response = await dashboardApi.getNetwork();
        setNetwork(response.data || { nodes: [], links: [], clusters: [] });
      } catch (err) {
        console.error('Failed to load network graph', err);
      } finally {
        setLoading(false);
      }
    };

    loadNetwork();
  }, []);

  const filteredNetwork = useMemo(() => {
    if (!showFlaggedOnly) return network;
    const flaggedVendors = new Set(network.nodes.filter((node) => node.type === 'vendor' && node.flagged).map((node) => node.id));
    const links = network.links.filter((link) => flaggedVendors.has(link.source) || flaggedVendors.has(link.target));
    const nodeIds = new Set(links.flatMap((link) => [link.source, link.target]));
    const nodes = network.nodes.filter((node) => nodeIds.has(node.id));
    const clusters = (network.clusters || []).filter((cluster) => cluster.member_ids.some((id) => nodeIds.has(id)));
    return { ...network, nodes, links, clusters, cluster_count: clusters.length };
  }, [network, showFlaggedOnly]);

  useEffect(() => {
    if (!svgRef.current || !wrapperRef.current || loading) return undefined;

    const rect = wrapperRef.current.getBoundingClientRect();
    const width = Math.max(900, rect.width);
    const height = Math.max(620, rect.height);
    const nodes = filteredNetwork.nodes.map((node) => ({ ...node }));
    const links = filteredNetwork.links.map((link) => ({ ...link }));
    const clusterLookup = new Map((filteredNetwork.clusters || []).map((cluster) => [cluster.id, cluster]));
    const svg = d3.select(svgRef.current);

    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const zoomLayer = svg.append('g');
    const clusterLayer = zoomLayer.append('g').attr('class', 'clusters');
    const linkLayer = zoomLayer.append('g').attr('class', 'links');
    const nodeLayer = zoomLayer.append('g').attr('class', 'nodes');

    svg.call(
      d3.zoom()
        .scaleExtent([0.35, 3.5])
        .on('zoom', (event) => zoomLayer.attr('transform', event.transform))
    );

    const maxValue = d3.max(links, (link) => Number(link.contract_value || 0)) || 1;
    const linkWidth = d3.scaleSqrt().domain([0, maxValue]).range([1, 8]);

    const link = linkLayer
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) => (d.flagged ? '#ef4444' : '#334155'))
      .attr('stroke-opacity', 0.75)
      .attr('stroke-width', (d) => linkWidth(d.contract_value));

    const node = nodeLayer
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.25).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node
      .append('circle')
      .attr('r', (d) => (d.type === 'mp' ? 20 : 10))
      .attr('fill', (d) => (d.type === 'mp' ? riskColor(d.avg_risk_score || 0) : d.flagged ? '#f97316' : '#64748b'))
      .attr('stroke', (d) => (d.cluster_id ? '#ef4444' : '#0f172a'))
      .attr('stroke-dasharray', (d) => (d.cluster_id ? '4 3' : null))
      .attr('stroke-width', (d) => (d.cluster_id ? 3 : 2));

    node
      .append('text')
      .text((d) => d.name)
      .attr('x', (d) => (d.type === 'mp' ? 26 : 15))
      .attr('y', 4)
      .attr('fill', '#cbd5e1')
      .attr('font-size', 11)
      .attr('font-weight', 700)
      .attr('paint-order', 'stroke')
      .attr('stroke', '#020617')
      .attr('stroke-width', 3);

    node.on('click', (event, d) => {
      const bounds = wrapperRef.current.getBoundingClientRect();
      setTooltip({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
        node: d,
      });
    });

    svg.on('click', (event) => {
      if (event.target === svgRef.current) setTooltip(null);
    });

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance((d) => 120 + Math.min(120, Number(d.contract_value || 0) / 600000)))
      .force('charge', d3.forceManyBody().strength((d) => (d.type === 'mp' ? -520 : -260)))
      .force('collision', d3.forceCollide().radius((d) => (d.type === 'mp' ? 42 : 28)))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const drawClusters = () => {
      const nodeById = new Map(nodes.map((d) => [d.id, d]));
      const clusterData = Array.from(clusterLookup.values()).map((cluster) => {
        const points = cluster.member_ids
          .map((id) => nodeById.get(id))
          .filter(Boolean)
          .map((d) => [d.x, d.y]);
        if (points.length < 3) return null;
        return { ...cluster, hull: d3.polygonHull(points) };
      }).filter((cluster) => cluster?.hull);

      clusterLayer
        .selectAll('path')
        .data(clusterData, (d) => d.id)
        .join('path')
        .attr('d', (d) => `M${d.hull.join('L')}Z`)
        .attr('fill', 'rgba(239, 68, 68, 0.08)')
        .attr('stroke', '#ef4444')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '8 6');
    };

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);

      node.attr('transform', (d) => `translate(${d.x},${d.y})`);
      drawClusters();
    });

    return () => simulation.stop();
  }, [filteredNetwork, loading]);

  return (
    <div className="h-[calc(100vh-9rem)] min-h-[680px] overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-2xl shadow-black/30">
      <div className="grid h-full grid-cols-1 lg:grid-cols-[320px_1fr]">
        <aside className="overflow-y-auto border-r border-white/10 bg-slate-950/95 p-5">
          <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-300">Vendor Network</p>
          <h1 className="mt-2 text-2xl font-black text-white">Collusion Graph</h1>
          <label className="mt-5 flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-sm font-bold text-slate-200">
            Show only flagged vendors
            <input type="checkbox" checked={showFlaggedOnly} onChange={(event) => setShowFlaggedOnly(event.target.checked)} className="h-5 w-5 rounded border-slate-600 bg-slate-900 accent-cyan-400" />
          </label>

          <div className="mt-5 rounded-lg border border-red-400/20 bg-red-500/10 p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-red-200">Collusion Clusters Detected</p>
            <p className="mt-2 text-4xl font-black text-white">{filteredNetwork.cluster_count || 0}</p>
          </div>

          <div className="mt-5 space-y-3">
            {(filteredNetwork.clusters || []).length === 0 ? (
              <p className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-500">No DBSCAN-style collusion clusters detected in this view.</p>
            ) : (
              filteredNetwork.clusters.map((cluster) => (
                <div key={cluster.id} className="rounded-lg border border-red-400/20 bg-slate-900/80 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-sm font-black text-white">{cluster.id}</h2>
                    <span className="rounded-full bg-red-500/15 px-2 py-1 text-[11px] font-bold text-red-200">{cluster.mp_count} MPs</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-slate-200">{cluster.vendor_name}</p>
                  <p className="mt-2 text-xs text-slate-400">{cluster.project_count} projects | {formatCrore(cluster.contract_value)} | Avg risk {cluster.avg_risk_score}</p>
                </div>
              ))
            )}
          </div>
        </aside>

        <main ref={wrapperRef} className="relative min-h-0 bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.10),transparent_32%),#020617]">
          <Legend />
          {loading ? (
            <div className="grid h-full place-items-center">
              <div className="h-12 w-12 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent" />
            </div>
          ) : (
            <svg ref={svgRef} className="h-full w-full" role="img" aria-label="Vendor MP force-directed graph" />
          )}

          {tooltip ? (
            <div className="pointer-events-none absolute z-20 w-72 rounded-lg border border-cyan-300/25 bg-slate-950/95 p-4 text-sm shadow-2xl backdrop-blur-xl" style={{ left: Math.min(tooltip.x + 14, 520), top: Math.max(12, tooltip.y - 20) }}>
              <p className="text-xs font-black uppercase tracking-wider text-cyan-300">{tooltip.node.type === 'mp' ? 'MP' : 'Vendor'}</p>
              <h2 className="mt-1 text-lg font-black text-white">{tooltip.node.name}</h2>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded bg-slate-900 p-2"><span className="text-slate-500">Projects</span><br /><b className="text-white">{tooltip.node.project_count || 0}</b></div>
                <div className="rounded bg-slate-900 p-2"><span className="text-slate-500">Avg Risk</span><br /><b className="text-white">{tooltip.node.avg_risk_score || 0}</b></div>
                <div className="rounded bg-slate-900 p-2"><span className="text-slate-500">Value</span><br /><b className="text-white">{formatCrore(tooltip.node.contract_value)}</b></div>
                <div className="rounded bg-slate-900 p-2"><span className="text-slate-500">Flags</span><br /><b className="text-white">{tooltip.node.flag_count || (tooltip.node.flagged ? 1 : 0)}</b></div>
              </div>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
