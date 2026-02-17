import { useState, useEffect } from 'react';
import { Settings, Key, Palette, Bell, Save, Check, AlertTriangle, Moon, Sun } from 'lucide-react';

interface SettingsState {
    apiKey: string;
    theme: 'light' | 'dark' | 'system';
    notifications: {
        email: boolean;
        browser: boolean;
        sound: boolean;
    };
    defaults: {
        questionCount: number;
        difficulty: string;
    };
}

interface SettingsPageProps {
    apiBaseUrl: string;
    apiKey: string;
}

const DEFAULT_SETTINGS: SettingsState = {
    apiKey: '',
    theme: 'light',
    notifications: {
        email: false,
        browser: true,
        sound: true,
    },
    defaults: {
        questionCount: 25,
        difficulty: 'balanced',
    },
};

const STORAGE_KEY = 'qbank_settings';

export function SettingsPage({ apiBaseUrl, apiKey }: SettingsPageProps) {
    const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
    const [saved, setSaved] = useState(false);
    const [activeTab, setActiveTab] = useState<'general' | 'api' | 'notifications' | 'defaults'>('general');

    // Load settings from localStorage
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setSettings({ ...DEFAULT_SETTINGS, ...parsed, apiKey: apiKey || parsed.apiKey });
            } catch {
                setSettings({ ...DEFAULT_SETTINGS, apiKey });
            }
        } else {
            setSettings({ ...DEFAULT_SETTINGS, apiKey });
        }
    }, [apiKey]);

    const handleSave = () => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    const updateSettings = <K extends keyof SettingsState>(key: K, value: SettingsState[K]) => {
        setSettings(prev => ({ ...prev, [key]: value }));
    };

    const tabs = [
        { id: 'general', label: 'General', icon: Settings },
        { id: 'api', label: 'API', icon: Key },
        { id: 'notifications', label: 'Notifications', icon: Bell },
        { id: 'defaults', label: 'Defaults', icon: Palette },
    ] as const;

    return (
        <div style={{ padding: 'var(--space-6)', maxWidth: '800px', margin: '0 auto' }}>
            {/* Header */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                    <Settings size={28} color="var(--primary-600)" />
                    <h1 style={{ margin: 0 }}>Settings</h1>
                </div>
                <p style={{ color: 'var(--gray-500)', margin: 0 }}>
                    Configure your QBank preferences
                </p>
            </div>

            {/* Tab Navigation */}
            <div style={{
                display: 'flex',
                gap: 'var(--space-1)',
                marginBottom: 'var(--space-4)',
                borderBottom: '1px solid var(--gray-200)',
                paddingBottom: 'var(--space-1)',
            }}>
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                            padding: 'var(--space-2) var(--space-3)',
                            background: activeTab === tab.id ? 'var(--primary-50)' : 'transparent',
                            border: 'none',
                            borderBottom: activeTab === tab.id ? '2px solid var(--primary-500)' : '2px solid transparent',
                            color: activeTab === tab.id ? 'var(--primary-700)' : 'var(--gray-600)',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: activeTab === tab.id ? 500 : 400,
                            marginBottom: '-1px',
                        }}
                    >
                        <tab.icon size={16} />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={{
                background: 'white',
                border: '1px solid var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-5)',
            }}>
                {activeTab === 'general' && (
                    <div>
                        <h3 style={{ margin: '0 0 var(--space-4) 0', fontSize: '16px' }}>Appearance</h3>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-2)' }}>
                                Theme
                            </label>
                            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                {(['light', 'dark', 'system'] as const).map(theme => (
                                    <button
                                        key={theme}
                                        onClick={() => updateSettings('theme', theme)}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 'var(--space-2)',
                                            padding: 'var(--space-2) var(--space-3)',
                                            background: settings.theme === theme ? 'var(--primary-100)' : 'var(--gray-50)',
                                            border: settings.theme === theme ? '2px solid var(--primary-500)' : '1px solid var(--gray-200)',
                                            borderRadius: 'var(--radius-md)',
                                            cursor: 'pointer',
                                            fontSize: '13px',
                                        }}
                                    >
                                        {theme === 'light' && <Sun size={14} />}
                                        {theme === 'dark' && <Moon size={14} />}
                                        {theme === 'system' && <Settings size={14} />}
                                        {theme.charAt(0).toUpperCase() + theme.slice(1)}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'api' && (
                    <div>
                        <h3 style={{ margin: '0 0 var(--space-4) 0', fontSize: '16px' }}>API Configuration</h3>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-2)' }}>
                                API Base URL
                            </label>
                            <input
                                type="text"
                                value={apiBaseUrl}
                                disabled
                                style={{
                                    width: '100%',
                                    padding: 'var(--space-2)',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                    background: 'var(--gray-50)',
                                    color: 'var(--gray-500)',
                                }}
                            />
                            <div style={{ fontSize: '11px', color: 'var(--gray-400)', marginTop: '4px' }}>
                                Set via VITE_API_BASE_URL environment variable
                            </div>
                        </div>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-2)' }}>
                                API Key
                            </label>
                            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                <input
                                    type="password"
                                    value={settings.apiKey}
                                    onChange={(e) => updateSettings('apiKey', e.target.value)}
                                    placeholder="Enter your API key"
                                    style={{
                                        flex: 1,
                                        padding: 'var(--space-2)',
                                        border: '1px solid var(--gray-200)',
                                        borderRadius: 'var(--radius-md)',
                                    }}
                                />
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--gray-400)', marginTop: '4px' }}>
                                Used for authenticating API requests
                            </div>
                        </div>

                        <div style={{
                            background: 'var(--warning-50)',
                            border: '1px solid var(--warning-200)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-3)',
                            display: 'flex',
                            gap: 'var(--space-2)',
                        }}>
                            <AlertTriangle size={16} color="var(--warning-600)" />
                            <div style={{ fontSize: '12px', color: 'var(--warning-700)' }}>
                                API keys are stored locally. Never share your API key with others.
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'notifications' && (
                    <div>
                        <h3 style={{ margin: '0 0 var(--space-4) 0', fontSize: '16px' }}>Notification Preferences</h3>

                        {[
                            { key: 'browser', label: 'Browser Notifications', desc: 'Show desktop notifications when jobs complete' },
                            { key: 'sound', label: 'Sound Alerts', desc: 'Play a sound when generation finishes' },
                            { key: 'email', label: 'Email Updates', desc: 'Receive email summaries (coming soon)' },
                        ].map(({ key, label, desc }) => (
                            <div
                                key={key}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: 'var(--space-3)',
                                    borderBottom: '1px solid var(--gray-100)',
                                }}
                            >
                                <div>
                                    <div style={{ fontSize: '14px', fontWeight: 500 }}>{label}</div>
                                    <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>{desc}</div>
                                </div>
                                <button
                                    onClick={() => updateSettings('notifications', {
                                        ...settings.notifications,
                                        [key]: !settings.notifications[key as keyof typeof settings.notifications],
                                    })}
                                    style={{
                                        width: '44px',
                                        height: '24px',
                                        borderRadius: '12px',
                                        border: 'none',
                                        cursor: key === 'email' ? 'not-allowed' : 'pointer',
                                        background: settings.notifications[key as keyof typeof settings.notifications]
                                            ? 'var(--primary-500)'
                                            : 'var(--gray-300)',
                                        position: 'relative',
                                        opacity: key === 'email' ? 0.5 : 1,
                                    }}
                                    disabled={key === 'email'}
                                >
                                    <div style={{
                                        width: '20px',
                                        height: '20px',
                                        borderRadius: '50%',
                                        background: 'white',
                                        position: 'absolute',
                                        top: '2px',
                                        left: settings.notifications[key as keyof typeof settings.notifications] ? '22px' : '2px',
                                        transition: 'left 0.2s',
                                        boxShadow: 'var(--shadow-sm)',
                                    }} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {activeTab === 'defaults' && (
                    <div>
                        <h3 style={{ margin: '0 0 var(--space-4) 0', fontSize: '16px' }}>Default Generation Settings</h3>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-2)' }}>
                                Default Question Count
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="100"
                                value={settings.defaults.questionCount}
                                onChange={(e) => updateSettings('defaults', {
                                    ...settings.defaults,
                                    questionCount: parseInt(e.target.value) || 25,
                                })}
                                style={{
                                    width: '120px',
                                    padding: 'var(--space-2)',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                }}
                            />
                        </div>

                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{ display: 'block', fontSize: '13px', color: 'var(--gray-600)', marginBottom: 'var(--space-2)' }}>
                                Default Difficulty Mix
                            </label>
                            <select
                                value={settings.defaults.difficulty}
                                onChange={(e) => updateSettings('defaults', {
                                    ...settings.defaults,
                                    difficulty: e.target.value,
                                })}
                                style={{
                                    padding: 'var(--space-2)',
                                    border: '1px solid var(--gray-200)',
                                    borderRadius: 'var(--radius-md)',
                                }}
                            >
                                <option value="easy">Practice (mostly easy)</option>
                                <option value="balanced">Balanced (standard mix)</option>
                                <option value="hard">Competitive (challenging)</option>
                            </select>
                        </div>
                    </div>
                )}
            </div>

            {/* Save Button */}
            <div style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: 'var(--space-4)',
            }}>
                <button
                    onClick={handleSave}
                    className="btn btn-primary"
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                    }}
                >
                    {saved ? <Check size={16} /> : <Save size={16} />}
                    {saved ? 'Saved!' : 'Save Settings'}
                </button>
            </div>
        </div>
    );
}

export default SettingsPage;
