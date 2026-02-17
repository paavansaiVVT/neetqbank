import { useState, useEffect } from 'react';
import { Coins, TrendingUp, TrendingDown, Calendar, DollarSign, Zap } from 'lucide-react';
import { QbankApiClient } from '../../api/client';
import { TokenUsageResponse } from '../../api/types';

interface TokenUsage {
    date: string;
    inputTokens: number;
    outputTokens: number;
    cost: number;
    costInr: number;
    generationTokens: number;
    qcTokens: number;
}

interface TokenUsageProps {
    usage?: TokenUsage[];
    apiClient?: QbankApiClient;
}

export function TokenUsageCard({ usage: initialUsage, apiClient }: TokenUsageProps) {
    const [period, setPeriod] = useState<'week' | 'month'>('week');
    const [usage, setUsage] = useState<TokenUsage[]>(initialUsage || []);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!apiClient) return;

        const fetchUsage = async () => {
            try {
                setLoading(true);
                const days = period === 'week' ? 7 : 30;
                const response = await apiClient.getTokenUsage(days);

                // Map API response to component format
                const mappedUsage = response.daily_usage.map(u => ({
                    date: u.date,
                    inputTokens: u.input_tokens,
                    outputTokens: u.output_tokens,
                    cost: u.cost,
                    costInr: u.cost_inr || u.cost * 86.5,
                    generationTokens: u.generation_tokens || 0,
                    qcTokens: u.qc_tokens || 0,
                }));

                setUsage(mappedUsage);
            } catch (err) {
                console.error("Failed to fetch token usage:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchUsage();
    }, [apiClient, period]);

    // If no data yet (loading or initial), show empty state or loading
    if (loading && usage.length === 0) {
        return (
            <div style={{
                background: 'white',
                border: '1px solid var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
                height: '240px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--gray-500)'
            }}>
                Loading usage data...
            </div>
        );
    }

    if (usage.length === 0) {
        return (
            <div style={{
                background: 'white',
                border: '1px solid var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
                height: '240px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--gray-500)'
            }}>
                No usage data available
            </div>
        );
    }

    // Calculate totals
    const totals = usage.reduce((acc, day) => ({
        inputTokens: acc.inputTokens + day.inputTokens,
        outputTokens: acc.outputTokens + day.outputTokens,
        cost: acc.cost + day.cost,
        costInr: acc.costInr + day.costInr,
        generationTokens: acc.generationTokens + day.generationTokens,
        qcTokens: acc.qcTokens + day.qcTokens,
    }), { inputTokens: 0, outputTokens: 0, cost: 0, costInr: 0, generationTokens: 0, qcTokens: 0 });

    const totalTokens = totals.inputTokens + totals.outputTokens;
    // const avgDailyCost = totals.cost / usage.length; // Unused
    const maxCost = Math.max(...usage.map(u => u.cost)) || 1; // Prevent div by zero

    // Calculate trend (compare last 3 days to previous 3)
    const recent = usage.slice(-3).reduce((a, b) => a + b.cost, 0) / 3;
    const previous = usage.slice(-6, -3).reduce((a, b) => a + b.cost, 0) / 3;
    const trend = previous > 0 ? ((recent - previous) / previous) * 100 : 0;

    return (
        <div style={{
            background: 'white',
            border: '1px solid var(--gray-200)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-4)',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 'var(--space-4)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <Coins size={20} color="var(--primary-600)" />
                    <h3 style={{ margin: 0, fontSize: '16px' }}>Token Usage</h3>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
                    {(['week', 'month'] as const).map(p => (
                        <button
                            key={p}
                            onClick={() => setPeriod(p)}
                            style={{
                                padding: '4px 10px',
                                fontSize: '12px',
                                border: 'none',
                                borderRadius: 'var(--radius-sm)',
                                background: period === p ? 'var(--primary-100)' : 'transparent',
                                color: period === p ? 'var(--primary-700)' : 'var(--gray-500)',
                                cursor: 'pointer',
                            }}
                        >
                            {p === 'week' ? '7 Days' : '30 Days'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Stats Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-4)',
            }}>
                <div style={{
                    padding: 'var(--space-3)',
                    background: 'var(--gray-50)',
                    borderRadius: 'var(--radius-md)',
                }}>
                    <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginBottom: '4px' }}>
                        Total Tokens
                    </div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                        <span style={{ fontSize: '20px', fontWeight: 600 }}>
                            {(totalTokens / 1000).toFixed(1)}k
                        </span>
                    </div>
                </div>

                <div style={{
                    padding: 'var(--space-3)',
                    background: 'var(--success-50)',
                    borderRadius: 'var(--radius-md)',
                }}>
                    <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginBottom: '4px' }}>
                        Total Cost
                    </div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                        <DollarSign size={14} color="var(--success-600)" />
                        <span style={{ fontSize: '20px', fontWeight: 600, color: 'var(--success-700)' }}>
                            {totals.cost.toFixed(2)}
                        </span>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--gray-500)', marginTop: '2px' }}>
                        ₹{totals.costInr.toFixed(2)}
                    </div>
                </div>

                <div style={{
                    padding: 'var(--space-3)',
                    background: trend > 0 ? 'var(--warning-50)' : 'var(--success-50)',
                    borderRadius: 'var(--radius-md)',
                }}>
                    <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginBottom: '4px' }}>
                        Trend
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {trend > 0 ? (
                            <TrendingUp size={16} color="var(--warning-600)" />
                        ) : (
                            <TrendingDown size={16} color="var(--success-600)" />
                        )}
                        <span style={{
                            fontSize: '16px',
                            fontWeight: 600,
                            color: trend > 0 ? 'var(--warning-700)' : 'var(--success-700)',
                        }}>
                            {trend > 0 ? '+' : ''}{trend.toFixed(0)}%
                        </span>
                    </div>
                </div>
            </div>

            {/* Simple Bar Chart */}
            <div style={{ marginBottom: 'var(--space-3)' }}>
                <div style={{ fontSize: '12px', color: 'var(--gray-500)', marginBottom: 'var(--space-2)' }}>
                    Daily Cost
                </div>
                <div style={{ display: 'flex', gap: '4px', alignItems: 'flex-end', height: '80px' }}>
                    {usage.map((day, i) => {
                        const height = (day.cost / maxCost) * 100;
                        const date = new Date(day.date);
                        const dayLabel = date.toLocaleDateString('en-US', { weekday: 'short' });

                        return (
                            <div
                                key={i}
                                style={{
                                    flex: 1,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '4px',
                                }}
                                title={`${day.date}: $${day.cost.toFixed(2)}`}
                            >
                                <div style={{
                                    width: '100%',
                                    height: `${height}%`,
                                    background: i === usage.length - 1
                                        ? 'var(--primary-500)'
                                        : 'var(--primary-200)',
                                    borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                                    minHeight: '4px',
                                    transition: 'height 0.3s',
                                }} />
                                <span style={{ fontSize: '10px', color: 'var(--gray-400)' }}>
                                    {dayLabel}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Token Breakdown */}
            <div style={{
                display: 'flex',
                gap: 'var(--space-4)',
                padding: 'var(--space-3)',
                background: 'var(--gray-50)',
                borderRadius: 'var(--radius-md)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: 'var(--primary-500)',
                    }} />
                    <span style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                        Input: {(totals.inputTokens / 1000).toFixed(1)}k tokens
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: 'var(--success-500)',
                    }} />
                    <span style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                        Output: {(totals.outputTokens / 1000).toFixed(1)}k tokens
                    </span>
                </div>
                {(totals.generationTokens > 0 || totals.qcTokens > 0) && (
                    <>
                        <div style={{ width: '1px', background: 'var(--gray-300)' }} />
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <Zap size={10} color="var(--warning-500)" />
                            <span style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                                Gen: {(totals.generationTokens / 1000).toFixed(1)}k
                            </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <div style={{
                                width: '8px',
                                height: '8px',
                                borderRadius: '50%',
                                background: 'var(--warning-400)',
                            }} />
                            <span style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                                QC: {(totals.qcTokens / 1000).toFixed(1)}k
                            </span>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default TokenUsageCard;
