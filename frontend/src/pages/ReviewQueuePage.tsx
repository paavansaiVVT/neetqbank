import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ClipboardList,
    Clock,
    AlertCircle,
    ArrowRight,
    CheckCircle,
    Filter,
    Inbox
} from 'lucide-react';
import { QbankApiClient } from '../api/client';
import { QueueItem, QueueItemPriority } from '../api/types';

interface ReviewQueuePageProps {
    apiBaseUrl: string;
    apiKey: string;
}

const priorityStyles = {
    urgent: { bg: 'var(--danger-50)', color: 'var(--danger-600)', label: 'Urgent' },
    normal: { bg: 'var(--warning-50)', color: 'var(--warning-600)', label: 'Normal' },
    low: { bg: 'var(--gray-100)', color: 'var(--gray-600)', label: 'Low' },
};

const formatRelativeTime = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
};

const formatDueTime = (timestamp: string) => {
    const diff = new Date(timestamp).getTime() - Date.now();
    const hours = Math.floor(diff / 3600000);
    if (hours < 0) return 'Overdue';
    if (hours < 1) return 'Due soon';
    if (hours < 24) return `${hours}h left`;
    return `${Math.floor(hours / 24)}d left`;
};

export function ReviewQueuePage({ apiBaseUrl, apiKey }: ReviewQueuePageProps) {
    const [queue, setQueue] = useState<QueueItem[]>([]);
    const [filter, setFilter] = useState<'all' | 'urgent' | 'normal' | 'low'>('all');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    // Initialize API client
    const [apiClient] = useState(() => new QbankApiClient(apiBaseUrl, apiKey));

    useEffect(() => {
        const fetchQueue = async () => {
            try {
                setLoading(true);
                const response = await apiClient.getReviewQueue();
                setQueue(response.items);
                setError(null);
            } catch (err) {
                console.error("Failed to fetch review queue:", err);
                setError("Failed to load review queue. Please try again.");
            } finally {
                setLoading(false);
            }
        };

        fetchQueue();
    }, [apiClient]);

    const filteredQueue = filter === 'all'
        ? queue
        : queue.filter(item => item.priority === filter);

    const urgentCount = queue.filter(q => q.priority === 'urgent').length;

    if (loading && queue.length === 0) {
        return (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--gray-500)' }}>
                Loading your queue...
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center' }}>
                <p style={{ color: 'var(--danger-600)', marginBottom: 'var(--space-4)' }}>{error}</p>
                <button
                    onClick={() => window.location.reload()}
                    style={{
                        padding: '8px 16px',
                        background: 'var(--primary-600)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer'
                    }}
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div style={{ padding: 'var(--space-6)' }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 'var(--space-6)',
            }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                        <ClipboardList size={28} color="var(--primary-600)" />
                        <h1 style={{ margin: 0 }}>My Review Queue</h1>
                        {urgentCount > 0 && (
                            <span style={{
                                background: 'var(--danger-500)',
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: '12px',
                                fontSize: '12px',
                                fontWeight: 600,
                            }}>
                                {urgentCount} urgent
                            </span>
                        )}
                    </div>
                    <p style={{ color: 'var(--gray-500)', margin: 0 }}>
                        Questions assigned to you for review
                    </p>
                </div>

                {/* Filter */}
                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    {(['all', 'urgent', 'normal', 'low'] as const).map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            style={{
                                padding: '6px 12px',
                                fontSize: '13px',
                                border: filter === f ? '2px solid var(--primary-500)' : '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-md)',
                                background: filter === f ? 'var(--primary-50)' : 'white',
                                color: filter === f ? 'var(--primary-700)' : 'var(--gray-600)',
                                cursor: 'pointer',
                                textTransform: 'capitalize',
                            }}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>

            {/* Queue List */}
            {filteredQueue.length === 0 ? (
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-8)',
                    background: 'var(--gray-50)',
                    borderRadius: 'var(--radius-lg)',
                }}>
                    <Inbox size={48} color="var(--gray-300)" style={{ marginBottom: 'var(--space-3)' }} />
                    <h3 style={{ margin: '0 0 var(--space-2) 0', color: 'var(--gray-600)' }}>
                        Queue is empty
                    </h3>
                    <p style={{ color: 'var(--gray-500)', margin: 0 }}>
                        No questions assigned for review. Check back later!
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {filteredQueue.map((item) => {
                        const style = priorityStyles[item.priority];

                        return (
                            <div
                                key={item.id}
                                onClick={() => navigate(`/job/${item.job_id}/review`)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 'var(--space-4)',
                                    padding: 'var(--space-4)',
                                    background: 'white',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-lg)',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s',
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.borderColor = 'var(--primary-300)';
                                    e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.borderColor = 'var(--gray-200)';
                                    e.currentTarget.style.boxShadow = 'none';
                                }}
                            >
                                {/* Priority Badge */}
                                <div style={{
                                    padding: '4px 10px',
                                    background: style.bg,
                                    color: style.color,
                                    borderRadius: 'var(--radius-sm)',
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.5px',
                                    flexShrink: 0,
                                }}>
                                    {style.label}
                                </div>

                                {/* Content */}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{
                                        fontSize: '14px',
                                        fontWeight: 500,
                                        marginBottom: '4px',
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                    }}>
                                        {item.question}
                                    </div>
                                    <div style={{
                                        display: 'flex',
                                        gap: 'var(--space-3)',
                                        fontSize: '12px',
                                        color: 'var(--gray-500)',
                                    }}>
                                        <span>{item.subject}</span>
                                        <span>•</span>
                                        <span>{item.chapter}</span>
                                        <span>•</span>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                            <Clock size={10} />
                                            Assigned {formatRelativeTime(item.assigned_at)}
                                        </span>
                                    </div>
                                </div>

                                {/* Due Date */}
                                {item.due_at && (
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                        padding: '4px 8px',
                                        background: 'var(--warning-50)',
                                        borderRadius: 'var(--radius-sm)',
                                        fontSize: '12px',
                                        color: 'var(--warning-700)',
                                    }}>
                                        <AlertCircle size={12} />
                                        {formatDueTime(item.due_at)}
                                    </div>
                                )}

                                {/* Arrow */}
                                <ArrowRight size={18} color="var(--gray-400)" />
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default ReviewQueuePage;
