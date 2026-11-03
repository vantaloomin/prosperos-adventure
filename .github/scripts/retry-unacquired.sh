#!/usr/bin/env bash
# Re-runs a CI run whose only problem is that GitHub never found a runner for some of its jobs.
#
# GitHub's hosted macOS arm64 runners (macos-latest) run short now and then. A job that waits too long gets
# "The job was not acquired by Runner of type hosted even after multiple attempts": it is cancelled without
# ever starting (no runner name), and the run fails although nothing was tested. Real failures, timeouts and
# runs superseded by a newer push are left alone.
#
# Needs GH_TOKEN (actions: write), REPO, RUN_ID and EVENT. Optional: MAX_ATTEMPTS (default 3), DRY_RUN=1.
set -euo pipefail

max_attempts=${MAX_ATTEMPTS:-3}
run=$(gh api "repos/$REPO/actions/runs/$RUN_ID")
attempt=$(jq -r .run_attempt <<< "$run")
branch=$(jq -r .head_branch <<< "$run")
workflow=$(jq -r .workflow_id <<< "$run")

if [ "$attempt" -ge "$max_attempts" ]; then
  echo "Attempt $attempt of $max_attempts already; a person decides from here."; exit 0
fi

# A pull request's newer run would be cancelled by re-running an older one (ci.yml's concurrency group).
if [ "$EVENT" = pull_request ]; then
  newest=$(gh api "repos/$REPO/actions/workflows/$workflow/runs?branch=$branch&event=pull_request&per_page=1" --jq '.workflow_runs[0].id')
  if [ "$newest" != "$RUN_ID" ]; then echo "Run $newest is newer on $branch; leaving $RUN_ID alone."; exit 0; fi
fi

jobs=$(gh api --paginate "repos/$REPO/actions/runs/$RUN_ID/attempts/$attempt/jobs?per_page=100" --jq '.jobs[]' | jq -s .)
unacquired=$(jq '[.[] | select(.conclusion == "cancelled" and ((.runner_name // "") == ""))]' <<< "$jobs")
other=$(jq '[.[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral")
                 | select((.conclusion == "cancelled" and ((.runner_name // "") == "")) | not)]' <<< "$jobs")

jq -r '.[] | "Never started: \(.name)"' <<< "$unacquired"
jq -r '.[] | "Did not pass: \(.name) (\(.conclusion))"' <<< "$other"

if [ "$(jq length <<< "$unacquired")" -eq 0 ]; then echo "Every job got a runner; nothing to retry."; exit 0; fi
if [ "$(jq length <<< "$other")" -ne 0 ]; then echo "Something else did not pass as well; not retrying."; exit 0; fi

if [ "${DRY_RUN:-}" = 1 ]; then echo "Would re-run the failed jobs of run $RUN_ID (attempt $attempt)."; exit 0; fi
gh api -X POST "repos/$REPO/actions/runs/$RUN_ID/rerun-failed-jobs" --silent
echo "Re-ran the jobs that never started (run $RUN_ID, attempt $((attempt + 1)))."
