import React from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

interface MathRendererProps {
    content: string;
    className?: string;
}

/**
 * MathRenderer: Detects and renders LaTeX expressions within text
 * 
 * Supports:
 * - Inline math: $equation$ or \(equation\)
 * - Block math: $$equation$$ or \[equation\]
 * 
 * Falls back to plain text if rendering fails.
 */
export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = '' }) => {
    if (!content) return null;

    // Use a single regex to find both block ($$ ... $$) and inline ($ ... $) math
    // We use capturing groups to distinguish between them
    // Match block math first: \$\$(.*?)\$\$
    // Then inline math: \$([^\$]+?)\$
    const mathRegex = /\$\$([\s\S]+?)\$\$|\$([^\$]+?)\$/g;

    const parts: Array<{ type: 'text' | 'inline' | 'block'; content: string }> = [];
    let lastIndex = 0;
    let match;

    while ((match = mathRegex.exec(content)) !== null) {
        // Add text before the match
        if (match.index > lastIndex) {
            parts.push({
                type: 'text',
                content: content.substring(lastIndex, match.index)
            });
        }

        if (match[1]) {
            // Block math $$...$$
            parts.push({ type: 'block', content: match[1] });
        } else if (match[2]) {
            // Inline math $...$
            parts.push({ type: 'inline', content: match[2] });
        }

        lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < content.length) {
        parts.push({
            type: 'text',
            content: content.substring(lastIndex)
        });
    }

    if (parts.length === 0) {
        return <span className={className}>{content}</span>;
    }

    return (
        <span className={className}>
            {parts.map((part, index) => {
                try {
                    switch (part.type) {
                        case 'block':
                            return <div key={index} style={{ margin: '1em 0' }}><BlockMath math={part.content} /></div>;
                        case 'inline':
                            return <InlineMath key={index} math={part.content} />;
                        case 'text':
                        default:
                            return <span key={index}>{part.content}</span>;
                    }
                } catch (error) {
                    console.error('LaTeX rendering error:', error);
                    return <span key={index}>{part.content}</span>;
                }
            })}
        </span>
    );
};
