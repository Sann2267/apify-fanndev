// Headless AWS WAF (goku) token minter for traveloka.com.
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

const SITE = 'https://www.traveloka.com';
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


  // --- canvas / WebGL shims: the Traveloka challenge fingerprints them ---
  const mkCtx2d = () => ({
    canvas: null, fillStyle: '', strokeStyle: '', font: '', globalAlpha: 1,
    textBaseline: '', lineWidth: 1, shadowColor: '', shadowBlur: 0,
    fillRect(){}, strokeRect(){}, clearRect(){}, fillText(){}, strokeText(){},
    beginPath(){}, closePath(){}, moveTo(){}, lineTo(){}, arc(){}, rect(){},
    bezierCurveTo(){}, quadraticCurveTo(){}, ellipse(){}, fill(){}, stroke(){},
    save(){}, restore(){}, translate(){}, rotate(){}, scale(){}, transform(){},
    setTransform(){}, clip(){}, drawImage(){}, putImageData(){},
    createLinearGradient: () => ({ addColorStop(){} }),
    createRadialGradient: () => ({ addColorStop(){} }),
    createPattern: () => null,
    measureText: (t) => ({ width: (String(t || '').length * 7.2), actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 }),
    getImageData: (x, y, w, h) => ({ data: new Uint8ClampedArray(Math.max(1, (w|0) * (h|0) * 4)), width: w|0, height: h|0 }),
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(Math.max(1, (w|0) * (h|0) * 4)), width: w|0, height: h|0 }),
    isPointInPath: () => false, getContextAttributes: () => ({ alpha: true }),
  });
  const GL_STRINGS = {
    7936: 'WebKit', 7937: 'WebKit WebGL', 7938: 'WebGL 1.0 (OpenGL ES 2.0 Chromium)',
    35724: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)',
    37445: 'Google Inc. (Intel)', 37446: 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)',
  };
  const mkCtxGL = () => ({
    canvas: null, drawingBufferWidth: 300, drawingBufferHeight: 150,
    getParameter: (p) => (p in GL_STRINGS ? GL_STRINGS[p] : 0),
    getExtension: (n) => (n === 'WEBGL_debug_renderer_info' ? { UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 } : null),
    getSupportedExtensions: () => ['WEBGL_debug_renderer_info', 'OES_texture_float'],
    getShaderPrecisionFormat: () => ({ rangeMin: 127, rangeMax: 127, precision: 23 }),
    createBuffer(){return {};}, bindBuffer(){}, bufferData(){}, createProgram(){return {};},
    createShader(){return {};}, shaderSource(){}, compileShader(){}, attachShader(){},
    linkProgram(){}, useProgram(){}, getAttribLocation(){return 0;}, getUniformLocation(){return {};},
    enableVertexAttribArray(){}, vertexAttribPointer(){}, uniform2f(){}, drawArrays(){},
    viewport(){}, clearColor(){}, clear(){}, enable(){}, disable(){}, readPixels(){},
  });
  w.HTMLCanvasElement.prototype.getContext = function (type) {
    const ctx = (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2') ? mkCtxGL() : mkCtx2d();
    ctx.canvas = this;
    return ctx;
  };
  w.HTMLCanvasElement.prototype.toDataURL = function () {
    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  };
  w.HTMLCanvasElement.prototype.toBlob = function (cb) { cb && cb(new w.Blob([], { type: 'image/png' })); };

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
