# Stack: Beanstalkd + Kafka Production Pipeline

> **For when Apify Marketplace per-result billing doesn't scale.** This is the alternative when you're scraping millions of records into your own infra: Beanstalkd as job queue (producer/consumer split), Kafka as output stream, MySQL for stateful account/session pools, S3 for content-addressed binary mirroring.

## When to use this stack (not Apify Marketplace)

- **Volume:** > 100k records/day continuous
- **Multi-stage scraping:** discovery → enrichment → reviews (each a separate worker pool)
- **Stateful account rotation** (Shopee Camoufox: accounts with cooldown/captcha states)
- **Image mirroring** required (S3 content-addressed paths)
- **Internal-only deployment** (no marketplace customers)
- **Existing Kafka infrastructure** to plug into

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Discovery      │      │  Detail         │      │  Reviews        │
│  Worker         │      │  Worker         │      │  Worker         │
│  (1..N pods)    │      │  (1..N pods)    │      │  (1..N pods)    │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         │  enqueue               │  enqueue               │  consume
         ▼                        ▼                        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │            Beanstalkd (greenstalk client)                     │
   │   tubes:  sc-shopee-keyword  sc-shopee-detail  sc-...-reviews │
   └──────────────────────────────────────────────────────────────┘
         │                        │                        │
         │  emit                  │  emit                  │  emit
         ▼                        ▼                        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                 Kafka (KRaft mode, no Zookeeper)              │
   │   topics: sc-shopee-crawler  tiktok_post  tokopedia-products  │
   └──────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                       Downstream consumers (ES / SQL / RAG)

   Optional sidecars:
   ┌─────────────┐                ┌─────────────┐
   │   MySQL     │                │   S3        │
   │ account     │                │ image       │
   │ pool +      │                │ mirror      │
   │ session     │                │ (md5 path)  │
   │ state       │                │             │
   └─────────────┘                └─────────────┘
```

## Tube/topic naming convention

```
Beanstalkd tubes:
  sc-{platform}-{stage}        e.g. sc-shopee-detail, sc-tokopedia-products
  
Kafka topics:
  sc-{platform}-{record-type}  e.g. sc-shopee-crawler, sc-tiktok-comment
  
S3 paths (content-addressed):
  image/marketplace/{platform}/{XX}/{YY}/image.{ext}
  where {XX}/{YY} = first 4 hex chars of md5(image_url)
```

## Component: `config.ini`

```ini
[beanstalk]
host = beanstalk.prod.internal
port = 11300
default_ttr = 300

[kafka]
bootstrap_servers = kafka01:9092,kafka02:9092,kafka03:9092
client_id = sc-shopee-detail-worker

[scraper]
mode = product_detail
max_concurrency = 4
request_delay_min = 0.5
request_delay_max = 1.5
max_retries = 3
sort_by = newest
filter_by = all

[s3]
endpoint = https://s3.internal:9000
bucket = sc-crawler-images
access_key = ...
secret_key = ...

[mysql]
host = mysql.prod.internal
db = shopee_camoufox
user = scraper
password = ...
```

## Component: producer (enqueue jobs)

```python
import greenstalk

class JobProducer:
    def __init__(self, host: str, port: int, tube: str):
        self.client = greenstalk.Client((host, port), use=tube)
    
    def push(self, payload: dict, priority: int = 1024, delay: int = 0, ttr: int = 300):
        """ttr = time to run before re-queue (seconds)."""
        return self.client.put(
            json.dumps(payload),
            priority=priority,
            delay=delay,
            ttr=ttr,
        )
    
    def close(self):
        self.client.close()


# Usage in discovery worker:
producer = JobProducer("beanstalk.prod.internal", 11300, "sc-shopee-detail")
for item_id in discovered_items:
    producer.push({"shop_id": shop_id, "item_id": item_id})
```

## Component: consumer (worker drain pattern)

```python
import greenstalk
import json
import time

class JobConsumer:
    def __init__(self, host: str, port: int, tube: str):
        self.client = greenstalk.Client((host, port), watch=tube)
        self.client.ignore("default")
    
    def run(self, handle_fn):
        """Loop forever. handle_fn(job_id, payload) returns True on success."""
        while True:
            try:
                job = self.client.reserve(timeout=60)
                if job is None:
                    continue
                
                payload = json.loads(job.body)
                try:
                    success = handle_fn(job.id, payload)
                    if success:
                        self.client.delete(job)
                    else:
                        self.client.bury(job)        # bury for later inspection
                except Exception as e:
                    logger.exception(f"Job {job.id} failed: {e}")
                    self.client.bury(job)
            except greenstalk.TimedOutError:
                continue
            except Exception as e:
                logger.exception("Worker loop error")
                time.sleep(5)
```

## Component: long-running TTR refresh

For jobs that take >TTR (e.g. browser-based scraping), touch every 30s:

```python
import threading

class TTRToucher:
    def __init__(self, client, job, interval=30):
        self.client = client
        self.job = job
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
    
    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.client.touch(self.job)
            except Exception:
                pass
    
    def __enter__(self):
        self._thread.start()
        return self
    
    def __exit__(self, *args):
        self._stop.set()


# Usage:
with TTRToucher(consumer.client, job):
    # do long-running work — TTR auto-refreshed every 30s
    result = scrape_with_browser(payload)
```

## Component: Kafka output

```python
from confluent_kafka import Producer
import json

class KafkaSink:
    def __init__(self, bootstrap: str, client_id: str):
        self.producer = Producer({
            "bootstrap.servers": bootstrap,
            "client.id": client_id,
            "compression.type": "snappy",
            "acks": "all",
            "retries": 5,
        })
    
    def emit(self, topic: str, key: str, value: dict):
        self.producer.produce(
            topic=topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            callback=self._delivery_callback,
        )
        self.producer.poll(0)
    
    def _delivery_callback(self, err, msg):
        if err:
            logger.error(f"Kafka delivery failed: {err}")
    
    def flush(self, timeout: float = 10):
        self.producer.flush(timeout)
```

**Key choice matters** — use a deterministic key (`{shop_id}_{item_id}`) so updates to the same entity land on the same partition for ordering guarantees.

## Component: S3 image mirroring (content-addressed)

```python
import hashlib
import boto3
from urllib.parse import urlparse

class S3ImageMirror:
    def __init__(self, endpoint: str, bucket: str, ak: str, sk: str):
        self.s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=ak, aws_secret_access_key=sk)
        self.bucket = bucket
    
    def mirror(self, url: str, platform: str) -> str:
        """Download URL, store at md5-prefixed path, return s3 key."""
        h = hashlib.md5(url.encode()).hexdigest()
        ext = urlparse(url).path.split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        
        key = f"image/marketplace/{platform}/{h[:2]}/{h[2:4]}/{h}.{ext}"
        
        # Idempotent: skip if already exists
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return key
        except self.s3.exceptions.ClientError:
            pass
        
        # Fetch + upload
        import requests
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=r.content, ContentType=f"image/{ext}")
        return key
```

## Component: account pool (MySQL-backed, Shopee Camoufox pattern)

```sql
CREATE TABLE accounts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) UNIQUE,
    state ENUM('available', 'in_use', 'captcha', 'cooldown', 'banned', 'disabled') NOT NULL,
    vm_ip VARCHAR(64),                       -- multi-VM scoping
    last_used_at DATETIME,
    captcha_count INT DEFAULT 0,
    cooldown_until DATETIME,
    notes TEXT
);

CREATE INDEX idx_state_vm ON accounts(state, vm_ip);
CREATE INDEX idx_lastused ON accounts(last_used_at);
```

```python
class AccountPool:
    def acquire(self, vm_ip: str) -> dict | None:
        """FIFO: oldest available + lowest captcha_count."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, username FROM accounts
                WHERE state = 'available' AND vm_ip = %s
                ORDER BY last_used_at ASC, captcha_count ASC
                LIMIT 1 FOR UPDATE
            """, (vm_ip,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("""
                UPDATE accounts SET state = 'in_use', last_used_at = NOW()
                WHERE id = %s
            """, (row["id"],))
        return row
    
    def mark_captcha(self, acct_id: int, cooldown_min: int = 10):
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE accounts
                SET state = 'cooldown',
                    captcha_count = captcha_count + 1,
                    cooldown_until = DATE_ADD(NOW(), INTERVAL %s MINUTE)
                WHERE id = %s
            """, (cooldown_min, acct_id))
    
    def release(self, acct_id: int):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE accounts SET state = 'available' WHERE id = %s", (acct_id,))
    
    def reset_stale_locks(self, max_age_min: int = 30):
        """Periodic cleanup: accounts stuck 'in_use' > N min → available."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE accounts
                SET state = 'available'
                WHERE state = 'in_use'
                  AND last_used_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)
            """, (max_age_min,))
```

## Docker Compose for local dev

```yaml
# docker-compose.yml
services:
  beanstalk:
    image: schickling/beanstalkd
    ports: ["11300:11300"]
  
  kafka:
    image: bitnami/kafka:3.7
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: broker,controller
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CFG_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    ports: ["9092:9092"]
  
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports: ["9000:9000", "9001:9001"]
  
  mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: scraper
    ports: ["3306:3306"]
```

## Operational discipline

- **Job acks:** delete on success, bury on failure. Never just timeout — bury makes the job inspectable.
- **TTR vs job duration:** TTR > p99 of job duration. If exceeded, use TTRToucher.
- **Kafka delivery:** use `acks=all` for at-least-once. Idempotent consumers downstream.
- **S3 idempotency:** content-addressed paths make re-runs free.
- **Monitoring:** Streamlit dashboard for tube stats + account pool health is standard pattern (Shopee shopesss has this).

## Where used

- Tokopedia production pipeline (3-mode: shop_detail → product_detail → product_reviews; Kafka topics `sc-tokopedia-*-data-industry`)
- TikTok Crawler — TikMine (Beanstalkd + Kafka, Pydantic-validated models)
- Shopee Camoufox shopesss (search + detail workers, MySQL account pool, S3 image mirror, Streamlit dashboard, Telegram alerting)

## Caveats

- **Beanstalkd is single-process; not HA.** Run a single node — if it dies, you lose buried jobs. For HA, swap to NATS or RabbitMQ.
- **Don't put long-lived state in tubes.** Tubes are for in-flight work. Persistent state → MySQL.
- **Kafka with KRaft (no Zookeeper)** is recommended for new deployments. Don't bring back ZK in 2026.
- **MinIO for local dev** is fine; production should use S3 / GCS / Azure Blob for durability.
- **Don't share account pool across platforms.** One pool per platform (shopee_camoufox, tokopedia_accounts) — different rules.

## See also
- [`stacks/python-apify-actor.md`](python-apify-actor.md) (the simpler alternative)
- [`stacks/nodejs-crypto-sidecar.md`](nodejs-crypto-sidecar.md) (when integrating TikTok X-Gnarly)
- [`conventions/dataset-envelope.md`](../conventions/dataset-envelope.md)
