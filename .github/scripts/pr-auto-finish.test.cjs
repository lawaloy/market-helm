const assert = require('node:assert/strict');
const test = require('node:test');

const finish = require('./pr-auto-finish.cjs');

test('post-release lane blocks feedback found immediately before merge', async () => {
  const originalLane = process.env.LANE;
  const originalPullNumber = process.env.PULL_NUMBER;
  process.env.LANE = 'post-release';
  process.env.PULL_NUMBER = '605';

  let mergeCalled = false;
  let failure = '';
  const pullRequest = {
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
  const listForRef = () => {};
  const listComments = () => {};
  const listReviews = () => {};
  const github = {
    rest: {
      checks: { listForRef },
      issues: { listComments },
      pulls: {
        get: async () => ({ data: pullRequest }),
        listReviews,
        merge: async () => {
          mergeCalled = true;
        },
      },
    },
    paginate: async (route) => {
      if (route === listForRef) return [];
      if (route === listComments) {
        return [
          {
            user: { login: 'reviewer' },
            body: 'Please address this late concern.',
          },
        ];
      }
      if (route === listReviews) return [];
      throw new Error('Unexpected pagination route');
    },
    graphql: async () => ({
      repository: { pullRequest: { reviewThreads: { nodes: [] } } },
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

  assert.equal(mergeCalled, false);
  assert.match(failure, /feedback received before merge/);
});
