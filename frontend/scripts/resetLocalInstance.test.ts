// @vitest-environment node

import { execFileSync } from 'node:child_process';
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter as pathDelimiter, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, '..', '..');
const resetScript = join(repoRoot, 'scripts', 'reset_local_instance.sh');

function runReset(args: string[] = [], env: NodeJS.ProcessEnv = {}): string {
  return execFileSync(resetScript, args, {
    cwd: repoRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      ...env,
    },
  });
}

function createFakeCommandBin(): { binDir: string; logPath: string } {
  const dir = mkdtempSync(join(tmpdir(), 'enclave-reset-fakes-'));
  const binDir = join(dir, 'bin');
  const logPath = join(dir, 'commands.log');

  execFileSync('mkdir', ['-p', binDir]);
  writeFileSync(logPath, '');

  const docker = `#!/usr/bin/env bash
set -euo pipefail
printf 'docker' >> "${logPath}"
for arg in "$@"; do printf ' %s' "$arg" >> "${logPath}"; done
printf '\\n' >> "${logPath}"
if [[ "$*" == "compose -f docker-compose.infra.yml -f docker-compose.app.yml config --volumes" ]]; then
  printf 'sage_workspace\\nembedding_cache\\nsqlite_data\\nsage_postgres_data\\nqdrant_data\\n'
fi
`;
  const curl = `#!/usr/bin/env bash
set -euo pipefail
printf 'curl' >> "${logPath}"
for arg in "$@"; do printf ' %s' "$arg" >> "${logPath}"; done
printf '\\n' >> "${logPath}"
if [[ "\${FAIL_CURL_URL:-}" != "" && "$*" == *"\${FAIL_CURL_URL}"* ]]; then
  exit 22
fi
`;
  const lsof = `#!/usr/bin/env bash
set -euo pipefail
printf 'lsof' >> "${logPath}"
for arg in "$@"; do printf ' %s' "$arg" >> "${logPath}"; done
printf '\\n' >> "${logPath}"
`;

  for (const [name, source] of Object.entries({ docker, curl, lsof })) {
    const path = join(binDir, name);
    writeFileSync(path, source);
    chmodSync(path, 0o755);
  }

  return { binDir, logPath };
}

function runWithFakes(args: string[] = [], env: NodeJS.ProcessEnv = {}) {
  const { binDir, logPath } = createFakeCommandBin();
  const output = runReset(args, {
    PATH: `${binDir}${pathDelimiter}${process.env.PATH ?? ''}`,
    ...env,
  });

  return { output, log: readFileSync(logPath, 'utf8') };
}

describe('local instance reset script', () => {
  it('resets runtime volumes and preserves the embedding cache by default', () => {
    const output = runReset(['--dry-run']);

    expect(output).toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down'
    );
    expect(output).toContain(
      'docker volume rm enclavefree-prototype_qdrant_data'
    );
    expect(output).toContain(
      'docker volume rm enclavefree-prototype_sage_postgres_data'
    );
    expect(output).toContain(
      'docker volume rm enclavefree-prototype_sage_workspace'
    );
    expect(output).toContain(
      'docker volume rm enclavefree-prototype_sqlite_data'
    );
    expect(output).not.toContain(
      'docker volume rm enclavefree-prototype_embedding_cache'
    );
    expect(output).toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d'
    );
    expect(output).toContain('curl -fsS http://localhost:8000/test');
    expect(output).toContain('curl -fsS http://localhost:8000/llm/test');
  });

  it('executes the default reset and smoke check workflow', () => {
    const { log } = runWithFakes();

    expect(log).toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down'
    );
    expect(log).toContain('docker volume rm enclavefree-prototype_qdrant_data');
    expect(log).toContain(
      'docker volume rm enclavefree-prototype_sage_postgres_data'
    );
    expect(log).toContain(
      'docker volume rm enclavefree-prototype_sage_workspace'
    );
    expect(log).toContain('docker volume rm enclavefree-prototype_sqlite_data');
    expect(log).not.toContain(
      'docker volume rm enclavefree-prototype_embedding_cache'
    );
    expect(log).toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d'
    );
    expect(log).toContain('lsof -nP -iTCP:8000 -sTCP:LISTEN');
    expect(log).toContain('curl -fsS http://localhost:8000/test');
    expect(log).toContain('curl -fsS http://localhost:8000/llm/test');
  });

  it('can reset every local volume including the embedding cache', () => {
    const { log } = runWithFakes(['--all']);

    expect(log).toContain(
      'docker volume rm enclavefree-prototype_embedding_cache'
    );
  });

  it('can start existing images without rebuilding', () => {
    const { log } = runWithFakes(['--no-build']);

    expect(log).toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d'
    );
    expect(log).not.toContain(
      'docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d'
    );
  });

  it('can skip smoke checks', () => {
    const { log } = runWithFakes(['--skip-smoke']);

    expect(log).not.toContain('curl -fsS http://localhost:8000/test');
    expect(log).not.toContain('curl -fsS http://localhost:8000/llm/test');
  });

  it('fails when a smoke check fails', () => {
    expect(() =>
      runWithFakes([], { FAIL_CURL_URL: 'http://localhost:8000/llm/test' })
    ).toThrow();
  });
});
