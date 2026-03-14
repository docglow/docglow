import { test, expect } from '@playwright/test'

test.describe('Keyboard Navigation & Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('search can be opened via search button', async ({ page }) => {
    await page.getByRole('button', { name: /Search/ }).click()
    const searchInput = page.getByPlaceholder('Search models, columns, sources...')
    await expect(searchInput).toBeVisible()
  })

  test('sidebar navigation buttons are present', async ({ page }) => {
    const sidebar = page.getByRole('complementary')
    // Sidebar has folder buttons for models and sources
    const modelButton = sidebar.getByRole('button', { name: /models/ })
    const sourceButton = sidebar.getByRole('button', { name: /sources/ })
    await expect(modelButton).toBeVisible()
    await expect(sourceButton).toBeVisible()
  })

  test('tab navigation works on model page tabs', async ({ page }) => {
    // Navigate to a model page via the overview table
    await page.locator('table tbody tr').filter({ hasText: 'orders' }).first().click()
    await page.waitForURL(/#\/model\//)

    const main = page.locator('main')
    // Tabs are rendered as buttons with text content
    const columnsTab = main.getByRole('button', { name: /Columns/ })
    const sqlTab = main.getByRole('button', { name: 'SQL', exact: true })
    await expect(columnsTab).toBeVisible()
    await expect(sqlTab).toBeVisible()

    // Each tab should be clickable without errors
    await sqlTab.click()
    await expect(main.getByRole('button', { name: 'Compiled', exact: true })).toBeVisible()
  })

  test('overview tables have proper structure', async ({ page }) => {
    // Overview page has a "Recent Models" table
    const table = page.locator('table').first()
    await expect(table).toBeVisible()

    const headers = table.locator('th')
    const headerCount = await headers.count()
    expect(headerCount).toBeGreaterThan(0)

    const rows = table.locator('tbody tr')
    const rowCount = await rows.count()
    expect(rowCount).toBeGreaterThan(0)
  })
})
