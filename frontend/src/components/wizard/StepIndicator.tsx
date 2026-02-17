import type { WizardStep } from "./types";

interface StepIndicatorProps {
    steps: WizardStep[];
    currentStep: number;
}

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
    return (
        <div className="step-indicator">
            {steps.map((step, index) => (
                <div key={step.id} className="step-item">
                    <div
                        className={`step-circle ${step.id < currentStep
                                ? "completed"
                                : step.id === currentStep
                                    ? "active"
                                    : "pending"
                            }`}
                    >
                        {step.id < currentStep ? "✓" : step.id}
                    </div>
                    <span
                        className={`step-label ${step.id === currentStep ? "active" : ""}`}
                    >
                        {step.label}
                    </span>
                    {index < steps.length - 1 && (
                        <div
                            className={`step-connector ${step.id < currentStep ? "completed" : ""
                                }`}
                        />
                    )}
                </div>
            ))}
        </div>
    );
}
