import logging
from typing import Tuple

from pr import create_all_changesets, wait_for_changesets, is_failed, Stack, Changeset, cloudformation, has_changes

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
debug = logger.debug

def execute_changeset(stack: Stack, changeset: Changeset) -> None:
    logger.info(f"Apply changeset for {stack.account_name}/{stack.stack_name}...")

    response = cloudformation.changeset_executor(stack.account_id).execute_change_set(
        ChangeSetName=changeset['ChangeSetId']
    )

    logger.info(response)

def execute_all_changesets(changesets: list[Tuple[Stack, Changeset]]) -> None:
    for stack, changeset in changesets:

        if is_failed(changeset):
            logger.error(f"Changeset for {stack.account_name}/{stack.stack_name} failed")
            continue

        execute_changeset(stack, changeset)

def main():
    changesets = create_all_changesets()
    changesets = wait_for_changesets(changesets)

    changesets = [(stack, changeset) for stack, changeset in changesets if has_changes(changeset)]

    # At this point we can compare the contents of the changeset with the one on the Pr to see if they match

    execute_all_changesets(changesets)
    changesets = wait_for_changesets(changesets)

    if any(is_failed(changeset) for _, changeset in changesets):
        raise Exception("One or more changesets failed")


if __name__ == '__main__':
    main()
