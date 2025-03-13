# Next.js 15 Migration Plan

This directory contains a comprehensive plan for migrating the Pyxis frontend from Vite/React to Next.js 15.

## Migration Documents

1. **Overview** - High-level summary of the migration approach
2. **Setup** - Initial project setup and configuration
3. **Routing** - Converting TanStack Router to Next.js App Router
4. **Components** - Migrating components to support Server Components
5. **Data Fetching** - Updating data fetching patterns for Next.js
6. **Authentication** - Moving to a more secure authentication system
7. **Testing** - Adapting the testing framework for Next.js
8. **Deployment** - Updating deployment configuration
9. **Implementation Steps** - Detailed step-by-step migration plan

## Key Benefits of Migration

- **Performance**: Server components reduce client-side JavaScript
- **SEO**: Better SEO with server-side rendering
- **Security**: Enhanced authentication with HTTP-only cookies
- **Developer Experience**: Simplified data fetching with Server Components
- **Scalability**: Better support for large applications with App Router
- **Maintenance**: Alignment with modern React patterns

## Getting Started

Begin by reading the `01-overview.md` document to understand the high-level migration approach. Then, follow the implementation steps in `09-implementation-steps.md` to execute the migration plan.

## Tools & Libraries

- Next.js 15
- React 18
- TypeScript
- Chakra UI
- TanStack Query
- Biome for linting
- Playwright for testing

## Contact

For questions or clarification about this migration plan, contact the project maintainers.