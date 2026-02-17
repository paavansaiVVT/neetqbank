import { useState, useMemo } from "react";
import type { QuestionItem } from "../wizard/types";
import { ReviewCard } from "./ReviewCard";
import { MathRenderer } from "../shared/MathRenderer";
import { CheckSquare, Square, CheckCircle, XCircle, List, LayoutGrid, CheckCheck } from "lucide-react";
import { RejectionModal } from "./RejectionModal";

import { QbankApiClient } from "../../api/client";

interface ReviewModeProps {
    items: QuestionItem[];
    subject: string;
    chapter: string;
    onUpdateItem: (itemId: number, updates: Partial<QuestionItem>) => Promise<void>;
    onBulkUpdate?: (itemIds: number[], patch: { review_status: string }) => Promise<void>;
    onExit: () => void;
    onComplete: () => void;
    apiClient?: QbankApiClient;
}

export function ReviewMode({
    items,
    subject,
    chapter,
    onUpdateItem,
    onBulkUpdate,
    onExit,
    onComplete,
    apiClient,
}: ReviewModeProps) {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [editingItem, setEditingItem] = useState<QuestionItem | null>(null);
    const [filter, setFilter] = useState<{ qc: string; review: string }>({
        qc: "",
        review: "pending",
    });
    const [viewMode, setViewMode] = useState<"card" | "list">("card");
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [bulkLoading, setBulkLoading] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState<{ itemId: number; question: string } | null>(null);
    const [approveAllLoading, setApproveAllLoading] = useState(false);
    const [showApproveAllConfirm, setShowApproveAllConfirm] = useState(false);

    // Filter items based on current filter
    const filteredItems = useMemo(() => {
        return items.filter((item) => {
            if (filter.qc && item.qc_status !== filter.qc) return false;
            if (filter.review && item.review_status !== filter.review) return false;
            return true;
        });
    }, [items, filter]);

    const currentItem = filteredItems[currentIndex];

    // Stats
    const stats = useMemo(() => {
        const pending = items.filter((i) => i.review_status === "pending").length;
        const approved = items.filter((i) => i.review_status === "approved").length;
        const rejected = items.filter((i) => i.review_status === "rejected").length;
        return { pending, approved, rejected, total: items.length };
    }, [items]);

    // Bulk selection helpers
    const toggleSelect = (itemId: number) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(itemId)) {
                next.delete(itemId);
            } else {
                next.add(itemId);
            }
            return next;
        });
    };

    const selectAll = () => {
        setSelectedIds(new Set(filteredItems.map((i) => i.item_id)));
    };

    const deselectAll = () => {
        setSelectedIds(new Set());
    };

    const handleBulkApprove = async () => {
        if (!onBulkUpdate || selectedIds.size === 0) return;
        setBulkLoading(true);
        try {
            await onBulkUpdate(Array.from(selectedIds), { review_status: "approved" });
            setSelectedIds(new Set());
        } finally {
            setBulkLoading(false);
        }
    };

    const handleApproveAll = async () => {
        if (!onBulkUpdate) return;
        const pendingIds = items
            .filter((i) => i.review_status === "pending")
            .map((i) => i.item_id);
        if (pendingIds.length === 0) return;
        setApproveAllLoading(true);
        try {
            await onBulkUpdate(pendingIds, { review_status: "approved" });
            setShowApproveAllConfirm(false);
        } finally {
            setApproveAllLoading(false);
        }
    };

    const handleBulkReject = async () => {
        if (!onBulkUpdate || selectedIds.size === 0) return;
        setBulkLoading(true);
        try {
            await onBulkUpdate(Array.from(selectedIds), { review_status: "rejected" });
            setSelectedIds(new Set());
        } finally {
            setBulkLoading(false);
        }
    };

    const handleApprove = async (itemId: number) => {
        await onUpdateItem(itemId, { review_status: "approved" });
        if (currentIndex < filteredItems.length - 1) {
            setCurrentIndex((prev) => prev + 1);
        } else if (stats.pending === 1) {
            onComplete();
        }
    };

    const handleReject = (itemId: number) => {
        const item = items.find(i => i.item_id === itemId);
        if (item) {
            setRejectionTarget({ itemId, question: item.question });
        }
    };

    const handleConfirmReject = async (itemId: number, reasons: string[], comment: string) => {
        await onUpdateItem(itemId, {
            review_status: "rejected",
            rejection_reasons: reasons,
            rejection_comment: comment,
        } as any);
        setRejectionTarget(null);
        if (currentIndex < filteredItems.length - 1) {
            setCurrentIndex((prev) => prev + 1);
        }
    };

    const handleEdit = (item: QuestionItem) => {
        setEditingItem(item);
    };

    const handleNext = () => {
        if (currentIndex < filteredItems.length - 1) {
            setCurrentIndex((prev) => prev + 1);
        }
    };

    const handlePrevious = () => {
        if (currentIndex > 0) {
            setCurrentIndex((prev) => prev - 1);
        }
    };

    // Handle inline field updates from ReviewCard
    const handleUpdateField = async (itemId: number, field: string, value: string) => {
        // Options are passed as a JSON-stringified array from the option editor
        if (field === 'options') {
            try {
                const parsed = JSON.parse(value);
                await onUpdateItem(itemId, { options: parsed } as Partial<QuestionItem>);
            } catch {
                // Fallback: shouldn't happen, but pass as-is
                await onUpdateItem(itemId, { [field]: value } as unknown as Partial<QuestionItem>);
            }
        } else {
            await onUpdateItem(itemId, { [field]: value } as Partial<QuestionItem>);
        }
    };

    // Show completion state if no items to review
    if (filteredItems.length === 0) {
        return (
            <div className="review-container">
                <div
                    className="wizard-card"
                    style={{ textAlign: "center", padding: "var(--space-12)" }}
                >
                    <div style={{ fontSize: "48px", marginBottom: "var(--space-4)" }}>
                        🎉
                    </div>
                    <h2 style={{ marginBottom: "var(--space-4)" }}>
                        All questions reviewed!
                    </h2>
                    <div style={{ marginBottom: "var(--space-6)", color: "var(--gray-500)" }}>
                        <div>✅ {stats.approved} approved</div>
                        <div>❌ {stats.rejected} rejected</div>
                    </div>
                    <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center" }}>
                        <button
                            className="btn btn-secondary"
                            onClick={() => setFilter({ qc: "", review: "" })}
                        >
                            View All
                        </button>
                        <button className="btn btn-primary" onClick={onComplete}>
                            Continue to Publish →
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <>
            {/* Stats Bar */}
            <div
                style={{
                    background: "white",
                    borderBottom: "1px solid var(--gray-200)",
                    padding: "var(--space-3) var(--space-6)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                }}
            >
                <div style={{ display: "flex", gap: "var(--space-6)", alignItems: "center" }}>
                    <div>
                        <span style={{ color: "var(--gray-500)", fontSize: "13px" }}>Pending: </span>
                        <span style={{ fontWeight: 600, color: "var(--warning-600)" }}>{stats.pending}</span>
                    </div>
                    <div>
                        <span style={{ color: "var(--gray-500)", fontSize: "13px" }}>Approved: </span>
                        <span style={{ fontWeight: 600, color: "var(--success-600)" }}>{stats.approved}</span>
                    </div>
                    <div>
                        <span style={{ color: "var(--gray-500)", fontSize: "13px" }}>Rejected: </span>
                        <span style={{ fontWeight: 600, color: "var(--danger-600)" }}>{stats.rejected}</span>
                    </div>
                </div>

                {/* Approve All Pending Button */}
                {onBulkUpdate && stats.pending > 0 && (
                    <button
                        onClick={() => setShowApproveAllConfirm(true)}
                        className="btn"
                        style={{
                            padding: "var(--space-2) var(--space-4)",
                            fontSize: "13px",
                            fontWeight: 600,
                            background: "linear-gradient(135deg, var(--success-500), var(--success-600))",
                            color: "white",
                            border: "none",
                            borderRadius: "var(--radius-md)",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
                            transition: "transform 0.15s, box-shadow 0.15s",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.transform = "translateY(-1px)";
                            e.currentTarget.style.boxShadow = "0 3px 8px rgba(0,0,0,0.18)";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "translateY(0)";
                            e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.12)";
                        }}
                    >
                        <CheckCheck size={16} />
                        Approve All ({stats.pending})
                    </button>
                )}

                <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                    {/* View Mode Toggle */}
                    <div style={{ display: "flex", border: "1px solid var(--gray-200)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
                        <button
                            onClick={() => setViewMode("card")}
                            style={{
                                padding: "var(--space-2)",
                                background: viewMode === "card" ? "var(--primary-50)" : "white",
                                border: "none",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                            }}
                            title="Card View"
                        >
                            <LayoutGrid size={16} color={viewMode === "card" ? "var(--primary-600)" : "var(--gray-400)"} />
                        </button>
                        <button
                            onClick={() => setViewMode("list")}
                            style={{
                                padding: "var(--space-2)",
                                background: viewMode === "list" ? "var(--primary-50)" : "white",
                                border: "none",
                                borderLeft: "1px solid var(--gray-200)",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                            }}
                            title="List View (Bulk Actions)"
                        >
                            <List size={16} color={viewMode === "list" ? "var(--primary-600)" : "var(--gray-400)"} />
                        </button>
                    </div>

                    <select
                        value={filter.review}
                        onChange={(e) => {
                            setFilter((prev) => ({ ...prev, review: e.target.value }));
                            setCurrentIndex(0);
                            setSelectedIds(new Set());
                        }}
                        style={{
                            padding: "var(--space-2) var(--space-3)",
                            borderRadius: "var(--radius-md)",
                            border: "1px solid var(--gray-200)",
                            fontSize: "13px",
                        }}
                    >
                        <option value="">All status</option>
                        <option value="pending">Pending only</option>
                        <option value="approved">Approved only</option>
                        <option value="rejected">Rejected only</option>
                    </select>
                    <select
                        value={filter.qc}
                        onChange={(e) => {
                            setFilter((prev) => ({ ...prev, qc: e.target.value }));
                            setCurrentIndex(0);
                            setSelectedIds(new Set());
                        }}
                        style={{
                            padding: "var(--space-2) var(--space-3)",
                            borderRadius: "var(--radius-md)",
                            border: "1px solid var(--gray-200)",
                            fontSize: "13px",
                        }}
                    >
                        <option value="">All QC</option>
                        <option value="pass">QC Pass</option>
                        <option value="fail">QC Fail</option>
                    </select>
                </div>
            </div>

            {/* Bulk Action Toolbar - Only in List View */}
            {viewMode === "list" && onBulkUpdate && (
                <div
                    style={{
                        background: selectedIds.size > 0 ? "var(--primary-50)" : "var(--gray-50)",
                        borderBottom: "1px solid var(--gray-200)",
                        padding: "var(--space-2) var(--space-6)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "background 0.2s",
                    }}
                >
                    <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
                        <button
                            onClick={selectedIds.size === filteredItems.length ? deselectAll : selectAll}
                            className="btn btn-secondary"
                            style={{ padding: "var(--space-1) var(--space-2)", fontSize: "12px" }}
                        >
                            {selectedIds.size === filteredItems.length ? "Deselect All" : "Select All"}
                        </button>
                        <span style={{ color: "var(--gray-600)", fontSize: "13px" }}>
                            {selectedIds.size} of {filteredItems.length} selected
                        </span>
                    </div>

                    {selectedIds.size > 0 && (
                        <div style={{ display: "flex", gap: "var(--space-2)" }}>
                            <button
                                onClick={handleBulkApprove}
                                disabled={bulkLoading}
                                className="btn"
                                style={{
                                    padding: "var(--space-1) var(--space-3)",
                                    fontSize: "12px",
                                    background: "var(--success-500)",
                                    color: "white",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                }}
                            >
                                <CheckCircle size={14} /> Approve {selectedIds.size}
                            </button>
                            <button
                                onClick={handleBulkReject}
                                disabled={bulkLoading}
                                className="btn"
                                style={{
                                    padding: "var(--space-1) var(--space-3)",
                                    fontSize: "12px",
                                    background: "var(--danger-500)",
                                    color: "white",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                }}
                            >
                                <XCircle size={14} /> Reject {selectedIds.size}
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Card View */}
            {viewMode === "card" && currentItem && (
                <ReviewCard
                    item={currentItem}
                    currentIndex={currentIndex}
                    totalCount={filteredItems.length}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    onEdit={handleEdit}
                    onUpdateField={handleUpdateField}
                    onNext={handleNext}
                    onPrevious={handlePrevious}
                    onExit={onExit}
                    subject={subject}
                    chapter={chapter}
                    apiClient={apiClient}
                />
            )}

            {/* List View with Checkboxes */}
            {viewMode === "list" && (
                <div style={{ padding: "var(--space-4)", maxHeight: "calc(100vh - 200px)", overflow: "auto" }}>
                    {filteredItems.map((item, idx) => (
                        <div
                            key={item.item_id}
                            style={{
                                background: selectedIds.has(item.item_id) ? "var(--primary-50)" : "white",
                                border: "1px solid var(--gray-200)",
                                borderRadius: "var(--radius-lg)",
                                padding: "var(--space-3)",
                                marginBottom: "var(--space-2)",
                                display: "flex",
                                gap: "var(--space-3)",
                                alignItems: "flex-start",
                                transition: "background 0.15s",
                            }}
                        >
                            {/* Checkbox */}
                            <button
                                onClick={() => toggleSelect(item.item_id)}
                                style={{
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    padding: "var(--space-1)",
                                    marginTop: "2px",
                                }}
                            >
                                {selectedIds.has(item.item_id) ? (
                                    <CheckSquare size={20} color="var(--primary-600)" />
                                ) : (
                                    <Square size={20} color="var(--gray-400)" />
                                )}
                            </button>

                            {/* Question Content */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontWeight: 500, marginBottom: "var(--space-1)" }}>
                                    <MathRenderer content={item.question} />
                                </div>
                                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", fontSize: "12px" }}>
                                    <span style={{
                                        padding: "2px 6px",
                                        borderRadius: "var(--radius-sm)",
                                        background: item.qc_status === "pass" ? "var(--success-100)" : "var(--danger-100)",
                                        color: item.qc_status === "pass" ? "var(--success-700)" : "var(--danger-700)",
                                    }}>
                                        QC: {item.qc_status}
                                    </span>
                                    <span style={{
                                        padding: "2px 6px",
                                        borderRadius: "var(--radius-sm)",
                                        background: "var(--gray-100)",
                                        color: "var(--gray-600)",
                                    }}>
                                        {item.cognitive_level}
                                    </span>
                                </div>
                            </div>

                            {/* Status Badge */}
                            <div style={{
                                padding: "4px 8px",
                                borderRadius: "var(--radius-md)",
                                fontSize: "12px",
                                fontWeight: 500,
                                background: item.review_status === "approved" ? "var(--success-100)" :
                                    item.review_status === "rejected" ? "var(--danger-100)" : "var(--warning-100)",
                                color: item.review_status === "approved" ? "var(--success-700)" :
                                    item.review_status === "rejected" ? "var(--danger-700)" : "var(--warning-700)",
                            }}>
                                {item.review_status}
                            </div>

                            {/* Quick Actions */}
                            <div style={{ display: "flex", gap: "var(--space-1)" }}>
                                <button
                                    onClick={() => handleApprove(item.item_id)}
                                    style={{
                                        padding: "var(--space-1)",
                                        background: "none",
                                        border: "none",
                                        cursor: "pointer",
                                        opacity: item.review_status === "approved" ? 0.3 : 1,
                                    }}
                                    title="Approve"
                                    disabled={item.review_status === "approved"}
                                >
                                    <CheckCircle size={18} color="var(--success-500)" />
                                </button>
                                <button
                                    onClick={() => handleReject(item.item_id)}
                                    style={{
                                        padding: "var(--space-1)",
                                        background: "none",
                                        border: "none",
                                        cursor: "pointer",
                                        opacity: item.review_status === "rejected" ? 0.3 : 1,
                                    }}
                                    title="Reject"
                                    disabled={item.review_status === "rejected"}
                                >
                                    <XCircle size={18} color="var(--danger-500)" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Edit Modal */}
            {editingItem && (
                <div
                    style={{
                        position: "fixed",
                        inset: 0,
                        background: "rgba(0,0,0,0.5)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        zIndex: 100,
                    }}
                    onClick={() => setEditingItem(null)}
                >
                    <div
                        style={{
                            background: "white",
                            borderRadius: "var(--radius-xl)",
                            padding: "var(--space-6)",
                            maxWidth: "600px",
                            width: "90%",
                            maxHeight: "80vh",
                            overflow: "auto",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 style={{ marginBottom: "var(--space-4)" }}>✏️ Edit Question</h3>
                        <p style={{ color: "var(--gray-500)", marginBottom: "var(--space-4)" }}>
                            Full editor coming soon. For now, close and use the table view.
                        </p>
                        <button
                            className="btn btn-primary"
                            onClick={() => setEditingItem(null)}
                        >
                            Close
                        </button>
                    </div>
                </div>
            )}
            {/* Rejection Modal */}
            <RejectionModal
                isOpen={rejectionTarget !== null}
                itemId={rejectionTarget?.itemId || 0}
                questionPreview={rejectionTarget?.question || ""}
                onConfirm={handleConfirmReject}
                onCancel={() => setRejectionTarget(null)}
            />

            {/* Approve All Confirmation Dialog */}
            {showApproveAllConfirm && (
                <div
                    style={{
                        position: "fixed",
                        inset: 0,
                        background: "rgba(0,0,0,0.4)",
                        backdropFilter: "blur(4px)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        zIndex: 200,
                    }}
                    onClick={() => !approveAllLoading && setShowApproveAllConfirm(false)}
                >
                    <div
                        style={{
                            background: "white",
                            borderRadius: "var(--radius-xl)",
                            padding: "var(--space-8)",
                            maxWidth: "440px",
                            width: "90%",
                            textAlign: "center",
                            boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div style={{ fontSize: "48px", marginBottom: "var(--space-3)" }}>✅</div>
                        <h3 style={{ marginBottom: "var(--space-2)", fontSize: "20px" }}>
                            Approve All Pending Questions?
                        </h3>
                        <p style={{
                            color: "var(--gray-500)",
                            marginBottom: "var(--space-6)",
                            fontSize: "14px",
                            lineHeight: 1.5,
                        }}>
                            This will approve <strong style={{ color: "var(--gray-800)" }}>{stats.pending} pending question{stats.pending !== 1 ? "s" : ""}</strong> at
                            once. You can still change individual reviews afterwards.
                        </p>
                        <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center" }}>
                            <button
                                className="btn btn-secondary"
                                onClick={() => setShowApproveAllConfirm(false)}
                                disabled={approveAllLoading}
                                style={{ padding: "var(--space-2) var(--space-5)" }}
                            >
                                Cancel
                            </button>
                            <button
                                className="btn"
                                onClick={handleApproveAll}
                                disabled={approveAllLoading}
                                style={{
                                    padding: "var(--space-2) var(--space-5)",
                                    background: "linear-gradient(135deg, var(--success-500), var(--success-600))",
                                    color: "white",
                                    border: "none",
                                    borderRadius: "var(--radius-md)",
                                    fontWeight: 600,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "6px",
                                    cursor: approveAllLoading ? "wait" : "pointer",
                                    opacity: approveAllLoading ? 0.7 : 1,
                                }}
                            >
                                <CheckCheck size={16} />
                                {approveAllLoading ? "Approving..." : `Yes, Approve All ${stats.pending}`}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default ReviewMode;
