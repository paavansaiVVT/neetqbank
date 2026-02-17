import type { QuestionTypeDistribution } from "../types";

interface CognitiveStepProps {
    cognitive: QuestionTypeDistribution;
    onCognitiveChange: (cognitive: QuestionTypeDistribution) => void;
}

const QUESTION_TYPES = [
    { key: "conceptual", label: "Conceptual", desc: "Direct concept-based MCQs", icon: "💡" },
    { key: "statement", label: "Statement", desc: "Statement-based reasoning", icon: "📝" },
    { key: "matching", label: "Matching", desc: "Match-the-following format", icon: "🔗" },
    { key: "assertion_reason", label: "Assertion–Reason", desc: "Assertion and reason pairs", icon: "⚖️" },
    { key: "numerical", label: "Numericals", desc: "Numerical problem solving", icon: "🔢" },
] as const;

const PRESETS = {
    neet: {
        conceptual: 40,
        statement: 20,
        matching: 5,
        assertion_reason: 15,
        numerical: 20,
    },
    balanced: {
        conceptual: 20,
        statement: 20,
        matching: 15,
        assertion_reason: 20,
        numerical: 25,
    },
    conceptual_heavy: {
        conceptual: 55,
        statement: 20,
        matching: 5,
        assertion_reason: 10,
        numerical: 10,
    },
};

export function CognitiveStep({ cognitive, onCognitiveChange }: CognitiveStepProps) {
    const toggleLevel = (key: keyof QuestionTypeDistribution) => {
        const newCognitive = { ...cognitive };
        if (newCognitive[key] > 0) {
            // Turning off - redistribute to others
            const value = newCognitive[key];
            newCognitive[key] = 0;

            const activeKeys = QUESTION_TYPES.filter(
                (l) => l.key !== key && cognitive[l.key] > 0
            ).map((l) => l.key);

            if (activeKeys.length > 0) {
                const share = Math.floor(value / activeKeys.length);
                activeKeys.forEach((k, i) => {
                    newCognitive[k] += i === activeKeys.length - 1
                        ? value - share * (activeKeys.length - 1)
                        : share;
                });
            }
        } else {
            // Turning on - take 10% from largest
            const maxKey = QUESTION_TYPES.reduce((max, l) =>
                cognitive[l.key] > cognitive[max.key] ? l : max
            ).key;
            if (cognitive[maxKey] >= 10) {
                newCognitive[maxKey] -= 10;
                newCognitive[key] = 10;
            }
        }
        onCognitiveChange(newCognitive);
    };

    const adjustLevel = (key: keyof QuestionTypeDistribution, delta: number) => {
        if (cognitive[key] + delta < 0 || cognitive[key] + delta > 100) return;

        const newCognitive = { ...cognitive };
        newCognitive[key] += delta;

        // Find another level to balance
        const otherKeys = QUESTION_TYPES.filter(
            (l) => l.key !== key && cognitive[l.key] > 0
        ).map((l) => l.key);

        if (otherKeys.length > 0) {
            // Take/give from the largest other
            const maxKey = otherKeys.reduce((max, k) =>
                cognitive[k] > cognitive[max] ? k : max
            );
            if (newCognitive[maxKey] - delta >= 0) {
                newCognitive[maxKey] -= delta;
                onCognitiveChange(newCognitive);
            }
        }
    };

    const applyPreset = (preset: keyof typeof PRESETS) => {
        onCognitiveChange(PRESETS[preset]);
    };

    return (
        <div className="animate-fadeIn">
            <div className="wizard-header">
                <h2 className="wizard-title">📋 What question types do you need?</h2>
                <p className="wizard-subtitle">
                    Set the distribution of question formats
                </p>
            </div>

            {/* Preset Buttons */}
            <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-6)" }}>
                <button
                    type="button"
                    onClick={() => applyPreset("neet")}
                    className="btn btn-secondary"
                    style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}
                >
                    NEET Pattern
                </button>
                <button
                    type="button"
                    onClick={() => applyPreset("balanced")}
                    className="btn btn-secondary"
                    style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}
                >
                    Balanced Mix
                </button>
                <button
                    type="button"
                    onClick={() => applyPreset("conceptual_heavy")}
                    className="btn btn-secondary"
                    style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}
                >
                    Conceptual Heavy
                </button>
            </div>

            {/* Question Type Cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {QUESTION_TYPES.map(({ key, label, desc, icon }) => {
                    const isActive = cognitive[key] > 0;
                    return (
                        <div
                            key={key}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "var(--space-4)",
                                padding: "var(--space-4)",
                                borderRadius: "var(--radius-md)",
                                border: `2px solid ${isActive ? "var(--primary-300)" : "var(--gray-200)"}`,
                                background: isActive ? "var(--primary-50)" : "white",
                                transition: "all var(--transition-fast)",
                            }}
                        >
                            {/* Checkbox */}
                            <input
                                type="checkbox"
                                checked={isActive}
                                onChange={() => toggleLevel(key)}
                                style={{ width: "20px", height: "20px", cursor: "pointer" }}
                            />

                            {/* Icon & Label */}
                            <div style={{ flex: 1 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                    <span style={{ fontSize: "18px" }}>{icon}</span>
                                    <span style={{ fontWeight: 600, color: "var(--gray-800)" }}>{label}</span>
                                </div>
                                <div style={{ fontSize: "13px", color: "var(--gray-500)", marginTop: "2px" }}>
                                    {desc}
                                </div>
                            </div>

                            {/* Percentage Control */}
                            {isActive && (
                                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                    <button
                                        type="button"
                                        onClick={() => adjustLevel(key, -5)}
                                        style={{
                                            width: "28px",
                                            height: "28px",
                                            borderRadius: "var(--radius-full)",
                                            border: "1px solid var(--gray-300)",
                                            background: "white",
                                            cursor: "pointer",
                                            fontSize: "16px",
                                        }}
                                    >
                                        −
                                    </button>
                                    <span
                                        style={{
                                            width: "50px",
                                            textAlign: "center",
                                            fontWeight: 700,
                                            fontSize: "16px",
                                            color: "var(--primary-600)",
                                        }}
                                    >
                                        {cognitive[key]}%
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => adjustLevel(key, 5)}
                                        style={{
                                            width: "28px",
                                            height: "28px",
                                            borderRadius: "var(--radius-full)",
                                            border: "1px solid var(--gray-300)",
                                            background: "white",
                                            cursor: "pointer",
                                            fontSize: "16px",
                                        }}
                                    >
                                        +
                                    </button>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Total Check */}
            <div
                style={{
                    marginTop: "var(--space-6)",
                    padding: "var(--space-3)",
                    background: "var(--gray-50)",
                    borderRadius: "var(--radius-md)",
                    textAlign: "center",
                    fontSize: "14px",
                    color: "var(--gray-600)",
                }}
            >
                Total: {Object.values(cognitive).reduce((a, b) => a + b, 0)}%
                {Object.values(cognitive).reduce((a, b) => a + b, 0) !== 100 && (
                    <span style={{ color: "var(--warning-600)", marginLeft: "var(--space-2)" }}>
                        ⚠️ Must equal 100%
                    </span>
                )}
            </div>
        </div>
    );
}
