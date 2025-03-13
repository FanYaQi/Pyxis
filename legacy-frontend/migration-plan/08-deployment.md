# Deployment Configuration

## Current Deployment

The current project uses:
- Vite for development and production builds
- Docker for containerization
- Nginx for serving static files and proxying API requests

## Next.js Deployment Approach

We'll update the deployment configuration for Next.js:

1. Update Docker configuration
2. Configure environment variables
3. Set up build and start scripts
4. Configure deployment platform-specific settings

## Next.js Docker Configuration

Create an updated Dockerfile:

```dockerfile
# Dockerfile
FROM node:20-alpine AS base

# 1. Install dependencies only when needed
FROM base AS deps
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies based on the preferred package manager
COPY package.json package-lock.json* ./
RUN npm ci

# 2. Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Uncomment the following line in case you want to disable telemetry.
ENV NEXT_TELEMETRY_DISABLED 1

RUN npm run build

# 3. Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000

CMD ["node", "server.js"]
```

## Docker Compose Updates

Update Docker Compose configuration:

```yaml
# docker-compose.yml
version: '3'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
  
  backend:
    # Backend configuration remains the same
```

## Scripts Update

Update package.json scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "biome check --apply-unsafe --no-errors-on-unmatched --files-ignore-unknown=true ./",
    "generate-client": "openapi-ts"
  }
}
```

## Environment Variables

Create `.env.local` for local development:

```
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Create `.env.production` for production:

```
# .env.production
NEXT_PUBLIC_API_URL=/api
```

## next.config.mjs Updates

Configure API proxy for production:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Configure image domains if needed
  images: {
    domains: [],
  },
  // API proxy for development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
```

## Static File Handling

Update static file handling:

1. Move public assets to `/public` directory
2. Update references in components:

```tsx
// Before
<img src="/assets/images/pyxis-logo.svg" alt="Pyxis Logo" />

// After
import Image from 'next/image'

// In component
<Image src="/assets/images/pyxis-logo.svg" alt="Pyxis Logo" width={100} height={50} />
```

## Deployment Platforms

### Vercel

For Vercel deployment:

1. Connect GitHub repository
2. Configure environment variables
3. Deploy with default settings

### AWS

For AWS deployment:

1. Configure AWS Amplify or Elastic Beanstalk
2. Set up environment variables
3. Configure custom domain

### Self-Hosted

For self-hosted deployment:

1. Set up reverse proxy (Nginx)
```nginx
# nginx.conf
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

2. Configure SSL with Certbot
3. Set up process manager (PM2)
```json
// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: 'pyxis-frontend',
      script: 'npm',
      args: 'start',
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
};
```