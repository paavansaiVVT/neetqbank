import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReviewMode } from '../components/review/ReviewMode';
import { QbankApiClient } from '../api/client';
import { DraftQuestionItem, GenerationJobResponse } from '../api/types';

interface ReviewBatchPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

export const ReviewBatchPage: React.FC<ReviewBatchPageProps> = ({ apiBaseUrl, apiKey }) => {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();
    const [items, setItems] = useState<DraftQuestionItem[]>([]);
    const [job, setJob] = useState<GenerationJobResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [publishState, setPublishState] = useState<'idle' | 'publishing' | 'success' | 'error'>('idle');
    const [publishedCount, setPublishedCount] = useState(0);

    const client = new QbankApiClient(apiBaseUrl, apiKey);

    useEffect(() => {
        if (!jobId) return;
        const fetchData = async () => {
            try {
                setLoading(true);
                const [jobData, itemsData] = await Promise.all([
                    client.getJob(jobId),
                    client.getItems(jobId, {})
                ]);
                setJob(jobData);
                setItems(itemsData.items);
            } catch (err) {
                setError("Failed to load review data.");
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [jobId, apiBaseUrl, apiKey]);

    const handleUpdateItem = async (itemId: number, updates: Partial<DraftQuestionItem>) => {
        if (!jobId) return;

        // Optimistic UI Update
        setItems(prev => prev.map(i => i.item_id === itemId ? { ...i, ...updates } : i));

        try {
            const payload: any = {};
            if (updates.question !== undefined) payload.question = updates.question;
            if (updates.explanation !== undefined) payload.explanation = updates.explanation;
            if (updates.options !== undefined) payload.options = updates.options;
            if (updates.correct_answer !== undefined) payload.correct_answer = updates.correct_answer;
            if (updates.review_status !== undefined) payload.review_status = updates.review_status;

            await client.patchItem(jobId, itemId, payload);
        } catch (err) {
            console.error("Failed to update item", err);
            // Revert optimistic update? For now just log.
        }
    };

    const handleBulkUpdate = async (itemIds: number[], patch: { review_status: string }) => {
        if (!jobId) return;

        // Optimistic update for all selected items
        setItems(prev => prev.map(i =>
            itemIds.includes(i.item_id) ? { ...i, review_status: patch.review_status as any } : i
        ));

        try {
            await client.bulkUpdateItems(jobId, itemIds, patch);
        } catch (err) {
            console.error("Failed to bulk update items", err);
            // Refresh items on failure
            const itemsData = await client.getItems(jobId, {});
            setItems(itemsData.items);
        }
    };

    const handlePublish = async () => {
        if (!jobId) return;
        setPublishState('publishing');
        try {
            const approvedCount = items.filter(i => i.review_status === 'approved').length;
            await client.publish(jobId, { publish_mode: "all_approved" });
            setPublishedCount(approvedCount);
            setPublishState('success');
        } catch (err) {
            setPublishState('error');
        }
    };

    if (loading) return <div style={{ padding: '40px', textAlign: 'center' }}>Loading review...</div>;
    if (error) return <div style={{ padding: '20px', color: 'red' }}>{error}</div>;

    // Publish success screen
    if (publishState === 'success') {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '70vh',
                padding: 'var(--space-6)',
            }}>
                <div style={{
                    background: 'white',
                    borderRadius: 'var(--radius-xl)',
                    padding: 'var(--space-10)',
                    textAlign: 'center',
                    maxWidth: '500px',
                    width: '100%',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
                }}>
                    <div style={{ fontSize: '64px', marginBottom: 'var(--space-4)' }}>🎉</div>
                    <h2 style={{
                        fontSize: '24px',
                        fontWeight: 700,
                        color: 'var(--gray-800)',
                        marginBottom: 'var(--space-3)',
                    }}>
                        Published Successfully!
                    </h2>
                    <p style={{
                        color: 'var(--gray-500)',
                        fontSize: '16px',
                        marginBottom: 'var(--space-6)',
                        lineHeight: 1.6,
                    }}>
                        <strong style={{ color: 'var(--success-600)' }}>{publishedCount} question{publishedCount !== 1 ? 's' : ''}</strong> have been
                        published to the Question Bank and are now available in the library.
                    </p>
                    <div style={{
                        background: 'var(--success-50)',
                        border: '1px solid var(--success-200)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-4)',
                        marginBottom: 'var(--space-6)',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-6)' }}>
                            <div>
                                <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--success-600)' }}>{publishedCount}</div>
                                <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>Published</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--danger-500)' }}>
                                    {items.filter(i => i.review_status === 'rejected').length}
                                </div>
                                <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>Rejected</div>
                            </div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center' }}>
                        <button
                            className="btn btn-secondary"
                            onClick={() => navigate('/library')}
                            style={{ padding: 'var(--space-3) var(--space-5)' }}
                        >
                            📚 View in Library
                        </button>
                        <button
                            className="btn btn-primary"
                            onClick={() => navigate('/jobs')}
                            style={{ padding: 'var(--space-3) var(--space-5)' }}
                        >
                            📋 Job History
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Publishing in progress
    if (publishState === 'publishing') {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '70vh',
            }}>
                <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '48px', marginBottom: 'var(--space-4)', animation: 'pulse 1.5s infinite' }}>📤</div>
                    <h3 style={{ color: 'var(--gray-600)' }}>Publishing questions...</h3>
                    <p style={{ color: 'var(--gray-400)', fontSize: '14px' }}>This may take a moment</p>
                </div>
            </div>
        );
    }

    // Publish error
    if (publishState === 'error') {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '70vh',
            }}>
                <div style={{ textAlign: 'center', maxWidth: '400px' }}>
                    <div style={{ fontSize: '48px', marginBottom: 'var(--space-4)' }}>❌</div>
                    <h3 style={{ color: 'var(--danger-600)', marginBottom: 'var(--space-3)' }}>Publishing Failed</h3>
                    <p style={{ color: 'var(--gray-500)', marginBottom: 'var(--space-5)' }}>
                        Something went wrong while publishing. Please try again.
                    </p>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center' }}>
                        <button className="btn btn-secondary" onClick={() => setPublishState('idle')}>
                            Go Back
                        </button>
                        <button className="btn btn-primary" onClick={handlePublish}>
                            Retry Publish
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div style={{ padding: 'var(--space-6)' }}>
            <ReviewMode
                items={items}
                subject={job?.selected_subject || ""}
                chapter={job?.selected_chapter || ""}
                onUpdateItem={handleUpdateItem}
                onBulkUpdate={handleBulkUpdate}
                onExit={() => navigate('/jobs')}
                onComplete={handlePublish}
                apiClient={client}
            />
        </div>
    );
};
