import type { NodeDetailResponse, NodeType } from '../types';

const TYPE_COLORS: Record<NodeType, string> = {
  file: '#64748b',
  class: '#3b82f6',
  function: '#22c55e',
  module: '#a855f7',
  symbol: '#f59e0b',
};

const MAX_EDGES_SHOWN = 10;

function formatMetaValue(val: unknown): string {
  if (typeof val === 'number') {
    return Number.isInteger(val) ? String(val) : val.toFixed(2);
  }
  return String(val);
}

function isNonEmpty(val: unknown): boolean {
  if (val === null || val === undefined) return false;
  if (typeof val === 'string' && val.trim() === '') return false;
  return true;
}


interface Props {
  nodeId: string;
  detail: NodeDetailResponse | null;
  loading: boolean;
  onClose: () => void;
  onShowBlastRadius: (nodeId: string) => void;
}

export function NodeDetailPanel({
  nodeId,
  detail,
  loading,
  onClose,
  onShowBlastRadius,
}: Props) {
  const node = detail?.node;
  const typeColor = node ? (TYPE_COLORS[node.type] ?? '#64748b') : '#64748b';

  const metaEntries = node
    ? Object.entries(node.metadata).filter(([, v]) => isNonEmpty(v))
    : [];

  return (
    <div className="detail-panel">
      {/* Header */}
      <div className="detail-header">
        <div className="detail-header-left">
          {node && (
            <span
              className="node-badge"
              style={{ backgroundColor: typeColor }}
            >
              {node.type}
            </span>
          )}
          <span className="detail-node-name">
            {node ? node.name : nodeId.slice(0, 16) + '…'}
          </span>
        </div>
        <button className="detail-close-btn" onClick={onClose} title="Close panel">
          ×
        </button>
      </div>

      {loading && (
        <div className="detail-loading">
          <div className="spinner" />
        </div>
      )}

      {!loading && node && (
        <>
          {/* File info */}
          <div className="detail-section">
            <div className="detail-section-label">LOCATION</div>
            <div className="detail-filepath">{node.file_path}</div>
            <div className="detail-meta-row">
              {node.language && (
                <span className="lang-badge">{node.language}</span>
              )}
              {node.start_line !== null && (
                <span className="line-range">
                  L{node.start_line}
                  {node.end_line !== null && node.end_line !== node.start_line
                    ? `–${node.end_line}`
                    : ''}
                </span>
              )}
            </div>
          </div>

          {/* Metadata */}
          {metaEntries.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-label">METADATA</div>
              <dl className="meta-dl">
                {metaEntries.map(([k, v]) => (
                  <div key={k} className="meta-row">
                    <dt className="meta-key">{k}</dt>
                    <dd className="meta-val">{formatMetaValue(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Incoming edges */}
          {detail.incoming.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-label">CALLED BY</div>
              <ul className="edge-list">
                {detail.incoming.slice(0, MAX_EDGES_SHOWN).map((e, i) => (
                  <li key={i} className="edge-item">
                    <span className="edge-type-badge">{e.type}</span>
                    <span className="edge-node-id">{e.source_id.slice(0, 16)}</span>
                  </li>
                ))}
                {detail.incoming.length > MAX_EDGES_SHOWN && (
                  <li className="edge-item edge-item-more">
                    + {detail.incoming.length - MAX_EDGES_SHOWN} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Outgoing edges */}
          {detail.outgoing.length > 0 && (
            <div className="detail-section">
              <div className="detail-section-label">CALLS / IMPORTS</div>
              <ul className="edge-list">
                {detail.outgoing.slice(0, MAX_EDGES_SHOWN).map((e, i) => (
                  <li key={i} className="edge-item">
                    <span className="edge-type-badge">{e.type}</span>
                    <span className="edge-node-id">{e.target_id.slice(0, 16)}</span>
                  </li>
                ))}
                {detail.outgoing.length > MAX_EDGES_SHOWN && (
                  <li className="edge-item edge-item-more">
                    + {detail.outgoing.length - MAX_EDGES_SHOWN} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Action */}
          <div className="detail-actions">
            <button
              className="blast-radius-btn"
              onClick={() => onShowBlastRadius(nodeId)}
            >
              Show Blast Radius
            </button>
          </div>
        </>
      )}

      {!loading && !node && (
        <div className="detail-empty">
          <p>Could not load node details.</p>
        </div>
      )}
    </div>
  );
}
