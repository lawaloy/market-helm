const assert = require('node:assert/strict');
const test = require('node:test');

const { _test } = require('./pr-final-gate.cjs');

const requiredSuccesses = [
  'Python',
  'PostgreSQL integration',
  'Dashboard frontend',
  'Analyze (actions)',
  'Analyze (javascript-typescript)',
  'Analyze (python)',
  'Compose + PostgreSQL operations',
  'Curl + Playwright',
  'update-description',
].map((name) => ({ name, status: 'completed', conclusion: 'success' }));

test('accepts absent Cursor after required checks pass', () => {
  const state = _test.classifyCheckRuns(requiredSuccesses);
  assert.deepEqual(state.missing, []);
  assert.deepEqual(state.pending, []);
  assert.deepEqual(state.unacceptable, []);
  assert.equal(state.cursor.length, 0);
});

test('waits for a present Cursor check', () => {
  const state = _test.classifyCheckRuns([
    ...requiredSuccesses,
    {
      name: 'Cursor Automation: Find critical bugs',
      status: 'in_progress',
      conclusion: null,
    },
  ]);
  assert.deepEqual(state.pending.map((run) => run.name), [
    'Cursor Automation: Find critical bugs',
  ]);
});

test('accepts neutral Cursor and rejects failed repository checks', () => {
  const neutral = _test.classifyCheckRuns([
    ...requiredSuccesses,
    {
      name: 'Cursor Automation: Find critical bugs',
      status: 'completed',
      conclusion: 'neutral',
    },
  ]);
  assert.deepEqual(neutral.unacceptable, []);

  const skipped = _test.classifyCheckRuns([
    ...requiredSuccesses,
    {
      name: 'Cursor Automation: Add test coverage',
      status: 'completed',
      conclusion: 'skipped',
    },
  ]);
  assert.deepEqual(skipped.unacceptable, []);

  const failed = _test.classifyCheckRuns([
    ...requiredSuccesses.filter((run) => run.name !== 'Python'),
    { name: 'Python', status: 'completed', conclusion: 'failure' },
  ]);
  assert.deepEqual(failed.unacceptable.map((run) => run.name), ['Python']);
});

test('reports missing required checks', () => {
  const state = _test.classifyCheckRuns(
    requiredSuccesses.filter((run) => run.name !== 'Curl + Playwright'),
  );
  assert.deepEqual(state.missing, ['Curl + Playwright']);
});

test('allows only the E2E sticky conversation comment', () => {
  const informational = {
    user: { login: 'github-actions[bot]' },
    body: '<!-- Sticky Pull Request Commente2e-smoke-PR E2E -->',
  };
  const actionable = {
    user: { login: 'review-bot[bot]' },
    body: 'Please address this issue.',
  };
  const blockers = _test.feedbackBlockers({
    comments: [informational, actionable],
    reviews: [],
    threads: [],
  });
  assert.deepEqual(blockers.conversation, [actionable]);
});

test('preserves a change request across a later COMMENTED review', () => {
  const blockers = _test.feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'reviewer' },
        state: 'CHANGES_REQUESTED',
        submitted_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 2,
        user: { login: 'reviewer' },
        state: 'COMMENTED',
        submitted_at: '2026-01-01T00:01:00Z',
      },
    ],
    threads: [{ isResolved: false }, { isResolved: true }],
  });
  assert.equal(blockers.changeRequests.length, 1);
  assert.equal(blockers.unresolvedThreads.length, 1);
});

test('clears a change request only with a later decisive review', () => {
  const blockers = _test.feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'reviewer' },
        state: 'CHANGES_REQUESTED',
        submitted_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 2,
        user: { login: 'reviewer' },
        state: 'APPROVED',
        submitted_at: '2026-01-01T00:01:00Z',
      },
    ],
    threads: [],
  });
  assert.equal(blockers.changeRequests.length, 0);
});

test('blocks substantive COMMENTED review bodies without inline threads', () => {
  const actionable = {
    id: 1,
    user: { login: 'reviewer' },
    state: 'COMMENTED',
    body: 'Please handle the backward-compatibility case before merging.',
    submitted_at: '2026-01-01T00:00:00Z',
  };
  const blockers = _test.feedbackBlockers({
    comments: [],
    reviews: [actionable],
    threads: [],
  });
  assert.deepEqual(blockers.reviewBodies, [actionable]);
});

test('allows the Codex wrapper while inline findings are tracked as threads', () => {
  const blockers = _test.feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'chatgpt-codex-connector[bot]' },
        state: 'COMMENTED',
        body:
          '### 💡 Codex Review\n\n' +
          'Here are some automated review suggestions for this pull request.\n\n' +
          '**Reviewed commit:** `abc123`\n\n' +
          '<details><summary>About Codex</summary>Info</details>',
        submitted_at: '2026-01-01T00:00:00Z',
      },
    ],
    threads: [{ isResolved: true }],
  });
  assert.equal(blockers.reviewBodies.length, 0);
});
