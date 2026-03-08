import { test, expect } from '@playwright/test'

test.describe('Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('opens search modal by clicking search button', async ({ page }) => {
    await page.getByText('Search...').click()
    const searchInput = page.getByPlaceholder('Search models, columns, sources...')
    await expect(searchInput).toBeVisible()
  })

  test('search returns results for valid query', async ({ page }) => {
    await page.getByText('Search...').click()
    const searchInput = page.getByPlaceholder('Search models, columns, sources...')
    await searchInput.fill('order')
    // Wait for Fuse.js search results
    await page.waitForTimeout(300)
    // Should show result items
    const resultItems = page.locator('ul li')
    const count = await resultItems.count()
    expect(count).toBeGreaterThan(0)
  })

  test('closes search modal with Escape', async ({ page }) => {
    await page.getByText('Search...').click()
    const searchInput = page.getByPlaceholder('Search models, columns, sources...')
    await expect(searchInput).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(searchInput).not.toBeVisible()
  })

  test('selecting search result navigates to model page', async ({ page }) => {
    await page.getByText('Search...').click()
    const searchInput = page.getByPlaceholder('Search models, columns, sources...')
    await searchInput.fill('customers')
    await page.waitForTimeout(300)
    // Click first result
    const firstResult = page.locator('ul li button').first()
    await firstResult.click()
    // Should navigate to a model or source page
    await expect(page).toHaveURL(/#\/(model|source)\//)
  })
})
