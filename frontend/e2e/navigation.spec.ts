import { expect, test } from '@playwright/test'

test('signed-out learner can reach the provider sign-in screen', async ({ page }) => {
  await page.goto('/signin')
  await expect(page.getByRole('heading', { name: 'Practice the decisions behind good data models.' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('href', '/api/v1/auth/google/start')
  await expect(page.getByRole('link', { name: 'Continue with GitHub' })).toHaveAttribute('href', '/api/v1/auth/github/start')
})

test('signed-out learner can browse the archive route', async ({ page }) => {
  await page.goto('/problems')
  await expect(page).toHaveURL(/\/problems$/)
  await expect(page.locator('main')).toBeVisible()
})
