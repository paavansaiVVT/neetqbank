import type { DifficultyDistribution } from "../types";

interface DifficultyStepProps {
    totalQuestions: number;
    difficulty: DifficultyDistribution;
    onTotalChange: (value: number) => void;
    onDifficultyChange: (difficulty: DifficultyDistribution) => void;
}

const DIFFICULTY_LEVELS = [
    { key: "easy", label: "Easy", color: "easy" },
    { key: "medium", label: "Medium", color: "medium" },
    { key: "hard", label: "Hard", color: "hard" },
    { key: "veryhard", label: "Very Hard", color: "veryhard" },
] as const;

const PRESETS = {
    balanced: { easy: 25, medium: 50, hard: 20, veryhard: 5 },
    neet: { easy: 30, medium: 45, hard: 20, veryhard: 5 },
    challenging: { easy: 10, medium: 30, hard: 40, veryhard: 20 },
};

export function DifficultyStep({
    totalQuestions,
    difficulty,
    onTotalChange,
    onDifficultyChange,
}: DifficultyStepProps) {
    const handleDifficultyChange = (key: keyof DifficultyDistribution, value: number) => {
        // Ensure values stay between 0-100 and sum to 100
        const oldValue = difficulty[key];
        const diff = value - oldValue;

        // Simple approach: adjust others proportionally
        const others = DIFFICULTY_LEVELS.filter((d) => d.key !== key);
        const otherSum = others.reduce((sum, d) => sum + difficulty[d.key], 0);

        if (otherSum === 0) {
            // Can't adjust if all others are 0
            return;
        }

        const newDifficulty = { ...difficulty, [key]: Math.max(0, Math.min(100, value)) };

        // Distribute the difference among other levels proportionally
        let remaining = -diff;
        others.forEach((d, i) => {
            if (i === others.length - 1) {
                // Last one gets the remainder to ensure sum is 100
                const currentSum = Object.values(newDifficulty).reduce((a, b) => a + b, 0);
                newDifficulty[d.key] = Math.max(0, 100 - (currentSum - newDifficulty[d.key]));
            } else {
                const proportion = difficulty[d.key] / otherSum;
                const adjustment = Math.round(remaining * proportion);
                newDifficulty[d.key] = Math.max(0, difficulty[d.key] + adjustment);
            }
        });

        // Final normalization to ensure sum is exactly 100
        const sum = Object.values(newDifficulty).reduce((a, b) => a + b, 0);
        if (sum !== 100) {
            // Find the largest value and adjust it
            const maxKey = DIFFICULTY_LEVELS.reduce((max, d) =>
                newDifficulty[d.key] > newDifficulty[max.key] ? d : max
            ).key;
            newDifficulty[maxKey] += 100 - sum;
        }

        onDifficultyChange(newDifficulty);
    };

    const applyPreset = (preset: keyof typeof PRESETS) => {
        onDifficultyChange(PRESETS[preset]);
    };

    const getQuestionCount = (percent: number) => Math.round((totalQuestions * percent) / 100);

    return (
        <div className="animate-fadeIn">
            <div className="wizard-header">
                <h2 className="wizard-title">🎯 How many questions and what difficulty?</h2>
                <p className="wizard-subtitle">
                    Configure the total count and difficulty distribution
                </p>
            </div>

            {/* Quantity Slider */}
            <div className="quantity-section">
                <div className="quantity-header">
                    <span className="quantity-label">Total Questions</span>
                    <span className="quantity-value">{totalQuestions}</span>
                </div>
                <input
                    type="range"
                    min="5"
                    max="100"
                    step="5"
                    value={totalQuestions}
                    onChange={(e) => onTotalChange(Number(e.target.value))}
                    className="quantity-slider"
                    style={{
                        background: `linear-gradient(to right, var(--primary-500) 0%, var(--primary-500) ${(totalQuestions / 100) * 100}%, var(--gray-200) ${(totalQuestions / 100) * 100}%, var(--gray-200) 100%)`,
                    }}
                />
                <p className="quantity-hint">
                    💡 Recommended: 25–50 for optimal quality. Maximum 100 per batch.
                </p>
            </div>

            {/* Preset Buttons */}
            <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-6)" }}>
                <button
                    type="button"
                    onClick={() => applyPreset("balanced")}
                    className="btn btn-secondary"
                    style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}
                >
                    Balanced
                </button>
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
                    onClick={() => applyPreset("challenging")}
                    className="btn btn-secondary"
                    style={{ fontSize: "13px", padding: "var(--space-2) var(--space-3)" }}
                >
                    Challenging
                </button>
            </div>

            {/* Difficulty Distribution */}
            <div className="difficulty-section">
                <label className="quantity-label" style={{ display: "block", marginBottom: "var(--space-4)" }}>
                    Difficulty Distribution
                </label>

                {DIFFICULTY_LEVELS.map(({ key, label, color }) => (
                    <div key={key} className="difficulty-row">
                        <span className="difficulty-label">{label}</span>
                        <div className="difficulty-bar-container">
                            <div
                                className={`difficulty-bar ${color}`}
                                style={{ width: `${difficulty[key]}%` }}
                            />
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={difficulty[key]}
                            onChange={(e) => handleDifficultyChange(key, Number(e.target.value))}
                            style={{
                                width: "80px",
                                height: "4px",
                                opacity: 0,
                                position: "absolute",
                            }}
                        />
                        <span className="difficulty-percent">{difficulty[key]}%</span>
                        <span className="difficulty-count">{getQuestionCount(difficulty[key])} Q</span>
                    </div>
                ))}
            </div>

            {/* Summary */}
            <div
                style={{
                    padding: "var(--space-4)",
                    background: "var(--gray-50)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--gray-200)",
                }}
            >
                <div style={{ fontSize: "14px", color: "var(--gray-600)" }}>
                    <strong>Summary:</strong> {totalQuestions} questions total —{" "}
                    {DIFFICULTY_LEVELS.map(({ key, label }) => (
                        <span key={key}>
                            {getQuestionCount(difficulty[key])} {label.toLowerCase()}
                            {key !== "veryhard" && ", "}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}
