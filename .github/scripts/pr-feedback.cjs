const DECISIVE_REVIEW_STATES = new Set([
  'APPROVED',
  'CHANGES_REQUESTED',
  'DISMISSED',
]);

const isInformationalConversationComment = (comment) => {
  const login = comment.user?.login || '';
  const body = comment.body || '';
  return (
    ['github-actions[bot]', 'app/github-actions'].includes(login) &&
    body.includes('<!-- Sticky Pull Request Commente2e-smoke-PR E2E -->')
  );
};

const isInformationalReviewBody = (review) => {
  const login = review.user?.login || '';
  const body = (review.body || '').trim();
  return (
    login === 'chatgpt-codex-connector[bot]' &&
    /^### 💡 Codex Review\s+Here are some automated review suggestions for this pull request\.\s+\*\*Reviewed commit:\*\* `[^`]+`\s+<details>[\s\S]*<\/details>$/.test(
      body,
    )
  );
};

const feedbackBlockers = ({ comments, reviews, threads }) => {
  const latestDecisiveReviews = new Map();
  for (const review of reviews) {
    if (!DECISIVE_REVIEW_STATES.has(review.state)) continue;

    const login = review.user?.login || `review-${review.id}`;
    const previous = latestDecisiveReviews.get(login);
    if (!previous || String(review.submitted_at) > String(previous.submitted_at)) {
      latestDecisiveReviews.set(login, review);
    }
  }

  const changeRequests = [...latestDecisiveReviews.values()].filter(
    (review) => review.state === 'CHANGES_REQUESTED',
  );
  const reviewBodies = reviews.filter(
    (review) =>
      review.state === 'COMMENTED' &&
      Boolean(review.body?.trim()) &&
      !isInformationalReviewBody(review),
  );
  const unresolvedThreads = threads.filter((thread) => !thread.isResolved);
  const conversation = comments.filter(
    (comment) => !isInformationalConversationComment(comment),
  );

  return { changeRequests, reviewBodies, unresolvedThreads, conversation };
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

const inspectFeedback = async ({ github, owner, repo, pull_number }) => {
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

  return feedbackBlockers({ comments, reviews, threads });
};

const hasFeedbackBlockers = (blockers) =>
  blockers.changeRequests.length > 0 ||
  blockers.reviewBodies.length > 0 ||
  blockers.unresolvedThreads.length > 0 ||
  blockers.conversation.length > 0;

const describeFeedbackBlockers = (blockers) =>
  `${blockers.changeRequests.length} change request(s), ` +
  `${blockers.reviewBodies.length} actionable review body/bodies, ` +
  `${blockers.unresolvedThreads.length} unresolved thread(s), ` +
  `${blockers.conversation.length} non-informational conversation comment(s)`;

module.exports = {
  describeFeedbackBlockers,
  feedbackBlockers,
  hasFeedbackBlockers,
  inspectFeedback,
  isInformationalConversationComment,
  isInformationalReviewBody,
};
