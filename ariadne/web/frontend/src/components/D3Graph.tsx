/**
 * D3Graph — Interactive knowledge graph visualization
 * Uses D3.js force-directed layout with zoom/pan/drag
 */

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { graphApi } from '../api/ariadne';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  label?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: { entities: number; relations: number };
}

const NODE_COLORS: Record<string, string> = {
  PERSON: '#5e6ad2',
  ORGANIZATION: '#2ea44f',
  LOCATION: '#f59e0b',
  CONCEPT: '#e03e3e',
  TECHNOLOGY: '#9333ea',
  EVENT: '#06b6d4',
  DEFAULT: '#6e6e73',
};

const TYPE_LABELS: Record<string, string> = {
  PERSON: '👤',
  ORGANIZATION: '🏢',
  LOCATION: '📍',
  CONCEPT: '💡',
  TECHNOLOGY: '🔧',
  EVENT: '📅',
  DEFAULT: '📌',
};

export default function D3Graph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [maxNodes, setMaxNodes] = useState(50);

  useEffect(() => {
    loadGraph();
  }, [maxNodes]);

  function loadGraph() {
    setLoading(true);
    setError('');
    graphApi.getData(maxNodes)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 700;
    const height = 500;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    // Defs: arrow markers
    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#999');

    // Zoom & pan
    const g = svg.append('g');

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        })
    );

    // Background
    g.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', '#fafafa');

    // Nodes and edges data
    const nodes: GraphNode[] = data.nodes.map(n => ({ ...n }));
    const edges: GraphEdge[] = data.edges.map(e => ({ ...e }));

    if (nodes.length === 0) return;

    // Force simulation
    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphEdge>(edges)
        .id(d => d.id)
        .distance(100)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // Edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#ccc')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)');

    // Edge labels
    const edgeLabel = g.append('g')
      .attr('class', 'edge-labels')
      .selectAll('text')
      .data(edges.filter(e => e.label))
      .join('text')
      .attr('font-size', 10)
      .attr('fill', '#888')
      .attr('text-anchor', 'middle')
      .text(d => d.label || '');

    // Node groups
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('cursor', 'pointer');

    // Drag behavior — use any to avoid strict D3 type incompatibility
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const dragBehavior = d3.drag<any, GraphNode>()
      .on('start', (event: d3.D3DragEvent<any, GraphNode, GraphNode>, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event: d3.D3DragEvent<any, GraphNode, GraphNode>, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event: d3.D3DragEvent<any, GraphNode, GraphNode>, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    node.call(dragBehavior as any);

    // Node circles
    node.append('circle')
      .attr('r', d => d.type ? 16 : 12)
      .attr('fill', d => NODE_COLORS[d.type?.toUpperCase()] || NODE_COLORS.DEFAULT)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))');

    // Node emoji labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('font-size', d => d.type ? 12 : 10)
      .text(d => TYPE_LABELS[d.type?.toUpperCase()] || TYPE_LABELS.DEFAULT);

    // Node text labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 32)
      .attr('font-size', 11)
      .attr('fill', '#333')
      .attr('font-weight', 500)
      .text(d => d.label.length > 20 ? d.label.slice(0, 18) + '…' : d.label);

    // Click handler
    node.on('click', (_event, d) => {
      setSelectedNode(d);
    });

    // Hover effect
    node.on('mouseover', function() {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', 20);
    }).on('mouseout', function(_event, d) {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', d.type ? 16 : 12);
    });

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x ?? 0)
        .attr('y1', d => (d.source as GraphNode).y ?? 0)
        .attr('x2', d => (d.target as GraphNode).x ?? 0)
        .attr('y2', d => (d.target as GraphNode).y ?? 0);

      edgeLabel
        .attr('x', d => (((d.source as GraphNode).x ?? 0) + ((d.target as GraphNode).x ?? 0)) / 2)
        .attr('y', d => (((d.source as GraphNode).y ?? 0) + ((d.target as GraphNode).y ?? 0)) / 2);

      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [data]);

  return (
    <div className="d3-graph-wrapper">
      <div className="graph-toolbar">
        <span className="graph-title">🕸️ Knowledge Graph</span>
        <div className="graph-controls">
          <label>
            Max nodes:
            <select value={maxNodes} onChange={e => setMaxNodes(Number(e.target.value))}>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </label>
          <button className="btn-icon" onClick={loadGraph} title="Refresh">🔄</button>
        </div>
        {data && (
          <span className="graph-stats">
            {data.stats?.entities ?? 0} entities · {data.stats?.relations ?? 0} relations
          </span>
        )}
      </div>

      <div ref={containerRef} className="d3-container">
        {loading && <div className="page-loading">Loading graph...</div>}
        {error && <div className="empty-state">Error: {error}</div>}
        {!loading && !error && data && data.nodes.length === 0 && (
          <div className="empty-state">
            <p>No entities in the knowledge graph yet.</p>
            <p>Go to <strong>Ingest</strong> and enable "Enrich Knowledge Graph" when ingesting files.</p>
          </div>
        )}
        <svg ref={svgRef} style={{ display: data && data.nodes.length > 0 ? 'block' : 'none' }} />
      </div>

      {selectedNode && (
        <div className="node-detail-panel" onClick={() => setSelectedNode(null)}>
          <div className="node-detail-card" onClick={e => e.stopPropagation()}>
            <div className="node-detail-header">
              <span className="node-detail-icon">
                {NODE_COLORS[selectedNode.type?.toUpperCase()] && TYPE_LABELS[selectedNode.type?.toUpperCase()]}
              </span>
              <h3>{selectedNode.label}</h3>
            </div>
            <div className="node-detail-body">
              <div className="node-detail-row">
                <span className="label">ID:</span>
                <code>{selectedNode.id}</code>
              </div>
              <div className="node-detail-row">
                <span className="label">Type:</span>
                <span className="type-badge">{selectedNode.type || 'Unknown'}</span>
              </div>
            </div>
            <button className="btn-primary" onClick={() => setSelectedNode(null)}>Close</button>
          </div>
        </div>
      )}

      <div className="graph-legend">
        {Object.entries(TYPE_LABELS).filter(([k]) => k !== 'DEFAULT').map(([type, emoji]) => (
          <span key={type} className="legend-item">
            <span className="legend-dot" style={{ background: NODE_COLORS[type] }} />
            {emoji} {type.charAt(0) + type.slice(1).toLowerCase()}
          </span>
        ))}
      </div>
    </div>
  );
}
