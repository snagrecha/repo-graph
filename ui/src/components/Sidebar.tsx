import type { OverlayMode, NodeType } from '../types';

const NODE_TYPES: { type: NodeType; label: string; color: string }[] = [
  { type: 'file', label: 'File', color: '#64748b' },
  { type: 'class', label: 'Class', color: '#3b82f6' },
  { type: 'function', label: 'Function', color: '#22c55e' },
  { type: 'module', label: 'Module', color: '#a855f7' },
  { type: 'symbol', label: 'Symbol', color: '#f59e0b' },
];

const OVERLAY_OPTIONS: { mode: OverlayMode; label: string }[] = [
  { mode: 'none', label: 'None' },
  { mode: 'complexity', label: 'Complexity' },
  { mode: 'churn', label: 'Churn' },
  { mode: 'ownership', label: 'Ownership' },
];

interface Props {
  nodeCount: number;
  edgeCount: number;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  overlayMode: OverlayMode;
  onOverlayChange: (mode: OverlayMode) => void;
  blastRadiusActive: boolean;
  onClearBlastRadius: () => void;
  loading: boolean;
}

export function Sidebar({
  nodeCount,
  edgeCount,
  searchQuery,
  onSearchChange,
  overlayMode,
  onOverlayChange,
  blastRadiusActive,
  onClearBlastRadius,
  loading,
}: Props) {
  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h1 className="sidebar-title">codenexus</h1>
        <div className="sidebar-stats" style={{ opacity: loading ? 0.4 : 1 }}>
          <span className="stat-chip">{nodeCount} nodes</span>
          <span className="stat-sep">·</span>
          <span className="stat-chip">{edgeCount} edges</span>
        </div>
      </div>

      {/* Search */}
      <div className="sidebar-section">
        <div className="search-wrapper">
          <span className="search-icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="9" cy="9" r="6" stroke="#94a3b8" strokeWidth="2" />
              <line x1="13.5" y1="13.5" x2="18" y2="18" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <input
            className="search-input"
            type="text"
            placeholder="Search nodes…"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* Overlays */}
      <div className="sidebar-section">
        <div className="sidebar-label">OVERLAYS</div>
        <div className="overlay-btn-group">
          {OVERLAY_OPTIONS.map(({ mode, label }) => (
            <button
              key={mode}
              className={`overlay-btn${overlayMode === mode ? ' active' : ''}`}
              onClick={() => onOverlayChange(mode)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="sidebar-section">
        <div className="sidebar-label">NODES</div>
        <ul className="legend-list">
          {NODE_TYPES.map(({ type, label, color }) => (
            <li key={type} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: color }} />
              <span className="legend-label">{label}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Blast radius banner */}
      {blastRadiusActive && (
        <div className="blast-banner">
          <span className="blast-banner-text">Blast radius active</span>
          <button className="blast-clear-btn" onClick={onClearBlastRadius} title="Clear blast radius">
            ✕ Clear
          </button>
        </div>
      )}

      {/* Footer hint */}
      <div className="sidebar-footer">
        Click a node to inspect · Drag to rotate
      </div>
    </aside>
  );
}
