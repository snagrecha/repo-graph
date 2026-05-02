import { useState, useEffect, useRef, useCallback } from 'react';
import { useGraph } from './hooks/useGraph';
import { useWebSocket } from './hooks/useWebSocket';
import { fetchNodeDetail, fetchBlastRadius, fetchOverlay } from './api';
import { GraphCanvas } from './components/GraphCanvas';
import { Sidebar } from './components/Sidebar';
import { NodeDetailPanel } from './components/NodeDetailPanel';
import type {
  NodeDetailResponse,
  BlastRadiusResponse,
  OverlayMode,
  GraphNode,
} from './types';

export default function App() {
  const { nodes, links, loading, error, reload } = useGraph();

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [blastRadius, setBlastRadius] = useState<BlastRadiusResponse | null>(null);

  const [overlayMode, setOverlayMode] = useState<OverlayMode>('none');
  const [overlayData, setOverlayData] = useState<Record<string, unknown> | null>(null);
  const overlayCache = useRef<Map<OverlayMode, Record<string, unknown>>>(new Map());

  const [searchQuery, setSearchQuery] = useState('');

  // Reconnect and reload graph on any websocket message
  const handleWsMessage = useCallback(() => {
    reload();
  }, [reload]);
  useWebSocket(handleWsMessage);

  // Fetch node detail when selection changes
  useEffect(() => {
    if (!selectedNodeId) {
      setNodeDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    fetchNodeDetail(selectedNodeId)
      .then((detail) => {
        if (!cancelled) {
          setNodeDetail(detail);
          setDetailLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedNodeId]);

  // Fetch overlay data when mode changes, with caching
  useEffect(() => {
    if (overlayMode === 'none') {
      setOverlayData(null);
      return;
    }
    const cached = overlayCache.current.get(overlayMode);
    if (cached) {
      setOverlayData(cached);
      return;
    }
    let cancelled = false;
    fetchOverlay(overlayMode as 'complexity' | 'churn' | 'ownership')
      .then((data) => {
        if (!cancelled) {
          overlayCache.current.set(overlayMode, data);
          setOverlayData(data);
        }
      })
      .catch(() => {
        // leave overlayData as null on error
      });
    return () => {
      cancelled = true;
    };
  }, [overlayMode]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNodeId(node.id);
    setBlastRadius(null);
  }, []);

  const handleClose = useCallback(() => {
    setSelectedNodeId(null);
    setNodeDetail(null);
    setBlastRadius(null);
  }, []);

  const handleShowBlastRadius = useCallback((nodeId: string) => {
    fetchBlastRadius(nodeId).then(setBlastRadius).catch(() => {});
  }, []);

  const handleClearBlastRadius = useCallback(() => {
    setBlastRadius(null);
  }, []);

  const blastRadiusSet = blastRadius
    ? {
        upstream: new Set(blastRadius.upstream.map((n) => n.id)),
        downstream: new Set(blastRadius.downstream.map((n) => n.id)),
      }
    : null;

  return (
    <div className="app">
      <Sidebar
        nodeCount={nodes.length}
        edgeCount={links.length}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        overlayMode={overlayMode}
        onOverlayChange={setOverlayMode}
        blastRadiusActive={blastRadius !== null}
        onClearBlastRadius={handleClearBlastRadius}
        loading={loading}
      />
      <main className="graph-area">
        {error && (
          <div className="graph-empty">
            <p style={{ color: 'var(--text-secondary)' }}>Failed to load graph: {error}</p>
          </div>
        )}
        <GraphCanvas
          nodes={nodes}
          links={links}
          selectedNodeId={selectedNodeId}
          blastRadiusSet={blastRadiusSet}
          overlayMode={overlayMode}
          overlayData={overlayData}
          searchQuery={searchQuery}
          loading={loading}
          onNodeClick={handleNodeClick}
        />
      </main>
      {selectedNodeId && (
        <NodeDetailPanel
          nodeId={selectedNodeId}
          detail={nodeDetail}
          loading={detailLoading}
          onClose={handleClose}
          onShowBlastRadius={handleShowBlastRadius}
        />
      )}
    </div>
  );
}
