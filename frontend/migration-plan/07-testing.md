# Testing Migration

## Current Testing Setup

The project currently uses Playwright for end-to-end testing with these key components:
- Test configuration in `playwright.config.ts`
- Auth setup in `tests/auth.setup.ts`
- Config in `tests/config.ts` for test data
- Utility functions in `tests/utils/`
- Feature-based test files (login.spec.ts, reset-password.spec.ts, etc.)

## Next.js Testing Approach

We'll adapt the Playwright setup to work with Next.js:

1. Update `playwright.config.ts`
2. Adjust auth setup for cookie-based auth
3. Update page selectors for Next.js app structure
4. Add tests for Next.js-specific features

## Playwright Configuration

Update the configuration for Next.js:

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'
import 'dotenv/config'

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'blob' : 'html',
  use: {
    // Updated to use Next.js default port
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
  // Update for Next.js dev server
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
```

## Authentication Setup

Update the auth setup for cookie-based authentication:

```typescript
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test'
import { firstSuperuser, firstSuperuserPassword } from './config'

setup('authenticate', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('Email').fill(firstSuperuser)
  await page.getByPlaceholder('Password', { exact: true }).fill(firstSuperuserPassword)
  await page.getByRole('button', { name: 'Log In' }).click()
  
  // Wait for successful authentication
  await expect(page.getByText('Welcome back, nice to see you again!')).toBeVisible()
  
  // Save the authentication state
  await page.context().storageState({ path: 'playwright/.auth/user.json' })
})
```

## Test Updates

Update test files for Next.js structure:

```typescript
// tests/login.spec.ts
import { type Page, expect, test } from '@playwright/test'
import { firstSuperuser, firstSuperuserPassword } from './config.ts'
import { randomPassword } from './utils/random.ts'

test.use({ storageState: { cookies: [], origins: [] } })

type OptionsType = {
  exact?: boolean
}

const fillForm = async (page: Page, email: string, password: string) => {
  await page.getByPlaceholder('Email').fill(email)
  await page.getByPlaceholder('Password', { exact: true }).fill(password)
}

const verifyInput = async (
  page: Page,
  placeholder: string,
  options?: OptionsType,
) => {
  const input = page.getByPlaceholder(placeholder, options)
  await expect(input).toBeVisible()
  await expect(input).toHaveText('')
  await expect(input).toBeEditable()
}

test('Inputs are visible, empty and editable', async ({ page }) => {
  await page.goto('/login')

  await verifyInput(page, 'Email')
  await verifyInput(page, 'Password', { exact: true })
})

// Additional tests...
```

## Route Testing

Add tests for Next.js-specific routes:

```typescript
// tests/routing.spec.ts
import { expect, test } from '@playwright/test'

test('redirects unauthenticated users from protected routes', async ({ page }) => {
  await page.goto('/settings')
  await expect(page).toHaveURL('/login')
})

test('redirects authenticated users from auth pages', async ({ page }) => {
  // This test uses the authenticated context
  await page.goto('/login')
  await expect(page).toHaveURL('/')
})

test('serves static assets correctly', async ({ page }) => {
  await page.goto('/')
  // Check if favicon and other static assets load correctly
  const response = await page.goto('/assets/images/favicon.png')
  expect(response?.status()).toBe(200)
})
```

## API Route Testing

Add tests for Next.js API routes:

```typescript
// tests/api.spec.ts
import { expect, test } from '@playwright/test'

test('API routes require authentication', async ({ request }) => {
  const response = await request.get('/api/auth/me')
  expect(response.status()).toBe(401)
})

test('authenticated API routes work', async ({ request, page }) => {
  // First login to get authenticated
  await page.goto('/login')
  await page.getByPlaceholder('Email').fill('admin@example.com')
  await page.getByPlaceholder('Password', { exact: true }).fill('password')
  await page.getByRole('button', { name: 'Log In' }).click()
  
  // Now API requests will have the auth cookie
  const response = await request.get('/api/auth/me')
  expect(response.status()).toBe(200)
  const data = await response.json()
  expect(data.email).toBe('admin@example.com')
})
```

## Component Testing

Consider adding React Testing Library and Jest for component testing:

```typescript
// __tests__/components/atoms/ButtonBasic.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ButtonBasic from '@/components/atoms/ButtonBasic'

describe('ButtonBasic', () => {
  it('renders correctly', () => {
    render(<ButtonBasic>Click me</ButtonBasic>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const mockOnClick = jest.fn()
    render(<ButtonBasic onClick={mockOnClick}>Click me</ButtonBasic>)
    await userEvent.click(screen.getByText('Click me'))
    expect(mockOnClick).toHaveBeenCalledTimes(1)
  })
})
```