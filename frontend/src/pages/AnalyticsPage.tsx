import { useState, useEffect, useCallback } from 'react';
import { QbankApiClient } from '../api/client';
import type { AnalyticsResponse } from '../api/types';
import './AnalyticsPage.css';

const getBaseUrl = () => {
    if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
    if (import.meta.env.DEV) return '';
    return `${window.location.protocol}//${window.location.hostname}:8000`;
};

const api = new QbankApiClient(
    getBaseUrl(),
    import.meta.env.VITE_QBANK_API_KEY || ''
);

// ── Color Palettes ──────────────────────────────────────────
const SUBJECT_COLORS = [
    '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899',
    '#8b5cf6', '#14b8a6', '#f97316', '#ef4444', '#3b82f6',
];

const DIFFICULTY_COLORS: Record<string, string> = {
    easy: '#10b981',
    medium: '#f59e0b',
    hard: '#f97316',
    veryhard: '#ef4444',
};

const COGNITIVE_COLORS: Record<string, string> = {
    remembering: '#06b6d4',
    understanding: '#3b82f6',
    applying: '#6366f1',
    analyzing: '#8b5cf6',
    evaluating: '#ec4899',
    creating: '#f97316',
};

const DIFFICULTY_LABELS: Record<string, string> = {
    easy: 'Easy',
    medium: 'Medium',
    hard: 'Hard',
    veryhard: 'Very Hard',
};

const COGNITIVE_LABELS: Record<string, string> = {
    remembering: 'Remembering',
    understanding: 'Understanding',
    applying: 'Applying',
    analyzing: 'Analyzing',
    evaluating: 'Evaluating',
    creating: 'Creating',
};

/**
 * Normalizes difficulty data from the backend.
 * Some items have JSON distribution strings as keys (e.g. '{"easy":30,"medium":45}')
 * instead of clean labels. This merges them into canonical buckets.
 */
function normalizeDifficulty(raw: Record<string, number>): Record<string, number> {
    const ALIAS: Record<string, string> = {
        easy: 'easy',
        medium: 'medium',
        moderate: 'medium',
        hard: 'hard',
        difficult: 'hard',
        veryhard: 'veryhard',
        very_hard: 'veryhard',
    };

    const result: Record<string, number> = {};

    for (const [key, count] of Object.entries(raw)) {
        const trimmed = key.trim().toLowerCase();
        const canonical = ALIAS[trimmed];

        if (canonical) {
            result[canonical] = (result[canonical] || 0) + count;
        } else if (trimmed.startsWith('{')) {
            // JSON distribution string — skip (it's noise from batch difficulty)
            // Don't add to results
        } else {
            // Unknown label — capitalize and keep
            result[trimmed] = (result[trimmed] || 0) + count;
        }
    }

    return result;
}

// ── Inline SVG Components ───────────────────────────────────

function DailyTrendChart({ data }: { data: AnalyticsResponse['daily_trend'] }) {
    if (!data.length) return <div className="chart-empty">No data for this period</div>;

    const maxCount = Math.max(...data.map(d => d.count), 1);
    const chartWidth = 600;
    const chartHeight = 200;
    const padding = { top: 20, right: 20, bottom: 40, left: 50 };
    const w = chartWidth - padding.left - padding.right;
    const h = chartHeight - padding.top - padding.bottom;

    const xStep = data.length > 1 ? w / (data.length - 1) : w / 2;

    const points = data.map((d, i) => ({
        x: padding.left + i * xStep,
        y: padding.top + h - (d.count / maxCount) * h,
        count: d.count,
        date: d.date,
    }));

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const areaPath = `${linePath} L ${points[points.length - 1].x} ${padding.top + h} L ${points[0].x} ${padding.top + h} Z`;

    // Y-axis ticks
    const yTicks = [0, Math.round(maxCount / 2), maxCount];

    return (
        <div className="chart-container">
            <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet">
                {/* Grid lines */}
                {yTicks.map(tick => {
                    const y = padding.top + h - (tick / maxCount) * h;
                    return (
                        <g key={tick}>
                            <line x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke="#e5e7eb" strokeWidth="1" />
                            <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">{tick}</text>
                        </g>
                    );
                })}

                {/* Area fill */}
                <path d={areaPath} fill="url(#trendGradient)" opacity="0.15" />

                {/* Line */}
                <path d={linePath} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {/* Dots */}
                {points.map((p, i) => (
                    <g key={i}>
                        <circle cx={p.x} cy={p.y} r="4" fill="#6366f1" stroke="white" strokeWidth="2" />
                        {/* Show count on every other dot or if small dataset */}
                        {(data.length <= 10 || i % 2 === 0) && (
                            <text x={p.x} y={p.y - 10} textAnchor="middle" fontSize="10" fontWeight="600" fill="#374151">
                                {p.count}
                            </text>
                        )}
                    </g>
                ))}

                {/* X-axis labels */}
                {points.map((p, i) => {
                    const show = data.length <= 10 || i % Math.ceil(data.length / 8) === 0 || i === data.length - 1;
                    if (!show) return null;
                    const label = new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    return (
                        <text key={i} x={p.x} y={chartHeight - 8} textAnchor="middle" fontSize="9" fill="#9ca3af">
                            {label}
                        </text>
                    );
                })}

                {/* Gradient def */}
                <defs>
                    <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                    </linearGradient>
                </defs>
            </svg>
        </div>
    );
}

function DonutChart({ data, colors, labels }: {
    data: Record<string, number>;
    colors: Record<string, string>;
    labels: Record<string, string>;
}) {
    const entries = Object.entries(data).filter(([, v]) => v > 0);
    if (!entries.length) return <div className="chart-empty">No data</div>;

    const total = entries.reduce((sum, [, v]) => sum + v, 0);
    const radius = 70;
    const strokeWidth = 20;
    const cx = 90;
    const cy = 90;

    let currentAngle = -90;

    const arcs = entries.map(([key, value]) => {
        const angle = (value / total) * 360;
        const startAngle = currentAngle;
        const endAngle = currentAngle + angle;
        currentAngle = endAngle;

        const startRad = (startAngle * Math.PI) / 180;
        const endRad = (endAngle * Math.PI) / 180;

        const x1 = cx + radius * Math.cos(startRad);
        const y1 = cy + radius * Math.sin(startRad);
        const x2 = cx + radius * Math.cos(endRad);
        const y2 = cy + radius * Math.sin(endRad);

        const largeArc = angle > 180 ? 1 : 0;
        const path = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;

        return { key, path, color: colors[key] || '#94a3b8' };
    });

    return (
        <div className="donut-container">
            <svg width="180" height="180" viewBox="0 0 180 180">
                {arcs.map(arc => (
                    <path
                        key={arc.key}
                        d={arc.path}
                        fill="none"
                        stroke={arc.color}
                        strokeWidth={strokeWidth}
                        strokeLinecap="round"
                    />
                ))}
                <text x={cx} y={cy - 6} textAnchor="middle" fontSize="22" fontWeight="700" fill="#374151">
                    {total}
                </text>
                <text x={cx} y={cy + 12} textAnchor="middle" fontSize="10" fill="#9ca3af">
                    Total
                </text>
            </svg>

            <div className="donut-legend">
                {entries.map(([key, value]) => (
                    <div key={key} className="donut-legend-item">
                        <span className="donut-legend-swatch" style={{ background: colors[key] || '#94a3b8' }} />
                        <span>{labels[key] || key}</span>
                        <span className="donut-legend-value">{value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function HorizontalBars({
    data,
    colorFn,
}: {
    data: { label: string; value: number }[];
    colorFn?: (index: number) => string;
}) {
    if (!data.length) return <div className="chart-empty">No data</div>;
    const maxVal = Math.max(...data.map(d => d.value), 1);

    return (
        <div>
            {data.map((item, i) => (
                <div key={i} className="hbar-row">
                    <span className="hbar-label" title={item.label}>{item.label}</span>
                    <div className="hbar-track">
                        <div
                            className="hbar-fill"
                            style={{
                                width: `${(item.value / maxVal) * 100}%`,
                                background: colorFn ? colorFn(i) : SUBJECT_COLORS[i % SUBJECT_COLORS.length],
                            }}
                        />
                    </div>
                    <span className="hbar-count">{item.value}</span>
                </div>
            ))}
        </div>
    );
}

// ── Main Page Component ─────────────────────────────────────

export default function AnalyticsPage() {
    const [data, setData] = useState<AnalyticsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [days, setDays] = useState(30);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.getAnalytics(days);
            setData(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load analytics');
        } finally {
            setLoading(false);
        }
    }, [days]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60_000);
        return () => clearInterval(interval);
    }, [fetchData]);

    if (loading && !data) {
        return (
            <div className="analytics-page">
                <div className="analytics-loading">
                    <div className="spinner" />
                    <span>Loading analytics…</span>
                </div>
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="analytics-page">
                <div className="analytics-error">
                    <span>⚠️ {error}</span>
                    <button onClick={fetchData}>Try Again</button>
                </div>
            </div>
        );
    }

    if (!data) return null;

    const { summary, daily_trend, by_subject, by_chapter, by_difficulty, by_cognitive, by_user, model_usage } = data;

    return (
        <div className="analytics-page">
            {/* Header */}
            <div className="analytics-header">
                <h1><span>📊</span> Analytics</h1>
                <div className="date-range-pills">
                    {[7, 14, 30].map(d => (
                        <button key={d} className={days === d ? 'active' : ''} onClick={() => setDays(d)}>
                            {d}d
                        </button>
                    ))}
                </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-label">Total MCQs</div>
                    <div className="kpi-value">{summary.total_mcqs.toLocaleString()}</div>
                    <div className="kpi-sub">Generated in {days} days</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">This Week</div>
                    <div className="kpi-value">{summary.mcqs_this_week.toLocaleString()}</div>
                    <div className="kpi-sub">Last 7 days</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Approval Rate</div>
                    <div className="kpi-value">{summary.approval_rate}%</div>
                    <div className="kpi-sub">{summary.rejection_rate}% rejected</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Published</div>
                    <div className="kpi-value">{summary.published_count.toLocaleString()}</div>
                    <div className="kpi-sub">Live in question bank</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Total Cost</div>
                    <div className="kpi-value">${summary.total_cost_usd.toFixed(2)}</div>
                    <div className="kpi-sub">≈ ₹{(summary.total_cost_usd * 83).toFixed(0)}</div>
                </div>
            </div>

            {/* Charts Grid */}
            <div className="charts-grid">
                {/* Daily Trend — Full Width */}
                <div className="chart-card full-width">
                    <h3><span>📈</span> Daily Questions Created</h3>
                    <DailyTrendChart data={daily_trend} />
                </div>

                {/* Subject Breakdown */}
                <div className="chart-card">
                    <h3><span>📚</span> By Subject</h3>
                    <HorizontalBars
                        data={by_subject.map(s => ({ label: s.subject, value: s.count }))}
                    />
                </div>

                {/* Difficulty Distribution */}
                <div className="chart-card">
                    <h3><span>🎯</span> Difficulty Distribution</h3>
                    <DonutChart data={normalizeDifficulty(by_difficulty)} colors={DIFFICULTY_COLORS} labels={DIFFICULTY_LABELS} />
                </div>

                {/* Chapter Heatmap */}
                <div className="chart-card">
                    <h3><span>📖</span> Top Chapters</h3>
                    <HorizontalBars
                        data={by_chapter.map(c => ({ label: c.chapter, value: c.count }))}
                        colorFn={(i) => SUBJECT_COLORS[i % SUBJECT_COLORS.length]}
                    />
                </div>

                {/* Cognitive Level */}
                <div className="chart-card">
                    <h3><span>🧠</span> Cognitive Levels</h3>
                    <DonutChart data={by_cognitive} colors={COGNITIVE_COLORS} labels={COGNITIVE_LABELS} />
                </div>

                {/* Model Usage */}
                {Object.keys(model_usage).length > 0 && (
                    <div className="chart-card">
                        <h3><span>🤖</span> Model Usage</h3>
                        <HorizontalBars
                            data={Object.entries(model_usage).map(([model, count]) => ({
                                label: model.split('/').pop() || model,
                                value: count,
                            }))}
                            colorFn={(i) => ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899'][i % 5]}
                        />
                    </div>
                )}

                {/* User Leaderboard */}
                {by_user.length > 0 && (
                    <div className="chart-card full-width">
                        <h3><span>👥</span> Team Leaderboard</h3>
                        <table className="leaderboard-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>User</th>
                                    <th>MCQs Created</th>
                                    <th>Approval Rate</th>
                                    <th>Cost</th>
                                </tr>
                            </thead>
                            <tbody>
                                {by_user.map((u, i) => (
                                    <tr key={u.user_id}>
                                        <td className="leaderboard-rank">{i + 1}</td>
                                        <td className="leaderboard-name">{u.user_name}</td>
                                        <td>{u.count.toLocaleString()}</td>
                                        <td>
                                            <span className={`badge-rate ${u.approval_rate >= 80 ? 'good' : u.approval_rate >= 50 ? 'ok' : 'low'}`}>
                                                {u.approval_rate}%
                                            </span>
                                        </td>
                                        <td>${u.cost.toFixed(2)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
