import React, { useState } from 'react';
import { Lightbulb, Check, X, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

interface Suggestion {
    id: string;
    type: 'wording' | 'difficulty' | 'options' | 'explanation';
    severity: 'low' | 'medium' | 'high';
    message: string;
    suggestedFix?: string;
    originalText?: string;
}

interface AISuggestionsProps {
    suggestions: Suggestion[];
    onApply?: (suggestionId: string, fixedValue: string) => void;
    onDismiss?: (suggestionId: string) => void;
}

const SEVERITY_COLORS = {
    low: { bg: 'var(--gray-100)', text: 'var(--gray-600)', border: 'var(--gray-200)' },
    medium: { bg: 'var(--warning-50)', text: 'var(--warning-700)', border: 'var(--warning-200)' },
    high: { bg: 'var(--danger-50)', text: 'var(--danger-700)', border: 'var(--danger-200)' },
};

const TYPE_LABELS = {
    wording: { icon: '📝', label: 'Wording' },
    difficulty: { icon: '🎯', label: 'Difficulty' },
    options: { icon: '📋', label: 'Options' },
    explanation: { icon: '💡', label: 'Explanation' },
};

// Helper to analyze question text for issues
export function analyzeQuestion(question: string, explanation: string, options: string[]): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Check for vague terms
    const vagueTerms = ['some', 'many', 'usually', 'often', 'sometimes', 'various', 'certain'];
    for (const term of vagueTerms) {
        const regex = new RegExp(`\\b${term}\\b`, 'gi');
        if (regex.test(question)) {
            suggestions.push({
                id: `vague-${term}`,
                type: 'wording',
                severity: 'medium',
                message: `Question contains vague term "${term}" which may confuse students`,
                suggestedFix: question.replace(regex, `[specific ${term}]`),
                originalText: question,
            });
        }
    }

    // Check for "NOT" questions without emphasis
    if (/\bnot\b/i.test(question) && !/\bNOT\b/.test(question)) {
        suggestions.push({
            id: 'not-emphasis',
            type: 'wording',
            severity: 'medium',
            message: 'Consider capitalizing "NOT" for emphasis in negative questions',
            suggestedFix: question.replace(/\bnot\b/gi, 'NOT'),
            originalText: question,
        });
    }

    // Check for short explanation
    if (!explanation || explanation.length < 50) {
        suggestions.push({
            id: 'short-explanation',
            type: 'explanation',
            severity: 'high',
            message: 'Explanation is too short. Students benefit from detailed explanations.',
        });
    }

    // Check for obvious wrong options (too short or too different in length)
    const optionLengths = options.map(o => o.length);
    const avgLength = optionLengths.reduce((a, b) => a + b, 0) / optionLengths.length;
    const shortOptions = options.filter(o => o.length < avgLength * 0.3);

    if (shortOptions.length > 0) {
        suggestions.push({
            id: 'unbalanced-options',
            type: 'options',
            severity: 'medium',
            message: 'Some options are much shorter than others, making them obviously wrong',
        });
    }

    // Check for "All of the above" type options
    const allAbovePatterns = /\b(all of the above|none of the above|both a and b)\b/i;
    if (options.some(o => allAbovePatterns.test(o))) {
        suggestions.push({
            id: 'avoid-all-above',
            type: 'options',
            severity: 'low',
            message: '"All of the above" type options are generally discouraged in MCQs',
        });
    }

    return suggestions;
}

export const AISuggestions: React.FC<AISuggestionsProps> = ({
    suggestions,
    onApply,
    onDismiss,
}) => {
    const [isExpanded, setIsExpanded] = useState(true);
    const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

    const visibleSuggestions = suggestions.filter(s => !dismissedIds.has(s.id));

    if (visibleSuggestions.length === 0) {
        return null;
    }

    const handleDismiss = (id: string) => {
        setDismissedIds(prev => new Set([...prev, id]));
        onDismiss?.(id);
    };

    const handleApply = (suggestion: Suggestion) => {
        if (suggestion.suggestedFix) {
            onApply?.(suggestion.id, suggestion.suggestedFix);
        }
        handleDismiss(suggestion.id);
    };

    const highPriorityCount = visibleSuggestions.filter(s => s.severity === 'high').length;

    return (
        <div style={{
            background: 'var(--primary-50)',
            border: '1px solid var(--primary-200)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: 'var(--space-4)',
            overflow: 'hidden',
        }}>
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
                    <Sparkles size={18} color="var(--primary-600)" />
                    <span style={{ fontWeight: 500, color: 'var(--primary-700)', fontSize: '14px' }}>
                        AI Suggestions
                    </span>
                    <span style={{
                        fontSize: '12px',
                        padding: '2px 8px',
                        background: 'var(--primary-200)',
                        borderRadius: 'var(--radius-full)',
                        color: 'var(--primary-700)',
                    }}>
                        {visibleSuggestions.length}
                    </span>
                    {highPriorityCount > 0 && (
                        <span style={{
                            fontSize: '12px',
                            padding: '2px 8px',
                            background: 'var(--danger-100)',
                            borderRadius: 'var(--radius-full)',
                            color: 'var(--danger-700)',
                        }}>
                            {highPriorityCount} important
                        </span>
                    )}
                </div>
                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>

            {/* Suggestions List */}
            {isExpanded && (
                <div style={{
                    borderTop: '1px solid var(--primary-200)',
                    padding: 'var(--space-3)',
                }}>
                    <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
                        {visibleSuggestions.map((suggestion) => {
                            const colors = SEVERITY_COLORS[suggestion.severity];
                            const typeInfo = TYPE_LABELS[suggestion.type];

                            return (
                                <div
                                    key={suggestion.id}
                                    style={{
                                        background: 'white',
                                        border: `1px solid ${colors.border}`,
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-3)',
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                            <span>{typeInfo.icon}</span>
                                            <span style={{
                                                fontSize: '11px',
                                                fontWeight: 500,
                                                padding: '2px 6px',
                                                background: colors.bg,
                                                color: colors.text,
                                                borderRadius: 'var(--radius-sm)',
                                            }}>
                                                {typeInfo.label}
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => handleDismiss(suggestion.id)}
                                            style={{
                                                background: 'none',
                                                border: 'none',
                                                cursor: 'pointer',
                                                padding: '2px',
                                                color: 'var(--gray-400)',
                                            }}
                                        >
                                            <X size={14} />
                                        </button>
                                    </div>

                                    <p style={{
                                        margin: '0 0 var(--space-2) 0',
                                        fontSize: '13px',
                                        color: 'var(--gray-700)',
                                        lineHeight: 1.5,
                                    }}>
                                        {suggestion.message}
                                    </p>

                                    {suggestion.suggestedFix && onApply && (
                                        <button
                                            onClick={() => handleApply(suggestion)}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '4px',
                                                padding: '4px 8px',
                                                fontSize: '12px',
                                                background: 'var(--primary-100)',
                                                color: 'var(--primary-700)',
                                                border: '1px solid var(--primary-200)',
                                                borderRadius: 'var(--radius-sm)',
                                                cursor: 'pointer',
                                            }}
                                        >
                                            <Check size={12} />
                                            Apply Fix
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AISuggestions;
