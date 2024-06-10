data "aws_iam_policy_document" "aws_users_main_trust_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "aws_users_main" {
  name               = "codebuild-main"
  path = "/aws-users/"
  assume_role_policy = data.aws_iam_policy_document.aws_users_main_trust_policy.json
}

data "aws_iam_policy_document" "aws_users_main" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "aws_users_main" {
  role   = aws_iam_role.aws_users_main.name
  policy = data.aws_iam_policy_document.aws_users_main.json
}

resource "aws_codebuild_project" "aws_users_main" {
  name           = "aws-users-main"
  description    = "Apply aws-users changes"
  build_timeout  = 60 * 2  # 2 hours

  service_role = aws_iam_role.aws_users_main.arn
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
    buildspec = "ci/buildspec-main.yaml"
  }
}

resource "aws_codebuild_webhook" "aws_users_main" {
  project_name = aws_codebuild_project.aws_users_main.name
  build_type   = "BUILD"

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PUSH"
    }

    filter {
      type    = "HEAD_REF"
      pattern = "main"
    }
  }
}