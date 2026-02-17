import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReviewCard } from './ReviewCard';
import { QuestionItem } from '../wizard/types';

// Mock dependencies
vi.mock('./CommentThread', () => ({
    CommentThread: ({ itemId }: { itemId: number }) => (
        <div data-testid="comment-thread">Comment Thread for {itemId}</div>
    ),
}));

vi.mock('../shared/MathRenderer', () => ({
    MathRenderer: ({ content }: { content: string }) => <span>{content}</span>,
}));

vi.mock('./InlineEditor', () => ({
    InlineEditor: ({ value, onSave }: { value: string; onSave: (v: string) => void }) => (
        <input
            data-testid="inline-editor"
            defaultValue={value}
            onBlur={(e) => onSave(e.target.value)}
        />
    ),
}));

vi.mock('./AISuggestions', () => ({
    AISuggestions: () => null,
    analyzeQuestion: () => [],
}));

const mockItem: QuestionItem = {
    item_id: 1,
    question: 'What is the capital of France?',
    options: ['Berlin', 'Paris', 'London', 'Madrid'],
    correct_answer: 'Paris',
    explanation: 'Paris is the capital and largest city of France.',
    difficulty: 'Medium',
    cognitive_level: 'Remembering',
    estimated_time: 1,
    qc_status: 'pass',
    review_status: 'pending',
};

describe('ReviewCard', () => {
    const mockOnApprove = vi.fn();
    const mockOnReject = vi.fn();
    const mockOnEdit = vi.fn();
    const mockOnNext = vi.fn();
    const mockOnPrevious = vi.fn();
    const mockOnExit = vi.fn();
    const mockOnUpdateField = vi.fn().mockResolvedValue(undefined);

    const defaultProps = {
        item: mockItem,
        currentIndex: 0,
        totalCount: 5,
        onApprove: mockOnApprove,
        onReject: mockOnReject,
        onEdit: mockOnEdit,
        onNext: mockOnNext,
        onPrevious: mockOnPrevious,
        onExit: mockOnExit,
        subject: 'Geography',
        chapter: 'European Capitals',
    };

    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('renders question and options', () => {
        render(<ReviewCard {...defaultProps} />);

        expect(screen.getByText('What is the capital of France?')).toBeInTheDocument();
        expect(screen.getByText('Berlin')).toBeInTheDocument();
        expect(screen.getByText('Paris')).toBeInTheDocument();
        expect(screen.getByText('London')).toBeInTheDocument();
        expect(screen.getByText('Madrid')).toBeInTheDocument();
    });

    it('renders explanation', () => {
        render(<ReviewCard {...defaultProps} />);

        expect(screen.getByText('Paris is the capital and largest city of France.')).toBeInTheDocument();
    });

    it('shows current progress', () => {
        render(<ReviewCard {...defaultProps} />);

        expect(screen.getByText('1 of 5')).toBeInTheDocument();
    });

    it('calls onApprove when Approve button is clicked', () => {
        render(<ReviewCard {...defaultProps} />);

        const approveButton = screen.getByText('Approve').closest('button');
        fireEvent.click(approveButton!);

        expect(mockOnApprove).toHaveBeenCalledWith(1);
    });

    it('calls onReject when Reject button is clicked', () => {
        render(<ReviewCard {...defaultProps} />);

        const rejectButton = screen.getByText('Reject').closest('button');
        fireEvent.click(rejectButton!);

        expect(mockOnReject).toHaveBeenCalledWith(1);
    });

    it('calls onNext when Next button is clicked', () => {
        render(<ReviewCard {...defaultProps} />);

        const nextButtons = screen.getAllByText(/Next/);
        const nextButton = nextButtons.find(el => el.closest('button.nav-btn'));
        fireEvent.click(nextButton!);

        expect(mockOnNext).toHaveBeenCalled();
    });

    it('calls onPrevious when Previous button is clicked', () => {
        render(<ReviewCard {...defaultProps} currentIndex={1} />);

        const prevButtons = screen.getAllByText(/Previous/);
        const prevButton = prevButtons.find(el => el.closest('button.nav-btn'));
        fireEvent.click(prevButton!);

        expect(mockOnPrevious).toHaveBeenCalled();
    });

    it('calls onExit when exit button is clicked', () => {
        render(<ReviewCard {...defaultProps} />);

        const exitButton = screen.getByText('← Exit Review');
        fireEvent.click(exitButton);

        expect(mockOnExit).toHaveBeenCalled();
    });

    // Keyboard Shortcuts Tests
    describe('Keyboard Shortcuts', () => {
        it('pressing "a" triggers approve', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'a' });

            expect(mockOnApprove).toHaveBeenCalledWith(1);
        });

        it('pressing "r" triggers reject', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'r' });

            expect(mockOnReject).toHaveBeenCalledWith(1);
        });

        it('pressing "k" triggers next', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'k' });

            expect(mockOnNext).toHaveBeenCalled();
        });

        it('pressing "j" triggers previous', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'j' });

            expect(mockOnPrevious).toHaveBeenCalled();
        });

        it('pressing "Escape" triggers exit', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'Escape' });

            expect(mockOnExit).toHaveBeenCalled();
        });

        it('pressing "e" with onUpdateField toggles edit mode', () => {
            render(<ReviewCard {...defaultProps} onUpdateField={mockOnUpdateField} />);

            // Initially no edit mode indicators
            expect(screen.queryByTestId('inline-editor')).not.toBeInTheDocument();

            fireEvent.keyDown(window, { key: 'e' });

            // Edit mode should show inline editors
            expect(screen.getAllByTestId('inline-editor').length).toBeGreaterThan(0);
        });

        it('pressing "e" without onUpdateField calls onEdit', () => {
            render(<ReviewCard {...defaultProps} />);

            fireEvent.keyDown(window, { key: 'e' });

            expect(mockOnEdit).toHaveBeenCalledWith(mockItem);
        });
    });

    // Metadata Display Tests
    describe('Metadata Display', () => {
        it('shows difficulty level', () => {
            render(<ReviewCard {...defaultProps} />);

            expect(screen.getByText(/Medium/)).toBeInTheDocument();
        });

        it('shows cognitive level', () => {
            render(<ReviewCard {...defaultProps} />);

            expect(screen.getByText(/Remembering/)).toBeInTheDocument();
        });

        it('shows QC status', () => {
            render(<ReviewCard {...defaultProps} />);

            expect(screen.getByText(/QC pass/)).toBeInTheDocument();
        });
    });

    // Navigation State Tests
    describe('Navigation State', () => {
        it('disables Previous button on first item', () => {
            render(<ReviewCard {...defaultProps} currentIndex={0} />);

            const prevButtons = screen.getAllByText(/Previous/);
            const prevButton = prevButtons.find(el => el.closest('button.nav-btn'))?.closest('button');
            expect(prevButton).toHaveAttribute('disabled');
        });

        it('disables Next button on last item', () => {
            render(<ReviewCard {...defaultProps} currentIndex={4} totalCount={5} />);

            const nextButtons = screen.getAllByText(/Next/);
            const nextButton = nextButtons.find(el => el.closest('button.nav-btn'))?.closest('button');
            expect(nextButton).toHaveAttribute('disabled');
        });
    });
});
