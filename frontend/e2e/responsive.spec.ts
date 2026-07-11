import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixturePath = new URL('./fixtures/docglow-data.json', import.meta.url)

function existingUi(fixture: Record<string, unknown>): Record<string, unknown> {
  const ui = fixture.ui
  return ui && typeof ui === 'object' && !Array.isArray(ui)
    ? ui as Record<string, unknown>
    : {}
}

async function routeFixture(
  page: Page,
  mutate?: (fixture: Record<string, unknown>) => void,
) {
  const fixture = JSON.parse(readFileSync(fixturePath, 'utf-8')) as Record<string, unknown>
  mutate?.(fixture)
  await page.route('**/docglow-data.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(fixture),
  }))
}

test.describe('Responsive Layout', () => {
  test('desktop layout shows sidebar', async ({ page }) => {
    await routeFixture(page)
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    const sidebar = page.getByRole('complementary')
    await expect(sidebar).toBeVisible()
  })

  test('desktop layout honours configured sidebar width', async ({ page }) => {
    await routeFixture(page, fixture => {
      fixture.ui = {
        ...existingUi(fixture),
        sidebar: {
          default_width: 320,
          min_width: 220,
          max_width: 560,
          resizable: true,
        },
      }
    })
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    const width = await page.getByRole('complementary').evaluate(el => el.getBoundingClientRect().width)
    expect(Math.round(width)).toBe(320)
  })

  test('desktop layout honours configured content max width', async ({ page }) => {
    await routeFixture(page, fixture => {
      fixture.ui = {
        ...existingUi(fixture),
        content_layout: {
          max_width: 960,
        },
      }
    })
    await page.setViewportSize({ width: 1600, height: 720 })
    await page.goto('/')

    const contentBox = await page.locator('main > div').evaluate(el => {
      const rect = el.getBoundingClientRect()
      const parentRect = el.parentElement?.getBoundingClientRect()
      return {
        width: rect.width,
        leftGap: parentRect ? rect.left - parentRect.left : 0,
        rightGap: parentRect ? parentRect.right - rect.right : 0,
      }
    })
    expect(Math.round(contentBox.width)).toBe(960)
    expect(Math.abs(contentBox.leftGap - contentBox.rightGap)).toBeLessThanOrEqual(1)
  })

  test('AI chat control is hidden when AI is disabled', async ({ page }) => {
    await routeFixture(page)
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')

    await expect(page.getByTitle('AI Chat (Ctrl+J)')).toHaveCount(0)
    await page.keyboard.press('Control+J')
    await expect(page.getByText('AI Chat Setup')).toHaveCount(0)
  })

  test('overview stat cards render on narrow viewport', async ({ page }) => {
    await routeFixture(page)
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')

    // Main content should be visible
    const main = page.locator('main')
    await expect(main).toBeVisible()

    // Project name heading should be visible
    await expect(page.locator('h1')).toContainText('jaffle_shop')
  })

  test('model page is usable on tablet viewport', async ({ page }) => {
    await routeFixture(page)
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
