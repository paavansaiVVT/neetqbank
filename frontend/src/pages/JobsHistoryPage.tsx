import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { QbankApiClient } from '../api/client';
import { GenerationJobResponse } from '../api/types';
import {
    Search, ChevronLeft, ChevronRight, Filter, Eye, FileText,
    CheckCircle, XCircle, Clock, Coins, ChevronDown, X, ArrowUpDown,
    BarChart2, RefreshCw
} from 'lucide-react';
import './JobsHistoryPage.css';

interface JobsHistoryPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

type SortField = 'date' | 'items' | 'cost';
type SortDir = 'asc' | 'desc';

export const JobsHistoryPage: React.FC<JobsHistoryPageProps> = ({ apiBaseUrl, apiKey }) => {
    const [jobs, setJobs] = useState<GenerationJobResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [limit] = useState(20);
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
    const [expandedItems, setExpandedItems] = useState<any[]>([]);
    const [expandedLoading, setExpandedLoading] = useState(false);
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [showFilters, setShowFilters] = useState(false);
    const [sortField, setSortField] = useState<SortField>('date');
    const [sortDir, setSortDir] = useState<SortDir>('desc');
    const navigate = useNavigate();

    const client = useMemo(() => new QbankApiClient(apiBaseUrl, apiKey), [apiBaseUrl, apiKey]);

    useEffect(() => {
        const fetchJobs = async () => {
            setLoading(true);
            try {
                const offset = (page - 1) * limit;
                const data = await client.listJobs(limit, offset);
                setJobs(data.items);
                setTotal(data.total);
            } catch (err) {
                console.error('Failed to load jobs:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchJobs();
    }, [client, page, limit]);

    // Filter and sort locally
    const filteredJobs = useMemo(() => {
        let result = jobs;

        // Search filter
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(j =>
                (j.selected_subject || '').toLowerCase().includes(q) ||
                (j.selected_chapter || '').toLowerCase().includes(q) ||
                (j.selected_input || '').toLowerCase().includes(q) ||
                j.job_id.toLowerCase().includes(q)
            );
        }

        // Status filter
        if (statusFilter !== 'all') {
            result = result.filter(j => j.status === statusFilter);
        }

        // Sort
        result = [...result].sort((a, b) => {
            let cmp = 0;
            if (sortField === 'date') {
                cmp = new Date(a.timestamps.created_at).getTime() - new Date(b.timestamps.created_at).getTime();
            } else if (sortField === 'items') {
                cmp = a.generated_count - b.generated_count;
            } else if (sortField === 'cost') {
                cmp = (a.token_usage?.total_cost || 0) - (b.token_usage?.total_cost || 0);
            }
            return sortDir === 'desc' ? -cmp : cmp;
        });

        return result;
    }, [jobs, searchQuery, statusFilter, sortField, sortDir]);

    const totalPages = Math.ceil(total / limit);

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const formatCost = (cost: number) => {
        if (cost < 0.01) return `$${cost.toFixed(4)}`;
        return `$${cost.toFixed(2)}`;
    };

    const formatCostINR = (cost: number) => {
        const inr = cost * 85; // approximate
        if (inr < 1) return `₹${inr.toFixed(2)}`;
        return `₹${inr.toFixed(1)}`;
    };

    const parseDifficulty = (diff: string | undefined) => {
        if (!diff) return null;
        try {
            const obj = JSON.parse(diff);
            if (typeof obj === 'object') return obj;
        } catch { }
        return diff; // simple string
    };

    const getStatusBadge = (status: string) => {
        const config: Record<string, { bg: string; color: string; icon: React.ReactNode }> = {
            completed: { bg: 'var(--success-50, #ecfdf5)', color: 'var(--success-700, #15803d)', icon: <CheckCircle size={12} /> },
            published: { bg: '#f3e8ff', color: '#7e22ce', icon: <FileText size={12} /> },
            failed: { bg: 'var(--danger-50, #fef2f2)', color: 'var(--danger-700, #b91c1c)', icon: <XCircle size={12} /> },
            running: { bg: 'var(--primary-50, #eff6ff)', color: 'var(--primary-700, #1d4ed8)', icon: <BarChart2 size={12} /> },
            queued: { bg: 'var(--gray-50, #f9fafb)', color: 'var(--gray-700, #374151)', icon: <Clock size={12} /> },
        };
        const s = config[status] || config.queued;
        return (
            <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: s.bg, color: s.color,
            }}>
                {s.icon} {status}
            </span>
        );
    };

    const toggleExpand = async (jobId: string) => {
        if (expandedJobId === jobId) {
            setExpandedJobId(null);
            setExpandedItems([]);
            return;
        }

        setExpandedJobId(jobId);
        setExpandedLoading(true);
        try {
            const data = await client.getItems(jobId, { limit: 100 });
            setExpandedItems(data.items);
        } catch (err) {
            console.error('Failed to load items:', err);
            setExpandedItems([]);
        } finally {
            setExpandedLoading(false);
        }
    };

    const toggleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDir('desc');
        }
    };

    const SortIcon = ({ field }: { field: SortField }) => (
        <ArrowUpDown
            size={12}
            style={{
                opacity: sortField === field ? 1 : 0.3,
                cursor: 'pointer',
                marginLeft: 4,
            }}
            onClick={(e) => { e.stopPropagation(); toggleSort(field); }}
        />
    );

    return (
        <div className="jobs-page-container">
            <div className="jobs-header">
                <div>
                    <h1 className="jobs-title">Job History</h1>
                    <p style={{ color: 'var(--gray-500)', fontSize: '14px', marginTop: '4px' }}>
                        {total} total batches · Click any row to see its questions
                    </p>
                </div>
                <div className="jobs-controls">
                    <div style={{ position: 'relative' }}>
                        <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: 'var(--gray-400)' }} />
                        <input
                            type="text"
                            placeholder="Search subject, chapter, topic..."
                            className="search-input"
                            style={{ paddingLeft: '36px' }}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        {searchQuery && (
                            <X
                                size={14}
                                style={{ position: 'absolute', right: 10, top: 12, cursor: 'pointer', color: 'var(--gray-400)' }}
                                onClick={() => setSearchQuery('')}
                            />
                        )}
                    </div>
                    <div style={{ position: 'relative' }}>
                        <button
                            className={`btn ${statusFilter !== 'all' ? 'btn-primary' : 'btn-secondary'}`}
                            onClick={() => setShowFilters(!showFilters)}
                        >
                            <Filter size={16} style={{ marginRight: 6 }} />
                            {statusFilter !== 'all' ? statusFilter : 'Filter'}
                            <ChevronDown size={14} style={{ marginLeft: 4 }} />
                        </button>
                        {showFilters && (
                            <div style={{
                                position: 'absolute', top: '100%', right: 0, marginTop: 4,
                                background: 'white', border: '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-md)', boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                                zIndex: 100, minWidth: 160, overflow: 'hidden',
                            }}>
                                {['all', 'completed', 'published', 'running', 'queued', 'failed'].map(s => (
                                    <button
                                        key={s}
                                        onClick={() => { setStatusFilter(s); setShowFilters(false); }}
                                        style={{
                                            display: 'block', width: '100%', padding: '8px 16px',
                                            border: 'none', background: statusFilter === s ? 'var(--primary-50)' : 'transparent',
                                            color: statusFilter === s ? 'var(--primary-700)' : 'var(--gray-700)',
                                            fontWeight: statusFilter === s ? 600 : 400,
                                            textAlign: 'left', cursor: 'pointer', fontSize: '13px',
                                        }}
                                    >
                                        {s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1)}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="jobs-table-container">
                <table className="jobs-table">
                    <thead>
                        <tr>
                            <th style={{ width: 40 }}></th>
                            <th>Batch Info</th>
                            <th>Status</th>
                            <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('items')}>
                                Items <SortIcon field="items" />
                            </th>
                            <th>Difficulty</th>
                            <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('cost')}>
                                Cost <SortIcon field="cost" />
                            </th>
                            <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('date')}>
                                Date <SortIcon field="date" />
                            </th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan={8} style={{ textAlign: 'center', padding: '40px' }}>Loading jobs...</td></tr>
                        ) : filteredJobs.length === 0 ? (
                            <tr><td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--gray-400)' }}>
                                {searchQuery ? 'No jobs match your search.' : 'No jobs found.'}
                            </td></tr>
                        ) : (
                            filteredJobs.map((job) => {
                                const isExpanded = expandedJobId === job.job_id;
                                const diff = parseDifficulty(job.difficulty);

                                return (
                                    <React.Fragment key={job.job_id}>
                                        <tr
                                            onClick={() => toggleExpand(job.job_id)}
                                            style={{
                                                cursor: 'pointer',
                                                background: isExpanded ? 'var(--primary-50, #eff6ff)' : undefined,
                                            }}
                                        >
                                            <td style={{ textAlign: 'center' }}>
                                                <ChevronDown
                                                    size={16}
                                                    style={{
                                                        color: 'var(--gray-400)',
                                                        transition: 'transform 0.2s',
                                                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                                    }}
                                                />
                                            </td>
                                            <td>
                                                <div style={{ fontWeight: 600, color: 'var(--gray-900)' }}>
                                                    {job.selected_subject || 'Unknown'}
                                                </div>
                                                <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>
                                                    {job.selected_chapter}
                                                    {job.selected_input ? ` · ${job.selected_input}` : ''}
                                                </div>
                                            </td>
                                            <td>{getStatusBadge(job.status)}</td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span style={{ fontWeight: 600, color: 'var(--gray-900)' }}>
                                                        {Math.min(job.generated_count, job.requested_count)}
                                                    </span>
                                                    <span style={{ color: 'var(--gray-400)', fontSize: '12px' }}>
                                                        / {job.requested_count}
                                                    </span>
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2, fontSize: '11px' }}>
                                                    <span style={{ color: 'var(--success-600, #16a34a)' }}>
                                                        ✓{job.passed_count}
                                                    </span>
                                                    {job.failed_count > 0 && (
                                                        <span style={{ color: 'var(--danger-600, #dc2626)' }}>
                                                            ✗{job.failed_count}
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                            <td>
                                                {typeof diff === 'object' && diff ? (
                                                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                                                        {Object.entries(diff).map(([k, v]) => (
                                                            <span key={k} style={{
                                                                display: 'inline-block', padding: '1px 6px',
                                                                fontSize: '10px', borderRadius: '8px',
                                                                background: k === 'easy' ? '#dcfce7' : k === 'medium' ? '#fef9c3' : k === 'hard' ? '#fee2e2' : '#ede9fe',
                                                                color: k === 'easy' ? '#166534' : k === 'medium' ? '#854d0e' : k === 'hard' ? '#991b1b' : '#5b21b6',
                                                                fontWeight: 600,
                                                            }}>
                                                                {k[0].toUpperCase()}{String(v)}%
                                                            </span>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <span style={{
                                                        display: 'inline-block', padding: '2px 8px',
                                                        fontSize: '11px', borderRadius: '8px', fontWeight: 600,
                                                        background: diff === 'easy' ? '#dcfce7' : diff === 'hard' ? '#fee2e2' : '#fef9c3',
                                                        color: diff === 'easy' ? '#166534' : diff === 'hard' ? '#991b1b' : '#854d0e',
                                                    }}>
                                                        {typeof diff === 'string' ? diff : 'medium'}
                                                    </span>
                                                )}
                                            </td>
                                            <td>
                                                <div style={{ fontSize: '13px', fontWeight: 500 }}>
                                                    {formatCost(job.token_usage?.total_cost || 0)}
                                                </div>
                                                <div style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                                                    {formatCostINR(job.token_usage?.total_cost || 0)}
                                                </div>
                                            </td>
                                            <td style={{ color: 'var(--gray-600)', fontSize: '13px' }}>
                                                {formatDate(job.timestamps.created_at)}
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', gap: 6 }}>
                                                    {job.status === 'published' ? (
                                                        <span
                                                            style={{
                                                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                                                padding: '4px 10px', borderRadius: '8px', fontSize: '11px',
                                                                fontWeight: 600, background: '#f0fdf4', color: '#15803d',
                                                                border: '1px solid #bbf7d0',
                                                            }}
                                                        >
                                                            <CheckCircle size={12} /> Published
                                                        </span>
                                                    ) : job.status === 'completed' ? (
                                                        <button
                                                            className="btn btn-primary"
                                                            style={{ padding: '5px 10px', fontSize: '11px' }}
                                                            onClick={(e) => { e.stopPropagation(); navigate(`/job/${job.job_id}/review`); }}
                                                        >
                                                            <FileText size={12} style={{ marginRight: 4 }} /> Review
                                                        </button>
                                                    ) : job.status === 'failed' ? (
                                                        <button
                                                            className="btn btn-secondary"
                                                            style={{
                                                                padding: '5px 10px', fontSize: '11px',
                                                                color: '#dc2626', borderColor: '#fca5a5',
                                                            }}
                                                            onClick={async (e) => {
                                                                e.stopPropagation();
                                                                try {
                                                                    await client.restartJob(job.job_id);
                                                                    // Refresh the job list
                                                                    const offset = (page - 1) * limit;
                                                                    const data = await client.listJobs(limit, offset);
                                                                    setJobs(data.items);
                                                                    setTotal(data.total);
                                                                } catch (err) {
                                                                    console.error('Failed to restart job:', err);
                                                                }
                                                            }}
                                                        >
                                                            <RefreshCw size={12} style={{ marginRight: 4 }} /> Restart
                                                        </button>
                                                    ) : job.status === 'running' ? (
                                                        <button
                                                            className="btn btn-primary"
                                                            style={{ padding: '5px 10px', fontSize: '11px' }}
                                                            onClick={(e) => { e.stopPropagation(); navigate(`/job/${job.job_id}`); }}
                                                        >
                                                            <Eye size={12} style={{ marginRight: 4 }} /> Watch
                                                        </button>
                                                    ) : (
                                                        <button
                                                            className="btn btn-secondary"
                                                            style={{ padding: '5px 10px', fontSize: '11px' }}
                                                            onClick={(e) => { e.stopPropagation(); navigate(`/job/${job.job_id}`); }}
                                                        >
                                                            View
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                        {isExpanded && (
                                            <tr>
                                                <td colSpan={8} style={{ padding: 0, background: 'var(--gray-50, #f9fafb)' }}>
                                                    <div style={{
                                                        padding: '16px 24px 16px 48px',
                                                        maxHeight: '400px', overflowY: 'auto',
                                                        borderTop: '1px solid var(--gray-100)',
                                                        borderBottom: '1px solid var(--gray-100)',
                                                    }}>
                                                        {expandedLoading ? (
                                                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--gray-400)' }}>
                                                                Loading questions...
                                                            </div>
                                                        ) : expandedItems.length === 0 ? (
                                                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--gray-400)' }}>
                                                                No questions generated yet.
                                                            </div>
                                                        ) : (
                                                            <>
                                                                <div style={{
                                                                    display: 'flex', justifyContent: 'space-between',
                                                                    alignItems: 'center', marginBottom: 12,
                                                                }}>
                                                                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)' }}>
                                                                        {expandedItems.length} Questions
                                                                    </span>
                                                                    <button
                                                                        className="btn btn-primary"
                                                                        style={{ padding: '4px 12px', fontSize: '12px' }}
                                                                        onClick={() => navigate(`/job/${job.job_id}/review`)}
                                                                    >
                                                                        Open Full Review →
                                                                    </button>
                                                                </div>
                                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                                                    {expandedItems.map((item, idx) => (
                                                                        <div
                                                                            key={item.item_id}
                                                                            style={{
                                                                                display: 'flex', gap: 12, alignItems: 'flex-start',
                                                                                padding: '10px 14px', background: 'white',
                                                                                borderRadius: 'var(--radius-md, 8px)',
                                                                                border: '1px solid var(--gray-100)',
                                                                                fontSize: '13px',
                                                                            }}
                                                                        >
                                                                            <span style={{
                                                                                minWidth: 24, height: 24,
                                                                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                                                borderRadius: '50%', fontSize: '11px', fontWeight: 700,
                                                                                background: 'var(--gray-100)', color: 'var(--gray-500)',
                                                                            }}>
                                                                                {idx + 1}
                                                                            </span>
                                                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                                                <div style={{
                                                                                    fontWeight: 500, color: 'var(--gray-800)',
                                                                                    lineHeight: 1.4,
                                                                                    overflow: 'hidden', textOverflow: 'ellipsis',
                                                                                    display: '-webkit-box',
                                                                                    WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                                                                                }}>
                                                                                    {item.question}
                                                                                </div>
                                                                                <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                                                                                    {item.difficulty && (
                                                                                        <span style={{
                                                                                            padding: '1px 6px', fontSize: '10px', borderRadius: '6px',
                                                                                            fontWeight: 600,
                                                                                            background: item.difficulty === 'easy' ? '#dcfce7' : item.difficulty === 'hard' ? '#fee2e2' : item.difficulty === 'veryhard' ? '#ede9fe' : '#fef9c3',
                                                                                            color: item.difficulty === 'easy' ? '#166534' : item.difficulty === 'hard' ? '#991b1b' : item.difficulty === 'veryhard' ? '#5b21b6' : '#854d0e',
                                                                                        }}>
                                                                                            {item.difficulty}
                                                                                        </span>
                                                                                    )}
                                                                                    <span style={{
                                                                                        padding: '1px 6px', fontSize: '10px', borderRadius: '6px',
                                                                                        fontWeight: 600,
                                                                                        background: '#f0f9ff', color: '#0369a1',
                                                                                    }}>
                                                                                        {item.cognitive_level}
                                                                                    </span>
                                                                                </div>
                                                                            </div>
                                                                            <div style={{
                                                                                display: 'flex', alignItems: 'center',
                                                                                color: item.qc_status === 'pass' ? 'var(--success-600, #16a34a)' : 'var(--danger-500, #ef4444)',
                                                                            }}>
                                                                                {item.qc_status === 'pass' ? <CheckCircle size={16} /> : <XCircle size={16} />}
                                                                            </div>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>

            <div className="pagination-controls">
                <div style={{ fontSize: '13px', color: 'var(--gray-500)' }}>
                    Showing {filteredJobs.length} of {total} batches
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button
                        className="btn btn-secondary"
                        disabled={page === 1}
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                    >
                        <ChevronLeft size={16} /> Previous
                    </button>
                    <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: '14px', color: 'var(--gray-600)' }}>
                        Page {page} of {totalPages || 1}
                    </div>
                    <button
                        className="btn btn-secondary"
                        disabled={page >= totalPages}
                        onClick={() => setPage(p => p + 1)}
                    >
                        Next <ChevronRight size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
};
