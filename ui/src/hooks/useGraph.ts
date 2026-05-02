import { useState, useEffect, useCallback } from 'react';
import { fetchGraph } from '../api';
import type { GraphNode, GraphLink } from '../types';

interface UseGraphResult {
  nodes: GraphNode[];
  links: GraphLink[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useGraph(): UseGraphResult {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => {
    setTick((t) => t + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchGraph()
      .then((data) => {
        if (cancelled) return;

        // Compute degree (number of edge endpoints involving each node)
        const degreeMap = new Map<string, number>();
        for (const edge of data.edges) {
          degreeMap.set(edge.source_id, (degreeMap.get(edge.source_id) ?? 0) + 1);
          degreeMap.set(edge.target_id, (degreeMap.get(edge.target_id) ?? 0) + 1);
        }

        const graphNodes: GraphNode[] = data.nodes.map((n) => ({
          ...n,
          degree: degreeMap.get(n.id) ?? 0,
        }));

        const graphLinks: GraphLink[] = data.edges.map((e) => ({
          source: e.source_id,
          target: e.target_id,
          type: e.type,
          metadata: e.metadata,
        }));

        setNodes(graphNodes);
        setLinks(graphLinks);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { nodes, links, loading, error, reload };
}
