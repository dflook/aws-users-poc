import json

import re
import logging
from json import JSONDecodeError
from typing import Optional, Any

from api import IssueUrl, GithubApi, CommentUrl

version = '0.0.1'

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

debug = logger.debug

collapse_threshold = 10

class GitHubComment:

    def __init__(self, *, issue_url: IssueUrl, comment_url: Optional[CommentUrl], headers: dict[str, str], body: str):
        self._issue_url = issue_url
        self._comment_url = comment_url
        self._headers = headers
        self._body = body.strip()

    def __eq__(self, other):
        if not isinstance(other, GitHubComment):
            return NotImplemented

        return (
            self._issue_url == other._issue_url and
            self._comment_url == other._comment_url and
            self._headers == other._headers and
            self._body == other._body
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f'GitHubComment(issue_url={self._issue_url!r}, comment_url={self._comment_url!r}, headers={self._headers!r}, body={self._body!r})'

    @property
    def comment_url(self) -> Optional[CommentUrl]:
        return self._comment_url

    @comment_url.setter
    def comment_url(self, comment_url: CommentUrl) -> None:
        if self._comment_url is not None:
            raise Exception('Can only set url for comments that don\'t exist yet')
        self._comment_url = comment_url

    @property
    def issue_url(self) -> IssueUrl:
        return self._issue_url

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def body(self) -> str:
        return self._body

def _format_comment_header(**kwargs) -> str:
    return f'<!-- hmrc/aws-users {json.dumps(kwargs, separators=(",",":"))} -->'

def _parse_comment_header(comment_header: Optional[str]) -> dict[str, str]:
    if comment_header is None:
        return {}

    if header := re.match(r'^<!--\shmrc/aws-users\s(?P<args>.*)\s-->', comment_header):
        try:
            return json.loads(header['args'])
        except JSONDecodeError:
            return {}

    return {}


def _from_api_payload(comment: dict[str, Any]) -> Optional[GitHubComment]:
    match = re.match(r'''
            (?P<headers><!--.*?-->\n)?
            (?P<body>.*)
        ''',
        comment['body'],
        re.VERBOSE | re.DOTALL
    )

    if not match:
        return None

    return GitHubComment(
        issue_url=comment['issue_url'],
        comment_url=comment['url'],
        headers=_parse_comment_header(match.group('headers')),
        body=match.group('body').strip()
    )


def _to_api_payload(comment: GitHubComment) -> str:
    header = _format_comment_header(**comment.headers)

    body = f'''{header}
{comment.body}
'''

    return body

def matching_headers(comment: GitHubComment, headers: dict[str, str]) -> bool:
    """
    Does a comment have all the specified headers

    Additional headers may be present in the comment, they are ignored if not specified in the headers argument.
    If a header should NOT be present in the comment, specify a header with a value of None
    """

    for header, value in headers.items():
        if value is None and header in comment.headers:
            return False

        if value is not None and comment.headers.get(header) != value:
            return False

    return True

def find_comment(github: GithubApi, issue_url: IssueUrl, username: str, headers: dict[str, str]) -> GitHubComment:
    """
    Find a github comment that matches the given headers

    If no comment is found with the specified headers, tries to find a comment that matches the specified description instead.
    This is in case the comment was made with an earlier version, where comments were matched by description only.

    If no existing comment is found a new GitHubComment object is returned which represents a PR comment yet to be created.

    :param github: The github api object to make requests with
    :param issue_url: The issue to find the comment in
    :param username: The user who made the comment
    :param headers: The headers that must be present on the comment
    """

    debug(f"Searching for comment with {headers=}")

    for comment_payload in github.paged_get(issue_url + '/comments', params={'per_page': 100}):
        if comment_payload['user']['login'] != username:
            continue

        if comment := _from_api_payload(comment_payload):

            if comment.headers:
                # Match by headers only

                if matching_headers(comment, headers):
                    debug(f'Found comment that matches headers {comment.headers=} ')
                    return comment

                debug(f"Didn't match comment with {comment.headers=}")

    debug('No existing comment exists')
    return GitHubComment(
        issue_url=issue_url,
        comment_url=None,
        headers={k: v for k, v in headers.items() if v is not None},
        body='',
    )


def update_comment(
    github: GithubApi,
    comment: GitHubComment,
    *,
    headers: dict[str, str] = None,
    body: str = None,
) -> GitHubComment:

    new_headers = headers if headers is not None else comment.headers
    new_headers['version'] = version

    new_comment = GitHubComment(
        issue_url=comment.issue_url,
        comment_url=comment.comment_url,
        headers=new_headers,
        body=body if body is not None else comment.body,
    )

    if comment.comment_url is not None:
        response = github.patch(comment.comment_url, json={'body': _to_api_payload(new_comment)})
        response.raise_for_status()
    else:
        response = github.post(comment.issue_url + '/comments', json={'body': _to_api_payload(new_comment)})
        response.raise_for_status()
        new_comment.comment_url = response.json()['url']

    return new_comment
