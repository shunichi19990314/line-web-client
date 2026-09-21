import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";

const app = new Hono();

// QR long-poll ~150–180s
const LONG_POLL_MS = 210_000;

// Official Chrome extension identity (keep in sync with patched build)
const EXT_ID = "ophjlpahpchlmihnnnihgmmeilfjmjjc";
const EXT_ORIGIN = `chrome-extension://${EXT_ID}`;
// Match a recent official build; fetch_and_patch should keep this aligned
const CHROME_VERSION = process.env.LINE_CHROME_VERSION || "3.7.2";
const UA =
  process.env.LINE_UA ||
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const HOSTS = {
  gateway: "https://line-chrome-gw.line-apps.com",
  ci: "https://ci.line-apps.com",
  obs: "https://obs.line-apps.com",
  uts: "https://uts-front.line-apps.com",
};

// --- Simple per-IP rate limit (reduce burst / bot-like traffic) ---
const rateMap = new Map();
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 120; // requests per minute per IP (normal chat is far below this)

function clientIp(c) {
  return (
    c.req.header("cf-connecting-ip") ||
    c.req.header("x-forwarded-for")?.split(",")[0]?.trim() ||
    c.req.header("x-real-ip") ||
    "unknown"
  );
}

function allowRequest(ip) {
  const now = Date.now();
  let entry = rateMap.get(ip);
  if (!entry || now - entry.start > RATE_WINDOW_MS) {
    entry = { start: now, count: 0 };
    rateMap.set(ip, entry);
  }
  entry.count += 1;
  // opportunistic cleanup
  if (rateMap.size > 5000) {
    for (const [k, v] of rateMap) {
      if (now - v.start > RATE_WINDOW_MS) rateMap.delete(k);
    }
  }
  return entry.count <= RATE_MAX;
}

/**
 * Forward to LINE with headers closer to the official extension.
 * Path+query are preserved (required for X-Hmac).
 */
async function forward(c, base) {
  const ip = clientIp(c);
  if (!allowRequest(ip)) {
    return c.json({ error: "rate_limited", message: "Too many requests" }, 429);
  }

  const incoming = new URL(c.req.url);
  const targetURL = base.replace(/\/$/, "") + incoming.pathname + incoming.search;

  const headers = new Headers();

  // Pass through client headers that LINE expects
  const pass = [
    "content-type",
    "accept",
    "accept-language",
    "x-line-access",
    "x-line-application",
    "x-line-channeltoken",
    "x-line-session-id",
    "x-lst",
    "x-hmac",
    "x-lal",
    "x-lpv",
  ];
  for (const name of pass) {
    const v = c.req.header(name);
    if (v) headers.set(name, v);
  }

  // Normalize identity headers to look like official extension
  headers.set("origin", EXT_ORIGIN);
  headers.set("referer", `${EXT_ORIGIN}/`);
  headers.set("user-agent", UA);
  headers.set("x-line-chrome-version", CHROME_VERSION);
  if (!headers.has("x-lal")) {
    headers.set("x-lal", "ja_JP");
  }
  if (!headers.has("accept-language")) {
    headers.set("accept-language", "ja,en-US;q=0.9,en;q=0.8");
  }
  // Do not forward browser cookies from the web origin
  headers.delete("cookie");

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
    // Avoid logging tokens / bodies
    if (process.env.DEBUG_PROXY === "1") {
      console.log(`[proxy] ${c.req.method} ${incoming.pathname}`);
    }
    const response = await fetch(targetURL, init);

    const resHeaders = new Headers(response.headers);
    resHeaders.set("Access-Control-Allow-Origin", "*");
    resHeaders.set("Access-Control-Allow-Methods", "*");
    resHeaders.set("Access-Control-Allow-Headers", "*");
    resHeaders.set("Access-Control-Expose-Headers", "*");
    resHeaders.set("Cache-Control", "no-store");
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");
    resHeaders.delete("set-cookie");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  } catch (err) {
    const timeout =
      err?.name === "TimeoutError" ||
      err?.name === "AbortError" ||
      String(err?.message || "")
        .toLowerCase()
        .includes("abort");
    if (process.env.DEBUG_PROXY === "1") {
      console.error(`[proxy] FAIL ${incoming.pathname}`, err?.name);
    }
    return c.json(
      {
        error: timeout ? "timeout" : "proxy_failed",
        message: timeout ? "Request timed out" : "Upstream error",
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

app.all("/api/*", (c) => forward(c, HOSTS.gateway));
app.all("/R4", (c) => forward(c, HOSTS.ci));
app.all("/R4/*", (c) => forward(c, HOSTS.ci));
app.all("/r/*", (c) => forward(c, HOSTS.obs));
app.all("/oa/*", (c) => forward(c, HOSTS.obs));

app.get("/healthz", (c) => c.text("ok"));

app.use("/*", serveStatic({ root: "./www" }));

app.notFound((c) => {
  if (/\.\w+$/.test(c.req.path)) return c.text("Not Found", 404);
  return c.redirect("/?fallbackBy=" + encodeURIComponent(c.req.path));
});

const port = Number(process.env.PORT) || 3000;
console.log(`LINE Web client on :${port} (chrome-version=${CHROME_VERSION})`);
serve({ fetch: app.fetch, port });
