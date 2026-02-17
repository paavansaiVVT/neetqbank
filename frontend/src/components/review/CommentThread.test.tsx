import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CommentThread } from './CommentThread';
import { QbankApiClient } from '../../api/client';

// Mock the API client
const mockApiClient = {
    getItemComments: vi.fn(),
    addItemComment: vi.fn(),
} as unknown as QbankApiClient;

const mockComments = {
    comments: [
        {
            id: 'c1',
            user_id: 'u1',
            user_name: 'User 1',
            content: 'First comment',
            created_at: new Date().toISOString(),
            parent_id: null,
        },
        {
            id: 'c2',
            user_id: 'u2',
            user_name: 'User 2',
            content: 'Reply to first',
            created_at: new Date().toISOString(),
            parent_id: 'c1',
        }
    ],
    total: 2
};

describe('CommentThread', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (mockApiClient.getItemComments as any).mockResolvedValue(mockComments);
        (mockApiClient.addItemComment as any).mockResolvedValue({
            id: 'new_c',
            user_id: 'u1',
            user_name: 'User 1',
            content: 'New comment',
            created_at: new Date().toISOString(),
            parent_id: null
        });
    });

    it('renders comments', async () => {
        render(<CommentThread itemId={1} apiClient={mockApiClient} />);

        // Expand thread
        const toggleButton = screen.getByText('Add comment');
        fireEvent.click(toggleButton);

        await waitFor(() => {
            expect(screen.getByText('First comment')).toBeInTheDocument();
            expect(screen.getByText('Reply to first')).toBeInTheDocument();
        });
    });

    it('adds a new comment', async () => {
        render(<CommentThread itemId={1} apiClient={mockApiClient} />);

        // Expand thread
        const toggleButton = screen.getByText('Add comment');
        fireEvent.click(toggleButton);

        // Wait for input to appear
        const input = await screen.findByPlaceholderText('Add a comment...');
        fireEvent.change(input, { target: { value: 'New comment' } });

        const button = screen.getByText('Send');
        fireEvent.click(button);

        await waitFor(() => {
            expect(mockApiClient.addItemComment).toHaveBeenCalledWith(1, 'New comment');
        });
    });

    it('handles reply', async () => {
        render(<CommentThread itemId={1} apiClient={mockApiClient} />);

        // Expand thread
        const toggleButton = screen.getByText('Add comment');
        fireEvent.click(toggleButton);

        await waitFor(() => {
            expect(screen.getByText('First comment')).toBeInTheDocument();
        });

        const replyButtons = screen.getAllByText('Reply');
        fireEvent.click(replyButtons[0]);

        const replyInput = await screen.findByPlaceholderText('Write a reply...');
        fireEvent.change(replyInput, { target: { value: 'My reply' } });

        // Press Enter to submit reply
        fireEvent.keyDown(replyInput, { key: 'Enter', code: 'Enter', charCode: 13 });

        await waitFor(() => {
            expect(mockApiClient.addItemComment).toHaveBeenCalledWith(1, 'My reply', 'c1');
        });
    });
});
