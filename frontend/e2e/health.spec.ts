import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixturePath = new URL('./fixtures/docglow-data.json', import.meta.url)

async function routeHealthDataWithComplexityTable(page: Page) {
  const fixture = JSON.parse(readFileSync(fixturePath, 'utf-8'))
  fixture.health.complexity.high_count = 1
  fixture.health.complexity.models = [
    {
      unique_id: 'model.test.very_long_complexity_model_name_for_responsive_table_check',
      name: 'very_long_complexity_model_name_for_responsive_table_check',
      folder: 'models/gold/semantic',
      sql_lines: 420,
      join_count: 18,
      cte_count: 14,
      subquery_count: 9,
      downstream_count: 42,
    },
  ]
  await page.route('**/docglow-data.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(fixture),
  }))
}

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

  test('complexity table exposes horizontal overflow instead of clipping final columns', async ({ page }) => {
    await routeHealthDataWithComplexityTable(page)
    await page.setViewportSize({ width: 760, height: 720 })
    await page.reload()
    await page.getByRole('button', { name: 'Complexity' }).click()

    const metrics = await page.locator('table').evaluate(table => {
      const frame = table.parentElement
      if (!frame) throw new Error('table frame missing')
      return {
        clientWidth: frame.clientWidth,
        overflowX: getComputedStyle(frame).overflowX,
        scrollWidth: frame.scrollWidth,
      }
    })

    expect(metrics.scrollWidth).toBeGreaterThan(metrics.clientWidth)
    expect(metrics.overflowX).toBe('auto')
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
