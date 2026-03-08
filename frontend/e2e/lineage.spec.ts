import { test, expect } from '@playwright/test'

test.describe('Lineage Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/lineage')
  })

  test('renders lineage heading and node count', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Lineage' })).toBeVisible()
    await expect(page.getByText(/\d+ nodes/)).toBeVisible()
  })

  test('displays filter buttons', async ({ page }) => {
    // Scope to main content area to avoid sidebar conflicts
    const main = page.locator('main')
    await expect(main.getByRole('button', { name: 'All' })).toBeVisible()
    await expect(main.getByRole('button', { name: 'Models', exact: true })).toBeVisible()
    await expect(main.getByRole('button', { name: 'Sources', exact: true })).toBeVisible()
  })

  test('displays zoom controls', async ({ page }) => {
    const main = page.locator('main')
    await expect(main.getByRole('button', { name: '+' })).toBeVisible()
    await expect(main.getByRole('button', { name: 'Fit' })).toBeVisible()
  })
})
