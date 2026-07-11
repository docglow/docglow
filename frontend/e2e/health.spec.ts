import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixturePath = new URL('./fixtures/docglow-data.json', import.meta.url)

async function routeHealthLayoutStressData(page: Page) {
  const fixture = JSON.parse(readFileSync(fixturePath, 'utf-8'))
  fixture.health.coverage.models_tested = { covered: 566, total: 694, rate: 566 / 694 }
  fixture.health.coverage.columns_tested = { covered: 3540, total: 10714, rate: 3540 / 10714 }
  fixture.health.coverage.by_folder = {
    'models/silver/intermediate': { covered: 97, total: 97, rate: 1 },
    'models/silver/staging': { covered: 114, total: 114, rate: 1 },
    'models/gold/dashboard_outputs': { covered: 15, total: 15, rate: 1 },
    'models/bronze': { covered: 118, total: 118, rate: 1 },
  }
  fixture.health.complexity.high_count = 1
  fixture.health.complexity.models = [
    {
      unique_id: 'model.test.dashboard_horizon_forecast_path',
      name: 'dashboard_horizon_forecast_path',
      folder: 'models/gold/dashboard_outputs',
      sql_lines: 2082,
      join_count: 31,
      cte_count: 28,
      subquery_count: 32,
      downstream_count: 117,
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

  test('complexity table exposes overflow instead of clipping the downstream column', async ({ page }) => {
    await routeHealthLayoutStressData(page)
    await page.setViewportSize({ width: 760, height: 720 })
    await page.reload()
    await page.getByRole('button', { name: 'Complexity' }).click()

    const metrics = await page.locator('table').evaluate(table => {
      const frame = table.parentElement
      if (!frame) throw new Error('table frame missing')
      return {
        downstreamHeader: table.querySelector('th:last-child')?.textContent,
        frameWidth: frame.clientWidth,
        overflowX: getComputedStyle(frame).overflowX,
        scrollWidth: frame.scrollWidth,
      }
    })

    expect(metrics.downstreamHeader).toBe('Downstream')
    expect(metrics.scrollWidth).toBeGreaterThan(metrics.frameWidth)
    expect(metrics.overflowX).toBe('auto')
  })

  test('coverage rows keep long labels and large counts from colliding', async ({ page }) => {
    await routeHealthLayoutStressData(page)
    await page.setViewportSize({ width: 1360, height: 720 })
    await page.reload()
    await page.getByRole('button', { name: 'Documentation' }).click()

    const layout = await page.getByText('models/gold/dashboard_outputs').evaluate(label => {
      const row = label.parentElement
      const bar = row?.querySelector('div[class*="rounded-full"]')
      if (!row || !(bar instanceof HTMLElement)) {
        throw new Error('coverage row layout missing')
      }
      const labelRect = label.getBoundingClientRect()
      const barRect = bar.getBoundingClientRect()
      return {
        gap: barRect.left - labelRect.right,
      }
    })
    const stagingCount = page.getByText('114/114 (100.0%)')

    expect(layout.gap).toBeGreaterThan(8)
    await expect(stagingCount).toBeVisible()
    await expect(stagingCount).toHaveCSS('white-space', 'nowrap')
  })

  test('testing summary coverage values remain on one line', async ({ page }) => {
    await routeHealthLayoutStressData(page)
    await page.setViewportSize({ width: 1360, height: 720 })
    await page.reload()
    await page.getByRole('button', { name: 'Testing' }).click()

    const modelCoverage = page.getByText('566/694 (81.6%)')
    const columnCoverage = page.getByText('3540/10714 (33.0%)')

    await expect(modelCoverage).toBeVisible()
    await expect(columnCoverage).toBeVisible()
    await expect(modelCoverage).toHaveCSS('white-space', 'nowrap')
    await expect(columnCoverage).toHaveCSS('white-space', 'nowrap')
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
