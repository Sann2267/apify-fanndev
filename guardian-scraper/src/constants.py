TLS_PROFILE = "chrome120"
BASE_URL = "https://www.theguardian.com"
RSS_BASE = "https://www.theguardian.com/world/rss"
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}
MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0
RSS_SECTIONS = [
    "world",
    "uk-news",
    "us-news",
    "business",
    "sport",
    "technology",
    "culture",
    "science",
]
