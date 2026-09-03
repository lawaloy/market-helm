const assert = require('node:assert/strict');
const test = require('node:test');

const finish = require('./pr-auto-finish.cjs');

const trustedPostReleasePr = {
  state: 'open',
  mergeable_state: 'clean',
  user: { login: 'market-helm[bot]' },
  head: {
    ref: 'chore/post-release-sync-1.2.3',
    sha: 'head-sha',
    repo: { full_name: 'lawaloy/market-helm' },
  },
  base: { ref: 'main' },
  labels: [],
};

const stickyE2eComment = {
  user: { login: 'github-actions[bot]' },
  body: '<!-- Sticky Pull Request Commente2e-smoke-PR E2E -->',
};

const codexWrapperReview = {
  id: 1,
  user: { login: 'chatgpt-codex-connector[bot]' },
  state: 'COMMENTED',
  body:
    '### 💡 Codex Review\n\n' +
    'Here are some automated review suggestions for this pull request.\n\n' +
    '**Reviewed commit:** `abc123`\n\n' +
    '<details><summary>About Codex</summary>Info</details>',
  submitted_at: '2026-01-01T00:00:00Z',
};

const runPostReleaseFinish = async ({ comments, reviews, threads }) => {
  const originalLane = process.env.LANE;
  const originalPullNumber = process.env.PULL_NUMBER;
  process.env.LANE = 'post-release';
  process.env.PULL_NUMBER = '605';

  let mergeCalled = false;
  let failure = '';
  const listForRef = () => {};
  const listComments = () => {};
  const listReviews = () => {};
  const github = {
    rest: {
      checks: { listForRef },
      issues: { listComments },
      pulls: {
        get: async () => ({ data: trustedPostReleasePr }),
        listReviews,
        merge: async () => {
          mergeCalled = true;
        },
      },
    },
    paginate: async (route) => {
      if (route === listForRef) return [];
      if (route === listComments) return comments;
      if (route === listReviews) return reviews;
      throw new Error('Unexpected pagination route');
    },
    graphql: async () => ({
      repository: {
        pullRequest: { reviewThreads: { nodes: threads } },
      },
    }),
  };
  const core = {
    info: () => {},
    setFailed: (message) => {
      failure = message;
    },
  };

  try {
    await finish({
      github,
      context: { payload: {}, repo: { owner: 'lawaloy', repo: 'market-helm' } },
      core,
    });
  } finally {
    if (originalLane === undefined) delete process.env.LANE;
    else process.env.LANE = originalLane;
    if (originalPullNumber === undefined) delete process.env.PULL_NUMBER;
    else process.env.PULL_NUMBER = originalPullNumber;
  }

  return { mergeCalled, failure };
};

test('post-release lane blocks feedback found immediately before merge', async () => {
  const { mergeCalled, failure } = await runPostReleaseFinish({
    comments: [
      {
        user: { login: 'reviewer' },
        body: 'Please address this late concern.',
      },
    ],
    reviews: [],
    threads: [],
  });

  assert.equal(mergeCalled, false);
  assert.match(failure, /feedback received before merge/);
});

test('post-release lane blocks unresolved threads with no conversation comments', async () => {
  const { mergeCalled, failure } = await runPostReleaseFinish({
    comments: [stickyE2eComment],
    reviews: [],
    threads: [{ isResolved: false }],
  });

  assert.equal(mergeCalled, false);
  assert.match(failure, /feedback received before merge/);
  assert.match(failure, /1 unresolved thread/);
});

test('post-release lane merges when only informational feedback remains', async () => {
  const { mergeCalled, failure } = await runPostReleaseFinish({
    comments: [stickyE2eComment],
    reviews: [codexWrapperReview],
    threads: [{ isResolved: true }],
  });

  assert.equal(failure, '');
  assert.equal(mergeCalled, true);
});

