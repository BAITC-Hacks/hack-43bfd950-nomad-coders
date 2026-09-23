import { defineConfig } from '@playwright/test'
import path from 'node:path'

const python = path.resolve('..', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const publicUrl = process.env.NOMAD_E2E_URL
export default defineConfig({
  testDir: './tests',
  testMatch: publicUrl ? '**/public-demo.spec.ts' : ['**/interface.spec.ts', '**/workflow.spec.ts'],
  workers: 1,
  use: { baseURL: publicUrl || 'http://127.0.0.1:8009', browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: publicUrl ? undefined : {
    command: '"' + python + '" ../backend/scripts/e2e_server.py',
    url: 'http://127.0.0.1:8009/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
