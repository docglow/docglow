import { test, expect } from '@playwright/test'

test.describe('Favicon and Meta', () => {
  test('page has a favicon link', async ({ page }) => {
    await page.goto('/')
    const faviconLink = page.locator('link[rel="icon"]')
    await expect(faviconLink).toHaveAttribute('href', /favicon\.svg/)
  })

  test('favicon returns 200', async ({ page }) => {
    await page.goto('/')
    const faviconHref = await page.locator('link[rel="icon"]').getAttribute('href')
    expect(faviconHref).toBeTruthy()

    const response = await page.goto(faviconHref!)
    expect(response?.status()).toBe(200)
  })

  test('page title is docglow', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle('docglow')
  })
})
