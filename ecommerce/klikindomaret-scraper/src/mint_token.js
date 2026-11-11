// Headless AWS WAF (goku) token minter for klikindomaret.com.
//
// Runs the site's AwsWafIntegration challenge SDK under jsdom with Node's
// WebCrypto, intercepts the multipart /mp_verify response, and prints the
// earned `x-aws-waf-token` to stdout. No browser required: the challenge is a
// `NetworkBandwidth` type whose "solution_data" is a fixed zero-byte blob, so a
// DOM shim + WebCrypto is enough to satisfy it.
//
// Usage: node mint_token.js <sdk_url>
const { JSDOM } = require('jsdom');
const { webcrypto } = require('crypto');

const SITE = 'https://www.klikindomaret.com';
const SDK_URL = process.argv[2];
if (!SDK_URL) {
  process.stderr.write('usage: node mint_token.js <sdk_url>\n');
  process.exit(2);
}

async function main() {
  const r = await fetch(SDK_URL, { headers: { Referer: SITE + '/' } });
  if (!r.ok) throw new Error('SDK fetch failed: ' + r.status);
  const src = await r.text();

  const dom = new JSDOM('<!DOCTYPE html><html><head></head><body></body></html>', {
    url: SITE + '/',
    referrer: SITE + '/',
    pretendToBeVisual: true,
    runScripts: 'outside-only',
  });
  const w = dom.window;
  Object.defineProperty(w, 'crypto', { value: webcrypto, writable: true, configurable: true });
  w.performance = w.performance || { now: () => Date.now() };

  let done = false;
  const gotToken = new Promise((resolve) => {
    w.__emit = (tok) => { if (!done && tok) { done = true; resolve(tok); } };
  });

  w.fetch = async (url, opts) => {
    const u = typeof url === 'string' ? url : url.url;
    let body = opts && opts.body;
    const headers = { ...(opts && opts.headers), Origin: SITE, Referer: SITE + '/' };
    // jsdom builds a FormData for the multipart verify; rebuild it for Node fetch
    // and drop the DOM-set content-type so the boundary is generated correctly.
    if (body && typeof body !== 'string' && typeof body.entries === 'function') {
      const nf = new FormData();
      for (const [k, v] of body.entries()) nf.append(k, v);
      body = nf;
      for (const k of Object.keys(headers)) {
        if (k.toLowerCase() === 'content-type') delete headers[k];
      }
    }
    const res = await fetch(u, { ...opts, body, headers });
    const text = await res.text();
    if (u.includes('/mp_verify')) {
      try {
        const j = JSON.parse(text);
        if (j.token) w.__emit(j.token);
      } catch (e) { /* ignore non-JSON */ }
    }
    return { ok: res.ok, status: res.status, json: async () => JSON.parse(text), text: async () => text };
  };

  w.eval(src);

  const token = await Promise.race([
    gotToken,
    new Promise((_, rej) => setTimeout(() => rej(new Error('mint timeout')), 45000)),
  ]);
  process.stdout.write(token || '');
  process.exit(0);
}

main().catch((e) => {
  process.stderr.write(String((e && e.stack) || e));
  process.exit(1);
});
