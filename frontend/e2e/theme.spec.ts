import { test, expect } from '@playwright/test'

test.describe('Theme Switching', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('theme toggle button is visible', async ({ page }) => {
    const themeButton = page.getByRole('button', { name: /Switch to (dark|light) mode/ })
    await expect(themeButton).toBeVisible()
  })

  test('theme toggle switches class on root element', async ({ page }) => {
    const html = page.locator('html')
    const hadDark = await html.evaluate((el) => el.classList.contains('dark'))

    // Click theme toggle
    const themeButton = page.getByRole('button', { name: /Switch to (dark|light) mode/ })
    await themeButton.click()

    const hasDark = await html.evaluate((el) => el.classList.contains('dark'))
    expect(hasDark).not.toBe(hadDark)
  })

  test('dark mode changes background color', async ({ page }) => {
    // Get initial background
    const body = page.locator('body')
    const initialBg = await body.evaluate((el) => getComputedStyle(el).backgroundColor)

    // Toggle theme
    const themeButton = page.getByRole('button', { name: /Switch to (dark|light) mode/ })
    await themeButton.click()

    const newBg = await body.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(newBg).not.toBe(initialBg)
  })
})
