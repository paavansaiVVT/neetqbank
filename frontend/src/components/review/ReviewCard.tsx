import { useEffect, useCallback, useState, useMemo } from "react";
import type { QuestionItem } from "../wizard/types";
import { MathRenderer } from "../shared/MathRenderer";
import { InlineEditor } from "./InlineEditor";
import { AISuggestions, analyzeQuestion } from "./AISuggestions";
import { Edit3, Check } from "lucide-react";
import "../../design-system.css";
import { QbankApiClient } from "../../api/client";
import { CommentThread } from "./CommentThread";

interface ReviewCardProps {
    item: QuestionItem;
    currentIndex: number;
    totalCount: number;
    onApprove: (itemId: number) => void;
    onReject: (itemId: number) => void;
    onEdit: (item: QuestionItem) => void;
    onUpdateField?: (itemId: number, field: string, value: string) => Promise<void>;
    onNext: () => void;
    onPrevious: () => void;
    onExit: () => void;
    subject: string;
    chapter: string;
    apiClient?: QbankApiClient;
}

export function ReviewCard({
    item,
    currentIndex,
    totalCount,
    onApprove,
    onReject,
    onEdit,
    onUpdateField,
    onNext,
    onPrevious,
    onExit,
    subject,
    chapter,
    apiClient,
}: ReviewCardProps) {
    const [editMode, setEditMode] = useState(false);
    const [saveToast, setSaveToast] = useState(false);

    // Keyboard shortcuts
    const handleKeyDown = useCallback(
        (event: KeyboardEvent) => {
            // Don't trigger if user is typing in an input
            if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
                return;
            }

            switch (event.key.toLowerCase()) {
                case "a":
                    event.preventDefault();
                    onApprove(item.item_id);
                    break;
                case "r":
                    event.preventDefault();
                    onReject(item.item_id);
                    break;
                case "e":
                    event.preventDefault();
                    if (onUpdateField) {
                        setEditMode(!editMode);
                    } else {
                        onEdit(item);
                    }
                    break;
                case "j":
                case "arrowleft":
                    event.preventDefault();
                    onPrevious();
                    break;
                case "k":
                case "arrowright":
                    event.preventDefault();
                    onNext();
                    break;
                case "escape":
                    event.preventDefault();
                    if (editMode) {
                        setEditMode(false);
                    } else {
                        onExit();
                    }
                    break;
            }
        },
        [item, editMode, onApprove, onReject, onEdit, onUpdateField, onNext, onPrevious, onExit]
    );

    useEffect(() => {
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [handleKeyDown]);

    // Reset edit mode when changing items
    useEffect(() => {
        setEditMode(false);
    }, [item.item_id]);

    const handleFieldSave = async (field: string, value: string) => {
        if (onUpdateField) {
            await onUpdateField(item.item_id, field, value);
            setSaveToast(true);
            setTimeout(() => setSaveToast(false), 2000);
        }
    };

    const progressPercent = ((currentIndex + 1) / totalCount) * 100;

    // Parse options - handle both array and string formats
    const options = Array.isArray(item.options)
        ? item.options
        : typeof item.options === "string"
            ? (item.options as string).split("|").map((o: string) => o.trim())
            : [];

    // AI-powered suggestions
    const aiSuggestions = useMemo(() => {
        return analyzeQuestion(item.question, item.explanation || '', options);
    }, [item.question, item.explanation, options]);

    const handleApplySuggestion = async (suggestionId: string, fixedValue: string) => {
        if (onUpdateField && suggestionId.includes('question')) {
            await onUpdateField(item.item_id, 'question', fixedValue);
        }
    };

    return (
        <div className="review-container">
            {/* Save Toast */}
            {saveToast && (
                <div style={{
                    position: 'fixed',
                    top: '80px',
                    right: '20px',
                    background: 'var(--success-500)',
                    color: 'white',
                    padding: 'var(--space-2) var(--space-4)',
                    borderRadius: 'var(--radius-lg)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    boxShadow: 'var(--shadow-lg)',
                    zIndex: 1000,
                    animation: 'slideIn 0.3s ease',
                }}>
                    <Check size={16} /> Saved successfully
                </div>
            )}

            {/* Header */}
            <div className="review-header">
                <button className="review-back" onClick={onExit}>
                    ← Exit Review
                </button>
                <div style={{ fontSize: "14px", color: "var(--gray-500)" }}>
                    {subject} / {chapter}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    {/* Edit Mode Toggle */}
                    {onUpdateField && (
                        <button
                            onClick={() => setEditMode(!editMode)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: 'var(--space-1) var(--space-2)',
                                background: editMode ? 'var(--primary-100)' : 'var(--gray-100)',
                                border: editMode ? '1px solid var(--primary-400)' : '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-md)',
                                cursor: 'pointer',
                                fontSize: '12px',
                                color: editMode ? 'var(--primary-700)' : 'var(--gray-600)',
                            }}
                        >
                            <Edit3 size={14} />
                            {editMode ? 'Exit Edit' : 'Edit Mode'}
                        </button>
                    )}
                    <div className="review-progress">
                        <span className="review-progress-text">
                            {currentIndex + 1} of {totalCount}
                        </span>
                        <div className="review-progress-bar">
                            <div
                                className="review-progress-fill"
                                style={{ width: `${progressPercent}%` }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Question Card */}
            <div className="question-card animate-slideIn" key={item.item_id}>
                {/* AI Suggestions */}
                {aiSuggestions.length > 0 && (
                    <div style={{ marginBottom: 'var(--space-3)' }}>
                        <AISuggestions
                            suggestions={aiSuggestions}
                            onApply={handleApplySuggestion}
                        />
                    </div>
                )}

                <div className="question-content">
                    {/* Question Text */}
                    <div className="question-text">
                        {editMode && onUpdateField ? (
                            <InlineEditor
                                value={item.question}
                                onSave={(v) => handleFieldSave('question', v)}
                                renderAs="math"
                                multiline
                                placeholder="Enter question text..."
                            />
                        ) : (
                            <MathRenderer content={item.question} />
                        )}
                    </div>

                    {/* Options */}
                    <div className="options-list">
                        {options.map((option, index) => {
                            const letter = String.fromCharCode(65 + index); // A, B, C, D
                            const isCorrect = item.correct_answer === option ||
                                item.correct_answer === letter ||
                                item.correct_answer?.includes(option);
                            return (
                                <div
                                    key={index}
                                    className={`option-item ${isCorrect ? "correct" : ""}`}
                                >
                                    {/* Correct answer radio in edit mode */}
                                    {editMode && onUpdateField ? (
                                        <input
                                            type="radio"
                                            name={`correct-${item.item_id}`}
                                            checked={isCorrect}
                                            onChange={() => {
                                                handleFieldSave('correct_answer', option);
                                            }}
                                            title="Set as correct answer"
                                            style={{ cursor: 'pointer', accentColor: 'var(--success-500)' }}
                                        />
                                    ) : (
                                        <span className="option-letter">{letter}</span>
                                    )}
                                    <span className="option-text" style={{ flex: 1 }}>
                                        {editMode && onUpdateField ? (
                                            <InlineEditor
                                                value={option}
                                                onSave={async (newValue) => {
                                                    // Update the entire options array with the edited option
                                                    const newOptions = [...options];
                                                    newOptions[index] = newValue;
                                                    // If the edited option was the correct answer, update correct_answer too
                                                    if (isCorrect) {
                                                        await onUpdateField(item.item_id, 'correct_answer', newValue);
                                                    }
                                                    await onUpdateField(item.item_id, 'options', JSON.stringify(newOptions));
                                                    setSaveToast(true);
                                                    setTimeout(() => setSaveToast(false), 2000);
                                                }}
                                                renderAs="math"
                                                placeholder={`Option ${letter}...`}
                                            />
                                        ) : (
                                            <MathRenderer content={option} />
                                        )}
                                    </span>
                                    {isCorrect && (
                                        <span className="correct-indicator">
                                            🎯 Correct Answer
                                        </span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Explanation */}
                <div className="explanation-section">
                    <div className="explanation-header">
                        <span>💡</span>
                        <span>Explanation</span>
                    </div>
                    <div className="explanation-text">
                        {editMode && onUpdateField ? (
                            <InlineEditor
                                value={item.explanation || ''}
                                onSave={(v) => handleFieldSave('explanation', v)}
                                renderAs="math"
                                multiline
                                placeholder="Add explanation..."
                            />
                        ) : (
                            item.explanation ? <MathRenderer content={item.explanation} /> :
                                <span style={{ color: 'var(--gray-400)', fontStyle: 'italic' }}>No explanation provided</span>
                        )}
                    </div>
                </div>

                {/* Metadata Tags */}
                <div className="meta-tags">
                    <span className="meta-tag difficulty">
                        🎯 {item.difficulty || "Medium"}
                    </span>
                    <span className="meta-tag cognitive">
                        🧠 {item.cognitive_level || "Understanding"}
                    </span>
                    <span className="meta-tag time">
                        ⏱️ {item.estimated_time ? `${item.estimated_time} min` : "1.5 min"}
                    </span>
                    <span className={`meta-tag ${item.qc_status === "pass" ? "qc-pass" : "qc-fail"}`}>
                        {item.qc_status === "pass" ? "✅" : "❌"} QC {item.qc_status}
                    </span>
                </div>

                {/* Comments Section */}
                <CommentThread itemId={item.item_id} apiClient={apiClient} />

                {/* Action Bar */}
                <div className="action-bar">
                    <div className="action-buttons">
                        <button
                            className="action-btn reject"
                            onClick={() => onReject(item.item_id)}
                        >
                            <span className="action-icon">❌</span>
                            <span>Reject</span>
                            <span className="action-shortcut">(R)</span>
                        </button>
                        <button
                            className="action-btn edit"
                            onClick={() => editMode ? setEditMode(false) : (onUpdateField ? setEditMode(true) : onEdit(item))}
                        >
                            <span className="action-icon">✏️</span>
                            <span>{editMode ? 'Done' : 'Edit'}</span>
                            <span className="action-shortcut">(E)</span>
                        </button>
                        <button
                            className="action-btn approve"
                            onClick={() => onApprove(item.item_id)}
                        >
                            <span className="action-icon">✅</span>
                            <span>Approve</span>
                            <span className="action-shortcut">(A)</span>
                        </button>
                    </div>

                    <div className="nav-buttons">
                        <button
                            className="nav-btn"
                            onClick={onPrevious}
                            disabled={currentIndex === 0}
                        >
                            ← Previous (J)
                        </button>
                        <button
                            className="nav-btn"
                            onClick={onNext}
                            disabled={currentIndex === totalCount - 1}
                        >
                            Next (K) →
                        </button>
                    </div>
                </div>

                {/* Keyboard Hint */}
                <div className="keyboard-hint">
                    ⌨️ Keyboard: <kbd>A</kbd>=Approve <kbd>R</kbd>=Reject <kbd>E</kbd>={editMode ? 'Done' : 'Edit'}{" "}
                    <kbd>J</kbd>=Prev <kbd>K</kbd>=Next <kbd>Esc</kbd>={editMode ? 'Exit Edit' : 'Exit'}
                </div>
            </div>
        </div>
    );
}

export default ReviewCard;
