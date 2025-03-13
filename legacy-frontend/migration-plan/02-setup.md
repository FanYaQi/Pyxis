# Next.js Project Setup

## Project Initialization

First, we'll create a new Next.js 15 project in a temporary directory so we can migrate the codebase incrementally:

```bash
# Create a new directory for Next.js project
mkdir nextjs-pyxis

# Initialize Next.js project
npx create-next-app@latest nextjs-pyxis
```

During setup, we'll select these options:
- TypeScript: Yes
- ESLint: Yes
- Tailwind CSS: No (we'll use Chakra UI)
- src/ directory: Yes
- App Router: Yes
- Import aliases: Yes

## Dependencies to Install

We'll need to install the current dependencies that are compatible with Next.js:

```bash
cd nextjs-pyxis

# Core dependencies
npm install @chakra-ui/react @emotion/react axios form-data react-error-boundary react-hook-form react-icons

# Dev dependencies
npm install --save-dev @biomejs/biome @hey-api/openapi-ts @playwright/test typescript @types/node @types/react @types/react-dom dotenv
```

## Configuration Files

### Next.js Config
Create `next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: [],
  },
  // Add any additional configuration needed
};

export default nextConfig;
```

### TypeScript Config
Update `tsconfig.json` to match the current path aliases:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/atoms/*": ["./src/components/atoms/*"],
      "@/molecules/*": ["./src/components/molecules/*"],
      "@/organisms/*": ["./src/components/organisms/*"],
      "@/ui/*": ["./src/components/ui/*"],
      "@/hooks/*": ["./src/hooks/*"],
      "@/utils/*": ["./src/utils/*"],
      "@/styles/*": ["./src/styles/*"],
      "@/types/*": ["./src/types/*"],
      "@/client/*": ["./src/client/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### Biome Config
Copy the current `biome.json` to maintain consistent formatting:

```json
{
  "$schema": "https://biomejs.dev/schemas/1.6.1/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "files": {
    "ignore": [
      "node_modules",
      ".next"
    ]
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "suspicious": {
        "noExplicitAny": "off",
        "noArrayIndexKey": "off"
      },
      "style": {
        "noNonNullAssertion": "off"
      }
    }
  },
  "formatter": {
    "indentStyle": "space"
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "asNeeded"
    }
  }
}
```