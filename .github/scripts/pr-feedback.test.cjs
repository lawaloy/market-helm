const assert = require('node:assert/strict');
const test = require('node:test');

const {
  describeFeedbackBlockers,
  feedbackBlockers,
  hasFeedbackBlockers,
} = require('./pr-feedback.cjs');

const stickyE2eComment = {
  user: { login: 'github-actions[bot]' },
  body: '<!-- Sticky Pull Request Commente2e-smoke-PR E2E -->',
};

test('later CHANGES_REQUESTED after APPROVED still blocks merge', () => {
  const blockers = feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'reviewer' },
        state: 'APPROVED',
        submitted_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 2,
        user: { login: 'reviewer' },
        state: 'CHANGES_REQUESTED',
        submitted_at: '2026-01-01T00:01:00Z',
      },
    ],
    threads: [],
  });
  assert.equal(blockers.changeRequests.length, 1);
  assert.equal(hasFeedbackBlockers(blockers), true);
});

test('one reviewer approving does not drop another reviewer change request', () => {
  const blockers = feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'approver' },
        state: 'APPROVED',
        submitted_at: '2026-01-01T00:02:00Z',
      },
      {
        id: 2,
        user: { login: 'requester' },
        state: 'CHANGES_REQUESTED',
        submitted_at: '2026-01-01T00:00:00Z',
      },
    ],
    threads: [],
  });
  assert.equal(blockers.changeRequests.length, 1);
  assert.equal(blockers.changeRequests[0].user.login, 'requester');
  assert.equal(hasFeedbackBlockers(blockers), true);
});

test('dismissing a change request clears it without a later approval', () => {
  const blockers = feedbackBlockers({
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
        state: 'DISMISSED',
        submitted_at: '2026-01-01T00:01:00Z',
      },
    ],
    threads: [],
  });
  assert.equal(blockers.changeRequests.length, 0);
  assert.equal(hasFeedbackBlockers(blockers), false);
});

test('whitespace-only COMMENTED review bodies are not merge blockers', () => {
  const blockers = feedbackBlockers({
    comments: [],
    reviews: [
      {
        id: 1,
        user: { login: 'reviewer' },
        state: 'COMMENTED',
        body: '   \n\t  ',
        submitted_at: '2026-01-01T00:00:00Z',
      },
    ],
    threads: [],
  });
  assert.deepEqual(blockers.reviewBodies, []);
  assert.equal(hasFeedbackBlockers(blockers), false);
});

test('Codex-like COMMENTED bodies that miss the wrapper regex still block', () => {
  const actionable = {
    id: 1,
    user: { login: 'chatgpt-codex-connector[bot]' },
    state: 'COMMENTED',
    body:
      '### Codex Review\n\n' +
      'Please fix the SSRF case before merging.\n\n' +
      '**Reviewed commit:** `abc123`',
    submitted_at: '2026-01-01T00:00:00Z',
  };
  const blockers = feedbackBlockers({
    comments: [],
    reviews: [actionable],
    threads: [],
  });
  assert.deepEqual(blockers.reviewBodies, [actionable]);
  assert.equal(hasFeedbackBlockers(blockers), true);
});

test('only the E2E sticky comment with resolved threads is clear to merge', () => {
  const blockers = feedbackBlockers({
    comments: [stickyE2eComment],
    reviews: [],
    threads: [{ isResolved: true }],
  });
  assert.equal(hasFeedbackBlockers(blockers), false);
  assert.match(
    describeFeedbackBlockers(blockers),
    /^0 change request\(s\), 0 actionable review body\/bodies, 0 unresolved thread\(s\), 0 non-informational conversation comment\(s\)$/,
  );
});

test('unresolved review threads block even when conversation is empty', () => {
  const blockers = feedbackBlockers({
    comments: [stickyE2eComment],
    reviews: [],
    threads: [{ isResolved: false }],
  });
  assert.equal(blockers.unresolvedThreads.length, 1);
  assert.equal(blockers.conversation.length, 0);
  assert.equal(hasFeedbackBlockers(blockers), true);
});
