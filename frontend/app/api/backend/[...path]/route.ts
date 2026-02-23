import { NextResponse } from "next/server";

const BACKEND_API_KEY = process.env.BACKEND_API_KEY?.trim();

function getBackendBaseUrl(): string {
  const configured = process.env.BACKEND_API_URL?.trim();
  if (!configured) return "http://127.0.0.1:8000";

  try {
    const parsed = new URL(configured);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return configured.replace(/\/$/, "");
    }
  } catch {
    // Fall through to default backend target.
  }

  return "http://127.0.0.1:8000";
}

function buildTargetUrl(requestUrl: string, pathSegments: string[]): string {
  const incoming = new URL(requestUrl);
  const joinedPath = pathSegments.join("/");
  return `${getBackendBaseUrl()}/${joinedPath}${incoming.search}`;
}

function canHaveBody(method: string): boolean {
  return !["GET", "HEAD"].includes(method.toUpperCase());
}

async function proxyRequest(
  request: Request,
  context: { params: Promise<{ path?: string[] }> }
) {
  const { path = [] } = await context.params;
  const targetUrl = buildTargetUrl(request.url, path);

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  if (BACKEND_API_KEY && !headers.has("x-api-key")) {
    headers.set("x-api-key", BACKEND_API_KEY);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };

  if (canHaveBody(request.method)) {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    responseHeaders.delete("transfer-encoding");

    return new NextResponse(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Proxy request failed";
    return NextResponse.json(
      {
        detail: "Failed to reach backend from frontend proxy.",
        target: targetUrl,
        error: message,
      },
      { status: 502 }
    );
  }
}

export { proxyRequest as GET, proxyRequest as POST, proxyRequest as PUT, proxyRequest as PATCH, proxyRequest as DELETE, proxyRequest as OPTIONS };
