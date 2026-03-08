import { test, expect } from '@playwright/test'

test.describe('Health Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/health')
  })

  test('displays health grade and score', async ({ page }) => {
    await expect(page.locator('h1')).toHaveText('Project Health')
    // Score like "64/100"
    await expect(page.getByText(/\/100/)).toBeVisible()
  })

  test('shows score bars for all categories', async ({ page }) => {
    // Use the ScoreBar labels which are inside span.w-36 elements
    const scoreLabels = page.locator('span.text-sm.w-36')
    await expect(scoreLabels).toHaveCount(6)
  })

  test('overview tab shows stat cards', async ({ page }) => {
    await expect(page.getByText('Models Documented')).toBeVisible()
    await expect(page.getByText('Models Tested')).toBeVisible()
  })

  test('can switch to documentation tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Documentation' }).click()
    await expect(page.getByText('Coverage by Folder')).toBeVisible()
  })

  test('can switch to testing tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Testing' }).click()
    await expect(page.getByText('Models with tests')).toBeVisible()
  })

  test('can switch to complexity tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Complexity' }).click()
    const hasTable = await page.locator('table').count()
    const hasEmpty = await page.getByText('No high-complexity').count()
    expect(hasTable + hasEmpty).toBeGreaterThan(0)
  })

  test('can switch to naming tab', async ({ page }) => {
    await page.getByRole('button', { name: 'Naming' }).click()
    const hasTable = await page.locator('table').count()
    const hasEmpty = await page.getByText('All models follow naming conventions').count()
    expect(hasTable + hasEmpty).toBeGreaterThan(0)
  })

  test('can switch to orphans tab', async ({ page }) => {
    await page.getByRole('button', { name: /Orphans/ }).click()
    const hasTable = await page.locator('table').count()
    const hasEmpty = await page.getByText('No orphan models found').count()
    expect(hasTable + hasEmpty).toBeGreaterThan(0)
  })
})
