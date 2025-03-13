# CLAUDE.md - Guide for Frontend Development

## Build/Run/Test Commands
- Development server: `npm run dev`
- Build: `npm run build`
- Lint and format: `npm run lint`
- Run all tests: `npx playwright test`
- Run specific test: `npx playwright test tests/login.spec.ts`
- Run specific test case: `npx playwright test -g "Log in with valid email and password"`
- Generate API client: `npm run generate-client`

## Code Style Guidelines
- **Imports**: Organized imports with @biomejs/biome
- **Formatting**: Space indentation, double quotes, semicolons as needed (Biome formatter)
- **Components**: Atomic design pattern (atoms, molecules, organisms)
- **TypeScript**: Strict type checking, proper interfaces and types
- **Paths**: Use aliases (@/components/*, @/hooks/*, etc.)
- **React**: Functional components with hooks
- **Linting**: Allow noExplicitAny, noArrayIndexKey, noNonNullAssertion exceptions

## Project Structure
- `/src/components`: UI components organized by atomic design
- `/src/hooks`: Custom React hooks
- `/src/routes`: Router definitions and page components
- `/src/store`: Global state management
- `/src/utils`: Utility functions
- `/src/types`: TypeScript type definitions
- `/tests`: Playwright end-to-end tests

## Tech Stack
- React with TypeScript
- Vite for bundling
- TanStack Query for data fetching
- TanStack Router for routing
- Chakra UI for components
- Biome for linting/formatting
- Playwright for testing