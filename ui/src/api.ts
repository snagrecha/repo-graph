import type {
  GraphResponse,
  NodeDetailResponse,
  BlastRadiusResponse,
  CommitInfo,
} from './types';

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`API error ${res.status} ${res.statusText} — ${path}`);
  }
  return res.json() as Promise<T>;
}

export function fetchGraph(): Promise<GraphResponse> {
  return apiFetch<GraphResponse>('/api/graph');
}

export function fetchNodeDetail(id: string): Promise<NodeDetailResponse> {
  return apiFetch<NodeDetailResponse>(`/api/graph/node/${encodeURIComponent(id)}`);
}

export function fetchBlastRadius(
  id: string,
  depth = 3,
): Promise<BlastRadiusResponse> {
  return apiFetch<BlastRadiusResponse>(
    `/api/graph/blast-radius/${encodeURIComponent(id)}?depth=${depth}`,
  );
}

export function fetchOverlay(
  mode: 'complexity' | 'churn' | 'ownership',
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(`/api/overlays/${mode}`);
}

export function fetchCommits(limit = 500): Promise<CommitInfo[]> {
  return apiFetch<CommitInfo[]>(`/api/timeline/commits?limit=${limit}`);
}

export function fetchGraphAtCommit(commitSha: string): Promise<GraphResponse> {
  return apiFetch<GraphResponse>(`/api/timeline/commits/${encodeURIComponent(commitSha)}`);
}
