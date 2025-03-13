# Next.js 15 Migration Plan

## Current Architecture
- Vite + React + TypeScript frontend
- TanStack Router for routing
- Chakra UI component library
- TanStack Query for data fetching
- Atomic design pattern (atoms/molecules/organisms)
- Biome for linting and formatting
- Playwright for end-to-end testing

## Migration Steps

### 1. Setup Next.js 15 Project Structure
- Initialize new Next.js 15 project
- Configure TypeScript and linting
- Configure path aliases to match current project
- Setup environment variables

### 2. Migrate Routing
- Convert TanStack Router routes to Next.js App Router
- Adapt layout components to Next.js conventions
- Implement route protection in new middleware
- Create dynamic route segments

### 3. Migrate Components
- Adapt Chakra UI setup for Next.js
- Convert components to support React Server Components where appropriate
- Move components into new Next.js structure

### 4. Migrate State Management
- Adapt TanStack Query to work with Server Components
- Setup provider architecture for client components
- Configure client-side authentication state

### 5. Migrate API Integration
- Update API client generation for Next.js
- Implement server-side API fetching where possible
- Setup client-side API patterns where needed

### 6. Testing & Validation
- Update Playwright configuration for Next.js
- Adapt existing tests to work with new structure
- Add new tests for Next.js specific features

### 7. Build & Deploy
- Configure Next.js build process
- Set up deployment configuration
- Update Docker configuration

## Key Differences to Address
- Client Components vs Server Components
- Data fetching patterns (RSC vs client-side)
- File-based routing structure
- Authentication flow changes
- Environment variable handling