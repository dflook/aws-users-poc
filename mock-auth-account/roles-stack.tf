resource "aws_cloudformation_stack" "roles" {
  name = "Roles"

  template_body = file("${path.module}/../templates/webops.yaml")

  capabilities = ["CAPABILITY_NAMED_IAM"]
}
