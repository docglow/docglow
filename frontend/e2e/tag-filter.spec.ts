import { test, expect } from '@playwright/test'

test.describe('Tag Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('sidebar displays tag chips when tags exist', async ({ page }) => {
    const sidebar = page.locator('aside')
    await expect(sidebar.getByText('Tags')).toBeVisible()
    // Should show tags from the fixture data
    await expect(sidebar.getByRole('button', { name: 'finance' })).toBeVisible()
    await expect(sidebar.getByRole('button', { name: 'staging' })).toBeVisible()
    await expect(sidebar.getByRole('button', { name: 'marketing' })).toBeVisible()
    await expect(sidebar.getByRole('button', { name: 'daily' })).toBeVisible()
  })

  test('clicking a tag chip filters the sidebar model list', async ({ page }) => {
    const sidebar = page.locator('aside')

    // Expand models folder to see all models
    await sidebar.getByRole('button', { name: /^models/ }).click()

    // Count initial models visible (before filter)
    const modelsSection = sidebar.locator('nav')
    const initialButtons = await modelsSection.getByRole('button').allTextContents()
    const initialModelNames = initialButtons.filter(t =>
      !['models', 'sources', 'Expand All', 'Collapse All', 'Lineage', 'Health', 'Layers',
        'finance', 'staging', 'marketing', 'daily', 'Clear'].includes(t.trim()) &&
      !t.match(/^\d+$/) &&
      !t.includes('/')
    )

    // Click 'finance' tag
    await sidebar.getByRole('button', { name: 'finance' }).click()

    // Footer should show filtered count
    await expect(sidebar.getByText(/\d+ of \d+ models/)).toBeVisible()

    // The 'finance' chip should be highlighted (has bg-primary style)
    const financeChip = sidebar.getByRole('button', { name: 'finance' })
    await expect(financeChip).toHaveClass(/bg-primary/)
  })

  test('clicking Clear removes the tag filter', async ({ page }) => {
    const sidebar = page.locator('aside')

    // Activate a tag filter
    await sidebar.getByRole('button', { name: 'finance' }).click()
    await expect(sidebar.getByText(/\d+ of \d+ models/)).toBeVisible()

    // Clear the filter
    await sidebar.getByRole('button', { name: 'Clear' }).click()

    // Footer should show unfiltered count (no "of")
    await expect(sidebar.getByText(/^\d+ models · \d+ sources$/)).toBeVisible()
  })

  test('tag filter persists in URL params', async ({ page }) => {
    const sidebar = page.locator('aside')

    // Click 'staging' tag
    await sidebar.getByRole('button', { name: 'staging' }).click()

    // URL should contain tags param
    await expect(page).toHaveURL(/tags=staging/)
  })

  test('tag filter restores from URL params on load', async ({ page }) => {
    // Navigate directly with tag filter in URL
    await page.goto('/#/?tags=finance')

    const sidebar = page.locator('aside')
    // The finance chip should be active
    const financeChip = sidebar.getByRole('button', { name: 'finance' })
    await expect(financeChip).toHaveClass(/bg-primary/)

    // Footer should show filtered count
    await expect(sidebar.getByText(/\d+ of \d+ models/)).toBeVisible()
  })

  test('overview page shows filtered models heading when tags active', async ({ page }) => {
    const sidebar = page.locator('aside')

    // No filter — shows "Recent Models"
    await expect(page.getByText('Recent Models')).toBeVisible()

    // Click a tag filter
    await sidebar.getByRole('button', { name: 'finance' }).click()

    // Should now show "Filtered Models"
    await expect(page.getByText('Filtered Models')).toBeVisible()
  })

  test('multiple tags can be selected', async ({ page }) => {
    const sidebar = page.locator('aside')

    await sidebar.getByRole('button', { name: 'finance' }).click()
    await sidebar.getByRole('button', { name: 'staging' }).click()

    // Both chips should be active
    await expect(sidebar.getByRole('button', { name: 'finance' })).toHaveClass(/bg-primary/)
    await expect(sidebar.getByRole('button', { name: 'staging' })).toHaveClass(/bg-primary/)

    // URL should contain both tags
    await expect(page).toHaveURL(/tags=/)
  })
})
