import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { LiveGenerationView } from '../components/generation/LiveGenerationView';
import { QbankApiClient } from '../api/client';
import { GenerationJobResponse } from '../api/types';

interface JobStatusPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

export const JobStatusPage: React.FC<JobStatusPageProps> = ({ apiBaseUrl, apiKey }) => {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();
    const [job, setJob] = useState<GenerationJobResponse | null>(null);
    const [error, setError] = useState<string>("");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!jobId) return;
        const fetchJob = async () => {
            try {
                const client = new QbankApiClient(apiBaseUrl, apiKey);
                const data = await client.getJob(jobId);
                setJob(data);

                // If already complete, redirect to review
                if (['completed', 'published'].includes(data.status)) {
                    navigate(`/job/${jobId}/review`, { replace: true });
                    return;
                }
            } catch (err) {
                setError("Failed to load job details.");
            } finally {
                setLoading(false);
            }
        };
        fetchJob();
    }, [jobId, apiBaseUrl, apiKey, navigate]);

    const handleComplete = (completedJobId: string) => {
        // When generation completes, navigate to review
        navigate(`/job/${completedJobId}/review`);
    };

    if (loading) {
        return <div style={{ padding: '40px', textAlign: 'center' }}>Loading job details...</div>;
    }

    if (error || !job) {
        return (
            <div style={{ padding: '20px', color: 'red', textAlign: 'center' }}>
                {error || "Job not found"}
                <br />
                <button className="btn btn-secondary" onClick={() => navigate('/jobs')} style={{ marginTop: '20px' }}>
                    Back to History
                </button>
            </div>
        );
    }

    return (
        <div style={{ padding: 'var(--space-6)', maxWidth: '1000px', margin: '0 auto' }}>
            <LiveGenerationView
                job={job}
                apiBaseUrl={apiBaseUrl}
                apiKey={apiKey}
                onComplete={handleComplete}
                onError={setError}
            />
        </div>
    );
};
