#!/usr/bin/env node
/**
 * Run ``npm audit --audit-level=high`` with retries for registry outages.
 *
 * Transient registry/network failures are retried, but a persistent outage fails
 * closed. High-severity findings also fail immediately (without a retry).
 */

const { spawnSync } = require('node:child_process');

const isRetryableAuditFailure = (output) =>
  /\b429\b|\b5\d\d\b|service unavailable|audit endpoint returned an error|eai_again|econnrefused|econnreset|etimedout|enotfound|socket hang up/i.test(
    output || '',
  );

const runNpmAudit = ({
  spawn = spawnSync,
  maxAttempts = 3,
  sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms),
  args = ['audit', '--audit-level=high', '--fetch-retries=2'],
} = {}) => {
  let lastOutput = '';
  let lastStatus = 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const result = spawn('npm', args, {
      encoding: 'utf8',
      shell: false,
    });
    lastOutput = `${result.stdout || ''}${result.stderr || ''}`;
    lastStatus = result.status == null ? 1 : result.status;
    if (lastStatus === 0) {
      return { ok: true, output: lastOutput, attempts: attempt };
    }
    if (!isRetryableAuditFailure(lastOutput) || attempt === maxAttempts) {
      return {
        ok: false,
        output: lastOutput,
        attempts: attempt,
        status: lastStatus,
      };
    }
    sleep(attempt * 15000);
  }
  return {
    ok: false,
    output: lastOutput,
    attempts: maxAttempts,
    status: lastStatus,
  };
};

if (require.main === module) {
  const result = runNpmAudit();
  process.stdout.write(result.output);
  if (!result.ok) {
    const title = isRetryableAuditFailure(result.output)
      ? 'npm registry unavailable after retries'
      : 'npm audit found vulnerabilities or failed';
    process.stderr.write(
      `::error title=${title}::See the npm audit output and uploaded debug log.\n`,
    );
    process.exit(result.status || 1);
  }
}

module.exports = {
  isRetryableAuditFailure,
  runNpmAudit,
};
