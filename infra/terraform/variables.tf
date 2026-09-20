variable "environment" {
  description = "Deployment environment; each value has its own state and Cloudflare bindings."
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "owner" {
  description = "Owning team or person, used for resource metadata and cost review."
  type        = string
  default     = "schemasprint"
}

variable "expiry" {
  description = "Optional expiry marker for non-production resources (YYYY-MM-DD)."
  type        = string
  default     = ""
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID; use an environment variable or an untracked tfvars file."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9a-f]{32}$", var.cloudflare_account_id))
    error_message = "cloudflare_account_id must be a 32-character hexadecimal account ID."
  }
}

variable "cloudflare_api_token" {
  description = "Short-lived least-privilege Cloudflare API token; injected as TF_VAR_cloudflare_api_token or CLOUDFLARE_API_TOKEN."
  type        = string
  sensitive   = true
  default     = null
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the API route and optional custom host."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.cloudflare_zone_id == null || can(regex("^[0-9a-f]{32}$", var.cloudflare_zone_id))
    error_message = "cloudflare_zone_id must be null or a 32-character hexadecimal zone ID."
  }
}

variable "api_hostname" {
  description = "Optional hostname for the Worker route, e.g. api.example.com."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.api_hostname == null || can(regex("^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", var.api_hostname))
    error_message = "api_hostname must be a lowercase DNS hostname or null."
  }
}

variable "api_base_url" {
  description = "Frontend API base; use /api for a same-origin route or an HTTPS gateway URL."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = var.api_base_url == null || var.api_base_url == "/api" || can(regex(
      "^https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?/api$",
      var.api_base_url,
    ))
    error_message = "api_base_url must be /api or an HTTPS hostname ending in /api."
  }
}

variable "pages_project_name" {
  description = "Cloudflare Pages project name."
  type        = string
  default     = "schemasprint-web"
}

variable "production_branch" {
  description = "Branch that Cloudflare Pages treats as production."
  type        = string
  default     = "main"
}

variable "worker_name" {
  description = "Worker gateway name."
  type        = string
  default     = "schemasprint-gateway"
}

variable "enable_paid_runtime" {
  description = "Explicit release gate for Workers Paid/Containers; keep false until budget and vendor gates pass."
  type        = bool
  default     = false
}

variable "enable_production_route" {
  description = "Whether Terraform should attach the API route. Disabled by default for safe previews."
  type        = bool
  default     = false
}
