const REQUIRED_CHECKS = [
  'Python',
  'PostgreSQL integration',
  'Dashboard frontend',
  'Analyze (actions)',
  'Analyze (javascript-typescript)',
  'Analyze (python)',
  'Compose + PostgreSQL operations',
  'Curl + Playwright',
  'update-description',
];

const CURSOR_PREFIX = 'Cursor Automation:';
const ACCEPTABLE_CURSOR_CONCLUSIONS = new Set(['success', 'neutral', 'skipped']);
const OWN_CHECKS = new Set([
  'Final automation gate',
  'Dependabot Auto Finish',
  'Dependency Maintenance Auto Finish',
  'Post-release Auto Finish',
]);

const hasSuccessfulAdvancedCodeQl = (checkRuns) =>
  checkRuns.some(
    (run) =>
      run.name?.startsWith('Analyze (') &&
      run.status === 'completed' &&
      run.conclusion === 'success',
  );

const isIgnoredCheck = (run, checkRuns) =>
  OWN_CHECKS.has(run.name) ||
  (run.name === 'CodeQL' && hasSuccessfulAdvancedCodeQl(checkRuns));

const classifyCheckRuns = (checkRuns) => {
  const relevant = checkRuns.filter((run) => !isIgnoredCheck(run, checkRuns));
  const missing = REQUIRED_CHECKS.filter(
    (name) => !relevant.some((run) => run.name === name),
  );
  const pending = relevant.filter(
    (run) => run.status === 'queued' || run.status === 'in_progress',
  );
  const unacceptable = relevant.filter((run) => {
    if (run.status !== 'completed') return false;
    if (run.name?.startsWith(CURSOR_PREFIX)) {
      return !ACCEPTABLE_CURSOR_CONCLUSIONS.has(run.conclusion);
    }
    return run.conclusion !== 'success';
  });
  const cursor = relevant.filter((run) => run.name?.startsWith(CURSOR_PREFIX));

  return { missing, pending, unacceptable, cursor };
};

const isInformationalConversationComment = (comment) => {
  const login = comment.user?.login || '';
  const body = comment.body || '';
  return (
    ['github-actions[bot]', 'app/github-actions'].includes(login) &&
    body.includes('<!-- Sticky Pull Request Commente2e-smoke-PR E2E -->')
  );
};

const feedbackBlockers = ({ comments, reviews, threads }) => {
  const latestReviews = new Map();
  for (const review of reviews) {
    const login = review.user?.login || `review-${review.id}`;
    const previous = latestReviews.get(login);
    if (!previous || String(review.submitted_at) > String(previous.submitted_at)) {
      latestReviews.set(login, review);
    }
  }

  const changeRequests = [...latestReviews.values()].filter(
    (review) => review.state === 'CHANGES_REQUESTED',
  );
  const unresolvedThreads = threads.filter((thread) => !thread.isResolved);
  const conversation = comments.filter(
    (comment) => !isInformationalConversationComment(comment),
  );

  return { changeRequests, unresolvedThreads, conversation };
};

const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

const checkRunsFromPage = (response) => {
  const data = response.data;
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.check_runs)) return data.check_runs;
  return [];
};

const threadQuery = `
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          nodes { isResolved }
        }
      }
    }
  }
`;

const runGate = async ({ github, context, core }) => {
  const pull_number = Number(process.env.PULL_NUMBER || 0);
  const expectedHeadSha = process.env.EXPECTED_HEAD_SHA || '';
  const { owner, repo } = context.repo;
  const maxAttempts = 90;
  const delayMs = 5000;
  const optionalDiscoveryMs = 120000;
  let requiredReadyAt = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const pullRequest = (
      await github.rest.pulls.get({ owner, repo, pull_number })
    ).data;
    const author = pullRequest.user?.login || '';
    const trusted =
      pullRequest.state === 'open' &&
      pullRequest.head?.repo?.full_name === `${owner}/${repo}` &&
      pullRequest.base?.ref === 'main' &&
      /^chore\/post-release-sync-\d+\.\d+\.\d+$/.test(pullRequest.head?.ref || '') &&
      ['market-helm[bot]', 'app/market-helm'].includes(author);

    if (!trusted) {
      core.setFailed('PR no longer satisfies trusted post-release provenance.');
      return;
    }
    if (pullRequest.head.sha !== expectedHeadSha) {
      core.setFailed('PR head changed while the final gate was running.');
      return;
    }

    const checkRuns = await github.paginate(
      github.rest.checks.listForRef,
      { owner, repo, ref: expectedHeadSha, per_page: 100 },
      checkRunsFromPage,
    );
    const state = classifyCheckRuns(checkRuns);

    if (state.unacceptable.length > 0) {
      core.setFailed(
        `Unacceptable check conclusion(s): ${state.unacceptable
          .map((run) => `${run.name}=${run.conclusion}`)
          .join(', ')}`,
      );
      return;
    }

    if (state.missing.length > 0 || state.pending.length > 0) {
      requiredReadyAt = null;
      core.info(
        `Attempt ${attempt}/${maxAttempts}: missing=[${state.missing.join(', ')}] ` +
          `pending=[${state.pending.map((run) => run.name).join(', ')}]`,
      );
    } else {
      requiredReadyAt ||= Date.now();
      const discoveryElapsed = Date.now() - requiredReadyAt;
      if (state.cursor.length === 0 && discoveryElapsed < optionalDiscoveryMs) {
        core.info(
          `Required checks passed; allowing ${Math.ceil(
            (optionalDiscoveryMs - discoveryElapsed) / 1000,
          )}s for optional Cursor checks to appear.`,
        );
      } else {
        const comments = await github.paginate(github.rest.issues.listComments, {
          owner,
          repo,
          issue_number: pull_number,
          per_page: 100,
        });
        const reviews = await github.paginate(github.rest.pulls.listReviews, {
          owner,
          repo,
          pull_number,
          per_page: 100,
        });
        const threadResult = await github.graphql(threadQuery, {
          owner,
          repo,
          number: pull_number,
        });
        const threads =
          threadResult.repository.pullRequest.reviewThreads.nodes || [];
        const blockers = feedbackBlockers({ comments, reviews, threads });

        if (
          blockers.changeRequests.length > 0 ||
          blockers.unresolvedThreads.length > 0 ||
          blockers.conversation.length > 0
        ) {
          core.setFailed(
            'Feedback requires manual resolution: ' +
              `${blockers.changeRequests.length} change request(s), ` +
              `${blockers.unresolvedThreads.length} unresolved thread(s), ` +
              `${blockers.conversation.length} non-informational conversation comment(s).`,
          );
          return;
        }

        await core.summary
          .addHeading('Post-release final gate')
          .addRaw(`Head SHA: \`${expectedHeadSha}\`\n\n`)
          .addRaw('Required checks: passed\n\n')
          .addRaw(
            `Cursor: ${
              state.cursor.length === 0
                ? 'not available (acceptable)'
                : state.cursor.map((run) => run.conclusion).join(', ')
            }\n\n`,
          )
          .addRaw('Feedback: clear')
          .write();
        core.info('Final automation gate passed.');
        return;
      }
    }

    if (attempt === maxAttempts) {
      core.setFailed(
        'Final gate timed out before all expected checks became terminal. ' +
          'Use the post-release workflow_dispatch recovery after investigating.',
      );
      return;
    }
    await sleep(delayMs);
  }
};

module.exports = runGate;
module.exports._test = {
  classifyCheckRuns,
  feedbackBlockers,
  isInformationalConversationComment,
};
