import type { DraftQuestionItem } from "../../api/types";

// Wizard Types

export interface DifficultyDistribution {
    easy: number;
    medium: number;
    hard: number;
    veryhard: number;
}

export interface QuestionTypeDistribution {
    conceptual: number;
    statement: number;
    matching: number;
    assertion_reason: number;
    numerical: number;
}

export interface CognitiveDistribution {
    remembering: number;
    understanding: number;
    applying: number;
    analyzing: number;
    evaluating: number;
    creating: number;
}

export interface FormState {
    subject: string;
    chapter: string;
    topic: string;
    batchName: string;
    totalQuestions: number;
    difficulty: DifficultyDistribution;
    questionTypes: QuestionTypeDistribution;
    cognitive: CognitiveDistribution;
    stream: string;
    questionQuality: string;
    generationModel?: string;
    qcModel?: string;
}

export interface WizardStep {
    id: number;
    label: string;
    icon: string;
}

// Review Types
// Alias to API type to ensure compatibility
export type QuestionItem = DraftQuestionItem;

export interface ReviewState {
    currentIndex: number;
    items: QuestionItem[];
    filter: {
        qc: string;
        review: string;
    };
}
