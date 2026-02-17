import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { QbankApiClient } from '../api/client';
import { GenerationJobResponse } from '../api/types';
import { TokenUsageCard } from '../components/dashboard/TokenUsageCard';
import { ActivityFeed } from '../components/dashboard/ActivityFeed';
import { PlusCircle, ArrowRight, BarChart2, CheckCircle, Zap, Clock } from 'lucide-react';
import './DashboardPage.css';

interface DashboardPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ apiBaseUrl, apiKey }) => {
    const [recentJobs, setRecentJobs] = useState<GenerationJobResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        totalQuestions: 0,
        passRate: 0,
        totalJobs: 0,
    });
    const navigate = useNavigate();

    // Initialize API client once
    const [apiClient] = useState(() => new QbankApiClient(apiBaseUrl, apiKey));

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                const [jobsData, statsData] = await Promise.all([
                    apiClient.listJobs(5), // Get latest 5 jobs
                    apiClient.getStats(),  // Get real stats from backend
                ]);

                setRecentJobs(jobsData.items);
                setStats({
                    totalQuestions: statsData.total_questions,
                    passRate: statsData.pass_rate,
                    totalJobs: statsData.total_jobs,
                });
            } catch (err) {
                console.error('Failed to load dashboard data:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchDashboardData();
    }, [apiClient]);

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const statusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'success';
            case 'published': return 'purple';
            case 'failed': return 'danger';
            case 'running': return 'primary';
            default: return 'queued';
        }
    };

    return (
        <div className="dashboard-container">
            <div className="dashboard-header">
                <div>
                    <h1 className="dashboard-title">Dashboard</h1>
                    <p className="dashboard-subtitle">Overview of your question generation activities</p>
                </div>
                <Link to="/create" className="btn btn-primary">
                    <PlusCircle size={18} /> New Batch
                </Link>
            </div>

            <div className="stats-overview">
                <div className="stat-card">
                    <div className="stat-icon blue">
                        <BarChart2 size={24} />
                    </div>
                    <div className="stat-value">{stats.totalJobs}</div>
                    <div className="stat-label">Total Batches</div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon green">
                        <CheckCircle size={24} />
                    </div>
                    <div className="stat-value">{stats.passRate}%</div>
                    <div className="stat-label">Avg. Pass Rate</div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon orange">
                        <Zap size={24} />
                    </div>
                    <div className="stat-value">{stats.totalQuestions}</div>
                    <div className="stat-label">Questions Generated</div>
                </div>
            </div>

            {/* Token Usage Analytics + Activity Feed */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 'var(--space-4)',
                marginBottom: 'var(--space-6)',
            }}>
                <TokenUsageCard apiClient={apiClient} />
                <ActivityFeed limit={5} apiClient={apiClient} />
            </div>

            <div className="recent-activity">
                <div className="section-header">
                    <h2 className="section-title">Recent Activity</h2>
                    <Link to="/jobs" className="view-all-link">View All jobs <ArrowRight size={14} /></Link>
                </div>

                <div className="jobs-table-container">
                    <table className="jobs-table">
                        <thead>
                            <tr>
                                <th>Batch Info</th>
                                <th>Status</th>
                                <th>Progress</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={5} style={{ textAlign: 'center' }}>Loading...</td></tr>
                            ) : recentJobs.length === 0 ? (
                                <tr><td colSpan={5} style={{ textAlign: 'center' }}>No recent activity</td></tr>
                            ) : (
                                recentJobs.map((job) => (
                                    <tr key={job.job_id} onClick={() => navigate(`/job/${job.job_id}`)} style={{ cursor: 'pointer' }}>
                                        <td>
                                            <div style={{ fontWeight: 600 }}>{job.selected_subject || 'Unknown Subject'}</div>
                                            <div style={{ fontSize: 12, color: 'var(--gray-500)' }}>{job.selected_chapter}</div>
                                        </td>
                                        <td>
                                            <span className={`status-badge ${statusColor(job.status)}`}>{job.status}</span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ flex: 1, height: 6, background: 'var(--gray-100)', borderRadius: 4, width: 100 }}>
                                                    <div style={{ width: `${job.progress_percent}%`, height: '100%', background: 'var(--primary-500)', borderRadius: 4 }}></div>
                                                </div>
                                                <span style={{ fontSize: 12 }}>{job.progress_percent}%</span>
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--gray-500)' }}>
                                                <Clock size={12} /> {formatDate(job.timestamps.created_at)}
                                            </div>
                                        </td>
                                        <td>
                                            <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: 12 }}>
                                                View
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};
