import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, TypedDict, Any

import boto3
import logging
import yaml

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

cloudformation = boto3.client('cloudformation', region_name='eu-west-1')

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


def defined_stacks() -> Iterable[Stack]:
    for account_name, account in yaml.safe_load(Path('stacks.yaml').read_text()).items():
        account_id = account['account-id']
        for stack in account['stacks']:
            stack_name = stack['name']
            template_path = Path(stack['template'])
            yield Stack(account_id, account_name, stack_name, template_path)


def create_changeset(stack: Stack) -> Changeset:
    logger.info(f"Creating changeset for {stack.account_name}/{stack.stack_name}...")
    response = cloudformation.create_change_set(
        StackName=stack.stack_name,
        TemplateBody=stack.template_path.read_text(),
        ChangeSetName=changeset_name(),
        Capabilities=['CAPABILITY_NAMED_IAM'],
        Description=f"Changeset generated from an aws-users PR",
    )

    logger.info(response)

    changeset = cloudformation.describe_change_set(
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
            changeset = cloudformation.describe_change_set(
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

def render_changeset(changeset: Changeset) -> str:
    s = changeset.get('StatusReason', '') + '\n'

    for change in changeset.get('Changes', []):

        change = change['ResourceChange']
        if change.get('Action') == 'Add':
            s += f'Add {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Modify':
            if change.get('Replacement') == 'True':
                s += f'Replace {change["ResourceType"]} {change["LogicalResourceId"]}\n'
            else:
                s += f'Update {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Remove':
            s += f'Remove {change["ResourceType"]} {change["LogicalResourceId"]}\n'
        elif change.get('Action') == 'Dynamic':
            s += f'Undetermined Change to {change["ResourceType"]} {change["LogicalResourceId"]}\n'

    return s


def main():
    changesets = create_all_changesets()
    changesets = wait_for_changesets(changesets)

    for stack, changeset in changesets:
        if has_changes(changeset):
            print(f"Changeset {stack.account_name}/{stack.stack_name} created with status {changeset['Status']}.")
            print(render_changeset(changeset))
            print(f'https://eu-west-1.console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/changesets/changes?stackId={changeset["StackId"]}&changeSetId={changeset["ChangeSetId"]}')
            print()
        else:
            print(f"No changes detected in {stack.account_name}/{stack.stack_name}.")


if __name__ == '__main__':
    main()
