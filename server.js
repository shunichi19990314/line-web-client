import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";

const app = new Hono();

/**
 * Proxy helper
 */
async function proxy(c, targetBase, pathReplace = null) {
  const url = new URL(c.req.url);
  const query = url.searchParams.toString();

  let path = c.req.path;
  if (pathReplace) {
    path = path.replace(pathReplace.from, pathReplace.to);
  }

  const targetURL = targetBase + path + (query ? `?${query}` : "");

  const headers = new Headers(c.req.raw.headers);
  // Remove hop-by-hop headers that can cause issues
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const init = {
    method: c.req.method,
    headers,
  };

  if (!["GET", "HEAD"].includes(c.req.method)) {
    init.body = c.req.raw.body;
    // @ts-ignore
    init.duplex = "half";
  }

  try {
    const response = await fetch(targetURL, init);

    const resHeaders = new Headers(response.headers);
    resHeaders.set("Access-Control-Allow-Origin", "*");
    resHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
    resHeaders.set("Access-Control-Allow-Headers", "*");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  } catch (err) {
    console.error("Proxy error:", err);
    return c.json({ error: "Proxy failed", message: String(err) }, 502);
  }
}

// CORS preflight
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

// ===== Proxies =====

// https://ci.line-apps.com/R4
app.all("/_proxy/R4", (c) => proxy(c, "https://ci.line-apps.com/R4", null));
app.all("/_proxy/R4/*", (c) =>
  proxy(c, "https://ci.line-apps.com", { from: "/_proxy/R4", to: "/R4" })
);

// https://line-chrome-gw.line-apps.com
app.all("/_proxy/CHROME_GW", (c) =>
  proxy(c, "https://line-chrome-gw.line-apps.com", null)
);
app.all("/_proxy/CHROME_GW/*", (c) =>
  proxy(c, "https://line-chrome-gw.line-apps.com", {
    from: "/_proxy/CHROME_GW",
    to: "",
  })
);

// ===== Static files =====
app.use(
  "/*",
  serveStatic({
    root: "./www",
    rewriteRequestPath: (path) => {
      // SPA fallback is handled by notFound
      return path;
    },
  })
);

// Fallback: redirect unknown paths to index
app.notFound((c) => {
  // If the request looks like a static asset, return 404
  if (c.req.path.includes(".")) {
    return c.text("Not Found", 404);
  }
  return c.redirect("/?fallbackBy=" + encodeURIComponent(c.req.path));
});

// ===== Start server =====
const port = Number(process.env.PORT) || 3000;

console.log(`LINE Web client running on http://localhost:${port}`);

serve({
  fetch: app.fetch,
  port,
});
