import type { CognitiveDistribution } from "../types";

interface CognitiveBloomStepProps {
    cognitive: CognitiveDistribution;
    onCognitiveChange: (cognitive: CognitiveDistribution) => void;
}

const COGNITIVE_LEVELS = [
    { key: "remembering", label: "Remembering", desc: "Recall facts and basic concepts", icon: "📌" },
    { key: "understanding", label: "Understanding", desc: "Explain ideas or concepts", icon: "💡" },
    { key: "applying", label: "Applying", desc: "Use information in new situations", icon: "🔧" },
    { key: "analyzing", label: "Analyzing", desc: "Draw connections among ideas", icon: "🔬" },
    { key: "evaluating", label: "Evaluating", desc: "Justify a stand or decision", icon: "⚖️" },
    { key: "creating", label: "Creating", desc: "Produce new or original work", icon: "🎨" },
] as const;

const PRESETS = {
    neet: {
        remembering: 10,
        understanding: 25,
        applying: 35,
        analyzing: 20,
        evaluating: 10,
        creating: 0,
    },
    conceptual: {
        remembering: 5,
        understanding: 40,
        applying: 30,
        analyzing: 20,
        evaluating: 5,
        creating: 0,
    },
    higher_order: {
        remembering: 0,
        understanding: 10,
        applying: 25,
        analyzing: 30,
        evaluating: 25,
        creating: 10,
    },
};

export function CognitiveBloomStep({ cognitive, onCognitiveChange }: CognitiveBloomStepProps) {
    const toggleLevel = (key: keyof CognitiveDistribution) => {
        const newCognitive = { ...cognitive };
        if (newCognitive[key] > 0) {
            const value = newCognitive[key];
            newCognitive[key] = 0;
            const activeKeys = COGNITIVE_LEVELS.filter(
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
            const maxKey = COGNITIVE_LEVELS.reduce((max, l) =>
                cognitive[l.key] > cognitive[max.key] ? l : max
            ).key;
            if (cognitive[maxKey] >= 10) {
                newCognitive[maxKey] -= 10;
                newCognitive[key] = 10;
            }
        }
        onCognitiveChange(newCognitive);
    };

    const adjustLevel = (key: keyof CognitiveDistribution, delta: number) => {
        if (cognitive[key] + delta < 0 || cognitive[key] + delta > 100) return;
        const newCognitive = { ...cognitive };
        newCognitive[key] += delta;
        const otherKeys = COGNITIVE_LEVELS.filter(
            (l) => l.key !== key && cognitive[l.key] > 0
        ).map((l) => l.key);
        if (otherKeys.length > 0) {
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
                <h2 className="wizard-title">🧠 What cognitive skills should questions test?</h2>
                <p className="wizard-subtitle">
                    Set the distribution based on Bloom's Taxonomy
                </p>
            </div>

            {/* Preset Buttons */}
            <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-6)" }}>
                <button type="button" onClick={() => applyPreset("neet")} className="btn btn-secondary" style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}>
                    NEET Pattern
                </button>
                <button type="button" onClick={() => applyPreset("conceptual")} className="btn btn-secondary" style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}>
                    Conceptual
                </button>
                <button type="button" onClick={() => applyPreset("higher_order")} className="btn btn-secondary" style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}>
                    Higher Order
                </button>
            </div>

            {/* Cognitive Level Cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {COGNITIVE_LEVELS.map(({ key, label, desc, icon }) => {
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
                            <input
                                type="checkbox"
                                checked={isActive}
                                onChange={() => toggleLevel(key)}
                                style={{ width: "20px", height: "20px", cursor: "pointer" }}
                            />
                            <div style={{ flex: 1 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                    <span style={{ fontSize: "18px" }}>{icon}</span>
                                    <span style={{ fontWeight: 600, color: "var(--gray-800)" }}>{label}</span>
                                </div>
                                <div style={{ fontSize: "13px", color: "var(--gray-500)", marginTop: "2px" }}>
                                    {desc}
                                </div>
                            </div>
                            {isActive && (
                                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                    <button type="button" onClick={() => adjustLevel(key, -5)} style={{ width: "28px", height: "28px", borderRadius: "var(--radius-full)", border: "1px solid var(--gray-300)", background: "white", cursor: "pointer", fontSize: "16px" }}>−</button>
                                    <span style={{ width: "50px", textAlign: "center", fontWeight: 700, fontSize: "16px", color: "var(--primary-600)" }}>{cognitive[key]}%</span>
                                    <button type="button" onClick={() => adjustLevel(key, 5)} style={{ width: "28px", height: "28px", borderRadius: "var(--radius-full)", border: "1px solid var(--gray-300)", background: "white", cursor: "pointer", fontSize: "16px" }}>+</button>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            <div style={{ marginTop: "var(--space-6)", padding: "var(--space-3)", background: "var(--gray-50)", borderRadius: "var(--radius-md)", textAlign: "center", fontSize: "14px", color: "var(--gray-600)" }}>
                Total: {Object.values(cognitive).reduce((a, b) => a + b, 0)}%
                {Object.values(cognitive).reduce((a, b) => a + b, 0) !== 100 && (
                    <span style={{ color: "var(--warning-600)", marginLeft: "var(--space-2)" }}>⚠️ Must equal 100%</span>
                )}
            </div>
        </div>
    );
}
