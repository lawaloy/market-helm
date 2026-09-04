const assert = require('node:assert/strict');
const test = require('node:test');

const { isRetryableAuditFailure, runNpmAudit } = require('./npm-audit-ci.cjs');

test('registry 503 and audit endpoint errors are retryable', () => {
  assert.equal(
    isRetryableAuditFailure(
      'npm warn audit 503 Service Unavailable - POST https://registry.npmjs.org/-/npm/v1/security/audits/quick',
    ),
    true,
  );
  assert.equal(
    isRetryableAuditFailure('{ error: \'Service Unavailable\' }\nnpm error audit endpoint returned an error'),
    true,
  );
  assert.equal(isRetryableAuditFailure('npm error ETIMEDOUT'), true);
});

test('high-severity findings are not retryable', () => {
  assert.equal(
    isRetryableAuditFailure('found 2 high severity vulnerabilities in 10 scanned packages'),
    false,
  );
  assert.equal(isRetryableAuditFailure(''), false);
});

test('runNpmAudit retries a 503 then succeeds', () => {
  const calls = [];
  const spawn = () => {
    calls.push(true);
    if (calls.length === 1) {
      return {
        status: 1,
        stdout: '',
        stderr: 'npm warn audit 503 Service Unavailable\nnpm error audit endpoint returned an error',
      };
    }
    return { status: 0, stdout: 'found 0 vulnerabilities\n', stderr: '' };
  };
  const slept = [];
  const result = runNpmAudit({ spawn, sleep: (ms) => slept.push(ms) });
  assert.equal(result.ok, true);
  assert.equal(result.attempts, 2);
  assert.deepEqual(slept, [15000]);
});

test('runNpmAudit does not retry high-severity findings', () => {
  const spawn = () => ({
    status: 1,
    stdout: 'found 2 high severity vulnerabilities\n',
    stderr: '',
  });
  const slept = [];
  const result = runNpmAudit({ spawn, sleep: (ms) => slept.push(ms) });
  assert.equal(result.ok, false);
  assert.equal(result.attempts, 1);
  assert.deepEqual(slept, []);
});
