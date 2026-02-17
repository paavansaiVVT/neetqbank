import type { FormState } from "../types";
import { MODEL_DISPLAY_NAMES } from "./ModelStep";

interface ReviewStepProps {
    form: FormState;
}

export function ReviewStep({ form }: ReviewStepProps) {
    const getQuestionCount = (percent: number) =>
        Math.round((form.totalQuestions * percent) / 100);

    const estimatedTokens = form.totalQuestions * 1200; // ~1200 tokens per question
    const estimatedCost = (estimatedTokens / 1000) * 0.003; // $0.003 per 1K tokens (approx)
    const estimatedTime = Math.ceil(form.totalQuestions / 5); // ~5 questions per minute

    return (
        <div className="animate-fadeIn">
            <div className="wizard-header">
                <h2 className="wizard-title">✅ Review your generation settings</h2>
                <p className="wizard-subtitle">
                    Make sure everything looks good before starting
                </p>
            </div>

            <div
                style={{
                    background: "white",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--gray-200)",
                    overflow: "hidden",
                }}
            >
                {/* Content Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>📚</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Content</span>
                    </div>
                    <div style={{ fontSize: "15px", color: "var(--gray-800)", paddingLeft: "var(--space-6)" }}>
                        <strong>{form.subject}</strong> → <strong>{form.chapter}</strong>
                        {form.topic && <> → <strong>{form.topic}</strong></>}
                    </div>
                </div>

                {/* Quantity Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>📊</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Quantity</span>
                    </div>
                    <div style={{ fontSize: "15px", color: "var(--gray-800)", paddingLeft: "var(--space-6)" }}>
                        <strong>{form.totalQuestions}</strong> questions total
                    </div>
                </div>

                {/* Difficulty Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>🎯</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Difficulty Mix</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", paddingLeft: "var(--space-6)" }}>
                        {form.difficulty.easy > 0 && (
                            <span style={{ padding: "var(--space-1) var(--space-3)", background: "#dcfce7", color: "#166534", borderRadius: "var(--radius-full)", fontSize: "13px", fontWeight: 500 }}>
                                {getQuestionCount(form.difficulty.easy)} Easy
                            </span>
                        )}
                        {form.difficulty.medium > 0 && (
                            <span style={{ padding: "var(--space-1) var(--space-3)", background: "#fef3c7", color: "#92400e", borderRadius: "var(--radius-full)", fontSize: "13px", fontWeight: 500 }}>
                                {getQuestionCount(form.difficulty.medium)} Medium
                            </span>
                        )}
                        {form.difficulty.hard > 0 && (
                            <span style={{ padding: "var(--space-1) var(--space-3)", background: "#fee2e2", color: "#991b1b", borderRadius: "var(--radius-full)", fontSize: "13px", fontWeight: 500 }}>
                                {getQuestionCount(form.difficulty.hard)} Hard
                            </span>
                        )}
                        {form.difficulty.veryhard > 0 && (
                            <span style={{ padding: "var(--space-1) var(--space-3)", background: "#ede9fe", color: "#5b21b6", borderRadius: "var(--radius-full)", fontSize: "13px", fontWeight: 500 }}>
                                {getQuestionCount(form.difficulty.veryhard)} V.Hard
                            </span>
                        )}
                    </div>
                </div>

                {/* Question Types Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>📋</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Question Types</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", paddingLeft: "var(--space-6)" }}>
                        {Object.entries(form.questionTypes)
                            .filter(([, value]) => value > 0)
                            .map(([key, value]) => (
                                <span
                                    key={key}
                                    style={{
                                        padding: "var(--space-1) var(--space-3)",
                                        background: "var(--primary-100)",
                                        color: "var(--primary-700)",
                                        borderRadius: "var(--radius-full)",
                                        fontSize: "13px",
                                        fontWeight: 500,
                                    }}
                                >
                                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} ({value}%)
                                </span>
                            ))}
                    </div>
                </div>

                {/* Cognitive Levels Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>🧠</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Cognitive Levels</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", paddingLeft: "var(--space-6)" }}>
                        {Object.entries(form.cognitive)
                            .filter(([, value]) => value > 0)
                            .map(([key, value]) => (
                                <span
                                    key={key}
                                    style={{
                                        padding: "var(--space-1) var(--space-3)",
                                        background: "#E0E7FF",
                                        color: "#3730A3",
                                        borderRadius: "var(--radius-full)",
                                        fontSize: "13px",
                                        fontWeight: 500,
                                    }}
                                >
                                    {key.charAt(0).toUpperCase() + key.slice(1)} ({value}%)
                                </span>
                            ))}
                    </div>
                </div>

                {/* Quality Level Section */}
                <div style={{ padding: "var(--space-5)", borderBottom: "1px solid var(--gray-100)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                        <span>🎯</span>
                        <span style={{ fontWeight: 600, color: "var(--gray-700)" }}>Quality Level</span>
                    </div>
                    <div style={{ fontSize: "14px", color: "var(--gray-600)", paddingLeft: "var(--space-6)" }}>
                        <div style={{ marginBottom: "var(--space-1)" }}>
                            Writer: <strong style={{ color: "var(--gray-800)" }}>{
                                MODEL_DISPLAY_NAMES[form.generationModel ?? ''] || form.generationModel || 'Standard (Recommended)'
                            }</strong>
                        </div>
                        <div>
                            Checker: <strong style={{ color: "var(--gray-800)" }}>{
                                MODEL_DISPLAY_NAMES[form.qcModel ?? ''] || form.qcModel || 'Advanced'
                            }</strong>
                        </div>
                    </div>
                </div>

                {/* Estimates */}
                <div style={{ padding: "var(--space-5)", background: "var(--gray-50)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-4)" }}>
                        <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                                <span>💰</span>
                                <span style={{ fontSize: "13px", color: "var(--gray-500)" }}>Estimated Cost</span>
                            </div>
                            <span style={{ fontSize: "18px", fontWeight: 700, color: "var(--gray-800)" }}>
                                ~${estimatedCost.toFixed(2)}
                            </span>
                        </div>
                        <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                                <span>⏱️</span>
                                <span style={{ fontSize: "13px", color: "var(--gray-500)" }}>Estimated Time</span>
                            </div>
                            <span style={{ fontSize: "18px", fontWeight: 700, color: "var(--gray-800)" }}>
                                ~{estimatedTime} min
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Info Note */}
            <div
                style={{
                    marginTop: "var(--space-4)",
                    padding: "var(--space-3) var(--space-4)",
                    background: "var(--primary-50)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--primary-200)",
                    fontSize: "13px",
                    color: "var(--primary-700)",
                }}
            >
                💡 You can review and edit each question after generation before publishing.
            </div>
        </div>
    );
}
