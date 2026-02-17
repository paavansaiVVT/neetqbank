import React, { useEffect, useState, useRef } from 'react';
import { Loader2, CheckCircle, XCircle, Sparkles, Zap, BrainCircuit } from 'lucide-react';
import { GenerationJobResponse } from '../../api/types';
import { QbankApiClient } from '../../api/client';
import './styles.css';

interface LiveGenerationViewProps {
    job: GenerationJobResponse;
    apiBaseUrl: string;
    apiKey: string;
    onComplete: (jobId: string) => void;
    onError: (error: string) => void;
}

interface ProgressPayload {
    status: string;
    progress_percent: number;
    generated_count: number;
    passed_count: number;
    failed_count: number;
    new_items?: any[];
    error?: string;
}

// Prevent unbounded memory growth - cap live feed at 100 items
const MAX_LIVE_ITEMS = 100;

export const LiveGenerationView: React.FC<LiveGenerationViewProps> = ({
    job,
    apiBaseUrl,
    apiKey,
    onComplete,
    onError,
}) => {
    const [progress, setProgress] = useState(job.progress_percent || 0);
    const [generatedCount, setGeneratedCount] = useState(job.generated_count || 0);
    const [passedCount, setPassedCount] = useState(job.passed_count || 0);
    const [failedCount, setFailedCount] = useState(job.failed_count || 0);
    const [items, setItems] = useState<any[]>([]);
    const [status, setStatus] = useState(job.status);
    const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
    const wsRef = useRef<WebSocket | null>(null);
    const itemsContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Construct WebSocket URL
        const httpUrl = apiBaseUrl.replace(/\/$/, ''); // Remove trailing slash
        const wsProtocol = httpUrl.startsWith('https') ? 'wss' : 'ws';
        const wsHost = httpUrl.replace(/^https?:\/\//, '');
        const wsUrl = `${wsProtocol}://${wsHost}/v2/qbank/ws/jobs/${job.job_id}?key=${apiKey}`;

        console.log('Connecting to WebSocket:', wsUrl);

        // Fetch initial items if job has already progress
        const fetchInitialItems = async () => {
            if (job.status !== 'queued') {
                try {
                    const client = new QbankApiClient(apiBaseUrl, apiKey);
                    const response = await client.getItems(job.job_id, { limit: 100 });
                    if (response.items && response.items.length > 0) {
                        setItems(response.items);
                    }
                } catch (err) {
                    console.error('Failed to fetch initial items:', err);
                }
            }
        };
        fetchInitialItems();

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log('WebSocket connected');
            setConnectionStatus('connected');
        };

        ws.onmessage = (event) => {
            try {
                const payload: ProgressPayload = JSON.parse(event.data);
                console.log('WS Message:', payload);

                if (payload.status) setStatus(payload.status as any);
                if (payload.progress_percent !== undefined) setProgress(payload.progress_percent);
                if (payload.generated_count !== undefined) setGeneratedCount(payload.generated_count);
                if (payload.passed_count !== undefined) setPassedCount(payload.passed_count);
                if (payload.failed_count !== undefined) setFailedCount(payload.failed_count);

                if (payload.new_items && Array.isArray(payload.new_items)) {
                    const newItems = payload.new_items as any[];
                    setItems((prev) => {
                        // Filter out duplicates if any
                        const existingIds = new Set(prev.map(i => i.item_id));
                        const uniqueNewItems = newItems.filter(i => !existingIds.has(i.item_id));
                        const combined = [...prev, ...uniqueNewItems];
                        // Keep only the latest MAX_LIVE_ITEMS to prevent memory leak
                        return combined.slice(-MAX_LIVE_ITEMS);
                    });
                }

                if (payload.status === 'completed' || payload.status === 'published') {
                    setTimeout(() => onComplete(job.job_id), 2000); // Small delay to show 100%
                }

                if (payload.status === 'failed') {
                    onError(payload.error || 'Job failed');
                }

            } catch (err) {
                console.error('Failed to parse WS message:', err);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setConnectionStatus('disconnected');
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            setConnectionStatus('disconnected');
        };

        return () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        };
    }, [job.job_id, apiBaseUrl, apiKey, onComplete, onError]);

    // Clean up effect for scroll
    useEffect(() => {
        if (itemsContainerRef.current) {
            itemsContainerRef.current.scrollTop = itemsContainerRef.current.scrollHeight;
        }
    }, [items]);

    return (
        <div className="live-gen-container">
            {/* Status Card */}
            <div className="status-card">
                <div className="status-header">
                    <div className="status-title">
                        <h2><Sparkles size={20} color="var(--primary-600)" /> Generating Content</h2>
                        <p className="status-subtitle">AI is crafting your questions in real-time...</p>
                    </div>
                    <div>
                        <div className="progress-number">{progress}%</div>
                        <div className="progress-label">Completion</div>
                    </div>
                </div>

                <div className="status-body">
                    <div className="progress-track" style={{ background: 'var(--gray-100)' }}>
                        <div className="progress-fill" style={{ width: `${progress}%` }} />
                    </div>

                    <div className="stats-grid">
                        <div className="stat-item neutral">
                            <div className="stat-label" style={{ color: 'var(--gray-600)' }}>Generated</div>
                            <div className="stat-value" style={{ color: 'var(--gray-700)' }}>{generatedCount}</div>
                        </div>
                        <div className="stat-item success">
                            <div className="stat-label" style={{ color: 'var(--success-600)' }}>Passed QC</div>
                            <div className="stat-value" style={{ color: 'var(--success-700)' }}>{passedCount}</div>
                        </div>
                        <div className="stat-item danger">
                            <div className="stat-label" style={{ color: 'var(--danger-600)' }}>Failed QC</div>
                            <div className="stat-value" style={{ color: 'var(--danger-700)' }}>{failedCount}</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Feed Card */}
            <div className="feed-card">
                <div className="feed-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Zap size={16} color="#f59e0b" /> Live Feed
                    </div>
                    <div className="feed-count">{items.length} items</div>
                </div>

                <div className="feed-list" ref={itemsContainerRef}>
                    {items.length === 0 ? (
                        <div className="feed-empty">
                            <BrainCircuit size={48} style={{ opacity: 0.2, marginBottom: 16 }} />
                            <p>Waiting for first batch...</p>
                        </div>
                    ) : (
                        items.map((item, idx) => (
                            <div key={idx} className="feed-item">
                                <div className="feed-item-header">
                                    <div style={{ flex: 1 }}>
                                        <div className="feed-question" title={item.question}>{item.question}</div>
                                        <div className="feed-badges">
                                            <span className="feed-badge">{item.question_type}</span>
                                            <span className="feed-badge">{item.cognitive_level}</span>
                                        </div>
                                    </div>
                                    <div className="feed-status-icon">
                                        {(item.qc_status === 'pass' || item.QC === 'pass') ? (
                                            <CheckCircle size={20} color="var(--success-500)" />
                                        ) : (
                                            <XCircle size={20} color="var(--danger-500)" />
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                    {status === 'running' && (
                        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px' }}>
                            <Loader2 className="animate-spin" size={24} color="var(--primary-400)" />
                        </div>
                    )}
                </div>
            </div>

            <div className="footer-info">
                Job ID: {job.job_id} • Status: {status} • Connection: {connectionStatus}
            </div>
        </div>
    );
};
