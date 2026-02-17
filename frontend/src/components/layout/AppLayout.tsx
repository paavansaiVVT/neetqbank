import React from 'react';
import topallLogo from '../../assets/topall-logo.png';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    History,
    PlusCircle,
    Settings,
    LogOut,
    User,
    Users,
    ChevronRight,
    Book,
    ClipboardList,
    BarChart3
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { ProtectedRoute } from '../auth/ProtectedRoute';
import './AppLayout.css';

export const AppLayout: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { user, logout, isLoading, hasRole } = useAuth();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    // Get user's initials for avatar
    const getInitials = (name: string) => {
        return name
            .split(' ')
            .map(n => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
    };

    // Format role for display
    const formatRole = (role: string) => {
        return role.charAt(0).toUpperCase() + role.slice(1);
    };

    return (
        <ProtectedRoute>
            <div className="app-shell">
                {/* Sidebar */}
                <aside className="sidebar">
                    <div className="sidebar-header">
                        <div className="brand-logo">
                            <img src={topallLogo} alt="TopAll" className="logo-icon" />
                            <span className="brand-text">Top<span className="light">All</span></span>
                        </div>
                    </div>

                    <nav className="sidebar-nav">
                        <div className="nav-section">
                            <span className="nav-label">Main</span>
                            <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                <LayoutDashboard size={20} />
                                <span>Dashboard</span>
                            </NavLink>
                            {hasRole(['creator', 'admin']) && (
                                <NavLink to="/create" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                    <PlusCircle size={20} />
                                    <span>New Batch</span>
                                </NavLink>
                            )}
                            <NavLink to="/jobs" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                <History size={20} />
                                <span>History</span>
                            </NavLink>
                            <NavLink to="/library" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                <Book size={20} />
                                <span>Library</span>
                            </NavLink>
                            {hasRole(['creator', 'reviewer', 'admin']) && (
                                <NavLink to="/queue" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                    <ClipboardList size={20} />
                                    <span>My Queue</span>
                                    <span style={{
                                        background: 'var(--danger-500)',
                                        color: 'white',
                                        padding: '1px 6px',
                                        borderRadius: '10px',
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        marginLeft: 'auto',
                                    }}>4</span>
                                </NavLink>
                            )}
                        </div>

                        <div className="nav-section">
                            <span className="nav-label">System</span>
                            {hasRole(['admin']) && (
                                <NavLink to="/analytics" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                    <BarChart3 size={20} />
                                    <span>Analytics</span>
                                </NavLink>
                            )}
                            {hasRole(['admin']) && (
                                <NavLink to="/users" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                    <Users size={20} />
                                    <span>Team</span>
                                </NavLink>
                            )}
                            <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                                <Settings size={20} />
                                <span>Settings</span>
                            </NavLink>
                        </div>
                    </nav>

                    <div className="sidebar-footer">
                        <div className="user-profile">
                            <div className="avatar">{user ? getInitials(user.name) : 'U'}</div>
                            <div className="user-info">
                                <span className="user-name">{user?.name || 'User'}</span>
                                <span className="user-role">{user ? formatRole(user.role) : 'Guest'}</span>
                            </div>
                            <button
                                className="logout-btn"
                                onClick={handleLogout}
                                title="Logout"
                            >
                                <LogOut size={18} />
                            </button>
                        </div>
                    </div>
                </aside>

                {/* Main Content */}
                <main className="main-wrapper">
                    <header className="top-header">
                        <div className="breadcrumbs">
                            <span className="crumb">TopAll</span>
                            <ChevronRight size={14} className="crumb-separator" />
                            <span className="crumb active">
                                {location.pathname === '/' ? 'Dashboard' :
                                    location.pathname.startsWith('/create') ? 'New Batch' :
                                        location.pathname.startsWith('/jobs') ? 'Job History' :
                                            location.pathname.startsWith('/library') ? 'Question Library' :
                                                location.pathname.startsWith('/queue') ? 'Review Queue' :
                                                    location.pathname.startsWith('/analytics') ? 'Analytics' :
                                                        location.pathname.startsWith('/users') ? 'Team' :
                                                            location.pathname.startsWith('/settings') ? 'Settings' :
                                                                'Page'}
                            </span>
                        </div>
                        <div className="header-actions">
                            {/* User welcome message */}
                            {user && (
                                <span style={{ fontSize: '14px', color: 'var(--gray-500)' }}>
                                    Welcome, <strong>{user.name}</strong>
                                </span>
                            )}
                        </div>
                    </header>

                    <div className="page-content">
                        <Outlet />
                    </div>
                </main>
            </div>
        </ProtectedRoute>
    );
};
