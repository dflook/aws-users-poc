resource "aws_cloudformation_stack" "roles" {
  name = "Roles"

  template_body = file("${path.module}/../output/stack-definitions/flooktech.yaml")

  capabilities = ["CAPABILITY_NAMED_IAM"]
}
