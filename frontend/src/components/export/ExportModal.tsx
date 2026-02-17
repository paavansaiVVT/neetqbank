import React, { useState } from 'react';
import { X, Download, FileText, FileSpreadsheet, FileJson, FileType, Loader2, CheckCircle2, Info } from 'lucide-react';
import { QbankApiClient } from '../../api/client';

type ExportFormat = 'pdf' | 'excel' | 'docx' | 'json';

interface ExportModalProps {
    isOpen: boolean;
    onClose: () => void;
    /** When set, export from a specific job */
    jobId?: string;
    /** When set, export from the library with optional filters */
    libraryMode?: boolean;
    questionCount: number;
    apiClient: QbankApiClient;
    subject?: string;
    chapter?: string;
}

const FORMAT_OPTIONS: {
    id: ExportFormat;
    label: string;
    icon: React.ElementType;
    description: string;
    extension: string;
    gradient: string;
}[] = [
        {
            id: 'pdf',
            label: 'PDF Document',
            icon: FileText,
            description: 'Print-ready, formatted questions with answers',
            extension: '.pdf',
            gradient: 'linear-gradient(135deg, #ef4444, #dc2626)',
        },
        {
            id: 'excel',
            label: 'Excel Spreadsheet',
            icon: FileSpreadsheet,
            description: 'Editable table with styled headers',
            extension: '.xlsx',
            gradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
        },
        {
            id: 'docx',
            label: 'Word Document',
            icon: FileType,
            description: 'Formatted document with rich styling',
            extension: '.docx',
            gradient: 'linear-gradient(135deg, #3b82f6, #2563eb)',
        },
        {
            id: 'json',
            label: 'JSON Data',
            icon: FileJson,
            description: 'Raw data for integrations & APIs',
            extension: '.json',
            gradient: 'linear-gradient(135deg, #f59e0b, #d97706)',
        },
    ];

export const ExportModal: React.FC<ExportModalProps> = ({
    isOpen,
    onClose,
    jobId,
    libraryMode = false,
    questionCount,
    apiClient,
    subject,
    chapter,
}) => {
    const [format, setFormat] = useState<ExportFormat>('pdf');
    const [includeExplanations, setIncludeExplanations] = useState(true);
    const [includeMetadata, setIncludeMetadata] = useState(false);
    const [onlyApproved, setOnlyApproved] = useState(true);
    const [isExporting, setIsExporting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    if (!isOpen) return null;

    const handleExport = async () => {
        setIsExporting(true);
        setError('');
        setSuccess(false);

        try {
            let result: { blob: Blob; filename: string };

            if (libraryMode) {
                result = await apiClient.exportLibrary({
                    format,
                    include_explanations: includeExplanations,
                    include_metadata: includeMetadata,
                    only_approved: onlyApproved,
                    subject,
                    chapter,
                });
            } else if (jobId) {
                result = await apiClient.exportJob(jobId, {
                    format,
                    include_explanations: includeExplanations,
                    include_metadata: includeMetadata,
                    only_approved: onlyApproved,
                });
            } else {
                throw new Error('No job ID or library mode specified');
            }

            // Download the file
            const url = window.URL.createObjectURL(result.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = result.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            setSuccess(true);
            setTimeout(() => {
                onClose();
                setSuccess(false);
            }, 1500);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Export failed. Please try again.');
            console.error('Export error:', err);
        } finally {
            setIsExporting(false);
        }
    };

    const selectedFormat = FORMAT_OPTIONS.find((f) => f.id === format)!;

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.5)',
                backdropFilter: 'blur(4px)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
                padding: 'var(--space-4)',
                animation: 'fadeIn 0.2s ease',
            }}
            onClick={onClose}
        >
            <div
                style={{
                    background: 'white',
                    borderRadius: 'var(--radius-xl)',
                    padding: 0,
                    maxWidth: '480px',
                    width: '100%',
                    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                    animation: 'slideUp 0.25s ease',
                    overflow: 'hidden',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header with gradient accent */}
                <div
                    style={{
                        background: 'var(--gradient-primary)',
                        padding: 'var(--space-5) var(--space-6)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <div
                            style={{
                                width: 36,
                                height: 36,
                                borderRadius: 'var(--radius-md)',
                                background: 'rgba(255,255,255,0.2)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            <Download size={20} color="white" />
                        </div>
                        <div>
                            <h3 style={{ margin: 0, color: 'white', fontSize: '16px' }}>Export Questions</h3>
                            <p style={{ margin: 0, color: 'rgba(255,255,255,0.7)', fontSize: '12px' }}>
                                {libraryMode ? 'Library Export' : 'Job Export'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'rgba(255,255,255,0.15)',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '6px',
                            borderRadius: 'var(--radius-sm)',
                            display: 'flex',
                            transition: 'background 0.15s',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.3)')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.15)')}
                    >
                        <X size={18} color="white" />
                    </button>
                </div>

                {/* Content */}
                <div style={{ padding: 'var(--space-5) var(--space-6)' }}>
                    {/* Format Selection */}
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <label
                            style={{
                                display: 'block',
                                fontWeight: 600,
                                marginBottom: 'var(--space-3)',
                                color: 'var(--gray-700)',
                                fontSize: '13px',
                                textTransform: 'uppercase',
                                letterSpacing: '0.04em',
                            }}
                        >
                            Choose Format
                        </label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
                            {FORMAT_OPTIONS.map((opt) => (
                                <label
                                    key={opt.id}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--space-3)',
                                        padding: 'var(--space-3)',
                                        borderRadius: 'var(--radius-md)',
                                        border:
                                            format === opt.id
                                                ? '2px solid var(--primary-500)'
                                                : '1px solid var(--gray-200)',
                                        background: format === opt.id ? 'var(--primary-50)' : 'white',
                                        cursor: 'pointer',
                                        transition: 'all 0.15s',
                                        transform: format === opt.id ? 'scale(1.02)' : 'scale(1)',
                                    }}
                                    onMouseEnter={(e) => {
                                        if (format !== opt.id)
                                            e.currentTarget.style.borderColor = 'var(--gray-300)';
                                    }}
                                    onMouseLeave={(e) => {
                                        if (format !== opt.id)
                                            e.currentTarget.style.borderColor = 'var(--gray-200)';
                                    }}
                                >
                                    <input
                                        type="radio"
                                        name="format"
                                        checked={format === opt.id}
                                        onChange={() => setFormat(opt.id)}
                                        style={{ display: 'none' }}
                                    />
                                    <div
                                        style={{
                                            width: 32,
                                            height: 32,
                                            borderRadius: 'var(--radius-sm)',
                                            background: opt.gradient,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            flexShrink: 0,
                                        }}
                                    >
                                        <opt.icon size={16} color="white" />
                                    </div>
                                    <div>
                                        <div
                                            style={{
                                                fontWeight: 600,
                                                color: 'var(--gray-800)',
                                                fontSize: '13px',
                                            }}
                                        >
                                            {opt.label}
                                        </div>
                                        <div style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                                            {opt.extension}
                                        </div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Format-specific description */}
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 'var(--space-2)',
                            padding: 'var(--space-3)',
                            background: 'var(--primary-50)',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: 'var(--space-4)',
                            border: '1px solid var(--primary-100)',
                        }}
                    >
                        <Info size={14} color="var(--primary-500)" style={{ marginTop: 1, flexShrink: 0 }} />
                        <span style={{ fontSize: '12px', color: 'var(--primary-700)' }}>
                            {selectedFormat.description}
                        </span>
                    </div>

                    {/* Options */}
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <label
                            style={{
                                display: 'block',
                                fontWeight: 600,
                                marginBottom: 'var(--space-2)',
                                color: 'var(--gray-700)',
                                fontSize: '13px',
                                textTransform: 'uppercase',
                                letterSpacing: '0.04em',
                            }}
                        >
                            Options
                        </label>
                        <div
                            style={{
                                display: 'grid',
                                gap: 'var(--space-1)',
                                background: 'var(--gray-50)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-3)',
                            }}
                        >
                            <ToggleOption
                                checked={onlyApproved}
                                onChange={setOnlyApproved}
                                label="Only approved questions"
                            />
                            <ToggleOption
                                checked={includeExplanations}
                                onChange={setIncludeExplanations}
                                label="Include explanations"
                            />
                            <ToggleOption
                                checked={includeMetadata}
                                onChange={setIncludeMetadata}
                                label="Include metadata (difficulty, cognitive, time)"
                            />
                        </div>
                    </div>

                    {/* Summary */}
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            background: 'var(--gray-50)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-3) var(--space-4)',
                            fontSize: '13px',
                        }}
                    >
                        <span style={{ color: 'var(--gray-500)' }}>
                            📦 {questionCount} {questionCount === 1 ? 'question' : 'questions'}
                        </span>
                        <span
                            style={{
                                fontWeight: 600,
                                color: 'var(--gray-700)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                            }}
                        >
                            <div
                                style={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    background: selectedFormat.gradient,
                                }}
                            />
                            {selectedFormat.extension}
                        </span>
                    </div>

                    {/* Error / Success */}
                    {error && (
                        <div
                            style={{
                                marginTop: 'var(--space-3)',
                                color: 'var(--danger-600)',
                                fontSize: '13px',
                                background: 'var(--danger-50)',
                                padding: 'var(--space-2) var(--space-3)',
                                borderRadius: 'var(--radius-md)',
                            }}
                        >
                            ❌ {error}
                        </div>
                    )}
                    {success && (
                        <div
                            style={{
                                marginTop: 'var(--space-3)',
                                color: 'var(--success-700)',
                                fontSize: '13px',
                                background: 'var(--success-50)',
                                padding: 'var(--space-2) var(--space-3)',
                                borderRadius: 'var(--radius-md)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 'var(--space-2)',
                            }}
                        >
                            <CheckCircle2 size={14} /> Download started!
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 'var(--space-2)',
                        padding: 'var(--space-4) var(--space-6)',
                        borderTop: '1px solid var(--gray-100)',
                        background: 'var(--gray-50)',
                    }}
                >
                    <button
                        onClick={onClose}
                        className="btn btn-secondary"
                        style={{ padding: 'var(--space-2) var(--space-5)' }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleExport}
                        disabled={isExporting || questionCount === 0}
                        className="btn btn-primary"
                        style={{
                            padding: 'var(--space-2) var(--space-5)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                        }}
                    >
                        {isExporting ? (
                            <>
                                <Loader2 size={14} className="animate-spin" />
                                Exporting...
                            </>
                        ) : (
                            <>
                                <Download size={14} />
                                Export {selectedFormat.extension}
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Animation keyframe (inline via style tag) */}
            <style>{`
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(16px) scale(0.97); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
            `}</style>
        </div>
    );
};

/** Small toggle-style checkbox */
function ToggleOption({
    checked,
    onChange,
    label,
}: {
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
}) {
    return (
        <label
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                cursor: 'pointer',
                padding: '4px 0',
            }}
        >
            <div
                onClick={() => onChange(!checked)}
                style={{
                    width: 32,
                    height: 18,
                    borderRadius: 'var(--radius-full)',
                    background: checked ? 'var(--primary-500)' : 'var(--gray-300)',
                    position: 'relative',
                    transition: 'background 0.2s',
                    cursor: 'pointer',
                    flexShrink: 0,
                }}
            >
                <div
                    style={{
                        width: 14,
                        height: 14,
                        borderRadius: '50%',
                        background: 'white',
                        position: 'absolute',
                        top: 2,
                        left: checked ? 16 : 2,
                        transition: 'left 0.2s',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                    }}
                />
            </div>
            <span style={{ fontSize: '13px', color: 'var(--gray-700)' }}>{label}</span>
        </label>
    );
}

export default ExportModal;
