import { test, expect } from '@playwright/test'

test.describe('Responsive Layout', () => {
  test('desktop layout shows sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    const sidebar = page.getByRole('complementary')
    await expect(sidebar).toBeVisible()
  })

  test('overview stat cards render on narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')

    // Main content should be visible
    const main = page.locator('main')
    await expect(main).toBeVisible()

    // Project name heading should be visible
    await expect(page.locator('h1')).toContainText('jaffle_shop')
  })

  test('model page is usable on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/')

    // Navigate to model via table
    await page.locator('table tbody tr').filter({ hasText: 'orders' }).first().click()
    await page.waitForURL(/#\/model\//)

    // Model name and tabs should be visible
    await expect(page.locator('h1')).toContainText('orders')
    const main = page.locator('main')
    await expect(main.getByRole('button', { name: /Columns/ })).toBeVisible()
  })
})
