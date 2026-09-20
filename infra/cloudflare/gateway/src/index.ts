import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  API_CONTAINER: DurableObjectNamespace<SchemaSprintApiContainer>;
  SCHEMASPRINT_ENVIRONMENT: string;
  SCHEMASPRINT_PAID_RUNTIME: string;
  SCHEMASPRINT_DATABASE_DSN?: string;
  SCHEMASPRINT_SESSION_PEPPER?: string;
  SCHEMASPRINT_CSRF_KEY?: string;
  SCHEMASPRINT_ALLOWED_ORIGIN?: string;
  SCHEMASPRINT_JEV_MODE?: string;
  SCHEMASPRINT_JEV_BASE_URL?: string;
  SCHEMASPRINT_JEV_API_KEY?: string;
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
  "SCHEMASPRINT_ENVIRONMENT",
  "SCHEMASPRINT_DATABASE_DSN",
  "SCHEMASPRINT_SESSION_PEPPER",
  "SCHEMASPRINT_CSRF_KEY",
  "SCHEMASPRINT_ALLOWED_ORIGIN",
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
    SCHEMASPRINT_ENVIRONMENT: env.SCHEMASPRINT_ENVIRONMENT,
    SCHEMASPRINT_DATABASE_DSN: env.SCHEMASPRINT_DATABASE_DSN,
    SCHEMASPRINT_SESSION_PEPPER: env.SCHEMASPRINT_SESSION_PEPPER,
    SCHEMASPRINT_CSRF_KEY: env.SCHEMASPRINT_CSRF_KEY,
    SCHEMASPRINT_ALLOWED_ORIGIN: env.SCHEMASPRINT_ALLOWED_ORIGIN,
    SCHEMASPRINT_JEV_MODE: env.SCHEMASPRINT_JEV_MODE,
    SCHEMASPRINT_JEV_BASE_URL: env.SCHEMASPRINT_JEV_BASE_URL,
    SCHEMASPRINT_JEV_API_KEY: env.SCHEMASPRINT_JEV_API_KEY,
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

    if (env.SCHEMASPRINT_PAID_RUNTIME !== "true") {
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
          environment: env.SCHEMASPRINT_ENVIRONMENT,
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
            environment: env.SCHEMASPRINT_ENVIRONMENT,
          });
          return json({ code: "UPSTREAM_TIMEOUT" }, 504);
        }
        throw error;
      } finally {
        clearTimeout(timeout);
      }
    } catch (error) {
      console.error("schemasprint_gateway_container_unavailable", {
        environment: env.SCHEMASPRINT_ENVIRONMENT,
        errorType: error instanceof Error ? error.name : "unknown",
      });
      return json({ code: "DEPENDENCY_UNAVAILABLE" }, 503);
    }
  },
};
