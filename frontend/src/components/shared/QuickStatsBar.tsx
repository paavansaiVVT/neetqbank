import { useState, useEffect } from 'react';
import { BarChart2, Clock, CheckCircle, Loader2, TrendingUp } from 'lucide-react';

interface QuickStats {
    questionsToday: number;
    pendingReview: number;
    passRate: number;
    activeJobs: number;
}

interface QuickStatsBarProps {
    apiBaseUrl: string;
    apiKey: string;
}

export function QuickStatsBar({ apiBaseUrl, apiKey }: QuickStatsBarProps) {
    const [stats, setStats] = useState<QuickStats>({
        questionsToday: 0,
        pendingReview: 0,
        passRate: 0,
        activeJobs: 0,
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await fetch(`${apiBaseUrl}/v2/qbank/stats`, {
                    headers: apiKey ? { 'X-API-Key': apiKey } : {},
                });
                if (response.ok) {
                    const data = await response.json();
                    setStats({
                        questionsToday: data.questions_today || data.total_questions || 0,
                        pendingReview: data.pending_review || 0,
                        passRate: data.pass_rate || 0,
                        activeJobs: data.active_jobs || 0,
                    });
                }
            } catch (err) {
                console.error('Failed to fetch quick stats:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
        // Refresh every 30 seconds
        const interval = setInterval(fetchStats, 30000);
        return () => clearInterval(interval);
    }, [apiBaseUrl, apiKey]);

    const statItems = [
        {
            icon: BarChart2,
            value: stats.questionsToday,
            label: 'Today',
            color: 'var(--primary-500)',
        },
        {
            icon: Clock,
            value: stats.pendingReview,
            label: 'Pending',
            color: 'var(--warning-500)',
        },
        {
            icon: CheckCircle,
            value: `${stats.passRate}%`,
            label: 'Pass Rate',
            color: 'var(--success-500)',
        },
        {
            icon: Loader2,
            value: stats.activeJobs,
            label: 'Running',
            color: 'var(--info-500)',
            animate: stats.activeJobs > 0,
        },
    ];

    if (loading) return null;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-4)',
            padding: 'var(--space-2) var(--space-4)',
            background: 'var(--gray-50)',
            borderBottom: '1px solid var(--gray-200)',
            fontSize: '13px',
        }}>
            {statItems.map((item, i) => (
                <div
                    key={i}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        padding: 'var(--space-1) var(--space-2)',
                        background: 'white',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--gray-200)',
                    }}
                >
                    <item.icon
                        size={14}
                        color={item.color}
                        className={item.animate ? 'animate-spin' : ''}
                    />
                    <span style={{ fontWeight: 600 }}>{item.value}</span>
                    <span style={{ color: 'var(--gray-500)', fontSize: '12px' }}>{item.label}</span>
                </div>
            ))}
        </div>
    );
}

export default QuickStatsBar;
