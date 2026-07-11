import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

const fixturePath = new URL('./fixtures/docglow-data.json', import.meta.url)
const stressModelId = 'model.jaffle_shop.orders'

async function routeDefaultData(page: Page) {
  await page.route('**/docglow-data.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: readFileSync(fixturePath, 'utf-8'),
  }))
}

async function routeColumnLayoutStressData(page: Page) {
  const fixture = JSON.parse(readFileSync(fixturePath, 'utf-8'))
  const model = fixture.models[stressModelId]
  model.columns = [
    {
      name: 'course_allocation_parameter_subquota_row_key',
      description: 'Surrogate key for the source allocation parameter subquota row.',
      data_type: '',
      meta: {},
      tags: [],
      tests: [
        { test_name: 'unique_course_allocation_parameter_subquota_row_key', test_type: 'unique', status: 'pass', config: {} },
        { test_name: 'not_null_course_allocation_parameter_subquota_row_key', test_type: 'not_null', status: 'pass', config: {} },
      ],
      profile: null,
      insights: {
        role: 'primary_key',
        semantic_type: 'identifier',
        sql_usage: [],
        confidence: 0.95,
        generated_description: null,
      },
    },
    {
      name: 'subquota_interpretation_review_status',
      description: 'Review status for interpreting source subquota rank and maximum-offer controls.',
      data_type: '',
      meta: {},
      tags: [],
      tests: [
        { test_name: 'not_null_subquota_interpretation_review_status', test_type: 'not_null', status: 'pass', config: {} },
        { test_name: 'accepted_values_subquota_interpretation_review_status', test_type: 'accepted_values', status: 'pass', config: {} },
      ],
      profile: null,
      insights: {
        role: 'categorical',
        semantic_type: 'categorical',
        sql_usage: [],
        confidence: 0.88,
        generated_description: null,
      },
    },
    {
      name: 'recommendation_readiness_status',
      description: 'Strategy-readiness status for recommendation use.',
      data_type: '',
      meta: {},
      tags: [],
      tests: [
        { test_name: 'not_null_recommendation_readiness_status', test_type: 'not_null', status: 'pass', config: {} },
        { test_name: 'accepted_values_recommendation_readiness_status', test_type: 'accepted_values', status: 'pass', config: {} },
      ],
      profile: null,
      insights: {
        role: 'categorical',
        semantic_type: 'categorical',
        sql_usage: [],
        confidence: 0.9,
        generated_description: null,
      },
    },
  ]
  fixture.ui = {
    ...fixture.ui,
    table_layout: {
      mode: 'auto',
      min_width: null,
      content_sized_columns: ['column', 'type', 'tests'],
      content_sized_max_width: 360,
    },
    lineage_badge: {
      abbreviation: 'smart',
      max_model_chars: 30,
      max_column_chars: 22,
    },
  }
  fixture.column_lineage = {
    [stressModelId]: {
      course_allocation_parameter_subquota_row_key: [
        {
          source_model: 'model.jaffle_shop.stg_orders',
          source_column: 'course_allocation_parameter_subquota_row_key',
          transformation: 'passthrough',
        },
      ],
      recommendation_readiness_status: [
        {
          source_model: 'model.jaffle_shop.stg_orders',
          source_column: 'recommendation_readiness_status',
          transformation: 'passthrough',
        },
      ],
    },
    'model.jaffle_shop.course_allocation_report_readiness': {
      readiness_status: [
        {
          source_model: stressModelId,
          source_column: 'recommendation_readiness_status',
          transformation: 'passthrough',
        },
      ],
    },
  }

  await page.route('**/docglow-data.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(fixture),
  }))
}

test.describe('Model Detail Page', () => {
  // Scope tab interactions to main content to avoid sidebar conflicts
  const mainSelector = 'main'

  test.beforeEach(async ({ page }) => {
    await routeDefaultData(page)
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
    await expect(page.locator('.react-flow').first()).toBeVisible()
  })

  test('can switch to tests tab', async ({ page }) => {
    const main = page.locator(mainSelector)
    await main.getByRole('button', { name: /Tests/ }).click()
    await expect(page.locator('table').first()).toBeVisible()
  })

  test('content-sized column table keeps names and tests readable', async ({ page }) => {
    await routeColumnLayoutStressData(page)
    await page.setViewportSize({ width: 1360, height: 720 })
    await page.goto(`/?column-layout-stress=1#/model/${encodeURIComponent(stressModelId)}`)

    const reviewRow = page.locator('#col-subquota_interpretation_review_status')
    await expect(reviewRow).toBeVisible()
    const rowMetrics = await reviewRow.evaluate(row => {
      const cells = Array.from(row.querySelectorAll('td'))
      return {
        columnWidth: cells[0].getBoundingClientRect().width,
        descriptionWidth: cells[2].getBoundingClientRect().width,
        testsWidth: cells[cells.length - 1].getBoundingClientRect().width,
        columnText: cells[0].textContent ?? '',
        testsText: cells[cells.length - 1].textContent ?? '',
      }
    })

    expect(rowMetrics.columnWidth).toBeGreaterThan(320)
    expect(rowMetrics.descriptionWidth).toBeLessThan(440)
    expect(rowMetrics.testsWidth).toBeGreaterThan(220)
    expect(rowMetrics.columnText).toContain('subquota_interpretation_review_status')
    expect(rowMetrics.testsText).toContain('accepted_values')

    const lineageRow = page.locator('#col-recommendation_readiness_status')
    await expect(lineageRow).toBeVisible()
    const badge = lineageRow.getByRole('button', {
      name: /To: model\.jaffle_shop\.course_allocation_report_readiness/,
    }).first()
    await expect(badge).toBeVisible()

    const compact = await badge.evaluate(button => {
      const buttonRect = button.getBoundingClientRect()
      const cellRect = button.closest('td')?.getBoundingClientRect()
      if (!cellRect) throw new Error('lineage cell missing')
      const childOverflows = Array.from(button.children)
        .filter((child): child is HTMLElement => child instanceof HTMLElement)
        .map(child => {
          const rect = child.getBoundingClientRect()
          return {
            left: rect.left,
            right: rect.right,
            width: rect.width,
          }
        })
        .filter(rect => rect.width > 0 && (
          rect.left < buttonRect.left - 1 ||
          rect.right > buttonRect.right + 1
        ))
      return {
        buttonRight: buttonRect.right,
        buttonWidth: buttonRect.width,
        childOverflows,
        cellRight: cellRect.right,
        hasNativeTitle: button.hasAttribute('title'),
        height: buttonRect.height,
        rowHeight: button.closest('tr')?.getBoundingClientRect().height ?? 0,
      }
    })

    expect(compact.buttonRight).toBeLessThanOrEqual(compact.cellRight + 1)
    expect(compact.buttonWidth).toBeLessThanOrEqual(261)
    expect(compact.childOverflows).toEqual([])
    expect(compact.hasNativeTitle).toBe(false)

    await badge.hover()
    const detailPanel = page.getByTestId('lineage-badge-detail')
    await expect(detailPanel).toBeVisible()

    const detailMetrics = await detailPanel.evaluate(panel => {
      const rect = panel.getBoundingClientRect()
      const topElement = document.elementsFromPoint(
        rect.left + rect.width / 2,
        rect.top + Math.min(rect.height / 2, 12),
      )[0]
      const backgroundColor = getComputedStyle(panel).backgroundColor
      const alpha = backgroundColor.startsWith('rgba(')
        ? Number(backgroundColor.replace(/^rgba\(|\)$/g, '').split(',')[3])
        : 1

      return {
        width: rect.width,
        isTopLayer: panel === topElement || panel.contains(topElement),
        alpha,
      }
    })

    expect(detailMetrics.isTopLayer).toBe(true)
    expect(detailMetrics.alpha).toBe(1)
    expect(detailMetrics.width).toBeLessThan(340)

    const expanded = await badge.evaluate(button => {
      const buttonRect = button.getBoundingClientRect()
      const cellRect = button.closest('td')?.getBoundingClientRect()
      if (!cellRect) throw new Error('lineage cell missing')
      return {
        buttonRight: buttonRect.right,
        buttonWidth: buttonRect.width,
        cellRight: cellRect.right,
        height: buttonRect.height,
        rowHeight: button.closest('tr')?.getBoundingClientRect().height ?? 0,
      }
    })

    expect(expanded.buttonRight).toBeLessThanOrEqual(expanded.cellRight + 1)
    expect(expanded.buttonWidth).toBeLessThanOrEqual(261)
    expect(expanded.height).toBeGreaterThanOrEqual(compact.height)
    expect(expanded.rowHeight).toBeLessThanOrEqual(compact.rowHeight + 1)
  })

})

test.describe('Model Not Found', () => {
  test('shows not found message for invalid model id', async ({ page }) => {
    await routeDefaultData(page)
    await page.goto('/#/model/nonexistent-model-id')
    await expect(page.getByText('Model not found')).toBeVisible()
  })
})
