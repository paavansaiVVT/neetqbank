/**
 * LoginPage - Authentication page for users to login.
 */
import React, { useState, FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import '../design-system.css';

export function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    // Get redirect path from state or default to dashboard
    const from = (location.state as { from?: string })?.from || '/';

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            await login(email, password);
            navigate(from, { replace: true });
        } catch (err) {
            if (err instanceof TypeError && err.message === 'Failed to fetch') {
                setError('Cannot connect to the server. Make sure the backend is running on port 8000.');
            } else {
                setError(err instanceof Error ? err.message : 'Login failed');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, var(--gray-900) 0%, var(--gray-800) 100%)',
        }}>
            <div style={{
                width: '100%',
                maxWidth: '400px',
                padding: 'var(--space-8)',
                background: 'var(--gray-50)',
                borderRadius: 'var(--radius-xl)',
                boxShadow: 'var(--shadow-2xl)',
            }}>
                {/* Logo/Title */}
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
                    <h1 style={{
                        fontSize: '28px',
                        fontWeight: 700,
                        color: 'var(--gray-900)',
                        marginBottom: 'var(--space-2)',
                    }}>
                        🎓 QBank V2
                    </h1>
                    <p style={{ color: 'var(--gray-500)' }}>
                        Sign in to your account
                    </p>
                </div>

                {/* Error Message */}
                {error && (
                    <div style={{
                        padding: 'var(--space-3)',
                        background: 'var(--error-100)',
                        border: '1px solid var(--error-300)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--error-700)',
                        marginBottom: 'var(--space-4)',
                        fontSize: '14px',
                    }}>
                        {error}
                    </div>
                )}

                {/* Login Form */}
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <label style={{
                            display: 'block',
                            marginBottom: 'var(--space-1)',
                            fontWeight: 500,
                            color: 'var(--gray-700)',
                            fontSize: '14px',
                        }}>
                            Email
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="admin@qbank.dev"
                            required
                            style={{
                                width: '100%',
                                padding: 'var(--space-3)',
                                border: '1px solid var(--gray-300)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '16px',
                                outline: 'none',
                                transition: 'border-color 0.2s',
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: 'var(--space-6)' }}>
                        <label style={{
                            display: 'block',
                            marginBottom: 'var(--space-1)',
                            fontWeight: 500,
                            color: 'var(--gray-700)',
                            fontSize: '14px',
                        }}>
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            style={{
                                width: '100%',
                                padding: 'var(--space-3)',
                                border: '1px solid var(--gray-300)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '16px',
                                outline: 'none',
                                transition: 'border-color 0.2s',
                            }}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        style={{
                            width: '100%',
                            padding: 'var(--space-3)',
                            background: isLoading ? 'var(--gray-400)' : 'var(--primary-600)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '16px',
                            fontWeight: 600,
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                            transition: 'background 0.2s',
                        }}
                    >
                        {isLoading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>

                {/* Demo Credentials */}
                <div style={{
                    marginTop: 'var(--space-6)',
                    padding: 'var(--space-3)',
                    background: 'var(--gray-100)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '13px',
                    color: 'var(--gray-600)',
                }}>
                    <strong>Demo Credentials:</strong><br />
                    Email: admin@qbank.dev<br />
                    Password: admin123
                </div>
            </div>
        </div>
    );
}

export default LoginPage;
