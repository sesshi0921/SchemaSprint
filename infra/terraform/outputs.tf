output "pages_project_name" {
  description = "Cloudflare Pages project name used by the direct-upload deployment job."
  value       = local.pages_name
}

output "environment" {
  description = "Authoritative environment value used by the Pages build and Worker config."
  value       = var.environment
}

output "pages_project_subdomain" {
  description = "Cloudflare Pages canonical subdomain."
  value       = cloudflare_pages_project.frontend.subdomain
}

output "worker_name" {
  description = "Cloudflare Worker gateway name."
  value       = local.gateway_name
}

output "api_route_pattern" {
  description = "API route pattern, null when the route release gate is disabled."
  value       = local.route_pattern
}

output "frontend_api_base_url" {
  description = "The API base URL baked into the frontend build configuration."
  value       = local.frontend_api_base_url
}

output "runtime_secret_names" {
  description = "Secret binding names required by the Worker/container; values never enter Terraform."
  value       = local.runtime_secret_names
}

output "runtime_gates" {
  description = "Authoritative release gates consumed by the protected deployment process."
  value = {
    paid_runtime         = var.enable_paid_runtime
    production_api_route = var.enable_production_route
  }
}
