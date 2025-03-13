# Routing Migration

## Current TanStack Router Structure

The current routing system uses TanStack Router with routes defined in `src/routes`:
- `__root.tsx` - Root route definition
- `_layout.tsx` - Main application layout
- `_layout/` - Nested routes under the main layout
  - `admin.tsx` - Admin routes
  - `index.tsx` - Dashboard/home page
  - `settings.tsx` - User settings
- `login.tsx`, `recover-password.tsx`, etc. - Auth-related routes

## Next.js App Router Structure

In Next.js App Router, we'll convert to this directory structure:

```
src/
  app/
    (auth)/
      login/
        page.tsx
      recover-password/
        page.tsx
      reset-password/
        page.tsx
      signup/
        page.tsx
    (dashboard)/
      page.tsx
      layout.tsx
      admin/
        page.tsx
      settings/
        page.tsx
    api/
      auth/
        [...route]/
          route.ts
    layout.tsx
    page.tsx
```

## Route Groups and Layouts

We'll use route groups (parentheses) to organize routes by section without affecting URL paths:

- `(auth)` - Authentication-related pages that use a shared auth layout
- `(dashboard)` - Protected dashboard pages that require authentication

## Authentication and Route Protection

Instead of TanStack Router's `beforeLoad` hooks, we'll implement middleware:

```typescript
// src/middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const isAuthenticated = !!request.cookies.get('access_token')
  const isAuthPage = request.nextUrl.pathname.startsWith('/login') ||
                    request.nextUrl.pathname.startsWith('/signup') ||
                    request.nextUrl.pathname.startsWith('/recover-password') ||
                    request.nextUrl.pathname.startsWith('/reset-password')
  
  // Redirect authenticated users away from auth pages
  if (isAuthenticated && isAuthPage) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  // Redirect unauthenticated users to login
  if (!isAuthenticated && !isAuthPage) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
}
```

## Converting Route Components

For each route in the current app, we'll create a corresponding Next.js page.

Example conversion:

### Current TanStack Router:
```tsx
// src/routes/login.tsx
import { createFileRoute } from '@tanstack/react-router'
import LoginForm from '@/components/organisms/Account/LoginForm'

export const Route = createFileRoute('/login')({
  component: LoginPage,
})

function LoginPage() {
  return <LoginForm />
}
```

### Next.js App Router:
```tsx
// src/app/(auth)/login/page.tsx
import LoginForm from '@/components/organisms/Account/LoginForm'

export default function LoginPage() {
  return <LoginForm />
}
```

## Dynamic Routes

For dynamic routes like `/reset-password?token=xyz`, we'll use:

```tsx
// src/app/(auth)/reset-password/page.tsx
export default function ResetPasswordPage({
  searchParams,
}: {
  searchParams: { token?: string }
}) {
  const token = searchParams.token
  
  return <ResetPasswordForm token={token} />
}
```

## Layouts

For the layout structure:

```tsx
// src/app/layout.tsx
import { Providers } from '@/components/ui/provider'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

```tsx
// src/app/(dashboard)/layout.tsx
import Sidebar from '@/components/Common/Sidebar'
import Navbar from '@/components/Common/Navbar'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="dashboard-layout">
      <Navbar />
      <div className="dashboard-content">
        <Sidebar />
        <main>{children}</main>
      </div>
    </div>
  )
}
```