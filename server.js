import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";

const app = new Hono();

// Long timeout for QR login polling (up to ~180s)
const LONG_POLL_MS = 200_000;

/**
 * Forward proxy with long-poll support and full header passthrough.
 */
async function proxy(c, targetBase, pathReplace = null) {
  const url = new URL(c.req.url);
  const query = url.searchParams.toString();

  let path = c.req.path;
  if (pathReplace) {
    path = path.replace(pathReplace.from, pathReplace.to);
  }

  // Avoid double slashes
  if (path.startsWith("/") && targetBase.endsWith("/")) {
    path = path.slice(1);
  }

  const targetURL = targetBase.replace(/\/$/, "") + path + (query ? `?${query}` : "");

  const headers = new Headers();
  // Copy client headers (important for X-Line-*, X-Hmac, X-LST, Session-ID, etc.)
  for (const [k, v] of c.req.raw.headers.entries()) {
    const lower = k.toLowerCase();
    if (
      lower === "host" ||
      lower === "connection" ||
      lower === "content-length" ||
      lower === "transfer-encoding"
    ) {
      continue;
    }
    headers.set(k, v);
  }

  // Ensure Origin looks like the extension for APIs that check it
  if (!headers.has("origin") || headers.get("origin")?.includes("onrender") || headers.get("origin")?.includes("localhost")) {
    headers.set("origin", "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc");
  }
  if (!headers.has("x-line-chrome-version")) {
    headers.set("x-line-chrome-version", "3.7.0");
  }

  const init = {
    method: c.req.method,
    headers,
    // Node fetch: allow long timeout via AbortSignal
    signal: AbortSignal.timeout(LONG_POLL_MS),
  };

  if (!["GET", "HEAD"].includes(c.req.method)) {
    init.body = c.req.raw.body;
    // Required for streaming body in Node
    init.duplex = "half";
  }

  try {
    const response = await fetch(targetURL, init);

    const resHeaders = new Headers(response.headers);
    resHeaders.set("Access-Control-Allow-Origin", "*");
    resHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
    resHeaders.set("Access-Control-Allow-Headers", "*");
    resHeaders.set("Access-Control-Expose-Headers", "*");
    // Prevent caching of auth responses
    resHeaders.set("Cache-Control", "no-store");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  } catch (err) {
    console.error("Proxy error:", targetURL, err?.message || err);
    if (err?.name === "TimeoutError" || err?.name === "AbortError") {
      return c.json({ error: "timeout", message: "Long-poll timed out" }, 504);
    }
    return c.json({ error: "Proxy failed", message: String(err?.message || err) }, 502);
  }
}

// CORS preflight for all routes
app.options("/*", (c) => {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Max-Age": "86400",
    },
  });
});

// ===== LINE API proxies (required for QR login + normal use) =====

// Primary gateway
app.all("/_proxy/CHROME_GW", (c) =>
  proxy(c, "https://line-chrome-gw.line-apps.com", null)
);
app.all("/_proxy/CHROME_GW/*", (c) =>
  proxy(c, "https://line-chrome-gw.line-apps.com", {
    from: "/_proxy/CHROME_GW",
    to: "",
  })
);

// ci.line-apps.com (R4 and related)
app.all("/_proxy/R4", (c) => proxy(c, "https://ci.line-apps.com/R4", null));
app.all("/_proxy/R4/*", (c) =>
  proxy(c, "https://ci.line-apps.com", { from: "/_proxy/R4", to: "/R4" })
);
app.all("/_proxy/CI/*", (c) =>
  proxy(c, "https://ci.line-apps.com", { from: "/_proxy/CI", to: "" })
);

// OBS (media / profile images)
app.all("/_proxy/OBS/*", (c) =>
  proxy(c, "https://obs.line-apps.com", { from: "/_proxy/OBS", to: "" })
);

// uts / other LINE hosts sometimes used
app.all("/_proxy/UTS/*", (c) =>
  proxy(c, "https://uts-front.line-apps.com", { from: "/_proxy/UTS", to: "" })
);

// ===== Static files (patched extension assets) =====
app.use(
  "/*",
  serveStatic({
    root: "./www",
  })
);

// SPA / unknown path fallback
app.notFound((c) => {
  if (c.req.path.includes(".")) {
    return c.text("Not Found", 404);
  }
  return c.redirect("/?fallbackBy=" + encodeURIComponent(c.req.path));
});

const port = Number(process.env.PORT) || 3000;
console.log(`LINE Web client running on http://localhost:${port}`);

serve({
  fetch: app.fetch,
  port,
});
