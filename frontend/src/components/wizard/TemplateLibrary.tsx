import React, { useState, useEffect } from 'react';
import { Save, FolderOpen, Trash2, Plus, X, Star } from 'lucide-react';

export interface GenerationTemplate {
    id: string;
    name: string;
    description?: string;
    createdAt: string;
    isDefault?: boolean;
    config: {
        subject?: string;
        chapter?: string;
        topic?: string;
        questionCount: number;
        difficulty: {
            easy: number;
            medium: number;
            hard: number;
            veryhard: number;
        };
        cognitiveLevel?: string;
        questionTypes?: string[];
    };
}

interface TemplateLibraryProps {
    onSelectTemplate: (template: GenerationTemplate) => void;
    currentConfig?: GenerationTemplate['config'];
}

const STORAGE_KEY = 'qbank_templates';

// Default templates that ship with the app
const DEFAULT_TEMPLATES: GenerationTemplate[] = [
    {
        id: 'default-balanced',
        name: 'Balanced Mix',
        description: 'Standard distribution for general assessments',
        createdAt: '2024-01-01',
        isDefault: true,
        config: {
            questionCount: 20,
            difficulty: { easy: 30, medium: 50, hard: 15, veryhard: 5 },
        },
    },
    {
        id: 'default-practice',
        name: 'Practice Set',
        description: 'Easier questions for student practice',
        createdAt: '2024-01-01',
        isDefault: true,
        config: {
            questionCount: 30,
            difficulty: { easy: 50, medium: 40, hard: 10, veryhard: 0 },
        },
    },
    {
        id: 'default-competitive',
        name: 'Competitive Exam',
        description: 'Challenging mix for exam preparation',
        createdAt: '2024-01-01',
        isDefault: true,
        config: {
            questionCount: 50,
            difficulty: { easy: 10, medium: 40, hard: 35, veryhard: 15 },
        },
    },
];

export function TemplateLibrary({ onSelectTemplate, currentConfig }: TemplateLibraryProps) {
    const [templates, setTemplates] = useState<GenerationTemplate[]>([]);
    const [showSaveModal, setShowSaveModal] = useState(false);
    const [newTemplateName, setNewTemplateName] = useState('');
    const [newTemplateDescription, setNewTemplateDescription] = useState('');

    // Load templates from localStorage
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                const userTemplates = JSON.parse(stored) as GenerationTemplate[];
                setTemplates([...DEFAULT_TEMPLATES, ...userTemplates]);
            } catch {
                setTemplates(DEFAULT_TEMPLATES);
            }
        } else {
            setTemplates(DEFAULT_TEMPLATES);
        }
    }, []);

    // Save user templates to localStorage
    const saveTemplates = (allTemplates: GenerationTemplate[]) => {
        const userTemplates = allTemplates.filter(t => !t.isDefault);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(userTemplates));
        setTemplates(allTemplates);
    };

    const handleSaveTemplate = () => {
        if (!newTemplateName.trim() || !currentConfig) return;

        const newTemplate: GenerationTemplate = {
            id: `user-${Date.now()}`,
            name: newTemplateName.trim(),
            description: newTemplateDescription.trim() || undefined,
            createdAt: new Date().toISOString(),
            isDefault: false,
            config: currentConfig,
        };

        saveTemplates([...templates, newTemplate]);
        setShowSaveModal(false);
        setNewTemplateName('');
        setNewTemplateDescription('');
    };

    const handleDeleteTemplate = (id: string) => {
        const template = templates.find(t => t.id === id);
        if (template?.isDefault) return; // Can't delete default templates

        saveTemplates(templates.filter(t => t.id !== id));
    };

    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 'var(--space-3)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <FolderOpen size={18} color="var(--primary-600)" />
                    <span style={{ fontWeight: 600, fontSize: '14px' }}>Templates</span>
                </div>
                {currentConfig && (
                    <button
                        onClick={() => setShowSaveModal(true)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            fontSize: '12px',
                            background: 'var(--primary-50)',
                            color: 'var(--primary-700)',
                            border: '1px solid var(--primary-200)',
                            borderRadius: 'var(--radius-md)',
                            cursor: 'pointer',
                        }}
                    >
                        <Save size={14} />
                        Save Current
                    </button>
                )}
            </div>

            {/* Template Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: 'var(--space-2)',
            }}>
                {templates.map((template) => (
                    <div
                        key={template.id}
                        onClick={() => onSelectTemplate(template)}
                        style={{
                            padding: 'var(--space-3)',
                            background: 'white',
                            border: '1px solid var(--gray-200)',
                            borderRadius: 'var(--radius-md)',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                            position: 'relative',
                        }}
                        onMouseEnter={(e) => {
                            (e.currentTarget as HTMLElement).style.borderColor = 'var(--primary-300)';
                            (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-sm)';
                        }}
                        onMouseLeave={(e) => {
                            (e.currentTarget as HTMLElement).style.borderColor = 'var(--gray-200)';
                            (e.currentTarget as HTMLElement).style.boxShadow = 'none';
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                            <div>
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    fontWeight: 500,
                                    fontSize: '13px',
                                    marginBottom: '4px',
                                }}>
                                    {template.isDefault && <Star size={12} color="var(--warning-500)" fill="var(--warning-500)" />}
                                    {template.name}
                                </div>
                                {template.description && (
                                    <div style={{
                                        fontSize: '11px',
                                        color: 'var(--gray-500)',
                                        marginBottom: '8px',
                                    }}>
                                        {template.description}
                                    </div>
                                )}
                            </div>
                            {!template.isDefault && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteTemplate(template.id);
                                    }}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '4px',
                                        color: 'var(--gray-400)',
                                    }}
                                >
                                    <Trash2 size={14} />
                                </button>
                            )}
                        </div>
                        <div style={{
                            display: 'flex',
                            gap: '4px',
                            flexWrap: 'wrap',
                        }}>
                            <span style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                background: 'var(--success-100)',
                                color: 'var(--success-700)',
                                borderRadius: 'var(--radius-sm)',
                            }}>
                                E:{template.config.difficulty.easy}%
                            </span>
                            <span style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                background: 'var(--primary-100)',
                                color: 'var(--primary-700)',
                                borderRadius: 'var(--radius-sm)',
                            }}>
                                M:{template.config.difficulty.medium}%
                            </span>
                            <span style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                background: 'var(--warning-100)',
                                color: 'var(--warning-700)',
                                borderRadius: 'var(--radius-sm)',
                            }}>
                                H:{template.config.difficulty.hard}%
                            </span>
                        </div>
                    </div>
                ))}
            </div>

            {/* Save Modal */}
            {showSaveModal && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.5)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1000,
                    }}
                    onClick={() => setShowSaveModal(false)}
                >
                    <div
                        style={{
                            background: 'white',
                            borderRadius: 'var(--radius-xl)',
                            padding: 'var(--space-5)',
                            maxWidth: '400px',
                            width: '90%',
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: 'var(--space-4)',
                        }}>
                            <h3 style={{ margin: 0, fontSize: '16px' }}>Save Template</h3>
                            <button
                                onClick={() => setShowSaveModal(false)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                            >
                                <X size={20} color="var(--gray-500)" />
                            </button>
                        </div>

                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            <label style={{
                                display: 'block',
                                fontSize: '12px',
                                color: 'var(--gray-600)',
                                marginBottom: '4px',
                            }}>
                                Template Name *
                            </label>
                            <input
                                type="text"
                                value={newTemplateName}
                                onChange={(e) => setNewTemplateName(e.target.value)}
                                placeholder="My Custom Template"
                                style={{
                                    width: '100%',
                                    padding: 'var(--space-2)',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                    fontSize: '14px',
                                }}
                            />
                        </div>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{
                                display: 'block',
                                fontSize: '12px',
                                color: 'var(--gray-600)',
                                marginBottom: '4px',
                            }}>
                                Description (optional)
                            </label>
                            <input
                                type="text"
                                value={newTemplateDescription}
                                onChange={(e) => setNewTemplateDescription(e.target.value)}
                                placeholder="Brief description..."
                                style={{
                                    width: '100%',
                                    padding: 'var(--space-2)',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                    fontSize: '14px',
                                }}
                            />
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
                            <button
                                onClick={() => setShowSaveModal(false)}
                                className="btn btn-secondary"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveTemplate}
                                disabled={!newTemplateName.trim()}
                                className="btn btn-primary"
                            >
                                Save Template
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default TemplateLibrary;
