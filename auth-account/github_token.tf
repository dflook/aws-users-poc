resource "aws_ssm_parameter" "github_token" {
  name = "/users/github_token"
  type = "SecureString"

  value = "nope"

  lifecycle {
    ignore_changes = [value]
  }
}