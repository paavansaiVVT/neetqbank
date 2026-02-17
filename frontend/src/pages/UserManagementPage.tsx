import { useState, useEffect, useMemo } from 'react';
import {
    Users, UserPlus, Shield, Search, X, Check,
    AlertTriangle, ChevronDown, ToggleLeft, ToggleRight
} from 'lucide-react';
import { QbankApiClient } from '../api/client';
import type { UserResponse, UserRole, UserCreateRequest } from '../api/types';

interface UserManagementPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

const ROLE_COLORS: Record<UserRole, { bg: string; text: string; label: string }> = {
    admin: { bg: 'var(--danger-100)', text: 'var(--danger-700)', label: 'Admin' },
    creator: { bg: 'var(--primary-100)', text: 'var(--primary-700)', label: 'Creator' },
    reviewer: { bg: 'var(--warning-100)', text: 'var(--warning-700)', label: 'Reviewer' },
    publisher: { bg: 'var(--success-100)', text: 'var(--success-700)', label: 'Publisher' },
};

const ALL_ROLES: UserRole[] = ['admin', 'creator', 'reviewer', 'publisher'];

export function UserManagementPage({ apiBaseUrl, apiKey }: UserManagementPageProps) {
    const client = useMemo(() => new QbankApiClient(apiBaseUrl, apiKey), [apiBaseUrl, apiKey]);
    const [users, setUsers] = useState<UserResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [showAddModal, setShowAddModal] = useState(false);
    const [actionFeedback, setActionFeedback] = useState<{ userId: number; msg: string } | null>(null);

    // Add user form state
    const [newUser, setNewUser] = useState<UserCreateRequest>({
        email: '',
        password: '',
        name: '',
        role: 'creator',
    });
    const [addError, setAddError] = useState<string | null>(null);
    const [adding, setAdding] = useState(false);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const data = await client.listUsers();
            setUsers(data);
            setError(null);
        } catch (err: any) {
            setError(err.message || 'Failed to load users');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchUsers(); }, [client]);

    const filteredUsers = useMemo(() => {
        if (!search.trim()) return users;
        const q = search.toLowerCase();
        return users.filter(u =>
            u.name.toLowerCase().includes(q) ||
            u.email.toLowerCase().includes(q) ||
            u.role.toLowerCase().includes(q)
        );
    }, [users, search]);

    const handleAddUser = async (e: React.FormEvent) => {
        e.preventDefault();
        setAddError(null);
        setAdding(true);
        try {
            await client.createUser(newUser);
            setShowAddModal(false);
            setNewUser({ email: '', password: '', name: '', role: 'creator' });
            await fetchUsers();
        } catch (err: any) {
            setAddError(err.message || 'Failed to create user');
        } finally {
            setAdding(false);
        }
    };

    const handleRoleChange = async (userId: number, role: UserRole) => {
        try {
            await client.updateUser(userId, { role });
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, role } : u));
            setActionFeedback({ userId, msg: `Role → ${role}` });
            setTimeout(() => setActionFeedback(null), 2000);
        } catch (err: any) {
            setError(err.message || 'Failed to update role');
        }
    };

    const handleToggleActive = async (userId: number, currentlyActive: boolean) => {
        try {
            await client.updateUser(userId, { is_active: !currentlyActive });
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !currentlyActive } : u));
            setActionFeedback({ userId, msg: !currentlyActive ? 'Activated' : 'Deactivated' });
            setTimeout(() => setActionFeedback(null), 2000);
        } catch (err: any) {
            setError(err.message || 'Failed to update user');
        }
    };

    return (
        <div style={{ padding: 'var(--space-6)', maxWidth: '1000px', margin: '0 auto' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-5)' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-1)' }}>
                        <Users size={28} color="var(--primary-600)" />
                        <h1 style={{ margin: 0 }}>Team Management</h1>
                    </div>
                    <p style={{ color: 'var(--gray-500)', margin: 0 }}>
                        Manage users, assign roles, and control access
                    </p>
                </div>
                <button
                    className="btn btn-primary"
                    onClick={() => setShowAddModal(true)}
                    style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
                >
                    <UserPlus size={18} />
                    Add User
                </button>
            </div>

            {/* Search Bar */}
            <div style={{
                position: 'relative',
                marginBottom: 'var(--space-4)',
            }}>
                <Search size={16} style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--gray-400)',
                }} />
                <input
                    type="text"
                    placeholder="Search by name, email, or role…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    style={{
                        width: '100%',
                        padding: '10px 12px 10px 36px',
                        border: '1px solid var(--gray-200)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '14px',
                        background: 'white',
                    }}
                />
            </div>

            {/* Error Banner */}
            {error && (
                <div style={{
                    background: 'var(--danger-50)',
                    border: '1px solid var(--danger-200)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3)',
                    marginBottom: 'var(--space-4)',
                    display: 'flex',
                    gap: 'var(--space-2)',
                    alignItems: 'center',
                }}>
                    <AlertTriangle size={16} color="var(--danger-600)" />
                    <span style={{ fontSize: '13px', color: 'var(--danger-700)' }}>{error}</span>
                    <button onClick={() => setError(null)} style={{
                        marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--danger-600)',
                    }}>
                        <X size={14} />
                    </button>
                </div>
            )}

            {/* Users Table */}
            <div style={{
                background: 'white',
                border: '1px solid var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
            }}>
                {/* Table Header */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 2fr 140px 100px 100px',
                    padding: 'var(--space-3) var(--space-4)',
                    borderBottom: '1px solid var(--gray-200)',
                    background: 'var(--gray-50)',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: 'var(--gray-500)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                }}>
                    <span>User</span>
                    <span>Email</span>
                    <span>Role</span>
                    <span style={{ textAlign: 'center' }}>Status</span>
                    <span style={{ textAlign: 'center' }}>Actions</span>
                </div>

                {/* Loading */}
                {loading && (
                    <div style={{
                        padding: 'var(--space-6)',
                        textAlign: 'center',
                        color: 'var(--gray-500)',
                    }}>
                        Loading users…
                    </div>
                )}

                {/* Empty */}
                {!loading && filteredUsers.length === 0 && (
                    <div style={{
                        padding: 'var(--space-6)',
                        textAlign: 'center',
                        color: 'var(--gray-400)',
                    }}>
                        {search ? 'No users match your search' : 'No users found'}
                    </div>
                )}

                {/* Rows */}
                {filteredUsers.map((user, idx) => (
                    <div
                        key={user.id}
                        style={{
                            display: 'grid',
                            gridTemplateColumns: '2fr 2fr 140px 100px 100px',
                            padding: 'var(--space-3) var(--space-4)',
                            borderBottom: idx < filteredUsers.length - 1 ? '1px solid var(--gray-100)' : 'none',
                            alignItems: 'center',
                            opacity: user.is_active ? 1 : 0.6,
                            transition: 'background 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--gray-50)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'white')}
                    >
                        {/* Name + Avatar */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <div style={{
                                width: '36px',
                                height: '36px',
                                borderRadius: '50%',
                                background: `linear-gradient(135deg, ${ROLE_COLORS[user.role].bg}, ${ROLE_COLORS[user.role].text}22)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '13px',
                                fontWeight: 600,
                                color: ROLE_COLORS[user.role].text,
                                flexShrink: 0,
                            }}>
                                {user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                            </div>
                            <div>
                                <div style={{ fontWeight: 500, fontSize: '14px' }}>{user.name}</div>
                                <div style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                                    Joined {new Date(user.created_at).toLocaleDateString()}
                                </div>
                            </div>
                        </div>

                        {/* Email */}
                        <span style={{ fontSize: '13px', color: 'var(--gray-600)' }}>{user.email}</span>

                        {/* Role Dropdown */}
                        <div style={{ position: 'relative' }}>
                            <select
                                value={user.role}
                                onChange={e => handleRoleChange(user.id, e.target.value as UserRole)}
                                style={{
                                    appearance: 'none',
                                    padding: '4px 24px 4px 10px',
                                    border: `1px solid ${ROLE_COLORS[user.role].bg}`,
                                    borderRadius: 'var(--radius-full)',
                                    background: ROLE_COLORS[user.role].bg,
                                    color: ROLE_COLORS[user.role].text,
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    width: '110px',
                                }}
                            >
                                {ALL_ROLES.map(r => (
                                    <option key={r} value={r}>{ROLE_COLORS[r].label}</option>
                                ))}
                            </select>
                            <ChevronDown size={12} style={{
                                position: 'absolute',
                                right: '28px',
                                top: '50%',
                                transform: 'translateY(-50%)',
                                pointerEvents: 'none',
                                color: ROLE_COLORS[user.role].text,
                            }} />
                        </div>

                        {/* Status */}
                        <div style={{ textAlign: 'center' }}>
                            {actionFeedback?.userId === user.id ? (
                                <span style={{
                                    fontSize: '11px',
                                    color: 'var(--success-600)',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '4px',
                                }}>
                                    <Check size={12} />
                                    {actionFeedback.msg}
                                </span>
                            ) : (
                                <span style={{
                                    padding: '2px 8px',
                                    borderRadius: 'var(--radius-full)',
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    background: user.is_active ? 'var(--success-100)' : 'var(--gray-100)',
                                    color: user.is_active ? 'var(--success-700)' : 'var(--gray-500)',
                                }}>
                                    {user.is_active ? 'Active' : 'Inactive'}
                                </span>
                            )}
                        </div>

                        {/* Toggle Active */}
                        <div style={{ textAlign: 'center' }}>
                            <button
                                onClick={() => handleToggleActive(user.id, user.is_active)}
                                title={user.is_active ? 'Deactivate user' : 'Activate user'}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    color: user.is_active ? 'var(--success-500)' : 'var(--gray-400)',
                                    padding: '4px',
                                }}
                            >
                                {user.is_active ?
                                    <ToggleRight size={24} /> :
                                    <ToggleLeft size={24} />
                                }
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* Summary */}
            {!loading && (
                <div style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    marginTop: 'var(--space-4)',
                    justifyContent: 'center',
                }}>
                    {ALL_ROLES.map(role => {
                        const count = users.filter(u => u.role === role).length;
                        return (
                            <div key={role} style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 'var(--space-1)',
                                fontSize: '12px',
                                color: 'var(--gray-500)',
                            }}>
                                <span style={{
                                    width: '8px',
                                    height: '8px',
                                    borderRadius: '50%',
                                    background: ROLE_COLORS[role].text,
                                }} />
                                {ROLE_COLORS[role].label}: {count}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Add User Modal */}
            {showAddModal && (
                <div style={{
                    position: 'fixed',
                    inset: 0,
                    background: 'rgba(0,0,0,0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000,
                }} onClick={() => setShowAddModal(false)}>
                    <div
                        style={{
                            background: 'white',
                            borderRadius: 'var(--radius-lg)',
                            padding: 'var(--space-6)',
                            width: '440px',
                            maxWidth: '90vw',
                            boxShadow: 'var(--shadow-xl)',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                <Shield size={20} color="var(--primary-600)" />
                                <h2 style={{ margin: 0, fontSize: '18px' }}>Add Team Member</h2>
                            </div>
                            <button onClick={() => setShowAddModal(false)} style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                color: 'var(--gray-400)', padding: '4px',
                            }}>
                                <X size={18} />
                            </button>
                        </div>

                        {addError && (
                            <div style={{
                                background: 'var(--danger-50)',
                                border: '1px solid var(--danger-200)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-3)',
                                marginBottom: 'var(--space-3)',
                                fontSize: '13px',
                                color: 'var(--danger-700)',
                            }}>
                                {addError}
                            </div>
                        )}

                        <form onSubmit={handleAddUser}>
                            {/* Name */}
                            <div style={{ marginBottom: 'var(--space-3)' }}>
                                <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: '4px', fontWeight: 500 }}>
                                    Full Name
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={newUser.name}
                                    onChange={e => setNewUser(p => ({ ...p, name: e.target.value }))}
                                    placeholder="John Doe"
                                    style={{
                                        width: '100%',
                                        padding: '8px 12px',
                                        border: '1px solid var(--gray-200)',
                                        borderRadius: 'var(--radius-md)',
                                        fontSize: '14px',
                                    }}
                                />
                            </div>

                            {/* Email */}
                            <div style={{ marginBottom: 'var(--space-3)' }}>
                                <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: '4px', fontWeight: 500 }}>
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    required
                                    value={newUser.email}
                                    onChange={e => setNewUser(p => ({ ...p, email: e.target.value }))}
                                    placeholder="john@example.com"
                                    style={{
                                        width: '100%',
                                        padding: '8px 12px',
                                        border: '1px solid var(--gray-200)',
                                        borderRadius: 'var(--radius-md)',
                                        fontSize: '14px',
                                    }}
                                />
                            </div>

                            {/* Password */}
                            <div style={{ marginBottom: 'var(--space-3)' }}>
                                <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: '4px', fontWeight: 500 }}>
                                    Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    minLength={8}
                                    value={newUser.password}
                                    onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))}
                                    placeholder="Minimum 8 characters"
                                    style={{
                                        width: '100%',
                                        padding: '8px 12px',
                                        border: '1px solid var(--gray-200)',
                                        borderRadius: 'var(--radius-md)',
                                        fontSize: '14px',
                                    }}
                                />
                            </div>

                            {/* Role */}
                            <div style={{ marginBottom: 'var(--space-4)' }}>
                                <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: '6px', fontWeight: 500 }}>
                                    Role
                                </label>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
                                    {ALL_ROLES.map(role => (
                                        <button
                                            key={role}
                                            type="button"
                                            onClick={() => setNewUser(p => ({ ...p, role }))}
                                            style={{
                                                padding: '8px 12px',
                                                border: newUser.role === role
                                                    ? `2px solid ${ROLE_COLORS[role].text}`
                                                    : '1px solid var(--gray-200)',
                                                borderRadius: 'var(--radius-md)',
                                                background: newUser.role === role ? ROLE_COLORS[role].bg : 'white',
                                                color: newUser.role === role ? ROLE_COLORS[role].text : 'var(--gray-600)',
                                                cursor: 'pointer',
                                                fontSize: '13px',
                                                fontWeight: newUser.role === role ? 600 : 400,
                                                textAlign: 'left',
                                            }}
                                        >
                                            <div style={{ fontWeight: 600 }}>{ROLE_COLORS[role].label}</div>
                                            <div style={{ fontSize: '11px', opacity: 0.7 }}>
                                                {role === 'creator' && 'Generate content & edit'}
                                                {role === 'reviewer' && 'Approve & reject'}
                                                {role === 'publisher' && 'Publish questions'}
                                                {role === 'admin' && 'Full access + manage'}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Submit */}
                            <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                                <button
                                    type="button"
                                    onClick={() => setShowAddModal(false)}
                                    style={{
                                        padding: '8px 16px',
                                        border: '1px solid var(--gray-200)',
                                        borderRadius: 'var(--radius-md)',
                                        background: 'white',
                                        cursor: 'pointer',
                                        fontSize: '13px',
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    disabled={adding}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--space-1)',
                                        opacity: adding ? 0.7 : 1,
                                    }}
                                >
                                    <UserPlus size={16} />
                                    {adding ? 'Creating…' : 'Create User'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default UserManagementPage;
