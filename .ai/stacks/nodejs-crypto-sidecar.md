# Stack: Node.js Crypto Sidecar

> **For when a target's signature algorithm is too complex to re-implement in Python.** Run a deterministic Node subprocess that takes inputs on argv/stdin and returns the signature on stdout. No browser, no DOM, no remote script — just pure crypto. ~25ms per call. The pattern that unlocked TikTok X-Gnarly without Camoufox.

## When to use this stack

✅ The algorithm is **pure crypto** (MD5/SHA/HMAC/AES/ChaCha20/RC4/XOR) — no DOM, no network, no canvas
✅ The reference implementation exists in JS (extracted from a webmssdk-like bundle)
✅ Re-implementing in Python is high-effort or error-prone (algorithm has many magic constants)
✅ ~25ms latency per call is acceptable

❌ Don't use for browser-VM-derived signatures (Shopee `x-sap-sec`) — those need actual JS engine with timers, navigator, etc. → Camoufox.

## Architecture

```
┌─────────────────────┐         subprocess          ┌──────────────────────┐
│  Python actor       │ ────────────────────────────│  node sidecar.js     │
│                     │  argv: query, body, ua, ub  │                      │
│  await subprocess() │                             │  output: signature   │
└─────────────────────┘ ◄────────────────────────────└──────────────────────┘
       │                       stdout
       ▼
   sign attached to outgoing HTTP request
```

## File: `shared/xgnarly.js` (TikTok example)

```javascript
// Targets webmssdk version 5.1.3-ZTCA
// Source: adapted from carcabot/tiktok-xgnarly-decoded
// Pure crypto — no DOM, no network, no remote scripts.

const crypto = require("crypto");

const VERSION = "5.1.3-ZTCA";
const SDK_VERSION = "1.0.0.368";
const BASE64_ALPHABET = "shopEeSHOPkrIJ45KL02/376BM+NQcdRntquvU1VW89XDFTACGYwxZabfgijlmyz";

function md5Hex(s) {
    return crypto.createHash("md5").update(s).digest("hex");
}

function chaCha20Encrypt(key, nonce, data) {
    const cipher = crypto.createCipheriv("chacha20", key, nonce);
    return Buffer.concat([cipher.update(data), cipher.final()]);
}

function customBase64Encode(buf) {
    // Standard base64 → custom alphabet substitution
    const std = buf.toString("base64").replace(/=+$/, "");
    const stdAlphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let out = "";
    for (const ch of std) {
        out += BASE64_ALPHABET[stdAlphabet.indexOf(ch)];
    }
    return out;
}

function xorChecksum(...ints) {
    return ints.reduce((acc, v) => acc ^ v, 0);
}

function xgnarlySign(queryString, body, userAgent, ubcode = 14) {
    const ts = Math.floor(Date.now() / 1000);
    
    const md5Q = md5Hex(queryString);
    const md5B = md5Hex(body || "");
    const md5U = md5Hex(userAgent);
    
    // Build the 16-field object (verified against decoded browser X-Gnarly)
    const payload = {
        ts,
        ubcode,
        version: VERSION,
        sdk: SDK_VERSION,
        md5_query: md5Q,
        md5_body: md5B,
        md5_ua: md5U,
        xor: xorChecksum(ts, ubcode, parseInt(md5Q.slice(0, 8), 16)),
        // ... other fields per webmssdk 5.1.3-ZTCA spec
    };
    
    // ChaCha20 with magic key derived from ts + md5 fields
    const key = Buffer.from(md5Hex(`${ts}${md5Q}${md5U}`).slice(0, 32), "hex");
    const nonce = Buffer.from(md5Hex(`${ubcode}${ts}`).slice(0, 24), "hex");
    
    const plaintext = Buffer.from(JSON.stringify(payload), "utf-8");
    const encrypted = chaCha20Encrypt(key, nonce, plaintext);
    
    return customBase64Encode(encrypted);
}

// CLI entry: argv = [node, script, queryString, body, ua, ubcode]
const [, , queryString = "", body = "", ua = "", ubcode = "14"] = process.argv;
console.log(xgnarlySign(queryString, body, ua, parseInt(ubcode, 10)));
```

## Python caller

```python
import asyncio
import subprocess
from pathlib import Path

SIDECAR_PATH = Path(__file__).parent / "shared" / "xgnarly.js"


async def x_gnarly_sign(query_string: str, body: str, ua: str, ubcode: int = 14) -> str:
    """Spawn Node subprocess, return signature string. ~25ms latency."""
    proc = await asyncio.create_subprocess_exec(
        "node", str(SIDECAR_PATH),
        query_string, body, ua, str(ubcode),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"xgnarly subprocess failed: {stderr.decode()}")
    return stdout.decode().strip()
```

## Performance optimization: long-running Node process

For high-throughput, the subprocess-per-call overhead (~25ms × N calls) adds up. Run a persistent Node process and pipe requests via stdin/stdout:

### `shared/xgnarly-daemon.js`

```javascript
const readline = require("readline");
// ... xgnarlySign function as above ...

const rl = readline.createInterface({ input: process.stdin });

rl.on("line", (line) => {
    try {
        const { id, queryString, body, ua, ubcode } = JSON.parse(line);
        const sig = xgnarlySign(queryString, body || "", ua, ubcode || 14);
        process.stdout.write(JSON.stringify({ id, sig }) + "\n");
    } catch (e) {
        process.stdout.write(JSON.stringify({ error: e.message }) + "\n");
    }
});
```

### Python caller (daemon mode)

```python
import asyncio
import json
import uuid

class XGnarlyDaemon:
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.proc = None
        self.pending = {}            # id -> Future
        self._reader_task = None
    
    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            "node", self.script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
    
    async def _read_loop(self):
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            resp = json.loads(line)
            fut = self.pending.pop(resp["id"], None)
            if fut and not fut.done():
                if "error" in resp:
                    fut.set_exception(RuntimeError(resp["error"]))
                else:
                    fut.set_result(resp["sig"])
    
    async def sign(self, query_string: str, body: str, ua: str, ubcode: int = 14) -> str:
        req_id = str(uuid.uuid4())
        fut = asyncio.get_event_loop().create_future()
        self.pending[req_id] = fut
        
        self.proc.stdin.write((json.dumps({
            "id": req_id,
            "queryString": query_string,
            "body": body,
            "ua": ua,
            "ubcode": ubcode,
        }) + "\n").encode())
        await self.proc.stdin.drain()
        
        return await fut
    
    async def close(self):
        if self.proc:
            self.proc.stdin.close()
            await self.proc.wait()
```

**Latency in daemon mode:** ~2–5ms per call (no process spawn overhead).

## Dockerfile (Python + Node together)

```dockerfile
FROM apify/actor-python:3.12

# Install Node.js 20 alongside Python
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && node --version

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# package.json optional — if your sidecar has no npm deps, skip it.
# COPY package.json ./
# RUN npm install --omit=dev

COPY . ./
```

## Layout

```
actor-tiktok-X/
├── .actor/
│   └── Dockerfile             # installs Node + Python
├── src/
│   ├── __main__.py
│   ├── main.py
│   ├── client.py
│   ├── shared/
│   │   ├── xbogus.py          # X-Bogus pure Python (URL-derivable)
│   │   ├── xgnarly.js         # X-Gnarly Node sidecar
│   │   └── tiktok_client.py   # client wrapper that invokes sidecar
│   └── ...
├── requirements.txt
└── package.json               # optional, if sidecar has npm deps
```

## Reliability patterns

### Graceful no-op fallback when Node missing

```python
async def maybe_sign(query_string: str, body: str, ua: str) -> str | None:
    if not SIDECAR_PATH.exists() or not shutil.which("node"):
        logger.warning("X-Gnarly sidecar unavailable — proceeding unsigned (some endpoints will fail)")
        return None
    return await x_gnarly_sign(query_string, body, ua)
```

This lets the actor still run on hosts without Node installed (CI smoke tests, etc.) — signed-only endpoints fail gracefully.

### Concurrent calls — semaphore on subprocess pool

```python
SIGN_SEM = asyncio.Semaphore(8)   # limit concurrent Node subprocesses

async def x_gnarly_sign_bounded(*args):
    async with SIGN_SEM:
        return await x_gnarly_sign(*args)
```

Without bounding, a burst of 100 concurrent scrapes spawns 100 Node processes simultaneously → OOM.

## Version drift management

The upstream algorithm (webmssdk) updates: 5.1.0 → 5.1.1 → 5.1.2 → 5.1.3 → 5.1.3-ZTCA over 6 months. When signatures stop validating:

1. Smoke test fails with 4xx
2. Pull latest `xgnarly.js` from `carcabot/tiktok-xgnarly-decoded` (or your upstream)
3. Update version constants
4. Re-deploy

**Cadence:** monthly check, immediate update on production failure.

## Sandboxing / safety

The Node sidecar **must not**:
- Make network requests
- Read/write arbitrary files (other than its own script directory)
- Execute remote code (no `vm.runInNewContext` of fetched bundles)
- Have npm deps that aren't audited

If the algorithm requires DOM/browser APIs (canvas, navigator) → it's NOT pure crypto → use Camoufox instead, not this sidecar.

## Where used

- TikTok Apify Actors Collection — `shared/xgnarly.js` invoked from all signed-call paths
- Pattern reusable for any sign-only algorithm extracted from a JS bundle:
  - Custom HMAC variants
  - JWT signing with non-standard alg
  - Proprietary signature schemes (e.g. Aliexpress signhash, Lazada smsign)

## Caveats

- **Don't bundle the original webmssdk JS file** — it has the JS-VM challenge code which would re-introduce browser dependency. Extract only the crypto subroutine into clean code.
- **Subprocess output must be a single line** of stdout. Any logging in the sidecar → log to stderr.
- **Permitted exception to "Python-only" rule** — the Node sidecar is considered an acceptable dependency. Document this explicitly in the actor README.
- **Don't update Node major version mid-deploy.** Pin Node 20 LTS until the next quarterly review.

## See also
- [`anti-bot/tiktok-mssdk.md`](../anti-bot/tiktok-mssdk.md)
- [`stacks/python-apify-actor.md`](python-apify-actor.md)
- [`lessons-learned.md`](../lessons-learned.md) (Camoufox alternatives)
