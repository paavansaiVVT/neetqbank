import React from 'react';
import { Cpu, Zap, Activity, ShieldCheck } from 'lucide-react';
import type { FormState } from '../types';

interface ModelStepProps {
    form: FormState;
    onModelChange: (genModel: string, qcModel: string) => void;
}

const MODELS = [
    {
        id: 'gemini-2.0-flash',
        label: 'Quick Draft',
        desc: 'Fastest option. Great for bulk-generating straightforward recall questions.',
        icon: Zap,
        color: '#64748b'
    },
    {
        id: 'gemini-2.5-flash',
        label: 'Standard (Recommended)',
        desc: 'Best balance of speed and quality. Ideal for everyday question creation.',
        icon: Activity,
        color: '#0ea5e9'
    },
    {
        id: 'gemini-2.5-pro',
        label: 'Advanced',
        desc: 'Deep reasoning. Excellent for complex, multi-step analytical questions.',
        icon: Cpu,
        color: '#8b5cf6'
    },
    {
        id: 'gemini-3-flash-preview',
        label: 'Next-Gen Fast ✨',
        desc: 'Near-Advanced quality with faster turnaround. Great all-rounder.',
        icon: Zap,
        color: '#f59e0b'
    },
    {
        id: 'gemini-3-pro-preview',
        label: 'Premium ✨',
        desc: 'Highest precision. Best for challenging, application-level questions.',
        icon: ShieldCheck,
        color: '#ef4444'
    }
];

/** Map model IDs to their display labels for use across the app. */
export const MODEL_DISPLAY_NAMES: Record<string, string> = {};
for (const m of MODELS) {
    MODEL_DISPLAY_NAMES[m.id] = m.label;
}

export const ModelStep: React.FC<ModelStepProps> = ({ form, onModelChange }) => {
    const currentGenModel = form.generationModel || 'gemini-2.5-flash';
    const currentQcModel = form.qcModel || 'gemini-2.5-pro';

    return (
        <div className="animate-fadeIn">
            <div className="wizard-header">
                <h2 className="wizard-title">🎯 Choose Generation Quality</h2>
                <p className="wizard-subtitle">
                    Select the quality level for question generation and checking
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-6)' }}>
                {/* Generation Model */}
                <section>
                    <label style={{
                        display: 'block',
                        fontSize: '14px',
                        fontWeight: 600,
                        color: 'var(--gray-700)',
                        marginBottom: 'var(--space-3)'
                    }}>
                        Question Writer
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-3)' }}>
                        {MODELS.map((model) => (
                            <div
                                key={model.id}
                                onClick={() => onModelChange(model.id, currentQcModel)}
                                style={{
                                    padding: 'var(--space-4)',
                                    background: currentGenModel === model.id ? 'var(--primary-50)' : 'white',
                                    border: `2px solid ${currentGenModel === model.id ? 'var(--primary-500)' : 'var(--gray-200)'}`,
                                    borderRadius: 'var(--radius-lg)',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s',
                                    position: 'relative'
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                                    <model.icon size={20} color={currentGenModel === model.id ? 'var(--primary-600)' : 'var(--gray-400)'} />
                                    <span style={{ fontWeight: 600, fontSize: '15px' }}>{model.label}</span>
                                </div>
                                <p style={{ fontSize: '12px', color: 'var(--gray-500)', margin: 0 }}>
                                    {model.desc}
                                </p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* QC Model Selection */}
                <section>
                    <label style={{
                        display: 'block',
                        fontSize: '14px',
                        fontWeight: 600,
                        color: 'var(--gray-700)',
                        marginBottom: 'var(--space-3)'
                    }}>
                        Quality Checker
                    </label>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        padding: 'var(--space-3)',
                        background: 'var(--gray-50)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--gray-200)'
                    }}>
                        <span style={{ fontSize: '13px', color: 'var(--gray-500)' }}>Checker:</span>
                        <select
                            value={currentQcModel}
                            onChange={(e) => onModelChange(currentGenModel, e.target.value)}
                            style={{
                                flex: 1,
                                padding: 'var(--space-1) var(--space-2)',
                                border: '1px solid var(--gray-300)',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '14px',
                                background: 'white'
                            }}
                        >
                            {MODELS.map(m => (
                                <option key={m.id} value={m.id}>{m.label}</option>
                            ))}
                        </select>
                    </div>
                    <p style={{ fontSize: '11px', color: 'var(--gray-400)', marginTop: 'var(--space-2)' }}>
                        💡 Using Advanced or Premium for quality checking provides the most rigorous validation.
                    </p>
                </section>
            </div>
        </div>
    );
};
