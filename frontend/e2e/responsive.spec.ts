import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixturePath = new URL('./fixtures/docglow-data.json', import.meta.url)

test.describe('Responsive Layout', () => {
  test('desktop layout shows sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    const sidebar = page.getByRole('complementary')
    await expect(sidebar).toBeVisible()
  })

  test('desktop layout honours configured sidebar width', async ({ page }) => {
    const fixture = JSON.parse(readFileSync(fixturePath, 'utf-8'))
    fixture.ui = {
      ...fixture.ui,
      sidebar: {
        default_width: 320,
        min_width: 220,
        max_width: 560,
        resizable: true,
      },
    }
    await page.route('**/docglow-data.json', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture),
    }))
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    const width = await page.getByRole('complementary').evaluate(el => el.getBoundingClientRect().width)
    expect(Math.round(width)).toBe(320)
  })

  test('AI chat control is hidden when AI is disabled', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    await expect(page.getByTitle('AI Chat (Ctrl+J)')).toHaveCount(0)
    await page.keyboard.press('Control+J')
    await expect(page.getByText('AI Chat Setup')).toHaveCount(0)
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
