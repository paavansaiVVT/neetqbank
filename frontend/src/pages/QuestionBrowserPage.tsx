import { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, ChevronDown, ChevronUp, Clock, FileText, FileSpreadsheet, FileDown, Check, CheckSquare, Square, ChevronLeft, ChevronRight, History, X } from 'lucide-react';
import { QbankApiClient } from '../api/client';
import { MathRenderer } from '../components/shared/MathRenderer';
import { useAuth } from '../contexts/AuthContext';

/* ─── Types ───────────────────────────────────────────────────────── */

interface LibraryQuestion {
    id: number;
    question: string;
    options: string[];
    correct_answer: string;
    explanation: string;
    difficulty: string;
    cognitive_level: string;
    question_type: string;
    estimated_time: number | null;
    concepts: string | null;
    subject: string;
    chapter: string;
    topic: string;
    created_at: string;
}

interface QuestionBrowserPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

interface DownloadRecord {
    id: string;
    format: string;
    count: number;
    timestamp: Date;
    filters: { subject?: string; chapter?: string; topic?: string };
    selectedOnly: boolean;
}

/* ─── Constants ───────────────────────────────────────────────────── */

const PAGE_SIZE = 10;

/* ─── Concept Tag Colors ──────────────────────────────────────────── */

const CONCEPT_COLORS = [
    { bg: '#FEE2E2', color: '#DC2626', border: '#FECACA' },
    { bg: '#FEF3C7', color: '#D97706', border: '#FDE68A' },
    { bg: '#D1FAE5', color: '#059669', border: '#A7F3D0' },
    { bg: '#DBEAFE', color: '#2563EB', border: '#BFDBFE' },
    { bg: '#E0E7FF', color: '#4F46E5', border: '#C7D2FE' },
    { bg: '#FCE7F3', color: '#DB2777', border: '#FBCFE8' },
    { bg: '#F3E8FF', color: '#7C3AED', border: '#DDD6FE' },
    { bg: '#CCFBF1', color: '#0D9488', border: '#99F6E4' },
];

/* ─── Difficulty / Cognitive Colors ────────────────────────────────── */

const DIFFICULTY_STYLES: Record<string, { bg: string; color: string }> = {
    easy: { bg: '#D1FAE5', color: '#065F46' },
    medium: { bg: '#FEF3C7', color: '#92400E' },
    hard: { bg: '#FEE2E2', color: '#991B1B' },
    veryhard: { bg: '#FDE8E8', color: '#7F1D1D' },
};

const COGNITIVE_STYLES: Record<string, { bg: string; color: string }> = {
    remembering: { bg: '#DBEAFE', color: '#1E40AF' },
    understanding: { bg: '#E0E7FF', color: '#3730A3' },
    applying: { bg: '#D1FAE5', color: '#065F46' },
    analyzing: { bg: '#FEF3C7', color: '#92400E' },
    evaluating: { bg: '#FCE7F3', color: '#9D174D' },
    creating: { bg: '#F3E8FF', color: '#5B21B6' },
};

/* ─── Main Component ──────────────────────────────────────────────── */

export function QuestionBrowserPage({ apiBaseUrl, apiKey }: QuestionBrowserPageProps) {
    const { hasRole } = useAuth();
    const [questions, setQuestions] = useState<LibraryQuestion[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
    const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);

    // Pagination
    const [currentPage, setCurrentPage] = useState(0);

    // Selection
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [isSelectMode, setIsSelectMode] = useState(false);

    // Download history
    const [downloadHistory, setDownloadHistory] = useState<DownloadRecord[]>([]);
    const [showHistory, setShowHistory] = useState(false);

    // Filters
    const [filters, setFilters] = useState({
        subject: '',
        chapter: '',
        topic: '',
        cognitive_level: '',
        difficulty: '',
        question_type: '',
    });

    const client = useMemo(() => new QbankApiClient(apiBaseUrl, apiKey), [apiBaseUrl, apiKey]);

    useEffect(() => {
        fetchQuestions();
    }, []);

    // Reset page when filters/search change
    useEffect(() => {
        setCurrentPage(0);
    }, [searchQuery, filters]);

    const fetchQuestions = async () => {
        setIsLoading(true);
        try {
            const jobsResponse = await client.listJobs(100, 0);
            const allQuestions: LibraryQuestion[] = [];

            for (const job of jobsResponse.items) {
                if (job.status === 'completed' || job.status === 'published') {
                    const itemsResponse = await client.getItems(job.job_id, { limit: 100, offset: 0 });
                    for (const item of itemsResponse.items) {
                        if (item.review_status === 'approved' || item.published) {
                            allQuestions.push({
                                id: item.item_id,
                                question: item.question,
                                options: item.options,
                                correct_answer: item.correct_answer,
                                explanation: item.explanation || '',
                                difficulty: (item as any).difficulty || (job as any).difficulty || 'medium',
                                cognitive_level: item.cognitive_level || '',
                                question_type: item.question_type || '',
                                estimated_time: item.estimated_time,
                                concepts: item.concepts || null,
                                subject: job.selected_subject || '',
                                chapter: job.selected_chapter || '',
                                topic: (job as any).selected_input || '',
                                created_at: item.created_at,
                            });
                        }
                    }
                }
            }

            setQuestions(allQuestions);
        } catch (error) {
            console.error('Failed to fetch questions:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Filtered list
    const filteredQuestions = useMemo(() => {
        return questions.filter(q => {
            if (searchQuery) {
                const query = searchQuery.toLowerCase();
                const matchesText =
                    q.question.toLowerCase().includes(query) ||
                    q.options.some(o => o.toLowerCase().includes(query)) ||
                    q.explanation.toLowerCase().includes(query) ||
                    (q.concepts || '').toLowerCase().includes(query);
                if (!matchesText) return false;
            }
            if (filters.subject && q.subject.toLowerCase() !== filters.subject.toLowerCase()) return false;
            if (filters.chapter && q.chapter.toLowerCase() !== filters.chapter.toLowerCase()) return false;
            if (filters.topic && q.topic.toLowerCase() !== filters.topic.toLowerCase()) return false;
            if (filters.difficulty && q.difficulty.toLowerCase() !== filters.difficulty.toLowerCase()) return false;
            if (filters.cognitive_level && q.cognitive_level.toLowerCase() !== filters.cognitive_level.toLowerCase()) return false;
            if (filters.question_type && q.question_type.toLowerCase().replace(/ /g, '_') !== filters.question_type.toLowerCase().replace(/ /g, '_')) return false;
            return true;
        });
    }, [questions, searchQuery, filters]);

    // Pagination
    const totalPages = Math.ceil(filteredQuestions.length / PAGE_SIZE);
    const paginatedQuestions = useMemo(() => {
        const start = currentPage * PAGE_SIZE;
        return filteredQuestions.slice(start, start + PAGE_SIZE);
    }, [filteredQuestions, currentPage]);

    const rangeStart = currentPage * PAGE_SIZE + 1;
    const rangeEnd = Math.min((currentPage + 1) * PAGE_SIZE, filteredQuestions.length);

    // Unique filter options
    const filterOptions = useMemo(() => ({
        subjects: [...new Set(questions.map(q => q.subject).filter(Boolean))],
        chapters: [...new Set(questions.map(q => q.chapter).filter(Boolean))],
        topics: [...new Set(questions.map(q => q.topic).filter(Boolean))],
        difficulties: ['easy', 'medium', 'hard', 'veryhard'],
        cognitive_levels: [...new Set(questions.map(q => q.cognitive_level).filter(Boolean))],
        question_types: [...new Set(questions.map(q => q.question_type).filter(Boolean))],
    }), [questions]);

    const hasActiveFilters = Object.values(filters).some(Boolean);

    const toggleExplanation = useCallback((id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    // Selection helpers
    const toggleSelectMode = () => {
        setIsSelectMode(prev => {
            if (prev) setSelectedIds(new Set()); // exiting select mode clears
            return !prev;
        });
    };

    const toggleSelect = useCallback((id: number) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    const allOnPageSelected = paginatedQuestions.length > 0 && paginatedQuestions.every(q => selectedIds.has(q.id));

    const toggleSelectAllOnPage = () => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (allOnPageSelected) {
                paginatedQuestions.forEach(q => next.delete(q.id));
            } else {
                paginatedQuestions.forEach(q => next.add(q.id));
            }
            return next;
        });
    };

    const selectAllFiltered = () => {
        setSelectedIds(new Set(filteredQuestions.map(q => q.id)));
    };

    // Download handler
    const handleDownload = async (format: 'pdf' | 'excel' | 'docx') => {
        setDownloadingFormat(format);
        try {
            const hasSelection = selectedIds.size > 0;
            const { blob, filename } = await client.exportLibrary({
                format,
                include_explanations: true,
                include_metadata: true,
                only_approved: true,
                subject: filters.subject || undefined,
                chapter: filters.chapter || undefined,
                item_ids: hasSelection ? Array.from(selectedIds) : undefined,
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            // Record in history
            setDownloadHistory(prev => [{
                id: `dl_${Date.now()}`,
                format,
                count: hasSelection ? selectedIds.size : filteredQuestions.length,
                timestamp: new Date(),
                filters: {
                    subject: filters.subject || undefined,
                    chapter: filters.chapter || undefined,
                    topic: filters.topic || undefined,
                },
                selectedOnly: hasSelection,
            }, ...prev]);
        } catch (err) {
            console.error(`Export ${format} failed:`, err);
        } finally {
            setDownloadingFormat(null);
        }
    };

    const formatLabel = (format: string) => {
        if (format === 'pdf') return 'PDF';
        if (format === 'excel') return 'Excel';
        if (format === 'docx') return 'Word';
        return format.toUpperCase();
    };

    return (
        <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto' }}>
            {/* Title */}
            <h1 style={{
                fontSize: 26,
                fontWeight: 700,
                margin: '0 0 20px 0',
                letterSpacing: '-0.01em',
            }}>
                ✨ AI Generated Question Bank
            </h1>

            {/* Filter Bar */}
            <div style={{
                display: 'flex',
                gap: 12,
                marginBottom: 16,
                flexWrap: 'wrap',
                alignItems: 'flex-end',
            }}>
                <FilterDropdown
                    label="Select Subject"
                    value={filters.subject}
                    options={filterOptions.subjects}
                    onChange={(v) => setFilters(f => ({ ...f, subject: v }))}
                />
                <FilterDropdown
                    label="Select Chapter"
                    value={filters.chapter}
                    options={filterOptions.chapters}
                    onChange={(v) => setFilters(f => ({ ...f, chapter: v }))}
                />
                <FilterDropdown
                    label="Select Topic"
                    value={filters.topic}
                    options={filterOptions.topics}
                    onChange={(v) => setFilters(f => ({ ...f, topic: v }))}
                />
                <FilterDropdown
                    label="Cognitive Level"
                    value={filters.cognitive_level}
                    options={filterOptions.cognitive_levels}
                    onChange={(v) => setFilters(f => ({ ...f, cognitive_level: v }))}
                />
                <FilterDropdown
                    label="Difficulty"
                    value={filters.difficulty}
                    options={filterOptions.difficulties}
                    onChange={(v) => setFilters(f => ({ ...f, difficulty: v }))}
                />
                <FilterDropdown
                    label="Question Type"
                    value={filters.question_type}
                    options={filterOptions.question_types}
                    onChange={(v) => setFilters(f => ({ ...f, question_type: v }))}
                />
                {hasActiveFilters && (
                    <button
                        onClick={() => setFilters({ subject: '', chapter: '', topic: '', cognitive_level: '', difficulty: '', question_type: '' })}
                        style={{
                            padding: '8px 16px',
                            background: '#111',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontWeight: 600,
                            fontSize: 13,
                            height: 38,
                        }}
                    >
                        Clear Filters
                    </button>
                )}
            </div>

            {/* Action Bar: Select toggle + Download buttons */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 10,
                marginBottom: 16,
                flexWrap: 'wrap',
            }}>
                {/* Left: Select mode toggle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button
                        onClick={toggleSelectMode}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '8px 16px',
                            background: isSelectMode ? '#EEF2FF' : '#F9FAFB',
                            color: isSelectMode ? '#4F46E5' : '#374151',
                            border: isSelectMode ? '1.5px solid #818CF8' : '1px solid #D1D5DB',
                            borderRadius: 8,
                            cursor: 'pointer',
                            fontWeight: 600,
                            fontSize: 13,
                            transition: 'all 0.15s',
                        }}
                    >
                        {isSelectMode ? <CheckSquare size={15} /> : <Square size={15} />}
                        {isSelectMode ? 'Exit Selection' : 'Select Questions'}
                    </button>

                    {isSelectMode && (
                        <>
                            <button
                                onClick={toggleSelectAllOnPage}
                                style={{
                                    padding: '7px 14px',
                                    background: '#fff',
                                    color: '#374151',
                                    border: '1px solid #D1D5DB',
                                    borderRadius: 6,
                                    cursor: 'pointer',
                                    fontWeight: 500,
                                    fontSize: 12,
                                }}
                            >
                                {allOnPageSelected ? 'Deselect Page' : 'Select Page'}
                            </button>
                            <button
                                onClick={selectAllFiltered}
                                style={{
                                    padding: '7px 14px',
                                    background: '#fff',
                                    color: '#374151',
                                    border: '1px solid #D1D5DB',
                                    borderRadius: 6,
                                    cursor: 'pointer',
                                    fontWeight: 500,
                                    fontSize: 12,
                                }}
                            >
                                Select All ({filteredQuestions.length})
                            </button>
                            {selectedIds.size > 0 && (
                                <span style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    padding: '4px 12px',
                                    background: '#EEF2FF',
                                    color: '#4338CA',
                                    borderRadius: 20,
                                    fontSize: 12,
                                    fontWeight: 700,
                                }}>
                                    <Check size={13} />
                                    {selectedIds.size} selected
                                </span>
                            )}
                        </>
                    )}
                </div>

                {/* Right: Download buttons (publisher/admin only) */}
                {hasRole(['publisher', 'admin']) ? (
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        {downloadHistory.length > 0 && (
                            <button
                                onClick={() => setShowHistory(h => !h)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 5,
                                    padding: '8px 14px',
                                    background: showHistory ? '#FEF3C7' : '#F9FAFB',
                                    color: showHistory ? '#92400E' : '#6B7280',
                                    border: showHistory ? '1px solid #FDE68A' : '1px solid #D1D5DB',
                                    borderRadius: 6,
                                    cursor: 'pointer',
                                    fontWeight: 500,
                                    fontSize: 12,
                                    transition: 'all 0.15s',
                                }}
                            >
                                <History size={14} />
                                Downloads ({downloadHistory.length})
                            </button>
                        )}
                        <DownloadButton
                            label={selectedIds.size > 0 ? `PDF (${selectedIds.size})` : 'PDF Download'}
                            icon={<FileText size={15} />}
                            color="#111"
                            loading={downloadingFormat === 'pdf'}
                            onClick={() => handleDownload('pdf')}
                        />
                        <DownloadButton
                            label={selectedIds.size > 0 ? `Excel (${selectedIds.size})` : 'Excel Download'}
                            icon={<FileSpreadsheet size={15} />}
                            color="#16A34A"
                            loading={downloadingFormat === 'excel'}
                            onClick={() => handleDownload('excel')}
                        />
                        <DownloadButton
                            label={selectedIds.size > 0 ? `Word (${selectedIds.size})` : 'Export to Word'}
                            icon={<FileDown size={15} />}
                            color="#2563EB"
                            loading={downloadingFormat === 'docx'}
                            onClick={() => handleDownload('docx')}
                        />
                    </div>
                ) : (
                    <div style={{ fontSize: 12, color: '#9CA3AF', fontStyle: 'italic' }}>
                        🔒 Download requires Publisher role
                    </div>
                )}
            </div>

            {/* Download History Panel */}
            {showHistory && downloadHistory.length > 0 && (
                <div style={{
                    marginBottom: 20,
                    background: '#FFFBEB',
                    border: '1px solid #FDE68A',
                    borderRadius: 10,
                    padding: '14px 18px',
                    animation: 'fadeIn 0.2s ease',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: '#92400E' }}>
                            📥 Recent Downloads
                        </span>
                        <button
                            onClick={() => setShowHistory(false)}
                            style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                color: '#92400E', padding: 2,
                            }}
                        >
                            <X size={14} />
                        </button>
                    </div>
                    <div style={{ display: 'grid', gap: 6 }}>
                        {downloadHistory.map(dl => (
                            <div key={dl.id} style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '8px 12px',
                                background: '#fff',
                                borderRadius: 6,
                                border: '1px solid #FDE68A',
                                fontSize: 12,
                            }}>
                                <span style={{
                                    padding: '2px 8px',
                                    background: dl.format === 'pdf' ? '#111' : dl.format === 'excel' ? '#16A34A' : '#2563EB',
                                    color: '#fff',
                                    borderRadius: 4,
                                    fontWeight: 700,
                                    fontSize: 10,
                                    textTransform: 'uppercase',
                                }}>
                                    {dl.format}
                                </span>
                                <span style={{ color: '#374151', fontWeight: 500 }}>
                                    {dl.count} question{dl.count !== 1 ? 's' : ''}
                                    {dl.selectedOnly && <span style={{ color: '#6366F1', marginLeft: 4 }}>(selected)</span>}
                                </span>
                                {dl.filters.subject && (
                                    <span style={{ padding: '1px 8px', background: '#EFF6FF', color: '#1D4ED8', borderRadius: 10, fontSize: 11 }}>
                                        {dl.filters.subject}
                                    </span>
                                )}
                                {dl.filters.chapter && (
                                    <span style={{ padding: '1px 8px', background: '#F0FDF4', color: '#15803D', borderRadius: 10, fontSize: 11 }}>
                                        {dl.filters.chapter}
                                    </span>
                                )}
                                <span style={{ marginLeft: 'auto', color: '#9CA3AF', fontSize: 11 }}>
                                    {dl.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Search bar */}
            <div style={{ position: 'relative', marginBottom: 20 }}>
                <Search
                    size={18}
                    style={{
                        position: 'absolute',
                        left: 14,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: '#9CA3AF',
                    }}
                />
                <input
                    type="text"
                    placeholder="Search questions, options, concepts..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{
                        width: '100%',
                        padding: '10px 14px 10px 42px',
                        borderRadius: 10,
                        border: '1px solid #E5E7EB',
                        fontSize: 14,
                        background: '#FAFAFA',
                        outline: 'none',
                        transition: 'border-color 0.15s',
                    }}
                    onFocus={(e) => (e.target.style.borderColor = '#6366F1')}
                    onBlur={(e) => (e.target.style.borderColor = '#E5E7EB')}
                />
            </div>

            {/* Results summary */}
            <div style={{
                fontSize: 13,
                color: '#6B7280',
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
            }}>
                <span>
                    {filteredQuestions.length > 0
                        ? `Showing ${rangeStart}–${rangeEnd} of ${filteredQuestions.length} questions`
                        : `Showing 0 of ${questions.length} questions`}
                </span>
                {totalPages > 1 && (
                    <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                        Page {currentPage + 1} of {totalPages}
                    </span>
                )}
            </div>

            {/* Questions */}
            {isLoading ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>
                    <div style={{
                        width: 32, height: 32,
                        border: '3px solid #E5E7EB',
                        borderTopColor: '#6366F1',
                        borderRadius: '50%',
                        margin: '0 auto 12px',
                        animation: 'spin 0.6s linear infinite',
                    }} />
                    Loading questions...
                </div>
            ) : filteredQuestions.length === 0 ? (
                <div style={{
                    textAlign: 'center',
                    padding: 60,
                    background: '#F9FAFB',
                    borderRadius: 12,
                    border: '1px dashed #D1D5DB',
                }}>
                    <p style={{ color: '#6B7280', margin: 0, fontSize: 15 }}>
                        {searchQuery || hasActiveFilters
                            ? 'No questions match your search'
                            : 'No approved questions yet'}
                    </p>
                    <p style={{ color: '#9CA3AF', margin: '8px 0 0', fontSize: 13 }}>
                        {searchQuery || hasActiveFilters
                            ? 'Try adjusting your filters'
                            : 'Generate and approve questions to see them here'}
                    </p>
                </div>
            ) : (
                <div style={{ display: 'grid', gap: 20 }}>
                    {paginatedQuestions.map((q, idx) => (
                        <QuestionCard
                            key={q.id}
                            question={q}
                            index={currentPage * PAGE_SIZE + idx + 1}
                            isExpanded={expandedIds.has(q.id)}
                            onToggleExplanation={() => toggleExplanation(q.id)}
                            isSelectMode={isSelectMode}
                            isSelected={selectedIds.has(q.id)}
                            onToggleSelect={() => toggleSelect(q.id)}
                        />
                    ))}
                </div>
            )}

            {/* Pagination Controls */}
            {totalPages > 1 && (
                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: 4,
                    marginTop: 28,
                    marginBottom: 20,
                }}>
                    <button
                        onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                        disabled={currentPage === 0}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '8px 14px',
                            background: currentPage === 0 ? '#F3F4F6' : '#fff',
                            color: currentPage === 0 ? '#9CA3AF' : '#374151',
                            border: '1px solid #D1D5DB',
                            borderRadius: 8,
                            cursor: currentPage === 0 ? 'not-allowed' : 'pointer',
                            fontWeight: 500,
                            fontSize: 13,
                            transition: 'all 0.15s',
                        }}
                    >
                        <ChevronLeft size={16} />
                        Previous
                    </button>

                    {/* Page numbers */}
                    {getPageNumbers(currentPage, totalPages).map((page, i) =>
                        page === '...' ? (
                            <span key={`ellipsis-${i}`} style={{ padding: '0 6px', color: '#9CA3AF', fontSize: 13 }}>…</span>
                        ) : (
                            <button
                                key={page}
                                onClick={() => setCurrentPage(page as number)}
                                style={{
                                    width: 36,
                                    height: 36,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    borderRadius: 8,
                                    border: currentPage === page ? '1.5px solid #6366F1' : '1px solid #D1D5DB',
                                    background: currentPage === page ? '#EEF2FF' : '#fff',
                                    color: currentPage === page ? '#4338CA' : '#374151',
                                    fontWeight: currentPage === page ? 700 : 500,
                                    fontSize: 13,
                                    cursor: 'pointer',
                                    transition: 'all 0.15s',
                                }}
                            >
                                {(page as number) + 1}
                            </button>
                        )
                    )}

                    <button
                        onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
                        disabled={currentPage === totalPages - 1}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '8px 14px',
                            background: currentPage === totalPages - 1 ? '#F3F4F6' : '#fff',
                            color: currentPage === totalPages - 1 ? '#9CA3AF' : '#374151',
                            border: '1px solid #D1D5DB',
                            borderRadius: 8,
                            cursor: currentPage === totalPages - 1 ? 'not-allowed' : 'pointer',
                            fontWeight: 500,
                            fontSize: 13,
                            transition: 'all 0.15s',
                        }}
                    >
                        Next
                        <ChevronRight size={16} />
                    </button>
                </div>
            )}

            {/* Spin + fadeIn animation */}
            <style>{`
                @keyframes spin { to { transform: rotate(360deg); } }
                @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            `}</style>
        </div>
    );
}

/* ─── Page Number Helper ──────────────────────────────────────────── */

function getPageNumbers(current: number, total: number): (number | '...')[] {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i);

    const pages: (number | '...')[] = [];
    pages.push(0);

    if (current > 2) pages.push('...');

    const start = Math.max(1, current - 1);
    const end = Math.min(total - 2, current + 1);
    for (let i = start; i <= end; i++) pages.push(i);

    if (current < total - 3) pages.push('...');

    pages.push(total - 1);
    return pages;
}

/* ─── Question Card ───────────────────────────────────────────────── */

function QuestionCard({
    question: q,
    index,
    isExpanded,
    onToggleExplanation,
    isSelectMode = false,
    isSelected = false,
    onToggleSelect,
}: {
    question: LibraryQuestion;
    index: number;
    isExpanded: boolean;
    onToggleExplanation: () => void;
    isSelectMode?: boolean;
    isSelected?: boolean;
    onToggleSelect?: () => void;
}) {
    const conceptList = q.concepts
        ? q.concepts.split(',').map(c => c.trim()).filter(Boolean)
        : [];

    const diffStyle = DIFFICULTY_STYLES[q.difficulty?.toLowerCase()] || DIFFICULTY_STYLES.medium;
    const cogStyle = COGNITIVE_STYLES[q.cognitive_level?.toLowerCase()] || { bg: '#F3F4F6', color: '#374151' };

    const formatDifficulty = (d: string) => {
        if (d === 'veryhard') return 'Very Hard';
        return d.charAt(0).toUpperCase() + d.slice(1);
    };

    const formatCognitive = (c: string) => {
        return c.charAt(0).toUpperCase() + c.slice(1);
    };

    return (
        <div style={{
            background: isSelected ? '#F5F3FF' : '#fff',
            border: isSelected ? '2px solid #818CF8' : '1px solid #E5E7EB',
            borderRadius: 12,
            padding: '20px 24px',
            transition: 'all 0.2s',
            position: 'relative',
        }}
            onMouseEnter={(e) => {
                if (!isSelected) (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 20px rgba(0,0,0,0.06)';
            }}
            onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.boxShadow = 'none';
            }}
        >
            {/* Selection checkbox */}
            {isSelectMode && (
                <button
                    onClick={(e) => { e.stopPropagation(); onToggleSelect?.(); }}
                    style={{
                        position: 'absolute',
                        top: 14,
                        left: -14,
                        width: 28,
                        height: 28,
                        borderRadius: 6,
                        border: isSelected ? '2px solid #6366F1' : '2px solid #D1D5DB',
                        background: isSelected ? '#6366F1' : '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                        zIndex: 2,
                    }}
                >
                    {isSelected && <Check size={16} color="#fff" strokeWidth={3} />}
                </button>
            )}

            {/* Top row: Question + Badges */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                <div style={{ flex: 1, fontSize: 15, lineHeight: 1.7, fontWeight: 500 }}>
                    <span style={{ fontWeight: 700 }}>{index}. </span>
                    <MathRenderer content={q.question} />
                </div>

                {/* Top-right badges */}
                <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {q.question_type && (
                        <BadgePill bg="#F3F4F6" color="#374151" border="#E5E7EB">
                            {q.question_type.replace(/_/g, ' ')}
                        </BadgePill>
                    )}
                    {q.cognitive_level && (
                        <BadgePill bg={cogStyle.bg} color={cogStyle.color}>
                            {formatCognitive(q.cognitive_level)}
                        </BadgePill>
                    )}
                    <BadgePill bg={diffStyle.bg} color={diffStyle.color}>
                        {formatDifficulty(q.difficulty)}
                    </BadgePill>
                    {q.estimated_time != null && (
                        <BadgePill bg="#F0F9FF" color="#0369A1" border="#BAE6FD">
                            <Clock size={12} style={{ marginRight: 4 }} />
                            {q.estimated_time} min{q.estimated_time !== 1 ? 's' : ''}
                        </BadgePill>
                    )}
                </div>
            </div>

            {/* Options */}
            <div style={{ margin: '16px 0' }}>
                {q.options.map((opt, i) => {
                    const letter = String.fromCharCode(65 + i);
                    const isCorrect = q.correct_answer === opt || q.correct_answer === letter;
                    return (
                        <div
                            key={i}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                padding: '8px 14px',
                                marginBottom: 4,
                                borderRadius: 8,
                                background: isCorrect ? '#DCFCE7' : 'transparent',
                                border: isCorrect ? '1px solid #BBF7D0' : '1px solid transparent',
                                transition: 'background 0.15s',
                                fontSize: 14,
                            }}
                        >
                            <span style={{
                                fontWeight: 600,
                                color: isCorrect ? '#16A34A' : '#6B7280',
                                minWidth: 60,
                            }}>
                                Option {letter}:
                            </span>
                            <span style={{ color: isCorrect ? '#15803D' : '#374151' }}>
                                <MathRenderer content={opt} />
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Subject / Chapter / Topic tags */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: conceptList.length > 0 ? 10 : 0 }}>
                {q.subject && (
                    <MetaTag emoji="🔬" label="Subject" value={q.subject} bg="#EFF6FF" color="#1D4ED8" />
                )}
                {q.chapter && (
                    <MetaTag emoji="📖" label="Chapter" value={q.chapter} bg="#F0FDF4" color="#15803D" />
                )}
                {q.topic && (
                    <MetaTag emoji="🎯" label="Topic" value={q.topic} bg="#FFF7ED" color="#C2410C" />
                )}
            </div>

            {/* Concepts row */}
            {conceptList.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                    <span style={{ fontSize: 13, color: '#6B7280', fontWeight: 600 }}>🧩 Concepts:</span>
                    {conceptList.map((concept, i) => {
                        const palette = CONCEPT_COLORS[i % CONCEPT_COLORS.length];
                        return (
                            <span
                                key={i}
                                style={{
                                    fontSize: 12,
                                    padding: '3px 10px',
                                    borderRadius: 20,
                                    background: palette.bg,
                                    color: palette.color,
                                    border: `1px solid ${palette.border}`,
                                    fontWeight: 500,
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {concept}
                            </span>
                        );
                    })}
                </div>
            )}

            {/* Collapsible Explanation */}
            {q.explanation && (
                <div style={{ marginTop: 8 }}>
                    <button
                        onClick={onToggleExplanation}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            width: '100%',
                            padding: '10px 14px',
                            background: isExpanded ? '#F9FAFB' : '#FAFAFA',
                            border: '1px solid #E5E7EB',
                            borderRadius: isExpanded ? '8px 8px 0 0' : 8,
                            cursor: 'pointer',
                            fontSize: 14,
                            fontWeight: 600,
                            color: '#374151',
                            transition: 'background 0.15s',
                        }}
                    >
                        <span>Explanation</span>
                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>
                    {isExpanded && (
                        <div style={{
                            padding: '16px 18px',
                            background: '#F9FAFB',
                            border: '1px solid #E5E7EB',
                            borderTop: 'none',
                            borderRadius: '0 0 8px 8px',
                            fontSize: 14,
                            lineHeight: 1.8,
                            color: '#374151',
                            animation: 'fadeIn 0.2s ease',
                        }}>
                            <MathRenderer content={q.explanation} />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ─── Sub-components ──────────────────────────────────────────────── */

function FilterDropdown({
    label,
    value,
    options,
    onChange,
}: {
    label: string;
    value: string;
    options: string[];
    onChange: (v: string) => void;
}) {
    return (
        <div style={{ minWidth: 160, flex: 1, maxWidth: 200 }}>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 6,
                    border: '1px solid #D1D5DB',
                    fontSize: 13,
                    color: value ? '#111827' : '#9CA3AF',
                    background: '#fff',
                    cursor: 'pointer',
                    appearance: 'auto',
                }}
            >
                <option value="">{label}</option>
                {options.map(o => (
                    <option key={o} value={o} style={{ color: '#111827' }}>{o}</option>
                ))}
            </select>
        </div>
    );
}

function BadgePill({
    bg,
    color,
    border,
    children,
}: {
    bg: string;
    color: string;
    border?: string;
    children: React.ReactNode;
}) {
    return (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            fontSize: 12,
            padding: '3px 10px',
            borderRadius: 20,
            background: bg,
            color: color,
            border: border ? `1px solid ${border}` : 'none',
            fontWeight: 600,
            whiteSpace: 'nowrap',
        }}>
            {children}
        </span>
    );
}

function MetaTag({
    emoji,
    label,
    value,
    bg,
    color,
}: {
    emoji: string;
    label: string;
    value: string;
    bg: string;
    color: string;
}) {
    return (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
            padding: '4px 12px',
            borderRadius: 20,
            background: bg,
            color: color,
            fontWeight: 500,
        }}>
            <span>{emoji}</span>
            <span style={{ fontWeight: 600 }}>{label}:</span>
            <span>{value}</span>
        </span>
    );
}

function DownloadButton({
    label,
    icon,
    color,
    loading,
    onClick,
}: {
    label: string;
    icon: React.ReactNode;
    color: string;
    loading: boolean;
    onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            disabled={loading}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                background: color,
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                cursor: loading ? 'wait' : 'pointer',
                fontWeight: 600,
                fontSize: 13,
                opacity: loading ? 0.7 : 1,
                transition: 'opacity 0.15s',
            }}
        >
            {icon}
            {loading ? 'Downloading...' : label}
        </button>
    );
}

export default QuestionBrowserPage;
