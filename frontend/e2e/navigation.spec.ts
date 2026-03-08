import { test, expect } from '@playwright/test'

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('sidebar displays models and sources tree sections', async ({ page }) => {
    const sidebar = page.locator('aside')
    await expect(sidebar).toBeVisible()
    // The tree sections use button elements with folder names
    await expect(sidebar.getByRole('button', { name: /^models/ })).toBeVisible()
    await expect(sidebar.getByRole('button', { name: /^sources/ })).toBeVisible()
  })

  test('sidebar shows model and source counts in footer', async ({ page }) => {
    const sidebar = page.locator('aside')
    // Footer text like "13 models · 6 sources"
    await expect(sidebar.getByText(/\d+ models/)).toBeVisible()
    await expect(sidebar.getByText(/\d+ sources/)).toBeVisible()
  })

  test('lineage button navigates to lineage page', async ({ page }) => {
    await page.locator('aside').getByRole('button', { name: 'Lineage' }).click()
    await expect(page).toHaveURL(/#\/lineage/)
  })

  test('health button navigates to health page', async ({ page }) => {
    await page.locator('aside').getByRole('button', { name: /Health/ }).click()
    await expect(page).toHaveURL(/#\/health/)
    await expect(page.locator('h1')).toHaveText('Project Health')
  })

  test('clicking sidebar model navigates to model detail', async ({ page }) => {
    // Click a known model leaf from the tree (e.g., "customers" under marts)
    const sidebar = page.locator('aside')
    await sidebar.getByRole('button', { name: 'customers', exact: true }).click()
    await expect(page).toHaveURL(/#\/model\//)
  })
})

test.describe('Header', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('displays project name and logo', async ({ page }) => {
    const header = page.locator('header')
    await expect(header).toBeVisible()
    await expect(header.getByText('d++')).toBeVisible()
    await expect(header.getByText('jaffle_shop')).toBeVisible()
  })

  test('search button is visible with keyboard shortcut', async ({ page }) => {
    await expect(page.getByText('Search...')).toBeVisible()
  })

  test('theme toggle button is present', async ({ page }) => {
    const themeButton = page.locator('header button[title*="Switch to"]')
    await expect(themeButton).toBeVisible()
  })

  test('theme toggles between light and dark', async ({ page }) => {
    const themeButton = page.locator('header button[title*="Switch to"]')
    await themeButton.click()
    const hasDark = await page.locator('html').evaluate(el => el.classList.contains('dark'))
    await themeButton.click()
    const hasDarkAfter = await page.locator('html').evaluate(el => el.classList.contains('dark'))
    expect(hasDark).not.toBe(hasDarkAfter)
  })
})
