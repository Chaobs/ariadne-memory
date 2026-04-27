/**
 * D3Graph — Interactive knowledge graph visualization
 * Features: zoom/pan/drag, type filtering, node search, highlighting, PNG export
 *
 * BUG FIX (v0.7.3): Nodes were jumping/resetting whenever searchQuery,
 * highlightedNodeId, or onNodeHighlight changed, because those values were all
 * in the D3 useEffect dependency array, causing the entire simulation to be
 * torn down and rebuilt on every keystroke or click.
 *
 * Fix strategy:
 * 1. The "build simulation" effect ONLY depends on [data] so the physics
 *    simulation is only recreated when the graph data actually changes.
 * 2. searchQuery filtering is applied by toggling node/edge visibility (opacity
 *    + pointer-events) in a separate effect that does NOT touch the simulation.
 * 3. highlightedNodeId styling (color, size) is applied in its own effect.
 * 4. onNodeHighlight is stored in a ref so its identity never causes re-renders.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { graphApi } from '../api/ariadne';
import { t } from '../i18n';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  description?: string;
  aliases?: string[];
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  label?: string;
  type?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: { entities: number; relations: number };
}

interface D3GraphProps {
  filterType?: string;
  searchQuery?: string;
  onNodeHighlight?: (nodeId: string | null) => void;
  highlightedNodeId?: string | null;
}

const NODE_COLORS: Record<string, string> = {
  PERSON: '#5e6ad2',
  ORGANIZATION: '#2ea44f',
  LOCATION: '#f59e0b',
  CONCEPT: '#e03e3e',
  TECHNOLOGY: '#9333ea',
  EVENT: '#06b6d4',
  WORK: '#ffc107',
  TOPIC: '#607d8b',
  DEFAULT: '#6e6e73',
};

const TYPE_LABELS: Record<string, string> = {
  PERSON: '👤',
  ORGANIZATION: '🏢',
  LOCATION: '💡',
  CONCEPT: '📍',
  TECHNOLOGY: '🔧',
  EVENT: '📅',
  WORK: '📄',
  TOPIC: '📁',
  DEFAULT: '📌',
};

export default function D3Graph({
  filterType,
  searchQuery = '',
  onNodeHighlight,
  highlightedNodeId,
}: D3GraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null);
  // Store D3 selections in refs so secondary effects can update them
  // without needing to re-run the simulation-building effect.
  const nodeSelRef = useRef<d3.Selection<SVGGElement, GraphNode, SVGGElement, unknown> | null>(null);
  const linkSelRef = useRef<d3.Selection<SVGLineElement, GraphEdge, SVGGElement, unknown> | null>(null);
  const edgeLabelSelRef = useRef<d3.Selection<SVGTextElement, GraphEdge, SVGGElement, unknown> | null>(null);

  // Keep onNodeHighlight in a ref — its identity should never affect effects.
  const onNodeHighlightRef = useRef(onNodeHighlight);
  useEffect(() => { onNodeHighlightRef.current = onNodeHighlight; }, [onNodeHighlight]);

  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [maxNodes, setMaxNodes] = useState(50);

  const loadGraph = useCallback(() => {
    setLoading(true);
    setError('');
    graphApi.getData(maxNodes, filterType)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [maxNodes, filterType]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // ── PNG export ─────────────────────────────────────────────────────────────
  useEffect(() => {
    function handleExportPNG() {
      if (!svgRef.current) return;
      const svg = svgRef.current;
      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(svg);
      const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = svg.clientWidth * 2;
        canvas.height = svg.clientHeight * 2;
        const ctx = canvas.getContext('2d')!;
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const a = document.createElement('a');
        a.download = 'knowledge-graph.png';
        a.href = canvas.toDataURL('image/png');
        a.click();
        URL.revokeObjectURL(url);
      };
      img.src = url;
    }
    window.addEventListener('graph:export-png', handleExportPNG);
    return () => window.removeEventListener('graph:export-png', handleExportPNG);
  }, []);

  // ── BUILD SIMULATION — only when graph data changes ────────────────────────
  // IMPORTANT: searchQuery, highlightedNodeId, and onNodeHighlight are
  // intentionally NOT in this dependency array.  Those values are handled by
  // separate, lightweight effects below that update visual attributes only,
  // without tearing down the simulation.
  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = 550;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    // All nodes participate in the simulation; searchQuery filtering is handled
    // visually via opacity in a separate effect.
    const displayNodes: GraphNode[] = data.nodes.map(n => ({ ...n }));
    const displayEdges: GraphEdge[] = data.edges.map(e => ({ ...e }));

    if (displayNodes.length === 0) return;

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

    // Drop shadow filter
    const filter = defs.append('filter')
      .attr('id', 'shadow')
      .attr('x', '-20%').attr('y', '-20%')
      .attr('width', '140%').attr('height', '140%');
    filter.append('feDropShadow')
      .attr('dx', 0).attr('dy', 2)
      .attr('stdDeviation', 3)
      .attr('flood-opacity', 0.2);

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

    // Force simulation
    const simulation = d3.forceSimulation<GraphNode>(displayNodes)
      .force('link', d3.forceLink<GraphNode, GraphEdge>(displayEdges)
        .id(d => d.id)
        .distance(120)
      )
      .force('charge', d3.forceManyBody().strength(-350))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));
    simulationRef.current = simulation;

    // Edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(displayEdges)
      .join('line')
      .attr('stroke', '#ccc')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)');

    // Edge labels
    const edgeLabel = g.append('g')
      .attr('class', 'edge-labels')
      .selectAll('text')
      .data(displayEdges.filter(e => e.label))
      .join('text')
      .attr('font-size', 10)
      .attr('fill', '#888')
      .attr('text-anchor', 'middle')
      .text(d => d.label || '');

    // Node groups
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(displayNodes)
      .join('g')
      .attr('cursor', 'pointer');

    // Store selections in refs for secondary effects
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    nodeSelRef.current = node as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    linkSelRef.current = link as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    edgeLabelSelRef.current = edgeLabel as any;

    // Drag behavior
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

    // Node circles — default (un-highlighted) style
    node.append('circle')
      .attr('r', d => d.type ? 16 : 12)
      .attr('fill', d => NODE_COLORS[d.type?.toUpperCase()] || NODE_COLORS.DEFAULT)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('filter', 'url(#shadow)');

    // Node emoji labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('font-size', d => d.type ? 12 : 10)
      .text(d => TYPE_LABELS[d.type?.toUpperCase()] || TYPE_LABELS.DEFAULT);

    // Node text labels
    node.append('text')
      .attr('class', 'node-label')
      .attr('text-anchor', 'middle')
      .attr('dy', 32)
      .attr('font-size', 11)
      .attr('font-weight', '500')
      .attr('fill', '#333')
      .text(d => d.label.length > 20 ? d.label.slice(0, 18) + '…' : d.label)
      .attr('paint-order', 'stroke')
      .attr('stroke', '#fafafa')
      .attr('stroke-width', 3);

    // Highlight connected edges when a node is hovered
    node.on('mouseover', function(_event, d) {
      link.attr('stroke', e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
        return (src === d.id || tgt === d.id) ? '#4CAF50' : '#ccc';
      }).attr('stroke-width', e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
        return (src === d.id || tgt === d.id) ? 2.5 : 1.5;
      });
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', 20);
    }).on('mouseout', function(_event, d) {
      link.attr('stroke', '#ccc').attr('stroke-width', 1.5);
      // Restore to the current highlighted radius (read from data attribute
      // set by the highlight effect, falling back to default).
      const isHighlighted = (d as GraphNode & { _highlighted?: boolean })._highlighted;
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', isHighlighted ? 22 : (d.type ? 16 : 12));
    });

    // Click handler
    node.on('click', (_event, d) => {
      setSelectedNode(d);
      onNodeHighlightRef.current?.(d.id);
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
      nodeSelRef.current = null;
      linkSelRef.current = null;
      edgeLabelSelRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);  // ← ONLY data; search/highlight handled by dedicated effects below

  // ── SEARCH FILTER — update node/edge visibility only ─────────────────────
  // Does NOT touch the simulation — nodes keep their positions.
  useEffect(() => {
    const node = nodeSelRef.current;
    const link = linkSelRef.current;
    const edgeLabel = edgeLabelSelRef.current;
    if (!node) return;

    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      // Show everything
      node.attr('opacity', 1).attr('pointer-events', 'all');
      link?.attr('opacity', 1);
      edgeLabel?.attr('opacity', 1);
      return;
    }

    // Dim nodes that don't match; highlight matching ones
    const matchingIds = new Set<string>();
    node.each(d => {
      if (d.label.toLowerCase().includes(q) || d.type.toLowerCase().includes(q)) {
        matchingIds.add(d.id);
      }
    });

    node
      .attr('opacity', d => matchingIds.has(d.id) ? 1 : 0.15)
      .attr('pointer-events', d => matchingIds.has(d.id) ? 'all' : 'none');

    link?.attr('opacity', e => {
      const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
      const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
      return (matchingIds.has(src) && matchingIds.has(tgt)) ? 1 : 0.05;
    });

    edgeLabel?.attr('opacity', e => {
      const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
      const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
      return (matchingIds.has(src) && matchingIds.has(tgt)) ? 1 : 0;
    });
  }, [searchQuery]);

  // ── HIGHLIGHT STYLE — update node colors/sizes only ──────────────────────
  // Does NOT touch the simulation — nodes keep their positions.
  useEffect(() => {
    const node = nodeSelRef.current;
    if (!node) return;

    node.each(function(d) {
      const g = d3.select(this);
      const isHighlighted = highlightedNodeId === d.id;
      // Attach flag for mouseout handler
      (d as GraphNode & { _highlighted?: boolean })._highlighted = isHighlighted;

      g.select('circle')
        .attr('r', isHighlighted ? 22 : (d.type ? 16 : 12))
        .attr('fill', isHighlighted
          ? '#4CAF50'
          : (NODE_COLORS[d.type?.toUpperCase()] || NODE_COLORS.DEFAULT))
        .attr('stroke', isHighlighted ? '#2E7D32' : '#fff')
        .attr('stroke-width', isHighlighted ? 3 : 2);

      g.select('text.node-label')
        .attr('font-weight', isHighlighted ? 'bold' : '500')
        .attr('fill', isHighlighted ? '#1a1a1a' : '#333');
    });
  }, [highlightedNodeId]);

  return (
    <div className="d3-graph-wrapper">
      <div className="graph-toolbar">
        <span className="graph-title">🕸️ Knowledge Graph</span>
        <div className="graph-controls">
          <label>
            {t('graph.max_nodes')}:
            <select value={maxNodes} onChange={e => setMaxNodes(Number(e.target.value))}>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </label>
          <button className="btn-icon" onClick={loadGraph} title={t('graph.refresh')}>🔄</button>
        </div>
        {data && (
          <span className="graph-stats">
            {data.stats?.entities ?? 0} {t('graph.entities')} · {data.stats?.relations ?? 0} {t('graph.relations')}
          </span>
        )}
      </div>

      <div ref={containerRef} className="d3-container">
        {loading && <div className="page-loading">{t('graph.loading')}</div>}
        {error && <div className="empty-state">Error: {error}</div>}
        {!loading && !error && data && data.nodes.length === 0 && (
          <div className="empty-state">
            <p>{t('graph.no_data')}</p>
            <p>Ingest files and enable <strong>Enrich Knowledge Graph</strong> to see entities.</p>
          </div>
        )}
        <svg
          ref={svgRef}
          style={{
            display: data && data.nodes.length > 0 ? 'block' : 'none',
            cursor: 'grab',
          }}
        />
      </div>

      {selectedNode && (
        <div className="node-detail-panel" onClick={() => { setSelectedNode(null); onNodeHighlight?.(null); }}>
          <div className="node-detail-card" onClick={e => e.stopPropagation()}>
            <div className="node-detail-header">
              <span className="node-detail-icon">
                {TYPE_LABELS[selectedNode.type?.toUpperCase()]}
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
              {selectedNode.description && (
                <div className="node-detail-row">
                  <span className="label">Description:</span>
                  <span>{selectedNode.description}</span>
                </div>
              )}
            </div>
            <button className="btn-primary" onClick={() => { setSelectedNode(null); onNodeHighlight?.(null); }}>
              {t('common.close')}
            </button>
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
