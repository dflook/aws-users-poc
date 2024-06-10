import os
from pathlib import Path
from typing import Iterable, Tuple

import boto3
import yaml

cloudformation = boto3.client('cloudformation', region_name='eu-west-1')


def changeset_name() -> str:
    return f"{os.environ.get('CODE_BUILD_WEBHOOK_TRIGGER', 'unknown-pr')}-{os.environ.get('CODEBUILD_RESOLVED_SOURCE_VERSION', 'unknown-commit')}"


def defined_stacks():
    return yaml.safe_load(Path('stacks.yaml').read_text())


def create_changeset(account_id: str, stack_name: str, template_path: Path) -> dict[str, str]:
    response = cloudformation.create_change_set(
        StackName=stack_name,
        TemplateBody=template_path.read_text(),
        ChangeSetName=changeset_name(),
        Capabilities=['CAPABILITY_NAMED_IAM'],
        Description=f"Changeset generated from an aws-users PR",
    )

    response['account-id'] = account_id
    response['stack-name'] = stack_name

    return response


def create_all_changesets():
    changesets = []

    for account_name, info in defined_stacks():
        info['account-name'] = account_name
        account_id = info['account-id']
        for stack in info['stacks']:
            stack_name = stack['name']
            template_path = Path(stack['template'])
            changeset = create_changeset(account_id, stack_name, template_path)
            changesets.append(changeset)

    return changesets


def wait_for_changesets(changesets):

    for changeset in changesets:
        print(f"Waiting for changeset {changeset['account-name']}/{changeset['name']} to be created...")
        cloudformation.get_waiter('change_set_create_complete').wait(
            ChangeSetName=changeset['Id'],
        )

def find_changes(changesets) -> Iterable[Tuple[dict, dict]]:

    for changeset in changesets:
        response = cloudformation.describe_change_set(
            ChangeSetName=changeset['Id'],
        )

        if response['Status'] == 'FAILED' and response['StatusReason'] == 'The submitted information didn\'t contain changes. Submit different information to create a change set.':
            # This is a no-op changeset, skip it
            continue

        yield changeset, response

def render_changeset(changeset: dict) -> str:
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
    wait_for_changesets(changesets)

    for changeset, response in find_changes(changesets):
        print(f"Changeset {changeset['account-name']}/{changeset['stack-name']} created with status {response['Status']}")
        print(render_changeset(response))
        print(f'https://eu-west-1.console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/changesets/changes?stackId={response["StackId"]}&changeSetId={response["ChangeSetId"]}')
        print()


if __name__ == '__main__':
    main()
