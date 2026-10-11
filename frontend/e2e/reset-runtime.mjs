import { mkdirSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const runtimeDir = resolve(dirname(fileURLToPath(import.meta.url)), '../test-results/runtime')

rmSync(runtimeDir, { recursive: true, force: true })
mkdirSync(runtimeDir, { recursive: true })
console.log(`Prepared isolated E2E runtime: ${runtimeDir}`)
