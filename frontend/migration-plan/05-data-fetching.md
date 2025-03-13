# Data Fetching Migration

## Current Approach

The current application uses TanStack Query and a generated OpenAPI client to fetch data:

```tsx
// Current approach
import { useQuery } from '@tanstack/react-query'
import { SomeService } from '@/client/services'

export function SomeComponent() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['someData'],
    queryFn: () => SomeService.getData()
  })
  
  // Component rendering
}
```

## Next.js Data Fetching Options

In Next.js 15, we have multiple options for data fetching:

1. **Server Components**: Fetch data directly on the server
2. **Route Handlers**: API endpoints for client-side fetching
3. **Client Components with TanStack Query**: For client-side interactive data

## Server Component Data Fetching

For static or initially loaded data, we'll use Server Components:

```tsx
// src/app/dashboard/page.tsx
import SomeComponent from '@/components/SomeComponent'
import { SomeService } from '@/lib/api'

export default async function DashboardPage() {
  const data = await SomeService.getData()
  return <SomeComponent initialData={data} />
}
```

## API Client Updates

We'll modify the API client generation to work with both server and client components:

1. Create a server-safe fetch wrapper:

```tsx
// src/lib/api/fetch.ts
import { headers } from 'next/headers'
import { cookies } from 'next/headers'

export async function serverFetch(url: string, options: RequestInit = {}) {
  // Get token from cookies on server
  const headersList = headers()
  const cookieStore = cookies()
  const token = cookieStore.get('access_token')?.value
  
  const mergedOptions: RequestInit = {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    }
  }
  
  const response = await fetch(url, mergedOptions)
  
  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`)
  }
  
  return response.json()
}
```

2. Create an API client factory:

```tsx
// src/lib/api/client.ts
import { serverFetch } from './fetch'
import axios from 'axios'

// For server components
export const serverApi = {
  get: async (url: string) => serverFetch(url),
  post: async (url: string, data: any) => serverFetch(url, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  // Add other methods...
}

// For client components
export const createClientApi = (token: string) => {
  const axiosInstance = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL,
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    }
  })
  
  return axiosInstance
}
```

## Server Actions for Mutations

For form submissions and data mutations, we'll use Server Actions:

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
```

## Client-Side Queries with TanStack Query

For interactive data fetching, we'll continue using TanStack Query in client components:

```tsx
// src/components/organisms/SourcesList/index.tsx
'use client'

import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { SourcesService } from '@/lib/api/client'
import { useAuth } from '@/hooks/useAuth'

export function SourcesList() {
  const { token } = useAuth()
  const api = createClientApi(token)
  
  const { data, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => SourcesService.getSources(api)
  })
  
  // Rest of component...
}
```

## OpenAPI Client Generation Updates

We'll need to update the OpenAPI client generation to support both server and client environments:

```ts
// openapi-ts.config.ts
import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: './openapi.json',
  output: './src/lib/api/generated',
  client: 'fetch',
  target: 'typescript',
  useOptions: true,
  // Additional configuration...
})
```