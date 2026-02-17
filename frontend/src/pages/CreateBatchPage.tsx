import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GenerationWizard } from '../components/wizard/GenerationWizard';
import { QbankApiClient } from '../api/client';
import { FormState as WizardFormState } from '../components/wizard/types';

interface CreateBatchPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

export const CreateBatchPage: React.FC<CreateBatchPageProps> = ({ apiBaseUrl, apiKey }) => {
    const navigate = useNavigate();
    const [subjectOptions, setSubjectOptions] = useState<string[]>([]);
    const [chapterOptions, setChapterOptions] = useState<string[]>([]);
    const [topicOptions, setTopicOptions] = useState<string[]>([]);
    const [loadingSubjects, setLoadingSubjects] = useState(false);
    const [loadingChapters, setLoadingChapters] = useState(false);
    const [loadingTopics, setLoadingTopics] = useState(false);

    // Client instance
    const client = new QbankApiClient(apiBaseUrl, apiKey);

    // Load Subjects on Mount
    useEffect(() => {
        async function loadSubjects() {
            try {
                setLoadingSubjects(true);
                const response = await client.getSubjects();
                setSubjectOptions(response.subjects);
            } catch (err) {
                console.error("Failed to load subjects", err);
            } finally {
                setLoadingSubjects(false);
            }
        }
        loadSubjects();
    }, [apiBaseUrl, apiKey]);

    const onSubjectSelect = async (subject: string) => {
        try {
            setLoadingChapters(true);
            const response = await client.getChapters(subject);
            setChapterOptions(response.chapters);
            setTopicOptions([]);
        } catch (err) {
            console.error("Failed to load chapters");
        } finally {
            setLoadingChapters(false);
        }
    };

    const onChapterSelect = async (chapter: string) => {
        // Current subject is not stored in state here easily without tracking it from onSubjectSelect or passing it down
        // But GenerationWizard passes the subject in form state? No, onChapterChange only sends chapter string.
        // We need to track current subject locally to fetch topics.
        // However, the wizard handles the UI state. We just need to fetch options.
        // Wait, GenerationWizard props: onSubjectChange(subject), onChapterChange(chapter).
        // We need to know the subject to fetch topics.
        // We can rely on a ref or simple state if we assume sequential selection.
    };

    // We need to track selections locally to fetch dependent options
    const [selectedSubject, setSelectedSubject] = useState("");

    const handleSubjectChange = (subject: string) => {
        setSelectedSubject(subject);
        onSubjectSelect(subject);
    };

    const handleChapterChange = async (chapter: string) => {
        if (!selectedSubject) return;
        try {
            setLoadingTopics(true);
            const response = await client.getTopics(selectedSubject, chapter);
            setTopicOptions(response.topics);
        } catch (err) {
            console.error("Failed to load topics");
        } finally {
            setLoadingTopics(false);
        }
    };

    const handleWizardComplete = async (formData: WizardFormState) => {
        try {
            const batchName = formData.batchName?.trim()
                || `${formData.subject} — ${formData.chapter}`;

            // Convert percentage distributions to actual question counts
            const total = formData.totalQuestions;
            const toCounts = (pctMap: Record<string, number>): Record<string, number> => {
                const counts: Record<string, number> = {};
                for (const [key, pct] of Object.entries(pctMap)) {
                    const count = Math.round((pct / 100) * total);
                    if (count > 0) counts[key] = count;
                }
                return counts;
            };

            const created = await client.createJob({
                selected_subject: formData.subject,
                selected_chapter: formData.chapter,
                selected_input: formData.topic,
                difficulty: formData.difficulty,
                count: formData.totalQuestions,
                requested_by: "internal-user",
                generation_model: formData.generationModel,
                qc_model: formData.qcModel,
                batch_name: batchName,
                cognitive: toCounts({ ...formData.cognitive }),
                question_types: toCounts({ ...formData.questionTypes }),
            });
            navigate(`/job/${created.job_id}`);
        } catch (createError) {
            console.error("Failed to create job", createError);
            alert("Failed to create job. Please try again.");
        }
    };

    return (
        <div style={{ padding: 'var(--space-6)', maxWidth: '1000px', margin: '0 auto' }}>
            <h1 style={{ fontSize: '24px', marginBottom: 'var(--space-6)', fontWeight: 700 }}>New Question Batch</h1>
            <GenerationWizard
                onComplete={handleWizardComplete}
                onCancel={() => navigate('/')}
                subjectOptions={subjectOptions}
                chapterOptions={chapterOptions}
                topicOptions={topicOptions}
                loadingChapters={loadingChapters}
                loadingTopics={loadingTopics}
                onSubjectChange={handleSubjectChange}
                onChapterChange={handleChapterChange}
            />
        </div>
    );
};
