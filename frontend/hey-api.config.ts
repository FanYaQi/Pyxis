// import './envConfig.ts'
import type { CreateClientConfig } from './src/client/client.gen.js';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: process.env.NEXT_PUBLIC_API_URL,
});
