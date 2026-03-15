import { test, expect } from '@playwright/test'

test.describe('Source Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Expand Sources folder in sidebar
    const sidebar = page.getByRole('complementary')
    await sidebar.getByRole('button', { name: /sources/ }).click()
    // Expand the "ecom" sub-folder
    await sidebar.getByRole('button', { name: /ecom/ }).click()
    // Click a specific source
    await sidebar.getByRole('button', { name: 'raw_customers' }).click()
    await page.waitForURL(/#\/source\//)
  })

  test('displays source name', async ({ page }) => {
    await expect(page.locator('h1')).toBeVisible()
    await expect(page.locator('h1')).toContainText('raw_customers')
  })

  test('shows columns heading and table', async ({ page }) => {
    const main = page.locator('main')
    await expect(main.getByRole('heading', { name: /Columns/ })).toBeVisible()
    await expect(main.locator('table').first()).toBeVisible()
  })

  test('shows source metadata', async ({ page }) => {
    const main = page.locator('main')
    await expect(main).toBeVisible()
    await expect(page.locator('h1')).toContainText('raw_customers')
  })
})

test.describe('Source Not Found', () => {
  test('shows not found message for invalid source id', async ({ page }) => {
    await page.goto('/#/source/nonexistent-source-id')
    await expect(page.getByText(/not found/i)).toBeVisible()
  })
})
