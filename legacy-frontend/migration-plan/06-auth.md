# Authentication Migration

## Current Authentication Flow

The current application uses a client-side authentication approach:
1. User logs in via the login form
2. Token is stored in localStorage
3. Auth state is managed with hooks and context
4. Protected routes check auth state via TanStack Router

## Next.js Authentication Approach

We'll migrate to a more secure approach using:
1. Server-side authentication with cookies
2. Next.js middleware for route protection
3. Server components for data fetching with auth
4. Server actions for authentication operations

## Cookie-Based Authentication

Instead of localStorage, we'll use HTTP-only cookies:

```tsx
// src/app/actions/auth.ts
'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { LoginService } from '@/lib/api'

export async function login(formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string
  
  try {
    const response = await LoginService.login({ email, password })
    
    // Set auth cookies
    cookies().set('access_token', response.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      path: '/',
      maxAge: 60 * 60 * 24 * 7, // 1 week
    })
    
    redirect('/')
  } catch (error) {
    return { error: 'Invalid credentials' }
  }
}

export async function logout() {
  cookies().delete('access_token')
  redirect('/login')
}
```

## Login Form Component

The login form will use Server Actions:

```tsx
// src/components/organisms/Account/LoginForm.tsx
'use client'

import { useForm } from 'react-hook-form'
import { useState } from 'react'
import { login } from '@/app/actions/auth'

export default function LoginForm() {
  const { register, handleSubmit, formState: { errors } } = useForm()
  const [serverError, setServerError] = useState('')
  
  async function onSubmit(data) {
    const result = await login(data)
    if (result?.error) {
      setServerError(result.error)
    }
  }
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Form fields */}
    </form>
  )
}
```

## Authentication Middleware

For route protection:

```tsx
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

## Client-Side Auth State

For client components that need to know auth state:

```tsx
// src/hooks/useAuth.ts
'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type AuthContextType = {
  isAuthenticated: boolean
  user: any | null
  loading: boolean
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  user: null,
  loading: true,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  
  useEffect(() => {
    async function checkAuth() {
      try {
        // API call to validate session and get user data
        const response = await fetch('/api/auth/me')
        
        if (response.ok) {
          const userData = await response.json()
          setUser(userData)
          setIsAuthenticated(true)
        } else {
          setIsAuthenticated(false)
          setUser(null)
        }
      } catch (error) {
        setIsAuthenticated(false)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    
    checkAuth()
  }, [router])
  
  return (
    <AuthContext.Provider value={{ isAuthenticated, user, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
```

## User Menu Component

Client components can use the auth hook:

```tsx
// src/components/Common/UserMenu.tsx
'use client'

import { useAuth } from '@/hooks/useAuth'
import { logout } from '@/app/actions/auth'
import { Button, Menu, MenuButton, MenuItem, MenuList } from '@chakra-ui/react'

export function UserMenu() {
  const { user } = useAuth()
  
  return (
    <Menu>
      <MenuButton as={Button} data-testid="user-menu">
        {user?.email}
      </MenuButton>
      <MenuList>
        <MenuItem as="a" href="/settings">Settings</MenuItem>
        <MenuItem onClick={() => logout()}>Log out</MenuItem>
      </MenuList>
    </Menu>
  )
}
```

## API Route for User Data

Create an API route to get the current user:

```tsx
// src/app/api/auth/me/route.ts
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { UsersService } from '@/lib/api'

export async function GET() {
  const cookieStore = cookies()
  const token = cookieStore.get('access_token')?.value
  
  if (!token) {
    return new NextResponse(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
    })
  }
  
  try {
    const userData = await UsersService.getCurrentUser()
    return NextResponse.json(userData)
  } catch (error) {
    return new NextResponse(JSON.stringify({ error: 'Failed to fetch user' }), {
      status: 500,
    })
  }
}
```