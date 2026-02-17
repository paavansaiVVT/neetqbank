import { useState, useEffect } from 'react';
import { MessageSquare, Send, Trash2, Edit2, MoreVertical, Reply } from 'lucide-react';
import { QbankApiClient } from '../../api/client';
import { Comment as ApiComment } from '../../api/types';

interface Comment {
    id: string;
    userId: string;
    userName: string;
    content: string;
    timestamp: string;
    replies?: Comment[];
}

interface CommentThreadProps {
    itemId: number;
    apiClient?: QbankApiClient;
    onCommentCountChange?: (count: number) => void;
}

const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};

export function CommentThread({ itemId, apiClient, onCommentCountChange }: CommentThreadProps) {
    const [comments, setComments] = useState<Comment[]>([]);
    const [newComment, setNewComment] = useState('');
    const [isExpanded, setIsExpanded] = useState(false);
    const [replyingTo, setReplyingTo] = useState<string | null>(null);
    const [replyText, setReplyText] = useState('');
    const [loading, setLoading] = useState(false);

    const fetchComments = async () => {
        if (!apiClient) return;
        try {
            setLoading(true);
            const response = await apiClient.getItemComments(itemId);

            // Transform flat API comments to threaded structure
            const apiComments = response.comments;
            const commentMap = new Map<string, Comment>();
            const rootComments: Comment[] = [];

            // First pass: create comment objects
            apiComments.forEach(c => {
                const comment: Comment = {
                    id: c.id.toString(),
                    userId: c.user_id,
                    userName: c.user_name || 'User', // Fallback if username missing
                    content: c.content,
                    timestamp: c.created_at,
                    replies: []
                };
                commentMap.set(c.id.toString(), comment);
            });

            // Second pass: build tree
            apiComments.forEach(c => {
                const comment = commentMap.get(c.id.toString())!;
                if (c.parent_id) {
                    const parent = commentMap.get(c.parent_id.toString());
                    if (parent) {
                        parent.replies = parent.replies || [];
                        parent.replies.push(comment);
                    } else {
                        // Parent not found, treat as root
                        rootComments.push(comment);
                    }
                } else {
                    rootComments.push(comment);
                }
            });

            setComments(rootComments);
            onCommentCountChange?.(apiComments.length);
        } catch (err) {
            console.error("Failed to fetch comments:", err);
        } finally {
            setLoading(false);
        }
    };

    // Load comments when expanded or itemId changes
    useEffect(() => {
        if (isExpanded) {
            fetchComments();
        }
    }, [itemId, isExpanded, apiClient]);

    const countTotalComments = (commentList: Comment[]): number => {
        return commentList.reduce((sum, c) => sum + 1 + (c.replies ? countTotalComments(c.replies) : 0), 0);
    };

    const handleAddComment = async () => {
        if (!newComment.trim() || !apiClient) return;

        try {
            await apiClient.addItemComment(itemId, newComment.trim());
            setNewComment('');
            fetchComments(); // Refresh comments
        } catch (err) {
            console.error("Failed to add comment:", err);
            alert("Failed to post comment. Please try again.");
        }
    };

    const handleAddReply = async (parentId: string) => {
        if (!replyText.trim() || !apiClient) return;

        try {
            await apiClient.addItemComment(itemId, replyText.trim(), parentId);
            setReplyText('');
            setReplyingTo(null);
            fetchComments(); // Refresh comments
        } catch (err) {
            console.error("Failed to add reply:", err);
            alert("Failed to post reply. Please try again.");
        }
    };

    const handleDeleteComment = async (commentId: string) => {
        // API doesn't have delete endpoint yet, so just log
        console.warn("Delete comment not implemented in API yet");
        alert("Delete feature coming soon");
    };

    // We can't easily know total count without fetching, unless passed as prop or separate count endpoint.
    // For now, we only show count if comments are loaded or we assume 0 initially.
    // Ideally the parent item has comment_count.
    const totalCount = countTotalComments(comments);

    return (
        <div style={{
            borderTop: '1px solid var(--gray-200)',
            marginTop: 'var(--space-4)',
        }}>
            {/* Toggle Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-3)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    width: '100%',
                    textAlign: 'left',
                    color: 'var(--gray-600)',
                }}
            >
                <MessageSquare size={16} />
                <span style={{ fontSize: '13px' }}>
                    {loading ? 'Loading comments...' : (
                        totalCount === 0 ? 'Add comment' : `${totalCount} comment${totalCount !== 1 ? 's' : ''}`
                    )}
                </span>
                <span style={{
                    marginLeft: 'auto',
                    fontSize: '12px',
                    color: 'var(--gray-400)',
                }}>
                    {isExpanded ? '▲' : '▼'}
                </span>
            </button>

            {isExpanded && (
                <div style={{ padding: '0 var(--space-3) var(--space-3)' }}>
                    {/* Comments List */}
                    {comments.length > 0 ? (
                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            {comments.map(comment => (
                                <div key={comment.id} style={{ marginBottom: 'var(--space-3)' }}>
                                    {/* Main Comment */}
                                    <div style={{
                                        display: 'flex',
                                        gap: 'var(--space-2)',
                                        padding: 'var(--space-2)',
                                        background: 'var(--gray-50)',
                                        borderRadius: 'var(--radius-md)',
                                    }}>
                                        <div style={{
                                            width: '28px',
                                            height: '28px',
                                            borderRadius: '50%',
                                            background: 'var(--primary-100)',
                                            color: 'var(--primary-700)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            fontSize: '11px',
                                            fontWeight: 600,
                                            flexShrink: 0,
                                        }}>
                                            {comment.userName.charAt(0).toUpperCase()}
                                        </div>
                                        <div style={{ flex: 1 }}>
                                            <div style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                marginBottom: '2px',
                                            }}>
                                                <div>
                                                    <span style={{ fontSize: '12px', fontWeight: 600 }}>
                                                        {comment.userName}
                                                    </span>
                                                    <span style={{
                                                        fontSize: '11px',
                                                        color: 'var(--gray-400)',
                                                        marginLeft: '8px',
                                                    }}>
                                                        {formatTime(comment.timestamp)}
                                                    </span>
                                                </div>
                                                {/* Delete button removed as API doesn't support it yet */}
                                            </div>
                                            <div style={{ fontSize: '13px', marginBottom: '4px' }}>
                                                {comment.content}
                                            </div>
                                            <button
                                                onClick={() => setReplyingTo(comment.id)}
                                                style={{
                                                    background: 'none',
                                                    border: 'none',
                                                    cursor: 'pointer',
                                                    fontSize: '11px',
                                                    color: 'var(--primary-600)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '4px',
                                                    padding: 0,
                                                }}
                                            >
                                                <Reply size={10} /> Reply
                                            </button>
                                        </div>
                                    </div>

                                    {/* Replies */}
                                    {comment.replies && comment.replies.length > 0 && (
                                        <div style={{ marginLeft: 'var(--space-5)', marginTop: 'var(--space-2)' }}>
                                            {comment.replies.map(reply => (
                                                <div
                                                    key={reply.id}
                                                    style={{
                                                        display: 'flex',
                                                        gap: 'var(--space-2)',
                                                        padding: 'var(--space-2)',
                                                        background: 'white',
                                                        border: '1px solid var(--gray-100)',
                                                        borderRadius: 'var(--radius-md)',
                                                        marginBottom: 'var(--space-1)',
                                                    }}
                                                >
                                                    <div style={{
                                                        width: '24px',
                                                        height: '24px',
                                                        borderRadius: '50%',
                                                        background: 'var(--gray-100)',
                                                        color: 'var(--gray-600)',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        fontSize: '10px',
                                                        fontWeight: 600,
                                                        flexShrink: 0,
                                                    }}>
                                                        {reply.userName.charAt(0).toUpperCase()}
                                                    </div>
                                                    <div style={{ flex: 1 }}>
                                                        <div style={{ fontSize: '11px' }}>
                                                            <strong>{reply.userName}</strong>
                                                            <span style={{ color: 'var(--gray-400)', marginLeft: '6px' }}>
                                                                {formatTime(reply.timestamp)}
                                                            </span>
                                                        </div>
                                                        <div style={{ fontSize: '12px' }}>{reply.content}</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {/* Reply Input */}
                                    {replyingTo === comment.id && (
                                        <div style={{
                                            marginLeft: 'var(--space-5)',
                                            marginTop: 'var(--space-2)',
                                            display: 'flex',
                                            gap: 'var(--space-2)',
                                        }}>
                                            <input
                                                type="text"
                                                value={replyText}
                                                onChange={(e) => setReplyText(e.target.value)}
                                                placeholder="Write a reply..."
                                                onKeyDown={(e) => e.key === 'Enter' && handleAddReply(comment.id)}
                                                style={{
                                                    flex: 1,
                                                    padding: '6px 10px',
                                                    border: '1px solid var(--gray-200)',
                                                    borderRadius: 'var(--radius-sm)',
                                                    fontSize: '12px',
                                                }}
                                            />
                                            <button
                                                onClick={() => handleAddReply(comment.id)}
                                                className="btn btn-primary"
                                                style={{ padding: '6px 10px', fontSize: '12px' }}
                                                disabled={!replyText.trim()}
                                            >
                                                <Send size={12} />
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        !loading && (
                            <div style={{
                                padding: 'var(--space-2)',
                                textAlign: 'center',
                                color: 'var(--gray-500)',
                                fontSize: '12px',
                                marginBottom: 'var(--space-3)'
                            }}>
                                No comments yet. Be the first to comment!
                            </div>
                        )
                    )}

                    {/* New Comment Input */}
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        <input
                            type="text"
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                            placeholder="Add a comment..."
                            onKeyDown={(e) => e.key === 'Enter' && handleAddComment()}
                            style={{
                                flex: 1,
                                padding: '8px 12px',
                                border: '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '13px',
                            }}
                        />
                        <button
                            onClick={handleAddComment}
                            disabled={!newComment.trim()}
                            className="btn btn-primary"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                opacity: newComment.trim() ? 1 : 0.5,
                            }}
                        >
                            <Send size={14} />
                            Send
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
