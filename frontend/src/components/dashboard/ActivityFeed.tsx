import { useState, useEffect } from 'react';
import {
    CheckCircle,
    XCircle,
    Plus,
    MessageSquare,
    Edit,
    Upload,
    Clock,
    User
} from 'lucide-react';
import { QbankApiClient } from '../../api/client';
import { ActivityItem, ActivityType } from '../../api/types';

interface ActivityFeedProps {
    limit?: number;
    apiClient?: QbankApiClient;
}

const getActivityIcon = (type: ActivityType) => {
    switch (type) {
        case 'approved': return { icon: CheckCircle, color: 'var(--success-500)' };
        case 'rejected': return { icon: XCircle, color: 'var(--danger-500)' };
        case 'generated': return { icon: Plus, color: 'var(--primary-500)' };
        case 'commented': return { icon: MessageSquare, color: 'var(--info-500)' };
        case 'edited': return { icon: Edit, color: 'var(--warning-500)' };
        case 'published': return { icon: Upload, color: 'var(--success-600)' };
        case 'created': return { icon: Plus, color: 'var(--primary-500)' };
        default: return { icon: Clock, color: 'var(--gray-500)' };
    }
};

const getActivityVerb = (type: ActivityType) => {
    switch (type) {
        case 'approved': return 'approved';
        case 'rejected': return 'rejected';
        case 'generated': return 'generated';
        case 'commented': return 'commented on';
        case 'edited': return 'edited';
        case 'published': return 'published';
        case 'created': return 'created';
        default: return 'acted on';
    }
};

const formatRelativeTime = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
};

export function ActivityFeed({ limit = 6, apiClient }: ActivityFeedProps) {
    const [activities, setActivities] = useState<ActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!apiClient) return;

        const fetchActivity = async () => {
            try {
                setLoading(true);
                const response = await apiClient.getActivityFeed(limit);
                setActivities(response.items);
                setError(null);
            } catch (err) {
                console.error("Failed to fetch activity feed:", err);
                setError("Failed to load activity");
            } finally {
                setLoading(false);
            }
        };

        fetchActivity();

        // Refresh every 30 seconds
        const interval = setInterval(fetchActivity, 30000);
        return () => clearInterval(interval);
    }, [apiClient, limit]);

    if (!apiClient) {
        return null;
    }

    return (
        <div style={{
            background: 'white',
            border: '1px solid var(--gray-200)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 'var(--space-3) var(--space-4)',
                borderBottom: '1px solid var(--gray-100)',
            }}>
                <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>
                    Recent Activity
                </h3>
                <span style={{ fontSize: '12px', color: 'var(--gray-400)' }}>
                    Live
                    <span style={{
                        display: 'inline-block',
                        width: '6px',
                        height: '6px',
                        background: 'var(--success-500)',
                        borderRadius: '50%',
                        marginLeft: '6px',
                        animation: 'pulse 2s infinite',
                    }} />
                </span>
            </div>

            {/* Activity List */}
            <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
                {loading && activities.length === 0 ? (
                    <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--gray-500)' }}>
                        Loading activity...
                    </div>
                ) : error ? (
                    <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--danger-500)' }}>
                        {error}
                    </div>
                ) : activities.length === 0 ? (
                    <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--gray-500)' }}>
                        No recent activity
                    </div>
                ) : (
                    activities.map((activity, i) => {
                        const { icon: Icon, color } = getActivityIcon(activity.activity_type);
                        const verb = getActivityVerb(activity.activity_type);

                        return (
                            <div
                                key={activity.id}
                                style={{
                                    display: 'flex',
                                    gap: 'var(--space-3)',
                                    padding: 'var(--space-3) var(--space-4)',
                                    borderBottom: i < activities.length - 1 ? '1px solid var(--gray-50)' : 'none',
                                    cursor: 'pointer',
                                    transition: 'background 0.15s',
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--gray-50)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                                {/* Icon */}
                                <div style={{
                                    width: '32px',
                                    height: '32px',
                                    borderRadius: '50%',
                                    background: `${color}15`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    flexShrink: 0,
                                }}>
                                    <Icon size={16} color={color} />
                                </div>

                                {/* Content */}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: '13px' }}>
                                        <strong>{activity.user_name}</strong>
                                        {' '}{verb}{' '}
                                        <span style={{ color: 'var(--primary-600)' }}>
                                            {activity.target_label}
                                        </span>
                                    </div>
                                    {activity.details && (
                                        <div style={{
                                            fontSize: '12px',
                                            color: 'var(--gray-500)',
                                            marginTop: '2px',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                        }}>
                                            "{activity.details}"
                                        </div>
                                    )}
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                        fontSize: '11px',
                                        color: 'var(--gray-400)',
                                        marginTop: '4px',
                                    }}>
                                        <Clock size={10} />
                                        {formatRelativeTime(activity.timestamp)}
                                    </div>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Footer */}
            <div style={{
                padding: 'var(--space-2) var(--space-4)',
                borderTop: '1px solid var(--gray-100)',
                textAlign: 'center',
            }}>
                <button
                    style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--primary-600)',
                        fontSize: '12px',
                        cursor: 'pointer',
                    }}
                >
                    View all activity →
                </button>
            </div>
        </div>
    );
}

export default ActivityFeed;
