/**
 * ProtectedRoute - Route guard that requires authentication.
 * Optionally restricts access to specific roles.
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface ProtectedRouteProps {
    children: React.ReactNode;
    allowedRoles?: ('creator' | 'reviewer' | 'publisher' | 'admin')[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
    const { isAuthenticated, isLoading, user, hasRole } = useAuth();
    const location = useLocation();

    // Show loading state while checking auth
    if (isLoading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '100vh',
                background: 'var(--gray-50)',
            }}>
                <div style={{
                    textAlign: 'center',
                    color: 'var(--gray-600)',
                }}>
                    <div style={{ fontSize: '24px', marginBottom: 'var(--space-2)' }}>🔐</div>
                    Loading...
                </div>
            </div>
        );
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: location.pathname }} replace />;
    }

    // Check role if specified
    if (allowedRoles && !hasRole(allowedRoles)) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '100vh',
                background: 'var(--gray-50)',
            }}>
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-8)',
                    maxWidth: '400px',
                }}>
                    <div style={{ fontSize: '48px', marginBottom: 'var(--space-4)' }}>🚫</div>
                    <h2 style={{ color: 'var(--gray-900)', marginBottom: 'var(--space-2)' }}>
                        Access Denied
                    </h2>
                    <p style={{ color: 'var(--gray-600)', marginBottom: 'var(--space-4)' }}>
                        Your role ({user?.role}) does not have permission to access this page.
                        <br />
                        Required: {allowedRoles.join(', ')}
                    </p>
                    <a
                        href="/"
                        style={{
                            color: 'var(--primary-600)',
                            textDecoration: 'none',
                            fontWeight: 500,
                        }}
                    >
                        ← Go to Dashboard
                    </a>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}

export default ProtectedRoute;
