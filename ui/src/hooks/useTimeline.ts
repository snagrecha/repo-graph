import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchCommits, fetchGraphAtCommit } from '../api';
import type { CommitInfo, GraphNode, GraphLink, GraphResponse } from '../types';

export interface TimelineState {
  commits: CommitInfo[];
  selectedCommit: CommitInfo | null;
  loading: boolean;
  error: string | null;
}

export interface TimelineActions {
  selectCommit: (commit: CommitInfo | null) => void;
  selectCommitBySha: (sha: string) => void;
  resetToHead: () => void;
}

export function useTimeline(
  reloadHeadGraph: () => void,
  setGraphData: (nodes: GraphNode[], links: GraphLink[]) => void,
) {
  const [state, setState] = useState<TimelineState>({
    commits: [],
    selectedCommit: null,
    loading: false,
    error: null,
  });

  const originalDataRef = useRef<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);

  // Load commits once on mount
  useEffect(() => {
    fetchCommits(500)
      .then((commits) => {
        // Newest first from API; reverse for chronological slider (oldest -> newest)
        setState((s) => ({ ...s, commits: commits.slice().reverse() }));
      })
      .catch((err) => {
        setState((s) => ({ ...s, error: String(err) }));
      });
  }, []);

  const selectCommit = useCallback(
    (commit: CommitInfo | null) => {
      if (commit === null) {
        setState((s) => ({ ...s, selectedCommit: null, loading: false }));
        if (originalDataRef.current) {
          setGraphData(originalDataRef.current.nodes, originalDataRef.current.links);
        } else {
          reloadHeadGraph();
        }
        return;
      }

      setState((s) => ({ ...s, selectedCommit: commit, loading: true, error: null }));

      fetchGraphAtCommit(commit.commit_sha)
        .then((data: GraphResponse) => {
          const nodes: GraphNode[] = data.nodes.map((n) => ({
            ...n,
            degree: 0, // will be computed by GraphCanvas
          }));
          const links: GraphLink[] = data.edges.map((e) => ({
            source: e.source_id,
            target: e.target_id,
            type: e.type,
            metadata: e.metadata,
          }));
          setGraphData(nodes, links);
          setState((s) => ({ ...s, loading: false }));
        })
        .catch((err) => {
          setState((s) => ({ ...s, loading: false, error: String(err) }));
        });
    },
    [reloadHeadGraph, setGraphData],
  );

  const selectCommitBySha = useCallback(
    (sha: string) => {
      const commit = state.commits.find((c) => c.commit_sha === sha) || null;
      selectCommit(commit);
    },
    [state.commits, selectCommit],
  );

  const resetToHead = useCallback(() => {
    selectCommit(null);
  }, [selectCommit]);

  const saveOriginalData = useCallback((nodes: GraphNode[], links: GraphLink[]) => {
    originalDataRef.current = { nodes, links };
  }, []);

  return {
    ...state,
    selectCommit,
    selectCommitBySha,
    resetToHead,
    saveOriginalData,
  };
}
