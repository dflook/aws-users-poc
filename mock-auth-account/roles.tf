resource "aws_iam_role" "RoleChangeSetCreator" {
  name = "RoleChangeSetCreator"
  assume_role_policy = data.aws_iam_policy_document.RoleChangeSetCreator_trust.json

  inline_policy {
    name   = "RoleChangeSetCreator"
    policy = data.aws_iam_policy_document.RoleChangeSetCreator.json
  }
}

data "aws_iam_policy_document" "RoleChangeSetCreator_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [data.aws_caller_identity.current.account_id]
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "RoleChangeSetCreator" {
  statement {
    effect = "Allow"

    actions = [
      "cloudformation:CreateChangeSet",
      "cloudformation:DescribeChangeSet",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role" "RoleIAMAdministrator" {
  name = "RoleIAMAdministrator"
  assume_role_policy = data.aws_iam_policy_document.RoleIAMAdministrator_trust.json

  inline_policy {
    name   = "RoleIAMAdministrator"
    policy = data.aws_iam_policy_document.RoleIAMAdministrator.json
  }
}

data "aws_iam_policy_document" "RoleIAMAdministrator_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [data.aws_caller_identity.current.account_id]
    }
  }
}


data "aws_iam_policy_document" "RoleIAMAdministrator" {
  statement {
    effect = "Allow"

    actions = [
      "cloudformation:CreateChangeSet",
      "cloudformation:DescribeChangeSet",
      "cloudformation:ExecuteChangeSet",
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "iam:*"
    ]

    resources = ["*"]
  }
}