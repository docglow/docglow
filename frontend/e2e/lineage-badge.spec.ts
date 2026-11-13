import { readFileSync } from 'node:fs'
import { test, expect, type Page } from '@playwright/test'

const fixture = JSON.parse(
  readFileSync(new URL('./fixtures/docglow-data.json', import.meta.url), 'utf-8'),
)

const LONG_MODEL = 'fact_orders_by_supplier_over_time_by_state_and_segment'
const LONG_COLUMN = 'customer_lifetime_value_in_usd_after_refunds'
const COLUMN = 'order_id'

async function openModelWithLongBadge(page: Page, lineageBadge: Record<string, unknown>) {
  const data = {
    ...fixture,
    ui: { lineage_badge: { abbreviation: 'middle', max_model_chars: 30, max_column_chars: 22, ...lineageBadge } },
    column_lineage: {
      'model.jaffle_shop.orders': {
        [COLUMN]: [
          {
            source_model: `model.jaffle_shop.${LONG_MODEL}`,
            source_column: LONG_COLUMN,
            transformation: 'derived',
          },
          {
            source_model: 'model.jaffle_shop.stg_orders',
            source_column: 'id',
            transformation: 'passthrough',
          },
        ],
      },
    },
  }
  await page.route('**/docglow-data.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  }))
  await page.goto('/#/model/model.jaffle_shop.orders')
  const row = page.locator(`tr[id="col-${COLUMN}"]`)
  const badge = row.locator('button').filter({ hasText: '…' })
  await expect(badge).toBeVisible()
  // Rest the pointer away from the table so the measured height is the unhovered one.
  await page.mouse.move(0, 0)
  return { row, badge }
}

const rowHeight = async (row: ReturnType<Page['locator']>) => (await row.boundingBox())!.height

test.describe('Lineage badge hover detail', () => {
  test('default mode expands the badge in place and grows the row', async ({ page }) => {
    const { row, badge } = await openModelWithLongBadge(page, {})
    const before = await rowHeight(row)
    await expect(badge).toHaveAttribute('title', new RegExp(`Type: derived`))

    await badge.hover()

    await expect.poll(() => rowHeight(row)).toBeGreaterThan(before)
    await expect(badge.getByText(LONG_MODEL, { exact: true })).toBeVisible()
    await expect(page.getByTestId('lineage-badge-detail')).toHaveCount(0)
  })

  test('panel mode opens a floating panel without changing the row height', async ({ page }) => {
    const { row, badge } = await openModelWithLongBadge(page, { hover_detail: 'panel' })
    const before = await rowHeight(row)

    await badge.hover()

    const panel = page.getByTestId('lineage-badge-detail')
    await expect(panel).toBeVisible()
    await expect(panel).toContainText(LONG_MODEL)
    await expect(panel).toContainText(LONG_COLUMN)
    await expect(panel).toContainText('Type: derived')
    expect(await rowHeight(row)).toBe(before)

    await page.mouse.move(0, 0)
    await expect(panel).toHaveCount(0)
  })

  test('panel mode leaves short badges static', async ({ page }) => {
    const { row } = await openModelWithLongBadge(page, { hover_detail: 'panel' })

    await row.getByRole('button', { name: /stg_orders/ }).hover()

    await expect(page.getByTestId('lineage-badge-detail')).toHaveCount(0)
  })

  test('panel mode opens on keyboard focus and closes on Escape', async ({ page }) => {
    const { badge } = await openModelWithLongBadge(page, { hover_detail: 'panel' })

    await badge.focus()
    const panel = page.getByTestId('lineage-badge-detail')
    await expect(panel).toBeVisible()

    await page.keyboard.press('Escape')
    await expect(panel).toHaveCount(0)
  })
})
