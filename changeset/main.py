
def render_changeset(changeset: dict) -> str:
    s = ''

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
