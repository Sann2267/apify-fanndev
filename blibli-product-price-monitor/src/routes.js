import { createHttpRouter } from 'crawlee';

import {
    ITEMS_PER_PAGE,
    MAX_PAGES_PER_QUERY,
    apiHeaders,
    buildSearchUrl,
    mergeProductDetail,
    normalizeProduct,
    pageHeaders,
    parseProductDetail,
    refererForQuery,
} from './blibli.js';

export const LABELS = {
    LIST: 'LIST',
    DETAIL: 'DETAIL',
};

/**
 * Membangun router crawler.
 *
 * `state` dibagi lintas request: penghitung per-query dan himpunan SKU yang
 * sudah terlihat menjaga agar plafon `maxItemsPerQuery` tetap dipatuhi meskipun
 * beberapa halaman diproses paralel.
 */
export function createRouter({ config, state }) {
    const router = createHttpRouter();

    router.addHandler(LABELS.LIST, async (context) => {
        const { request, body, json, response, session, crawler, log, pushData } = context;
        const { query, page } = request.userData;

        const payload = json ?? safeJsonParse(body);

        // Halaman blokir Blibli tetap berstatus 200 tapi isinya HTML, bukan JSON.
        // Sesi dibuang supaya percobaan ulang memakai identitas baru.
        if (!payload?.data) {
            session?.retire();
            throw new Error(
                `Respons bukan JSON pencarian (status ${response?.statusCode}) — kemungkinan diblokir.`,
            );
        }

        const { products = [], paging = {} } = payload.data;

        if (page === 1) {
            log.info(
                `[${query.label}] ${paging.total_item ?? 0} produk cocok di Blibli, `
                + `mengambil hingga ${config.maxItemsPerQuery}.`,
            );
            await enqueueRemainingPages({ context, query, paging, config });
        }

        const scrapedAt = new Date().toISOString();
        const detailRequests = [];
        let accepted = 0;

        for (const [index, raw] of products.entries()) {
            if (countFor(state, query) >= config.maxItemsPerQuery) break;

            const sku = raw.sku ?? raw.id;
            if (!sku) continue;

            if (!config.includeOutOfStock && raw.status !== 'AVAILABLE') continue;

            // Produk yang sama bisa muncul lagi kalau peringkat bergeser saat
            // paginasi berlangsung; dedup per query, bukan global, supaya sebuah
            // produk yang memang cocok untuk dua kata kunci tetap tercatat dua kali.
            const dedupeKey = `${query.key}::${sku}`;
            if (state.seen.has(dedupeKey)) continue;
            state.seen.add(dedupeKey);

            const item = normalizeProduct(raw, {
                query,
                position: (page - 1) * ITEMS_PER_PAGE + index + 1,
                scrapedAt,
            });

            bumpCount(state, query);
            accepted++;

            if (config.fetchProductDetails && item.url) {
                detailRequests.push({
                    url: item.url,
                    label: LABELS.DETAIL,
                    headers: pageHeaders(refererForQuery(query)),
                    userData: { item },
                });
            } else {
                await pushData(item);
                state.pushed++;
            }
        }

        if (detailRequests.length) {
            await crawler.addRequests(detailRequests);
        }

        log.debug(`[${query.label}] halaman ${page}: ${accepted}/${products.length} produk diambil.`);
    });

    router.addHandler(LABELS.DETAIL, async ({ request, body, session, log, pushData }) => {
        const { item } = request.userData;

        const summary = parseProductDetail(body.toString('utf-8'));

        if (!summary) {
            // Halaman produk gagal diurai bukan alasan membuang baris — data
            // listing tetap punya harga, rating, dan status stok.
            session?.retire();
            log.warning(`Detail tidak terbaca untuk ${item.productSku}; memakai data listing saja.`);
            await pushData({ ...item, hasDetail: false });
        } else {
            await pushData(mergeProductDetail(item, summary));
        }

        state.pushed++;
    });

    return router;
}

/**
 * Mengantrekan seluruh sisa halaman untuk satu query sekaligus.
 *
 * Menghitungnya di muka (bukan berantai halaman-per-halaman) membuat paginasi
 * satu query berjalan paralel, bukan berurutan.
 */
async function enqueueRemainingPages({ context, query, paging, config }) {
    const { crawler, request } = context;

    const pagesForTarget = Math.ceil(config.maxItemsPerQuery / ITEMS_PER_PAGE);
    const lastPage = Math.min(
        pagesForTarget,
        paging.total_page || 1,
        MAX_PAGES_PER_QUERY,
    );

    if (lastPage < 2) return;

    const requests = [];
    for (let page = 2; page <= lastPage; page++) {
        requests.push({
            url: buildSearchUrl({
                searchTerm: query.kind === 'search' ? query.value : undefined,
                categoryId: query.kind === 'category' ? query.value : undefined,
                page,
                sort: config.sort,
                minPrice: config.minPrice,
                maxPrice: config.maxPrice,
            }),
            label: LABELS.LIST,
            headers: apiHeaders(request.headers?.Referer ?? refererForQuery(query)),
            userData: { query, page },
        });
    }

    await crawler.addRequests(requests);
}

function countFor(state, query) {
    return state.counts.get(query.key) ?? 0;
}

function bumpCount(state, query) {
    state.counts.set(query.key, countFor(state, query) + 1);
}

function safeJsonParse(body) {
    try {
        return JSON.parse(body.toString('utf-8'));
    } catch {
        return null;
    }
}
