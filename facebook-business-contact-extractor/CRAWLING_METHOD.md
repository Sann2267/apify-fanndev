# Crawling method — Facebook business contacts

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## There is no public page search, so discovery goes through the Ad Library

Every Facebook search vertical returns **HTTP 404** to a logged-out client:

```
/search/pages/?q=coffee%20shop%20jakarta   404
/search/places/?q=dentist%20london         404
/search/groups/?q=photography              404
/search/top/?q=plumber%20chicago           404
/search/posts/?q=coffee                    404
```

(`/events/search/?q=` is the one exception, and it only returns events.)

The Ad Library is keyword-addressable and country-scoped, and every ad node
carries `snapshot.page_profile_uri`, `snapshot.page_name` and `page_id`. So a
keyword search there is, in effect, a page search — with the bonus that
everything it returns belongs to a business currently paying for ads. A live run
for `"dentist"` in the US produced 53 distinct pages from 90 ads. The Ad Library
transport (403 `__rd_verify` challenge, SSR, GraphQL pagination) is documented in
the `facebook-ad-library-scraper` actor and reused verbatim here.

## The about tab is the contact source

`GET /{slug}/about` returns 8–18 MB with the contact block in its embedded JSON:

```
field_section_type: about_contact_info
  profile_fields.nodes[]
    {field_type: "profile_email",     title.text: "info@barbutonyc.com"}
    {field_type: "profile_phone",     title.text: "+1 212-924-9700"}
    {field_type: "website",           title.text: "http://www.barbutonyc.com/"}
    {field_type: "address",           title.text: "113 horatio street, ..."}
    {field_type: "business_hours",    title.text: "Closed now"}
    {field_type: "business_price",    title.text: "Price range · ££"}
    {field_type: "business_services", title.text: "Delivery · Takeaway"}
    {field_type: "screenname",        title.text: "Barbutonyc"}
    {field_type: "ratings",           title.text: "94% recommend (1,236 reviews)"}
    {field_type: "category",          title.text: "Italian restaurant"}
```

Surveyed across five pages: local businesses expose the full set; large brands
(`dominos`, `starbucks`) publish only `website`, `category` and `ratings`. That
is the business's own choice, and the actor reports the difference rather than
hiding it behind empty strings.

`/{slug}/about_contact_and_basic_info` returns the same fields at the same size,
so there is no cheaper sub-tab to fetch. The page root (1.4 MB) carries **no**
contact fields at all.

## Opening hours are not published

`business_hours` is `"Open now"` or `"Closed now"` — a status, not a schedule.
Its `list_item_groups` contains only the label `"Hours"`. There is no weekly
timetable anywhere in the logged-out payload, which is why the output field is
called `hoursLabel`.

## The transparency tab adds qualification data

`GET /{slug}/about_profile_transparency` (17 MB) publishes a different field set:

```
{field_type: "page_id",       title.text: "312424259859"}
{field_type: "creation_date", title.text: "17 February 2010"}
{field_type: "ad_status",     title.text: "This Page isn't currently running ads."}
```

Page age and advertising status are both strong lead qualifiers, which is why
this is offered — but it doubles the bandwidth per page, so it is opt-in.

## Websites come wrapped

`link_url` is `https://l.facebook.com/l.php?u=<encoded>&h=<token>`, and the token
changes between two fetches of the same page — so the wrapped URL is not even
stable, let alone useful. `unwrap_link()` recovers the real destination.

## Existence is judged on payload size, not status code

Facebook answers HTTP 200 for a slug that does not exist and serves a ~330 KB
shell. `zz-not-a-real-page-98765` returns the shell; `BarbutoNYC` returns 17 MB.
The actor emits a `page_not_found` error row for the former rather than a blank
business row — the same discriminator the `facebook-page-validator` actor is
built on.

## Cost shape

One request per page (8–18 MB), doubled when the transparency tab is on, plus
the Ad Library requests for discovery (~1 request per 30 ads). Concurrency
defaults to 4 because of the payload size, not because of rate limiting. No
proxy, no browser.
