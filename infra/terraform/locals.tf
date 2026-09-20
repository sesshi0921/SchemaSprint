locals {
  pages_name   = "${var.pages_project_name}-${var.environment}"
  gateway_name = "${var.worker_name}-${var.environment}"

  common_tags = {
    product     = "schemasprint"
    environment = var.environment
    owner       = var.owner
    expiry      = var.expiry
  }

  # A route must be explicitly enabled; keep the output truthful when the
  # production gate is closed even if a hostname was supplied in tfvars.
  route_pattern = var.enable_production_route && var.api_hostname != null && var.cloudflare_zone_id != null ? "${var.api_hostname}/api/*" : null

  frontend_api_base_url = var.api_base_url == null ? "/api" : var.api_base_url

  runtime_secret_names = {
    database_dsn   = "SCHEMASPRINT_DATABASE_DSN"
    session_pepper = "SCHEMASPRINT_SESSION_PEPPER"
    csrf_key       = "SCHEMASPRINT_CSRF_KEY"
    allowed_origin = "SCHEMASPRINT_ALLOWED_ORIGIN"
    jev_mode       = "SCHEMASPRINT_JEV_MODE"
    jev_base_url   = "SCHEMASPRINT_JEV_BASE_URL"
    jev_api_key    = "SCHEMASPRINT_JEV_API_KEY"
  }
}
