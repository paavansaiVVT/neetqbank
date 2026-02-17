import { test, expect } from '@playwright/test';

test('smoke test: user can navigate and start generation wizard', async ({ page }) => {
  // 1. Land on Dashboard
  await page.goto('/');
  await expect(page).toHaveTitle(/QBank/i);

  // Check for Dashboard elements
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

  // 2. Navigate to Generation Wizard
  // Link text is "New Batch", href is "/create"
  // We use first() because it might appear in sidebar and main content
  await page.getByRole('link', { name: 'New Batch' }).first().click();

  // 3. Verify Wizard loads
  await expect(page).toHaveURL(/.*create/);
  await expect(page.getByRole('heading', { name: 'New Question Batch' })).toBeVisible();

  // 4. Verify Wizard steps are present
  // "Content" is the label for step 1
  await expect(page.getByText('Content', { exact: true })).toBeVisible();

  // Check for Continue button
  await expect(page.getByRole('button', { name: /continue/i })).toBeVisible();

  // 5. Check Review Queue access
  await page.goto('/queue');
  await expect(page.getByRole('heading', { name: /review queue/i })).toBeVisible();
});
