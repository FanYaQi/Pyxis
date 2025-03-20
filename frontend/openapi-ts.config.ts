// import { defaultPlugins } from '@hey-api/openapi-ts';
import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",
  plugins: [
    "@hey-api/typescript",
    {
      name: "@hey-api/sdk",
      operationId: true,
      // NOTE: this doesn't allow tree-shaking
      asClass: true,
      methodNameBuilder: (operation) => {
        // @ts-ignore
        let tag = operation.tags[0]
        // @ts-ignore
        let name = operation.id.slice(tag.length)
        return name.charAt(0).toLowerCase() + name.slice(1)
      },
    },
    {
      name: "@hey-api/client-next",
      runtimeConfigPath: './hey-api.config.ts', 
    },
    "@tanstack/react-query",
  ],
})
