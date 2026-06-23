import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          margin: '40px auto',
          maxWidth: '600px',
          background: 'var(--bg-glass, #111)',
          border: '1px solid var(--accent-red, #ff4444)',
          borderRadius: '8px',
          color: 'white',
          fontFamily: 'monospace'
        }}>
          <h2 style={{ color: 'var(--accent-red, #ff4444)' }}>System Error</h2>
          <p>The Sentinel dashboard encountered an unexpected exception.</p>
          <pre style={{ 
            background: 'rgba(0,0,0,0.5)', 
            padding: '16px', 
            borderRadius: '4px',
            overflowX: 'auto'
          }}>
            {this.state.error?.toString()}
          </pre>
          <button 
            onClick={() => window.location.reload()}
            style={{
              marginTop: '20px',
              padding: '8px 16px',
              background: 'var(--accent-blue, #4488ff)',
              border: 'none',
              borderRadius: '4px',
              color: 'white',
              cursor: 'pointer'
            }}
          >
            Restart Interface
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
