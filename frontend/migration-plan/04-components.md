# Components Migration

## Client vs Server Components

Next.js 15 introduces React Server Components (RSC). We'll need to identify which components should be:

1. **Server Components** (default in Next.js App Router):
   - Don't need interactivity
   - Fetch data directly from the server
   - Don't use browser-only APIs
   - Don't use React hooks

2. **Client Components** (must add `'use client'` directive):
   - Need interactivity (onClick, onChange, etc.)
   - Use hooks (useState, useEffect, etc.)
   - Use browser-only APIs (localStorage, etc.)
   - Need event listeners

## Chakra UI Setup for Next.js

Chakra UI requires client components. We'll set up a providers component:

```tsx
// src/components/ui/provider.tsx
'use client'

import { CacheProvider } from '@chakra-ui/next-js'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ErrorBoundary } from 'react-error-boundary'
import { theme } from '@/theme'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient())
  
  return (
    <ErrorBoundary fallback={<div>Something went wrong</div>}>
      <CacheProvider>
        <ChakraProvider theme={theme}>
          <QueryClientProvider client={queryClient}>
            {children}
            <ReactQueryDevtools initialIsOpen={false} />
          </QueryClientProvider>
        </ChakraProvider>
      </CacheProvider>
    </ErrorBoundary>
  )
}
```

## Layout Components Migration

Layout components need special attention:

```tsx
// src/components/Common/Navbar.tsx
'use client'

import { Box, Flex } from '@chakra-ui/react'
import { UserMenu } from './UserMenu'
// Rest of component...
```

```tsx
// src/components/Common/Sidebar.tsx
'use client'

import { Box, VStack } from '@chakra-ui/react'
import { SidebarItems } from './SidebarItems'
// Rest of component...
```

## Form Components

Forms will remain client components:

```tsx
// src/components/organisms/Account/LoginForm.tsx
'use client'

import { useForm } from 'react-hook-form'
import { useRouter } from 'next/navigation'
// Rest of component...
```

## Data Fetching Components

For components that fetch data, we'll use Server Components:

```tsx
// src/components/organisms/SourceDetails/index.tsx
import { getSourceDetails } from '@/lib/api'
import SourceDetailsClient from './SourceDetailsClient'

export default async function SourceDetails({ id }: { id: string }) {
  const data = await getSourceDetails(id)
  return <SourceDetailsClient data={data} />
}

// src/components/organisms/SourceDetails/SourceDetailsClient.tsx
'use client'

import { useState } from 'react'
// Interactive client component logic
```