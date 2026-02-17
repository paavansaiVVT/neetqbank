-- Migration: Add cost tracking columns to qbank_generation_jobs
-- Date: 2026-02-09
-- Description: Adds input_cost, output_cost, total_cost columns for
--              per-model cost tracking based on actual Gemini API pricing.

ALTER TABLE qbank_generation_jobs
    ADD COLUMN input_cost FLOAT NOT NULL DEFAULT 0.0 AFTER total_tokens,
    ADD COLUMN output_cost FLOAT NOT NULL DEFAULT 0.0 AFTER input_cost,
    ADD COLUMN total_cost FLOAT NOT NULL DEFAULT 0.0 AFTER output_cost;
