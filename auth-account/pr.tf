data "aws_iam_policy_document" "aws_users_pr_trust_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "aws_users_pr" {
  name               = "codebuild-pr"
  path = "/aws-users/"
  assume_role_policy = data.aws_iam_policy_document.aws_users_pr_trust_policy.json
}

data "aws_iam_policy_document" "aws_users_pr" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "cloudformation:CreateChangeSet",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "aws_users_pr" {
  role   = aws_iam_role.aws_users_pr.name
  policy = data.aws_iam_policy_document.aws_users_pr.json
}

resource "aws_codebuild_project" "aws_users_pr" {
  name           = "aws-users-pr"
  description    = "Create changeset for aws-users changes"
  build_timeout  = 60 * 2  # 2 hours

  service_role = aws_iam_role.aws_users_pr.arn
  concurrent_build_limit = 1

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_MEDIUM"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
  }

  source {
    type            = "GITHUB"
    location        = var.aws_users_repo
    git_clone_depth = 1
    buildspec = "ci/buildspec-pr.yaml"
  }
}

resource "aws_codebuild_webhook" "aws_users_pr" {
  project_name = aws_codebuild_project.aws_users_pr.name
  build_type   = "BUILD"

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PULL_REQUEST_CREATED"
    }

    filter {
      type    = "BASE_REF"
      pattern = "main"
    }
  }

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PULL_REQUEST_UPDATED"
    }

    filter {
      type    = "BASE_REF"
      pattern = "main"
    }
  }
}