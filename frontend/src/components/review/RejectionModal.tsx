import React, { useState } from 'react';
import { X, AlertCircle, Send } from 'lucide-react';

interface RejectionModalProps {
    isOpen: boolean;
    itemId: number;
    questionPreview: string;
    onConfirm: (itemId: number, reasons: string[], comment: string) => void;
    onCancel: () => void;
}

const REJECTION_REASONS = [
    { id: 'factual', label: 'Factually incorrect', description: 'Contains wrong information' },
    { id: 'ambiguous', label: 'Ambiguous wording', description: 'Question or options unclear' },
    { id: 'difficulty', label: 'Wrong difficulty level', description: 'Too easy/hard for cognitive level' },
    { id: 'explanation', label: 'Poor explanation', description: 'Explanation missing or inadequate' },
    { id: 'duplicate', label: 'Duplicate content', description: 'Similar to existing question' },
    { id: 'formatting', label: 'Formatting issues', description: 'LaTeX, options, or structure problems' },
    { id: 'off-topic', label: 'Off-topic', description: 'Not relevant to subject/chapter' },
    { id: 'other', label: 'Other issue', description: 'Specify in comments' },
];

export const RejectionModal: React.FC<RejectionModalProps> = ({
    isOpen,
    itemId,
    questionPreview,
    onConfirm,
    onCancel,
}) => {
    const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
    const [comment, setComment] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    if (!isOpen) return null;

    const toggleReason = (reasonId: string) => {
        setSelectedReasons(prev =>
            prev.includes(reasonId)
                ? prev.filter(r => r !== reasonId)
                : [...prev, reasonId]
        );
    };

    const handleSubmit = async () => {
        if (selectedReasons.length === 0) return;

        setIsSubmitting(true);
        try {
            onConfirm(itemId, selectedReasons, comment);
        } finally {
            setIsSubmitting(false);
            setSelectedReasons([]);
            setComment('');
        }
    };

    const handleCancel = () => {
        setSelectedReasons([]);
        setComment('');
        onCancel();
    };

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
            }}
            onClick={handleCancel}
        >
            <div
                style={{
                    background: 'white',
                    borderRadius: 'var(--radius-xl)',
                    padding: 0,
                    maxWidth: '500px',
                    width: '90%',
                    maxHeight: '90vh',
                    overflow: 'hidden',
                    boxShadow: 'var(--shadow-xl)',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--gray-200)',
                    background: 'var(--danger-50)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <AlertCircle size={20} color="var(--danger-600)" />
                        <h3 style={{ margin: 0, color: 'var(--danger-700)' }}>Reject Question</h3>
                    </div>
                    <button
                        onClick={handleCancel}
                        style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 'var(--space-1)',
                        }}
                    >
                        <X size={20} color="var(--gray-500)" />
                    </button>
                </div>

                {/* Content */}
                <div style={{ padding: 'var(--space-5)', maxHeight: 'calc(90vh - 150px)', overflow: 'auto' }}>
                    {/* Question Preview */}
                    <div style={{
                        background: 'var(--gray-50)',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-3)',
                        marginBottom: 'var(--space-4)',
                        fontSize: '13px',
                        color: 'var(--gray-600)',
                        maxHeight: '60px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                    }}>
                        "{questionPreview.slice(0, 100)}{questionPreview.length > 100 ? '...' : ''}"
                    </div>

                    {/* Rejection Reasons */}
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <label style={{
                            display: 'block',
                            fontWeight: 600,
                            marginBottom: 'var(--space-2)',
                            color: 'var(--gray-700)',
                        }}>
                            Why are you rejecting this question? *
                        </label>
                        <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
                            {REJECTION_REASONS.map((reason) => (
                                <label
                                    key={reason.id}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: 'var(--space-2)',
                                        padding: 'var(--space-2) var(--space-3)',
                                        borderRadius: 'var(--radius-md)',
                                        border: selectedReasons.includes(reason.id)
                                            ? '1px solid var(--danger-400)'
                                            : '1px solid var(--gray-200)',
                                        background: selectedReasons.includes(reason.id)
                                            ? 'var(--danger-50)'
                                            : 'white',
                                        cursor: 'pointer',
                                        transition: 'all 0.15s',
                                    }}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedReasons.includes(reason.id)}
                                        onChange={() => toggleReason(reason.id)}
                                        style={{ marginTop: '2px' }}
                                    />
                                    <div>
                                        <div style={{ fontWeight: 500, fontSize: '13px', color: 'var(--gray-800)' }}>
                                            {reason.label}
                                        </div>
                                        <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>
                                            {reason.description}
                                        </div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Comment Field */}
                    <div>
                        <label style={{
                            display: 'block',
                            fontWeight: 600,
                            marginBottom: 'var(--space-2)',
                            color: 'var(--gray-700)',
                        }}>
                            Additional comments (optional)
                        </label>
                        <textarea
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            placeholder="Add any specific feedback for the content team..."
                            style={{
                                width: '100%',
                                minHeight: '80px',
                                padding: 'var(--space-3)',
                                borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--gray-200)',
                                fontSize: '13px',
                                resize: 'vertical',
                            }}
                        />
                    </div>
                </div>

                {/* Footer */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-4) var(--space-5)',
                    borderTop: '1px solid var(--gray-200)',
                    background: 'var(--gray-50)',
                }}>
                    <button
                        onClick={handleCancel}
                        className="btn btn-secondary"
                        style={{ padding: 'var(--space-2) var(--space-4)' }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={selectedReasons.length === 0 || isSubmitting}
                        className="btn"
                        style={{
                            padding: 'var(--space-2) var(--space-4)',
                            background: selectedReasons.length === 0 ? 'var(--gray-300)' : 'var(--danger-500)',
                            color: 'white',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                        }}
                    >
                        <Send size={14} />
                        {isSubmitting ? 'Rejecting...' : 'Reject Question'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RejectionModal;
