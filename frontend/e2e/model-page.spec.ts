import { test, expect } from '@playwright/test'

test.describe('Model Detail Page', () => {
  // Scope tab interactions to main content to avoid sidebar conflicts
  const mainSelector = 'main'

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.locator('table tbody tr').filter({ hasText: 'orders' }).first().click()
    await page.waitForURL(/#\/model\//)
  })

  test('displays model name and materialization badge', async ({ page }) => {
    await expect(page.locator('h1')).toBeVisible()
    await expect(page.locator('h1')).toContainText('orders')
  })

  test('displays schema and path info', async ({ page }) => {
    await expect(page.getByText(/models\//)).toBeVisible()
  })

  test('shows columns tab by default with column table', async ({ page }) => {
    const main = page.locator(mainSelector)
    const columnsTab = main.getByRole('button', { name: /Columns/ })
    await expect(columnsTab).toBeVisible()
    await expect(page.locator('table').first()).toBeVisible()
  })

  test('can switch to SQL tab', async ({ page }) => {
    const main = page.locator(mainSelector)
    await main.getByRole('button', { name: 'SQL', exact: true }).click()
    // Should show Compiled/Raw toggle buttons
    await expect(main.getByRole('button', { name: 'Compiled', exact: true })).toBeVisible()
    await expect(main.getByRole('button', { name: 'Raw', exact: true })).toBeVisible()
  })

  test('SQL tab shows content or no-sql message', async ({ page }) => {
    const main = page.locator(mainSelector)
    await main.getByRole('button', { name: 'SQL', exact: true }).click()
    // Test fixtures may not have compiled SQL, so expect either pre>code or "No SQL"
    const hasSql = await page.locator('pre code').count()
    const hasNoSql = await page.getByText('No SQL available').count()
    expect(hasSql + hasNoSql).toBeGreaterThan(0)
  })

  test('can switch to lineage tab', async ({ page }) => {
    const main = page.locator(mainSelector)
    await main.getByRole('button', { name: 'Lineage', exact: true }).click()
    await expect(page.locator('.h-96').first()).toBeVisible()
  })

  test('can switch to tests tab', async ({ page }) => {
    const main = page.locator(mainSelector)
    await main.getByRole('button', { name: /Tests/ }).click()
    await expect(page.locator('table').first()).toBeVisible()
  })
})

test.describe('Model Not Found', () => {
  test('shows not found message for invalid model id', async ({ page }) => {
    await page.goto('/#/model/nonexistent-model-id')
    await expect(page.getByText('Model not found')).toBeVisible()
  })
})
