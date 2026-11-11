import { Actor } from 'apify';
import { HttpCrawler, log } from 'crawlee';

import {
    ITEMS_PER_PAGE,
    MAX_ITEMS_PER_QUERY,
    SORT_OPTIONS,
    apiHeaders,
    buildSearchUrl,
    parseCategoryId,
    refererForQuery,
} from './blibli.js';
import { LABELS, createRouter } from './routes.js';

await Actor.init();

const input = (await Actor.getInput()) ?? {};

const {
    searchTerms = [],
    categories = [],
    maxItemsPerQuery = 100,
    sortBy = 'relevance',
    minPrice,
    maxPrice,
    fetchProductDetails = false,
    includeOutOfStock = true,
    maxConcurrency = 8,
    proxyConfiguration: proxyInput,
} = input;

const queries = buildQueries({ searchTerms, categories });

if (!queries.length) {
    await Actor.fail(
        'Tidak ada yang bisa dipantau. Isi minimal satu kata kunci di "searchTerms" '
        + 'atau satu kategori di "categories".',
    );
}

if (!(sortBy in SORT_OPTIONS)) {
    await Actor.fail(
        `sortBy "${sortBy}" tidak dikenal. Pilihan: ${Object.keys(SORT_OPTIONS).join(', ')}.`,
    );
}

// Blibli berhenti melayani setelah 20 halaman, jadi tak ada gunanya meminta lebih.
const cappedMaxItems = Math.min(maxItemsPerQuery, MAX_ITEMS_PER_QUERY);
if (cappedMaxItems < maxItemsPerQuery) {
    log.warning(
        `Blibli membatasi ${MAX_ITEMS_PER_QUERY} hasil per query; `
        + `maxItemsPerQuery diturunkan dari ${maxItemsPerQuery} ke ${cappedMaxItems}. `
        + 'Untuk menembusnya, pecah query dengan rentang minPrice/maxPrice.',
    );
}

const config = {
    maxItemsPerQuery: cappedMaxItems,
    sort: SORT_OPTIONS[sortBy],
    minPrice: Number.isFinite(minPrice) ? minPrice : undefined,
    maxPrice: Number.isFinite(maxPrice) ? maxPrice : undefined,
    fetchProductDetails,
    includeOutOfStock,
};

const state = {
    counts: new Map(),
    seen: new Set(),
    pushed: 0,
};

const proxyConfiguration = await Actor.createProxyConfiguration(proxyInput);

const crawler = new HttpCrawler({
    proxyConfiguration,
    maxConcurrency,
    // IP residensial kena 403 secara acak per IP; tiap retry memakai sesi (IP)
    // baru, jadi butuh jatah retry yang lebar agar satu query tidak kosong.
    maxRequestRetries: 20,
    requestHandlerTimeoutSecs: 90,
    // Endpoint pencarian mengembalikan application/json, yang secara default
    // dilewati HttpCrawler.
    additionalMimeTypes: ['application/json'],
    useSessionPool: true,
    persistCookiesPerSession: true,
    sessionPoolOptions: {
        sessionOptions: { maxErrorScore: 1 },
    },
    preNavigationHooks: [
        // Blibli mencocokkan Sec-Fetch-*, sec-ch-ua, dan User-Agent satu sama lain,
        // jadi header dikunci ke satu profil Chrome desktop agar tidak saling
        // bertentangan dengan header eksplisit tiap request.
        async (_context, gotOptions) => {
            gotOptions.headerGeneratorOptions = {
                browsers: [{ name: 'chrome', minVersion: 120 }],
                devices: ['desktop'],
                operatingSystems: ['windows', 'macos'],
                locales: ['id-ID', 'en-US'],
            };
        },
    ],
    requestHandler: createRouter({ config, state }),
    failedRequestHandler: async ({ request }, error) => {
        log.error(`Menyerah pada ${request.url}: ${error.message}`);
    },
});

const startRequests = queries.map((query) => ({
    url: buildSearchUrl({
        searchTerm: query.kind === 'search' ? query.value : undefined,
        categoryId: query.kind === 'category' ? query.value : undefined,
        page: 1,
        sort: config.sort,
        minPrice: config.minPrice,
        maxPrice: config.maxPrice,
    }),
    label: LABELS.LIST,
    headers: apiHeaders(refererForQuery(query)),
    userData: { query, page: 1 },
}));

log.info(
    `Memantau ${queries.length} query (${queries.map((q) => q.label).join(', ')}) `
    + `— maksimal ${config.maxItemsPerQuery} produk per query, `
    + `${ITEMS_PER_PAGE} produk per permintaan.`,
);

await crawler.run(startRequests);

const summary = queries
    .map((q) => `${q.label}: ${state.counts.get(q.key) ?? 0}`)
    .join(' | ');

log.info(`Selesai. ${state.pushed} produk tersimpan. ${summary}`);
await Actor.setStatusMessage(`${state.pushed} produk tersimpan dari ${queries.length} query.`);

await Actor.exit();

/**
 * Mengubah input mentah menjadi daftar query bernama.
 *
 * `key` dipakai untuk penghitung dan dedup; `label` hanya untuk log.
 */
function buildQueries({ searchTerms, categories }) {
    const queries = [];

    for (const term of asArray(searchTerms)) {
        const value = String(term ?? '').trim();
        if (!value) continue;
        queries.push({
            kind: 'search',
            value,
            key: `search:${value.toLowerCase()}`,
            label: `kata kunci "${value}"`,
        });
    }

    for (const entry of asArray(categories)) {
        // Field bisa berupa string atau objek {url} kalau editor Apify
        // merendernya sebagai daftar request.
        const rawValue = typeof entry === 'object' && entry !== null ? (entry.url ?? entry.value) : entry;
        const categoryId = parseCategoryId(rawValue);

        if (!categoryId) {
            log.warning(`Melewati kategori yang tidak bisa dibaca: ${JSON.stringify(entry)}`);
            continue;
        }

        queries.push({
            kind: 'category',
            value: categoryId,
            key: `category:${categoryId}`,
            label: `kategori ${categoryId}`,
        });
    }

    // Query kembar cuma menghabiskan kuota tanpa menambah baris baru.
    const unique = new Map();
    for (const query of queries) {
        if (!unique.has(query.key)) unique.set(query.key, query);
    }

    return [...unique.values()];
}

function asArray(value) {
    if (Array.isArray(value)) return value;
    if (value === undefined || value === null || value === '') return [];
    return [value];
}
