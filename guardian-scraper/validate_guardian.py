from curl_cffi import requests

url = 'https://www.theguardian.com/world/2024/aug/02/uk-rainfall-flooding-weather'
resp = requests.get(url, timeout=30, impersonate='chrome120')
print('status=', resp.status_code)
print('content_type=', resp.headers.get('content-type'))
print('has_jsonld=', 'application/ld+json' in resp.text)
print('has_headline=', 'headline' in resp.text.lower())
print('sample=', resp.text[:300].replace('\n', ' '))
print('rss_status=', requests.get('https://www.theguardian.com/world/rss', timeout=30, impersonate='chrome120').status_code)
