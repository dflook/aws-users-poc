import json
import os
import re
import logging
from typing import Optional, Any, cast, Iterable, Tuple

from api import PrUrl, GithubApi, IssueUrl

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

debug = logger.debug

class WorkflowException(Exception):
    """An exception that should result in an error in the workflow log"""


def find_pr(github: GithubApi) -> Tuple[PrUrl, IssueUrl]:
    """
    Find the pull request this event is related to

    >>> find_pr()
    'https://api.github.com/repos/dflook/terraform-github-actions/pulls/8'

    """

    event: Optional[dict[str, Any]]

    repo = os.environ['CODEBUILD_SOURCE_REPO_URL'][len('https://github.com/'):-len('.git')]
    event_type = os.environ.get('CODEBUILD_WEBHOOK_EVENT', 'PUSH')

    if event_type.startswith('PULL_REQUEST_'):
        _, pr_number = os.environ['CODEBUILD_WEBHOOK_TRIGGER'].rsplit('/', 1)
        return cast(PrUrl, f'https://api.github.com/repos/{repo}/pulls/{pr_number}'), cast(IssueUrl, f'https://api.github.com/repos/{repo}/issues/{pr_number}')

    elif event_type == 'PUSH':
        commit = os.environ.get('CODEBUILD_RESOLVED_SOURCE_VERSION', 'unknown')

        def prs() -> Iterable[dict[str, Any]]:
            url = cast(PrUrl, f'https://api.github.com/repos/{repo}/pulls')
            yield from github.paged_get(url, params={'state': 'all'})

        for pr in prs():
            if pr['merge_commit_sha'] == commit:
                return cast(PrUrl, pr['url']), cast(IssueUrl, pr['_links']['issue']['href'])

        raise WorkflowException(f'No PR found in {repo} for commit {commit} (was it pushed directly to the target branch?)')

    raise WorkflowException(f"The {event_type} event doesn\'t relate to a Pull Request.")
