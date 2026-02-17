import React, { useState, useRef, useEffect } from 'react';
import { MathRenderer } from '../shared/MathRenderer';
import { Check, X, Edit3 } from 'lucide-react';

interface InlineEditorProps {
    value: string;
    onSave: (newValue: string) => Promise<void>;
    renderAs?: 'text' | 'math';
    placeholder?: string;
    multiline?: boolean;
    className?: string;
}

export const InlineEditor: React.FC<InlineEditorProps> = ({
    value,
    onSave,
    renderAs = 'text',
    placeholder = 'Click to edit...',
    multiline = false,
    className = '',
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(value);
    const [isSaving, setIsSaving] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [isEditing]);

    // Reset edit value when prop value changes
    useEffect(() => {
        if (!isEditing) {
            setEditValue(value);
        }
    }, [value, isEditing]);

    const handleStartEdit = () => {
        setEditValue(value);
        setIsEditing(true);
    };

    const handleCancel = () => {
        setEditValue(value);
        setIsEditing(false);
    };

    const handleSave = async () => {
        if (editValue === value) {
            setIsEditing(false);
            return;
        }

        setIsSaving(true);
        try {
            await onSave(editValue);
            setIsEditing(false);
        } catch (err) {
            console.error('Failed to save:', err);
            // Keep editing mode open on error
        } finally {
            setIsSaving(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            handleCancel();
        } else if (e.key === 'Enter' && !multiline) {
            e.preventDefault();
            handleSave();
        } else if (e.key === 'Enter' && e.metaKey) {
            e.preventDefault();
            handleSave();
        }
    };

    if (isEditing) {
        return (
            <div className={`inline-editor editing ${className}`} style={{ position: 'relative' }}>
                {multiline ? (
                    <textarea
                        ref={inputRef as React.RefObject<HTMLTextAreaElement>}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isSaving}
                        placeholder={placeholder}
                        style={{
                            width: '100%',
                            minHeight: '80px',
                            padding: 'var(--space-3)',
                            borderRadius: 'var(--radius-md)',
                            border: '2px solid var(--primary-500)',
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                            resize: 'vertical',
                            outline: 'none',
                        }}
                    />
                ) : (
                    <input
                        ref={inputRef as React.RefObject<HTMLInputElement>}
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isSaving}
                        placeholder={placeholder}
                        style={{
                            width: '100%',
                            padding: 'var(--space-2) var(--space-3)',
                            borderRadius: 'var(--radius-md)',
                            border: '2px solid var(--primary-500)',
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                            outline: 'none',
                        }}
                    />
                )}

                {/* Preview for math content */}
                {renderAs === 'math' && editValue && (
                    <div style={{
                        marginTop: 'var(--space-2)',
                        padding: 'var(--space-2)',
                        background: 'var(--gray-50)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                        color: 'var(--gray-500)',
                    }}>
                        <div style={{ marginBottom: '4px' }}>Preview:</div>
                        <MathRenderer content={editValue} />
                    </div>
                )}

                {/* Action buttons */}
                <div style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    marginTop: 'var(--space-2)',
                    justifyContent: 'flex-end',
                }}>
                    <button
                        onClick={handleCancel}
                        disabled={isSaving}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: 'var(--space-1) var(--space-2)',
                            background: 'var(--gray-100)',
                            border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                            fontSize: '12px',
                        }}
                    >
                        <X size={14} /> Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: 'var(--space-1) var(--space-2)',
                            background: 'var(--success-500)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                            fontSize: '12px',
                        }}
                    >
                        <Check size={14} /> {isSaving ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </div>
        );
    }

    // View mode - click to edit
    return (
        <div
            className={`inline-editor ${className}`}
            onClick={handleStartEdit}
            style={{
                cursor: 'pointer',
                position: 'relative',
                padding: 'var(--space-1)',
                borderRadius: 'var(--radius-sm)',
                transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'var(--gray-50)';
            }}
            onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'transparent';
            }}
            title="Click to edit"
        >
            {value ? (
                renderAs === 'math' ? <MathRenderer content={value} /> : value
            ) : (
                <span style={{ color: 'var(--gray-400)', fontStyle: 'italic' }}>{placeholder}</span>
            )}
            <Edit3
                size={14}
                style={{
                    position: 'absolute',
                    top: '4px',
                    right: '4px',
                    opacity: 0.3,
                    color: 'var(--gray-500)',
                }}
            />
        </div>
    );
};

export default InlineEditor;
