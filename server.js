import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";

const app = new Hono();

// QR long-poll can take ~150–180s
const LONG_POLL_MS = 210_000;

const HOSTS = {
  gateway: "https://line-chrome-gw.line-apps.com",
  ci: "https://ci.line-apps.com",
  obs: "https://obs.line-apps.com",
  uts: "https://uts-front.line-apps.com",
};

/**
 * Forward to LINE keeping path+query identical (required for X-Hmac).
 */
async function forward(c, base) {
  const incoming = new URL(c.req.url);
  const targetURL = base.replace(/\/$/, "") + incoming.pathname + incoming.search;

  const headers = new Headers();
  for (const [k, v] of c.req.raw.headers.entries()) {
    const l = k.toLowerCase();
    if (
      l === "host" ||
      l === "connection" ||
      l === "content-length" ||
      l === "transfer-encoding" ||
      l === "accept-encoding"
    ) {
      continue;
    }
    headers.set(k, v);
  }

  headers.set("origin", "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc");
  headers.set("referer", "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/");
  if (!headers.has("x-line-chrome-version")) {
    headers.set("x-line-chrome-version", "3.7.0");
  }
  if (!headers.has("x-lal")) {
    headers.set("x-lal", "ja_JP");
  }

  const init = {
    method: c.req.method,
    headers,
    signal: AbortSignal.timeout(LONG_POLL_MS),
  };

  if (!["GET", "HEAD"].includes(c.req.method)) {
    init.body = c.req.raw.body;
    init.duplex = "half";
  }

  try {
    console.log(`[proxy] ${c.req.method} ${incoming.pathname} -> ${base}`);
    const response = await fetch(targetURL, init);

    const resHeaders = new Headers(response.headers);
    resHeaders.set("Access-Control-Allow-Origin", "*");
    resHeaders.set("Access-Control-Allow-Methods", "*");
    resHeaders.set("Access-Control-Allow-Headers", "*");
    resHeaders.set("Access-Control-Expose-Headers", "*");
    resHeaders.set("Cache-Control", "no-store");
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  } catch (err) {
    console.error(`[proxy] FAIL ${targetURL}`, err?.name, err?.message);
    const timeout =
      err?.name === "TimeoutError" ||
      err?.name === "AbortError" ||
      String(err?.message || "").toLowerCase().includes("abort");
    return c.json(
      {
        error: timeout ? "timeout" : "proxy_failed",
        message: String(err?.message || err),
      },
      timeout ? 504 : 502
    );
  }
}

app.options("/*", (c) =>
  new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "*",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Max-Age": "86400",
    },
  })
);

// Path-preserving routes (client patched to use same origin)
app.all("/api/*", (c) => forward(c, HOSTS.gateway));
app.all("/R4", (c) => forward(c, HOSTS.ci));
app.all("/R4/*", (c) => forward(c, HOSTS.ci));

// OBS media paths sometimes absolute
app.all("/r/*", (c) => forward(c, HOSTS.obs));
app.all("/oa/*", (c) => forward(c, HOSTS.obs));

app.get("/healthz", (c) => c.text("ok"));

// Static files from patched extension (www/)
app.use(
  "/*",
  serveStatic({
    root: "./www",
  })
);

app.notFound((c) => {
  if (/\.\w+$/.test(c.req.path)) return c.text("Not Found", 404);
  return c.redirect("/?fallbackBy=" + encodeURIComponent(c.req.path));
});

const port = Number(process.env.PORT) || 3000;
console.log(`LINE Web client listening on :${port}`);
serve({ fetch: app.fetch, port });
