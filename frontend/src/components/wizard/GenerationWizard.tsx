import { useState, useCallback } from "react";
import type { FormState, WizardStep } from "./types";
import { StepIndicator } from "./StepIndicator";
import { ContentStep } from "./steps/ContentStep";
import { DifficultyStep } from "./steps/DifficultyStep";
import { CognitiveStep } from "./steps/CognitiveStep";
import { CognitiveBloomStep } from "./steps/CognitiveBloomStep";
import { ModelStep } from "./steps/ModelStep";
import { ReviewStep } from "./steps/ReviewStep";
import { TemplateLibrary, GenerationTemplate } from "./TemplateLibrary";
import "../../design-system.css";

const STEPS: WizardStep[] = [
    { id: 1, label: "Content", icon: "📚" },
    { id: 2, label: "Difficulty", icon: "🎯" },
    { id: 3, label: "Types", icon: "📋" },
    { id: 4, label: "Cognitive", icon: "🧠" },
    { id: 5, label: "Quality", icon: "🤖" },
    { id: 6, label: "Review", icon: "✅" },
];

const INITIAL_FORM: FormState = {
    subject: "",
    chapter: "",
    topic: "",
    batchName: "",
    totalQuestions: 25,
    difficulty: {
        easy: 30,
        medium: 50,
        hard: 15,
        veryhard: 5,
    },
    questionTypes: {
        conceptual: 40,
        statement: 20,
        matching: 5,
        assertion_reason: 15,
        numerical: 20,
    },
    cognitive: {
        remembering: 10,
        understanding: 25,
        applying: 35,
        analyzing: 20,
        evaluating: 10,
        creating: 0,
    },
    stream: "NEET",
    questionQuality: "Standard",
    generationModel: "gemini-2.5-flash",
    qcModel: "gemini-2.5-flash",
};

interface WizardProps {
    onComplete: (formData: FormState) => void;
    onCancel: () => void;
    subjectOptions: string[];
    chapterOptions: string[];
    topicOptions: string[];
    loadingChapters: boolean;
    loadingTopics: boolean;
    onSubjectChange: (subject: string) => void;
    onChapterChange: (chapter: string) => void;
}

export function GenerationWizard({
    onComplete,
    onCancel,
    subjectOptions,
    chapterOptions,
    topicOptions,
    loadingChapters,
    loadingTopics,
    onSubjectChange,
    onChapterChange,
}: WizardProps) {
    const [currentStep, setCurrentStep] = useState(1);
    const [form, setForm] = useState<FormState>(INITIAL_FORM);

    const updateForm = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
        setForm((prev) => ({ ...prev, [key]: value }));
    }, []);

    // Apply template to form
    const handleApplyTemplate = useCallback((template: GenerationTemplate) => {
        setForm((prev) => ({
            ...prev,
            totalQuestions: template.config.questionCount,
            difficulty: template.config.difficulty,
        }));
    }, []);

    // Get current config for template saving
    const getCurrentConfig = (): GenerationTemplate['config'] => ({
        subject: form.subject,
        chapter: form.chapter,
        topic: form.topic,
        questionCount: form.totalQuestions,
        difficulty: form.difficulty,
    });

    const handleSubjectSelect = useCallback((subject: string) => {
        updateForm("subject", subject);
        updateForm("chapter", "");
        updateForm("topic", "");
        onSubjectChange(subject);
    }, [updateForm, onSubjectChange]);

    const handleChapterSelect = useCallback((chapter: string) => {
        updateForm("chapter", chapter);
        updateForm("topic", "");
        onChapterChange(chapter);
    }, [updateForm, onChapterChange]);

    const handleTopicSelect = useCallback((topic: string) => {
        updateForm("topic", topic);
    }, [updateForm]);

    const handleModelChange = useCallback((generationModel: string, qcModel: string) => {
        setForm(prev => ({ ...prev, generationModel, qcModel }));
    }, []);

    const TOTAL_STEPS = STEPS.length;

    const canProceed = (): boolean => {
        switch (currentStep) {
            case 1:
                return form.subject !== "" && form.chapter !== "";
            case 2:
                return form.totalQuestions >= 1 && form.totalQuestions <= 100;
            default:
                return true;
        }
    };

    const handleNext = () => {
        if (currentStep < TOTAL_STEPS) {
            setCurrentStep((prev) => prev + 1);
        } else {
            onComplete(form);
        }
    };

    const handleBack = () => {
        if (currentStep > 1) {
            setCurrentStep((prev) => prev - 1);
        } else {
            onCancel();
        }
    };

    const renderStep = () => {
        switch (currentStep) {
            case 1:
                return (
                    <ContentStep
                        form={form}
                        subjectOptions={subjectOptions}
                        chapterOptions={chapterOptions}
                        topicOptions={topicOptions}
                        loadingChapters={loadingChapters}
                        loadingTopics={loadingTopics}
                        onSubjectSelect={handleSubjectSelect}
                        onChapterSelect={handleChapterSelect}
                        onTopicSelect={handleTopicSelect}
                        onBatchNameChange={(name) => updateForm("batchName", name)}
                    />
                );
            case 2:
                return (
                    <>
                        <TemplateLibrary
                            onSelectTemplate={handleApplyTemplate}
                            currentConfig={getCurrentConfig()}
                        />
                        <DifficultyStep
                            totalQuestions={form.totalQuestions}
                            difficulty={form.difficulty}
                            onTotalChange={(value) => updateForm("totalQuestions", value)}
                            onDifficultyChange={(difficulty) => updateForm("difficulty", difficulty)}
                        />
                    </>
                );
            case 3:
                return (
                    <CognitiveStep
                        cognitive={form.questionTypes}
                        onCognitiveChange={(qt) => updateForm("questionTypes", qt)}
                    />
                );
            case 4:
                return (
                    <CognitiveBloomStep
                        cognitive={form.cognitive}
                        onCognitiveChange={(cog) => updateForm("cognitive", cog)}
                    />
                );
            case 5:
                return (
                    <ModelStep
                        form={form}
                        onModelChange={handleModelChange}
                    />
                );
            case 6:
                return <ReviewStep form={form} />;
            default:
                return null;
        }
    };

    return (
        <div className="wizard-container">
            <div className="wizard-card animate-fadeIn">
                <StepIndicator steps={STEPS} currentStep={currentStep} />

                {renderStep()}

                <div className="wizard-nav">
                    <button type="button" className="btn btn-secondary" onClick={handleBack}>
                        ← {currentStep === 1 ? "Cancel" : "Back"}
                    </button>
                    <button
                        type="button"
                        className="btn btn-primary"
                        onClick={handleNext}
                        disabled={!canProceed()}
                    >
                        {currentStep === TOTAL_STEPS ? "🚀 Start Generation" : "Continue →"}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default GenerationWizard;
