import React, { useState, useEffect } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, X } from 'lucide-react';
import { MathRenderer } from '../shared/MathRenderer';

interface SimilarQuestion {
    id: number;
    question: string;
    similarity: number;
    subject: string;
    chapter: string;
}

interface DuplicateWarningProps {
    currentQuestion: string;
    similarQuestions: SimilarQuestion[];
    onDismiss?: () => void;
    showAlways?: boolean;
}

// Helper function to calculate text similarity (Jaccard index)
export function calculateSimilarity(text1: string, text2: string): number {
    const normalize = (text: string): string[] => {
        return text
            .toLowerCase()
            .replace(/[^\w\s]/g, '')
            .split(/\s+/)
            .filter(w => w.length > 2);
    };

    const words1 = new Set(normalize(text1));
    const words2 = new Set(normalize(text2));

    if (words1.size === 0 || words2.size === 0) return 0;

    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);

    return intersection.size / union.size;
}

export const DuplicateWarning: React.FC<DuplicateWarningProps> = ({
    currentQuestion,
    similarQuestions,
    onDismiss,
    showAlways = false,
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [dismissed, setDismissed] = useState(false);

    // Only show if there are similar questions
    if (similarQuestions.length === 0 || (dismissed && !showAlways)) {
        return null;
    }

    const handleDismiss = () => {
        setDismissed(true);
        onDismiss?.();
    };

    const topMatch = similarQuestions[0];
    const hasHighSimilarity = topMatch.similarity >= 0.7;

    return (
        <div
            style={{
                background: hasHighSimilarity ? 'var(--warning-50)' : 'var(--gray-50)',
                border: `1px solid ${hasHighSimilarity ? 'var(--warning-300)' : 'var(--gray-200)'}`,
                borderRadius: 'var(--radius-lg)',
                marginBottom: 'var(--space-4)',
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-3) var(--space-4)',
                    cursor: 'pointer',
                }}
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <AlertTriangle
                        size={18}
                        color={hasHighSimilarity ? 'var(--warning-600)' : 'var(--gray-500)'}
                    />
                    <span style={{
                        fontWeight: 500,
                        color: hasHighSimilarity ? 'var(--warning-700)' : 'var(--gray-600)',
                        fontSize: '14px',
                    }}>
                        {hasHighSimilarity ? 'Potential Duplicate Detected' : 'Similar Questions Found'}
                    </span>
                    <span style={{
                        fontSize: '12px',
                        padding: '2px 8px',
                        background: hasHighSimilarity ? 'var(--warning-200)' : 'var(--gray-200)',
                        borderRadius: 'var(--radius-full)',
                        color: hasHighSimilarity ? 'var(--warning-800)' : 'var(--gray-600)',
                    }}>
                        {Math.round(topMatch.similarity * 100)}% match
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <button
                        onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
                        style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '4px',
                            color: 'var(--gray-500)',
                        }}
                        title="Dismiss warning"
                    >
                        <X size={16} />
                    </button>
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && (
                <div style={{
                    borderTop: `1px solid ${hasHighSimilarity ? 'var(--warning-200)' : 'var(--gray-200)'}`,
                    padding: 'var(--space-4)',
                }}>
                    <div style={{ fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-3)' }}>
                        Found {similarQuestions.length} similar question{similarQuestions.length > 1 ? 's' : ''} in the library:
                    </div>

                    <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
                        {similarQuestions.slice(0, 3).map((sq) => (
                            <div
                                key={sq.id}
                                style={{
                                    background: 'white',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                    padding: 'var(--space-3)',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                                    <div style={{
                                        fontSize: '13px',
                                        lineHeight: 1.5,
                                        display: '-webkit-box',
                                        WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical',
                                        overflow: 'hidden',
                                        flex: 1,
                                    }}>
                                        <MathRenderer content={sq.question} />
                                    </div>
                                    <span style={{
                                        fontSize: '11px',
                                        fontWeight: 600,
                                        padding: '2px 6px',
                                        background: sq.similarity >= 0.7 ? 'var(--danger-100)' : 'var(--warning-100)',
                                        color: sq.similarity >= 0.7 ? 'var(--danger-700)' : 'var(--warning-700)',
                                        borderRadius: 'var(--radius-sm)',
                                        marginLeft: 'var(--space-2)',
                                        whiteSpace: 'nowrap',
                                    }}>
                                        {Math.round(sq.similarity * 100)}%
                                    </span>
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-2)', fontSize: '11px', color: 'var(--gray-500)' }}>
                                    <span>{sq.subject}</span>
                                    <span>•</span>
                                    <span>{sq.chapter}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    {similarQuestions.length > 3 && (
                        <div style={{
                            marginTop: 'var(--space-3)',
                            fontSize: '12px',
                            color: 'var(--gray-500)',
                            textAlign: 'center',
                        }}>
                            And {similarQuestions.length - 3} more similar questions...
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default DuplicateWarning;
