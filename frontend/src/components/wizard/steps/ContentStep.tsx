import { useState } from "react";
import type { FormState } from "../types";

interface ContentStepProps {
    form: FormState;
    subjectOptions: string[];
    chapterOptions: string[];
    topicOptions: string[];
    loadingChapters: boolean;
    loadingTopics: boolean;
    onSubjectSelect: (subject: string) => void;
    onChapterSelect: (chapter: string) => void;
    onTopicSelect: (topic: string) => void;
    onBatchNameChange: (name: string) => void;
}

const SUBJECT_ICONS: Record<string, string> = {
    Biology: "🧬",
    Physics: "⚛️",
    Chemistry: "🧪",
    Botany: "🌱",
    Zoology: "🦎",
};

export function ContentStep({
    form,
    subjectOptions,
    chapterOptions,
    topicOptions,
    loadingChapters,
    loadingTopics,
    onSubjectSelect,
    onChapterSelect,
    onTopicSelect,
    onBatchNameChange,
}: ContentStepProps) {
    const [chapterSearch, setChapterSearch] = useState("");

    const filteredChapters = chapterOptions.filter((chapter) =>
        chapter.toLowerCase().includes(chapterSearch.toLowerCase())
    );

    return (
        <div className="animate-fadeIn">
            <div className="wizard-header">
                <h2 className="wizard-title">📚 What content do you want to create?</h2>
                <p className="wizard-subtitle">
                    Name your batch, then select subject, chapter, and optionally a topic
                </p>
            </div>

            {/* Batch Name */}
            <div style={{ marginBottom: "var(--space-6)" }}>
                <label className="quantity-label" style={{ display: "block", marginBottom: "var(--space-2)" }}>
                    Batch Name <span style={{ color: "var(--gray-400)", fontWeight: 400 }}>(Optional)</span>
                </label>
                <input
                    type="text"
                    placeholder="e.g. Physics Ch3 — NEET Prep"
                    value={form.batchName}
                    onChange={(e) => onBatchNameChange(e.target.value)}
                    style={{
                        width: "100%",
                        padding: "var(--space-3) var(--space-4)",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--gray-200)",
                        fontSize: "14px",
                        backgroundColor: "white",
                    }}
                />
                <div style={{ fontSize: "12px", color: "var(--gray-400)", marginTop: "var(--space-1)" }}>
                    Leave empty to auto-generate from subject & chapter
                </div>
            </div>

            {/* Subject Selection */}
            <div style={{ marginBottom: "var(--space-6)" }}>
                <label className="quantity-label" style={{ display: "block", marginBottom: "var(--space-3)" }}>
                    Subject
                </label>
                <div className="subject-grid">
                    {subjectOptions.map((subject) => (
                        <div
                            key={subject}
                            className={`subject-card ${form.subject === subject ? "selected" : ""}`}
                            onClick={() => onSubjectSelect(subject)}
                        >
                            <span className="subject-icon">
                                {SUBJECT_ICONS[subject] || "📖"}
                            </span>
                            <span className="subject-name">{subject}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Chapter Selection */}
            {form.subject && (
                <div style={{ marginBottom: "var(--space-6)" }} className="animate-fadeIn">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                        <label className="quantity-label">Chapter</label>
                        <input
                            type="text"
                            placeholder="🔍 Search chapters..."
                            value={chapterSearch}
                            onChange={(e) => setChapterSearch(e.target.value)}
                            style={{
                                padding: "var(--space-2) var(--space-3)",
                                borderRadius: "var(--radius-md)",
                                border: "1px solid var(--gray-200)",
                                fontSize: "13px",
                                width: "180px",
                            }}
                        />
                    </div>

                    {loadingChapters ? (
                        <div style={{ padding: "var(--space-6)", textAlign: "center", color: "var(--gray-400)" }}>
                            Loading chapters...
                        </div>
                    ) : (
                        <div className="chapter-list">
                            {filteredChapters.map((chapter) => (
                                <div
                                    key={chapter}
                                    className={`chapter-item ${form.chapter === chapter ? "selected" : ""}`}
                                    onClick={() => onChapterSelect(chapter)}
                                >
                                    <span className="chapter-arrow">
                                        {form.chapter === chapter ? "●" : "▸"}
                                    </span>
                                    <span className="chapter-name">{chapter}</span>
                                </div>
                            ))}
                            {filteredChapters.length === 0 && (
                                <div style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--gray-400)" }}>
                                    No chapters found
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Topic Selection (Optional) */}
            {form.chapter && (
                <div className="animate-fadeIn">
                    <label className="quantity-label" style={{ display: "block", marginBottom: "var(--space-3)" }}>
                        Topic <span style={{ color: "var(--gray-400)", fontWeight: 400 }}>(Optional)</span>
                    </label>

                    {loadingTopics ? (
                        <div style={{ padding: "var(--space-3)", color: "var(--gray-400)" }}>
                            Loading topics...
                        </div>
                    ) : (
                        <select
                            value={form.topic}
                            onChange={(e) => onTopicSelect(e.target.value)}
                            style={{
                                width: "100%",
                                padding: "var(--space-3) var(--space-4)",
                                borderRadius: "var(--radius-md)",
                                border: "1px solid var(--gray-200)",
                                fontSize: "14px",
                                backgroundColor: "white",
                            }}
                        >
                            <option value="">All topics in this chapter</option>
                            {topicOptions.map((topic) => (
                                <option key={topic} value={topic}>
                                    {topic}
                                </option>
                            ))}
                        </select>
                    )}
                </div>
            )}

            {/* Selection Summary */}
            {form.subject && form.chapter && (
                <div
                    className="animate-fadeIn"
                    style={{
                        marginTop: "var(--space-6)",
                        padding: "var(--space-4)",
                        background: "var(--primary-50)",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--primary-200)",
                    }}
                >
                    <div style={{ fontSize: "13px", color: "var(--primary-700)" }}>
                        📍 <strong>{form.subject}</strong> → <strong>{form.chapter}</strong>
                        {form.topic && <> → <strong>{form.topic}</strong></>}
                    </div>
                </div>
            )}
        </div>
    );
}
