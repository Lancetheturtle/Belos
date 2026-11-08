import { useSyncExternalStore } from 'react';
import { getConnection, subscribeConnection } from '../api/client';
export default function ConnectionStatus({
  onRetry,
  busy = false,
}: {
  onRetry?: () => void;
  busy?: boolean;
}) {
  const status = useSyncExternalStore(subscribeConnection, getConnection);
  const labels = {
    connecting: 'Connecting…',
    connected: 'Server connected',
    disconnected: 'Disconnected',
  };
  return (
    <span
      className={`connection-status ${status.state}`}
      role="status"
      title={status.error}
    >
      <span className="dot" />
      {labels[status.state]}
      {status.state === 'disconnected' && onRetry && (
        <button disabled={busy} onClick={onRetry}>
          Retry
        </button>
      )}
    </span>
  );
}
