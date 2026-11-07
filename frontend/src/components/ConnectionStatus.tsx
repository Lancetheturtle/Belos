import { isDemo } from '../api/client';

export default function ConnectionStatus() {
  return (
          <span className="demo-label">
            <span className="dot" />
            {isDemo ? 'Demo shift' : 'Backend mode'}
          </span>
  );
}
