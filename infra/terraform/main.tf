resource "terraform_data" "configuration_guard" {
  input = {
    environment             = var.environment
    enable_paid_runtime     = var.enable_paid_runtime
    enable_production_route = var.enable_production_route
    api_hostname            = var.api_hostname
    api_base_url            = local.frontend_api_base_url
    cloudflare_zone_id      = var.cloudflare_zone_id
  }

  lifecycle {
    precondition {
      condition = !var.enable_production_route || (
        var.cloudflare_zone_id != null
        && var.api_hostname != null
        && var.api_base_url != null
        && startswith(var.api_base_url, "https://${var.api_hostname}/api")
      )
      error_message = "An enabled API route requires cloudflare_zone_id, api_hostname, and an HTTPS api_base_url for that exact host."
    }

    precondition {
      condition     = !var.enable_production_route || var.environment == "production"
      error_message = "enable_production_route is a production gate and may only be enabled for environment=production."
    }

    precondition {
      condition     = var.enable_paid_runtime == false || var.environment != "development"
      error_message = "Workers Paid/Containers cannot be enabled for the development environment."
    }
  }
}

resource "cloudflare_pages_project" "frontend" {
  account_id        = var.cloudflare_account_id
  name              = local.pages_name
  production_branch = var.production_branch

  build_config = {
    build_command   = "npm ci && npm run build"
    destination_dir = "dist"
    root_dir        = "frontend"
    build_caching   = true
  }

  # Pages direct-upload is performed by the authorized deployment workflow. These
  # values are non-secret and make the build contract explicit for Git integration.
  deployment_configs = {
    preview = {
      env_vars = {
        VITE_APP_ENV = {
          type  = "plain_text"
          value = var.environment
        }
        VITE_API_BASE_URL = {
          type  = "plain_text"
          value = local.frontend_api_base_url
        }
      }
    }
    production = {
      env_vars = {
        VITE_APP_ENV = {
          type  = "plain_text"
          value = var.environment
        }
        VITE_API_BASE_URL = {
          type  = "plain_text"
          value = local.frontend_api_base_url
        }
      }
    }
  }
}

# The Worker shell and route are managed by Terraform. The version upload is kept
# in the deployment workflow so the container image and secret bindings never enter
# Terraform state; see infra/cloudflare/gateway/wrangler.jsonc.
resource "cloudflare_worker" "gateway" {
  account_id = var.cloudflare_account_id
  name       = local.gateway_name
  tags       = [for k, v in local.common_tags : "${k}:${v}" if v != ""]

  logpush = false
  observability = {
    enabled = true
    logs = {
      enabled            = true
      invocation_logs    = true
      persist            = false
      head_sampling_rate = var.environment == "production" ? 1 : 0.1
    }
  }

  subdomain = {
    enabled          = false
    previews_enabled = false
  }
}

resource "cloudflare_workers_route" "api" {
  count   = var.enable_production_route && var.cloudflare_zone_id != null && local.route_pattern != null ? 1 : 0
  zone_id = var.cloudflare_zone_id
  pattern = local.route_pattern
  script  = cloudflare_worker.gateway.name
}
