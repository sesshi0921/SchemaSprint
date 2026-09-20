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
    database_dsn         = "DATABASE_DSN"
    session_pepper       = "SESSION_PEPPER"
    csrf_key             = "CSRF_KEY"
    allowed_origin       = "ALLOWED_ORIGIN"
    jev_mode             = "JEV_MODE"
    jev_base_url         = "JEV_BASE_URL"
    jev_api_key          = "JEV_API_KEY"
    jev_model            = "JEV_MODEL"
    jev_timeout_seconds  = "JEV_TIMEOUT_SECONDS"
    jev_max_retries      = "JEV_MAX_RETRIES"
    llm_mode             = "LLM_MODE"
    groq_api_url         = "GROQ_API_URL"
    groq_api_key         = "GROQ_API_KEY"
    groq_model           = "GROQ_MODEL"
    groq_timeout_seconds = "GROQ_TIMEOUT_SECONDS"
  }
}
