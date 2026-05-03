import type { CommitInfo } from '../types';

interface Props {
  commits: CommitInfo[];
  selectedCommit: CommitInfo | null;
  onSelectCommit: (commit: CommitInfo | null) => void;
  loading: boolean;
}

export function TimeSlider({ commits, selectedCommit, onSelectCommit, loading }: Props) {
  if (commits.length === 0) {
    return (
      <div className="timeline-empty">
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          No commit history available
        </span>
      </div>
    );
  }

  const selectedIndex = selectedCommit
    ? commits.findIndex((c) => c.commit_sha === selectedCommit.commit_sha)
    : commits.length - 1;

  const current = selectedCommit ?? commits[commits.length - 1];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const idx = parseInt(e.target.value, 10);
    if (idx >= 0 && idx < commits.length) {
      onSelectCommit(commits[idx]);
    }
  };

  const handleReset = () => {
    onSelectCommit(null);
  };

  const formatDate = (ts: number) => {
    try {
      return new Date(ts * 1000).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return '—';
    }
  };

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <span className="timeline-label">History</span>
        {selectedCommit && (
          <button className="timeline-reset" onClick={handleReset} type="button">
            Reset to HEAD
          </button>
        )}
        {loading && <span className="timeline-loading">Loading…</span>}
      </div>

      <input
        type="range"
        min={0}
        max={commits.length - 1}
        value={Math.max(0, selectedIndex)}
        onChange={handleChange}
        className="timeline-slider"
        disabled={loading}
      />

      <div className="timeline-meta">
        <span className="timeline-sha" title={current.commit_sha}>
          {current.commit_sha.slice(0, 7)}
        </span>
        <span className="timeline-date">{formatDate(current.committed_at)}</span>
        <span className="timeline-author">{current.author}</span>
      </div>

      <div className="timeline-message" title={current.message}>
        {current.message.split('\n')[0]}
      </div>
    </div>
  );
}
