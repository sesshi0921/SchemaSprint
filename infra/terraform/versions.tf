terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.24"
    }
  }

  # Configure an encrypted remote backend at init time. Never commit credentials or
  # a local state file. See README.md for the per-environment examples.
  backend "s3" {}
}
