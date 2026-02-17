import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
        this.setState({ errorInfo });

        // Could send to error tracking service here
        // e.g., Sentry.captureException(error);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    handleGoHome = () => {
        window.location.href = '/';
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div
                    style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minHeight: '60vh',
                        padding: 'var(--space-8)',
                        textAlign: 'center',
                    }}
                >
                    <div
                        style={{
                            background: 'var(--danger-50)',
                            borderRadius: 'var(--radius-full)',
                            padding: 'var(--space-4)',
                            marginBottom: 'var(--space-4)',
                        }}
                    >
                        <AlertTriangle size={48} color="var(--danger-500)" />
                    </div>

                    <h2 style={{ marginBottom: 'var(--space-2)', color: 'var(--gray-800)' }}>
                        Something went wrong
                    </h2>

                    <p style={{ color: 'var(--gray-500)', marginBottom: 'var(--space-6)', maxWidth: 400 }}>
                        An unexpected error occurred. Try refreshing the page or going back to the dashboard.
                    </p>

                    {import.meta.env.DEV && this.state.error && (
                        <details
                            style={{
                                background: 'var(--gray-50)',
                                borderRadius: 'var(--radius-lg)',
                                padding: 'var(--space-4)',
                                marginBottom: 'var(--space-6)',
                                maxWidth: 600,
                                width: '100%',
                                textAlign: 'left',
                            }}
                        >
                            <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--gray-700)' }}>
                                Error Details (Dev Mode)
                            </summary>
                            <pre
                                style={{
                                    marginTop: 'var(--space-2)',
                                    fontSize: '12px',
                                    overflow: 'auto',
                                    whiteSpace: 'pre-wrap',
                                    color: 'var(--danger-700)',
                                }}
                            >
                                {this.state.error.toString()}
                                {this.state.errorInfo?.componentStack}
                            </pre>
                        </details>
                    )}

                    <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                        <button
                            onClick={this.handleReset}
                            className="btn btn-secondary"
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
                        >
                            <RefreshCw size={16} /> Try Again
                        </button>
                        <button
                            onClick={this.handleGoHome}
                            className="btn btn-primary"
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
                        >
                            <Home size={16} /> Go to Dashboard
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
