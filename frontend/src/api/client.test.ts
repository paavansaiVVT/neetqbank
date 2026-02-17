import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QbankApiClient } from './client';

describe('QbankApiClient', () => {
    let client: QbankApiClient;
    const baseUrl = 'http://api.test';
    const apiKey = 'test-key';

    beforeEach(() => {
        client = new QbankApiClient(baseUrl, apiKey);
        global.fetch = vi.fn();
    });

    it('instantiates correctly', () => {
        expect(client).toBeInstanceOf(QbankApiClient);
    });

    it('fetches activity feed', async () => {
        const mockResponse = { items: [], total: 0 };
        (global.fetch as any).mockResolvedValue({
            ok: true,
            json: async () => mockResponse,
        });

        const result = await client.getActivityFeed(10);

        expect(global.fetch).toHaveBeenCalledWith(
            `${baseUrl}/v2/qbank/activity?limit=10`,
            expect.objectContaining({
                headers: expect.objectContaining({
                    'X-Internal-API-Key': apiKey,
                }),
            })
        );
        expect(result).toEqual(mockResponse);
    });

    it('fetches token usage', async () => {
        const mockResponse = { daily_usage: [], total_cost: 0 };
        (global.fetch as any).mockResolvedValue({
            ok: true,
            json: async () => mockResponse,
        });

        const result = await client.getTokenUsage(7);

        expect(global.fetch).toHaveBeenCalledWith(
            `${baseUrl}/v2/qbank/usage?days=7`,
            expect.anything()
        );
        expect(result).toEqual(mockResponse);
    });

    it('fetches review queue with priority', async () => {
        const mockResponse = { items: [], total: 0 };
        (global.fetch as any).mockResolvedValue({
            ok: true,
            json: async () => mockResponse,
        });

        await client.getReviewQueue('urgent');

        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('priority=urgent'),
            expect.anything()
        );
    });

    it('adds a comment', async () => {
        const mockResponse = { id: 'cmt_1', content: 'test' };
        (global.fetch as any).mockResolvedValue({
            ok: true,
            json: async () => mockResponse,
        });

        await client.addItemComment(1, 'test', 'parent_1');

        expect(global.fetch).toHaveBeenCalledWith(
            `${baseUrl}/v2/qbank/items/1/comments`,
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ content: 'test', parent_id: 'parent_1' }),
            })
        );
    });

    it('handles API errors', async () => {
        (global.fetch as any).mockResolvedValue({
            ok: false,
            status: 404,
            clone: () => ({
                json: async () => ({ detail: 'Not found' }),
            }),
        });

        await expect(client.getJob('job-1')).rejects.toThrow('Request failed: 404 - Not found');
    });
});
