import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, TypedDict, Any, Optional

import boto3
import logging
import yaml

from api import GithubApi
from find_pr import find_pr
from comment import find_comment, update_comment

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
debug = logger.debug

github = GithubApi('https://api.github.com', os.environ.get('GITHUB_TOKEN'))

@dataclass
class Stack:
    account_id: str
    account_name: str
    stack_name: str
    template_path: Path

class Changeset(TypedDict):
    ChangeSetName: str
    ChangeSetId: str
    StackId: str
    StackName: str
    Status: str
    StatusReason: str
    Changes: list[dict[str, Any]]

def changeset_name() -> str:
    return f"{os.environ.get('CODE_BUILD_WEBHOOK_TRIGGER', 'unknown-pr')}-{os.environ.get('CODEBUILD_RESOLVED_SOURCE_VERSION', 'unknown-commit')}-{os.environ.get('CODEBUILD_BUILD_NUMBER', int(time.time()))}"

class Cloudformation:
    def __init__(self):
        self._clients = {}

    def cloudformation_client(self, account_id: str, role_name: str):

        role_arn = f'arn:aws:iam::{account_id}:role/{role_name}'

        if role_arn not in self._clients:

            sts = boto3.client('sts').assume_role(
                RoleArn=f'arn:aws:iam::{account_id}:role/{role_name}',
                RoleSessionName='aws-users',
                DurationSeconds=60 * 60,
            )['Credentials']

            self._clients[role_arn] = boto3.client(
                'cloudformation',
                aws_access_key_id=sts.get('AccessKeyId'),
                aws_secret_access_key=sts.get('SecretAccessKey'),
                aws_session_token=sts.get('SessionToken'),
                region_name='eu-west-1'
            )

        return self._clients[role_arn]

    def changeset_creator(self, account_id: str):
        return self.cloudformation_client(account_id, 'RoleChangeSetCreator')

    def changeset_executor(self, account_id: str):
        return self.cloudformation_client(account_id, 'RoleIAMAdministrator')

cloudformation = Cloudformation()

def defined_stacks() -> Iterable[Stack]:
    for account_name, account in yaml.safe_load(Path('stacks.yaml').read_text()).items():
        account_id = account['account-id']
        for stack in account['stacks']:
            stack_name = stack['name']
            template_path = Path(stack['template'])
            yield Stack(account_id, account_name, stack_name, template_path)


def create_changeset(stack: Stack) -> Changeset:
    logger.info(f"Creating changeset for {stack.account_name}/{stack.stack_name}...")
    response = cloudformation.changeset_creator(stack.account_id).create_change_set(
        StackName=stack.stack_name,
        TemplateBody=stack.template_path.read_text(),
        ChangeSetName=changeset_name(),
        Capabilities=['CAPABILITY_NAMED_IAM'],
        Description=f"Changeset generated from an aws-users PR",
    )

    logger.info(response)

    changeset = cloudformation.changeset_creator(stack.account_id).describe_change_set(
        ChangeSetName=response['Id'],
    )
    logger.info(changeset)
    return changeset


def create_all_changesets() -> list[Tuple[Stack, Changeset]]:
    changesets = []

    for stack in defined_stacks():
        changesets.append((stack, create_changeset(stack)))

    return changesets


def wait_for_changesets(changesets: list[Tuple[Stack, Changeset]]) -> list[Tuple[Stack, Changeset]]:

    ready_changesets = []

    sleep = 1

    for stack, changeset in changesets:
        while True:
            changeset = cloudformation.changeset_creator(stack.account_id).describe_change_set(
                ChangeSetName=changeset['ChangeSetId']
            )

            logger.info(changeset)

            if changeset.get('Status').endswith('_COMPLETE') or changeset.get('Status').endswith('FAILED'):
                ready_changesets.append((stack, changeset))
                break

            print(f"Waiting for changeset {stack.account_name}/{stack.stack_name} to be created...")
            time.sleep(sleep)
            sleep = min(sleep * 2, 30)

    return ready_changesets


def has_changes(changeset: Changeset) -> bool:
    if changeset['Status'] == 'FAILED' and changeset['StatusReason'] == 'The submitted information didn\'t contain changes. Submit different information to create a change set.':
        return False

    return True

def is_failed(changeset: Changeset) -> bool:
    return changeset['Status'] == 'FAILED'

def render_changeset_diff(changeset: Changeset) -> str:

    s = '```diff\n'

    for change in changeset.get('Changes', []):

        change = change['ResourceChange']
        if change.get('Action') == 'Add':
            s += f'+ {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Modify':
            if change.get('Replacement') == 'True':
                s += f'! {change["ResourceType"]} {change["LogicalResourceId"]}\n'
            else:
                s += f'! {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Remove':
            s += f'- {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Dynamic':
            s += f'! Undetermined to {change["ResourceType"]} {change["LogicalResourceId"]}\n'

    s += '```\n'

    return s

def render_changesets(changesets: list[Tuple[Stack, Changeset]]) -> str:
    s = ''

    for stack, changeset in changesets:
        if s:
            s += '<hr>\n'

        s += f"Changeset for __{stack.account_name}/{stack.stack_name}__\n"

        if changeset['Status'] == 'FAILED':
            s += f"Status: {changeset['Status']}: {changeset['StatusReason']}.\n"
        else:
            s += render_changeset_diff(changeset)
        s += f'\n[View Changeset](https://eu-west-1.console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/changesets/changes?stackId={changeset["StackId"]}&changeSetId={changeset["ChangeSetId"]})'

    if not s:
        s = 'No changes detected'

    return s

def current_user() -> str:
    def graphql() -> Optional[str]:
        graphql_url = 'https://api.github.com/graphql'

        response = github.post(graphql_url, json={
            'query': "query { viewer { login } }"
        })
        debug(f'graphql response: {response.content}')

        if response.ok:
            try:
                return response.json()['data']['viewer']['login']
            except Exception as e:
                pass

        debug('Failed to get current user from graphql')

    def rest() -> Optional[str]:
        response = github.get('https://api.github.com/user')
        debug(f'rest response: {response.content}')

        if response.ok:
            user = response.json()

            return user['login']

    # Not all tokens can be used with graphql
    # There is also no rest endpoint that can get the current login for app tokens :(
    # Try graphql first, then fallback to rest (e.g. for fine grained PATs)

    username = graphql() or rest()

    if username is None:
        debug('Unable to get username for the github token')
        username = 'unknown'

    debug(f'token username is {username}')
    return username


def main():
    changesets = create_all_changesets()
    changesets = wait_for_changesets(changesets)

    result = render_changesets(changesets)
    print(result)

    pr_url, issue_url = find_pr(github)
    username = current_user()

    comment = find_comment(github, issue_url, username, {})

    update_comment(github, comment, body=result)

    if any(is_failed(changeset) for _, changeset in changesets):
        raise Exception("One or more changesets failed")


if __name__ == '__main__':
    main()
