provider "cloudflare" {
  # The provider reads CLOUDFLARE_API_TOKEN from the environment in CI/local shells.
  # Do not put a token in *.tfvars or Terraform source.
  api_token = var.cloudflare_api_token
}
