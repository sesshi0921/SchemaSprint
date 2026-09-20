import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  API_CONTAINER: DurableObjectNamespace<SchemaSprintApiContainer>;
  ENVIRONMENT: string;
  PAID_RUNTIME: string;
  DATABASE_DSN?: string;
  SESSION_PEPPER?: string;
  CSRF_KEY?: string;
  ALLOWED_ORIGIN?: string;
  JEV_MODE?: string;
  JEV_BASE_URL?: string;
  JEV_API_KEY?: string;
  JEV_MODEL?: string;
  JEV_TIMEOUT_SECONDS?: string;
  JEV_MAX_RETRIES?: string;
  LLM_MODE?: string;
  GROQ_API_URL?: string;
  GROQ_API_KEY?: string;
  GROQ_MODEL?: string;
  GROQ_TIMEOUT_SECONDS?: string;
}

/**
 * Private Python/Rust BFF container. It is reachable only through this Worker
 * binding; no public origin URL or client-controlled identity header is used.
 */
export class SchemaSprintApiContainer extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "10m";
  envVars: Record<string, string> = {
    PYTHONUNBUFFERED: "1",
  };

  constructor(state: DurableObjectState<Env>, env: Env) {
    super(state, env);
    const configured = runtimeEnv(env);
    if (configured !== null) {
      this.envVars = configured;
    }
  }

  override onError(error: unknown): void {
    // Do not serialize error objects: a dependency error can contain a DSN,
    // request headers, or provider response data.
    console.error("schemasprint_api_container_error", {
      errorType: error instanceof Error ? error.name : "unknown",
    });
  }
}

const MAX_REQUEST_BYTES = 1_048_576;
const METHODS = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]);
const SPOOFABLE_IDENTITY_HEADERS = [
  "x-user-id",
  "x-user-role",
  "x-user-email",
  "x-forwarded-user",
  "x-forwarded-email",
  "x-auth-user",
  "x-auth-role",
];
const REQUIRED_RUNTIME_ENV = [
  "ENVIRONMENT",
  "DATABASE_DSN",
  "SESSION_PEPPER",
  "CSRF_KEY",
  "ALLOWED_ORIGIN",
] as const;
const UPSTREAM_TIMEOUT_MS = 15_000;

function json(body: Record<string, string>, status: number): Response {
  return securityHeaders(new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  }));
}

function securityHeaders(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("cache-control", "no-store");
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "no-referrer");
  headers.set("content-security-policy", "default-src 'none'; frame-ancestors 'none'");
  return new Response(response.body, { status: response.status, headers });
}

function runtimeEnv(env: Env): Record<string, string> | null {
  const raw: Record<string, string | undefined> = {
    ENVIRONMENT: env.ENVIRONMENT,
    DATABASE_DSN: env.DATABASE_DSN,
    SESSION_PEPPER: env.SESSION_PEPPER,
    CSRF_KEY: env.CSRF_KEY,
    ALLOWED_ORIGIN: env.ALLOWED_ORIGIN,
    JEV_MODE: env.JEV_MODE,
    JEV_BASE_URL: env.JEV_BASE_URL,
    JEV_API_KEY: env.JEV_API_KEY,
    JEV_MODEL: env.JEV_MODEL,
    JEV_TIMEOUT_SECONDS: env.JEV_TIMEOUT_SECONDS,
    JEV_MAX_RETRIES: env.JEV_MAX_RETRIES,
    LLM_MODE: env.LLM_MODE,
    GROQ_API_URL: env.GROQ_API_URL,
    GROQ_API_KEY: env.GROQ_API_KEY,
    GROQ_MODEL: env.GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS: env.GROQ_TIMEOUT_SECONDS,
  };
  if (REQUIRED_RUNTIME_ENV.some((name) => !raw[name])) {
    return null;
  }
  return Object.fromEntries(
    Object.entries(raw).filter((entry): entry is [string, string] =>
      typeof entry[1] === "string" && entry[1].length > 0,
    ),
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!METHODS.has(request.method)) {
      return json({ code: "METHOD_NOT_ALLOWED" }, 405);
    }

    const isHealth = url.pathname === "/healthz" || url.pathname === "/api/healthz";
    const isApi = url.pathname.startsWith("/api/v1/");
    if (!isHealth && !isApi) {
      return json({ code: "NOT_FOUND" }, 404);
    }

    if (env.PAID_RUNTIME !== "true") {
      return json({ code: "PAID_RUNTIME_DISABLED" }, 503);
    }

    if (request.method === "OPTIONS") {
      return securityHeaders(new Response(null, { status: 204 }));
    }

    const length = request.headers.get("content-length");
    if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_REQUEST_BYTES)) {
      return json({ code: "REQUEST_BODY_TOO_LARGE" }, 413);
    }

    const forwardedHeaders = new Headers(request.headers);
    for (const name of SPOOFABLE_IDENTITY_HEADERS) {
      forwardedHeaders.delete(name);
    }
    forwardedHeaders.set("x-schemasprint-gateway", "1");
    forwardedHeaders.delete("host");

    // The application exposes /health/live; keep the public health contract
    // separate without making the container public.
    const target = new URL(url);
    if (isHealth) target.pathname = "/health/live";
    const forwarded = new Request(target, {
      method: request.method,
      headers: forwardedHeaders,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });

    try {
      const containerEnv = runtimeEnv(env);
      if (containerEnv === null) {
        console.error("schemasprint_gateway_runtime_not_configured", {
          environment: env.ENVIRONMENT,
        });
        return json({ code: "GATEWAY_NOT_CONFIGURED" }, 503);
      }
      const container = getContainer(env.API_CONTAINER, "schemasprint-api");
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
      try {
        const timedRequest = new Request(forwarded, { signal: controller.signal });
        return securityHeaders(await container.fetch(timedRequest));
      } catch (error) {
        if (controller.signal.aborted) {
          console.error("schemasprint_gateway_upstream_timeout", {
            environment: env.ENVIRONMENT,
          });
          return json({ code: "UPSTREAM_TIMEOUT" }, 504);
        }
        throw error;
      } finally {
        clearTimeout(timeout);
      }
    } catch (error) {
      console.error("schemasprint_gateway_container_unavailable", {
        environment: env.ENVIRONMENT,
        errorType: error instanceof Error ? error.name : "unknown",
      });
      return json({ code: "DEPENDENCY_UNAVAILABLE" }, 503);
    }
  },
};
