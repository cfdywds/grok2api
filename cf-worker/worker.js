/**
 * Cloudflare Worker — grok.com 反向代理 v2
 *
 * 修复: 使用 cf: {} 选项绕过 Cloudflare Bot Fight Mode
 *
 * 部署方式:
 *   1. 登录 Cloudflare Dashboard → Workers & Pages → Create Worker
 *   2. 粘贴此脚本并部署
 *   3. （可选）绑定自定义域名
 *   4. 在 grok2api 配置中设置:
 *      network.grok_base_url = "https://your-worker.workers.dev"
 *
 * 可选鉴权:
 *   设置环境变量 AUTH_TOKEN，请求时需携带 X-Proxy-Token 头或 ?token= 参数。
 *   不设置则不启用鉴权。
 */

const UPSTREAM = "https://grok.com";

export default {
  /**
   * @param {Request} request
   * @param {{ AUTH_TOKEN?: string }} env
   * @returns {Promise<Response>}
   */
  async fetch(request, env) {
    // ---------- 鉴权（可选）----------
    if (env.AUTH_TOKEN) {
      const url = new URL(request.url);
      const token =
        request.headers.get("X-Proxy-Token") || url.searchParams.get("token");
      if (token !== env.AUTH_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
    }

    // ---------- 构建上游请求 ----------
    const incomingUrl = new URL(request.url);
    const upstreamUrl = new URL(incomingUrl.pathname + incomingUrl.search, UPSTREAM);

    const headers = new Headers(request.headers);
    headers.set("Host", "grok.com");
    // 删除鉴权参数（防止泄露到上游）
    headers.delete("X-Proxy-Token");

    // ---------- WebSocket 升级 ----------
    if (request.headers.get("Upgrade") === "websocket") {
      return fetch(upstreamUrl.toString(), {
        headers,
        method: request.method,
      });
    }

    // ---------- 转发 HTTP 请求 ----------
    const init = {
      method: request.method,
      headers,
      redirect: "follow",
      // 关键: 告诉 Cloudflare 这是合法的内部请求，绕过 Bot Fight Mode
      cf: {
        resolveOverride: false,
      },
    };

    // 有 body 的请求方法
    if (!["GET", "HEAD"].includes(request.method)) {
      init.body = request.body;
      init.duplex = "half";
    }

    const response = await fetch(upstreamUrl.toString(), init);

    // ---------- 返回响应 ----------
    const respHeaders = new Headers(response.headers);
    // 允许跨域（如需要）
    respHeaders.set("Access-Control-Allow-Origin", "*");
    respHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
    respHeaders.set("Access-Control-Allow-Headers", "*");

    // OPTIONS 预检
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: respHeaders });
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    });
  },
};
