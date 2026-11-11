import { createHttpRouter } from 'crawlee';

import {
    CATEGORY_API,
    ITEMS_PER_PAGE,
    MAX_PAGES_PER_QUERY,
    apiHeaders,
    buildCandidatesUrl,
    buildFacetUrl,
    categoryPageUrl,
    pageHeaders,
    parseProductSummary,
    parseSubcategories,
    toLeaderboardEntry,
} from './blibli.js';

export const LABELS = {
    ROOT_CATEGORIES: 'ROOT_CATEGORIES',
    FACET: 'FACET',
    CANDIDATES: 'CANDIDATES',
    PRODUCT: 'PRODUCT',
};

export function createRouter({ config, state }) {
    const router = createHttpRouter();

    // Daftar kategori level 1 — titik awal penelusuran pohon kategori.
    router.addHandler(LABELS.ROOT_CATEGORIES, async ({ json, body, session, crawler, log }) => {
        const payload = json ?? safeJsonParse(body);
        const roots = payload?.data;

        if (!Array.isArray(roots)) {
            session?.retire();
            throw new Error('Daftar kategori tidak terbaca — kemungkinan diblokir.');
        }

        const wanted = config.rootCategoryCodes.length
            ? roots.filter((c) => config.rootCategoryCodes.includes(c.categoryCode))
            : roots;

        log.info(`Menelusuri ${wanted.length} kategori induk menuju level ${config.categoryLevel}.`);

        await crawler.addRequests(wanted.map((category) => facetRequest({
            code: category.categoryCode,
            name: category.name,
            level: category.level ?? 1,
        })));
    });

    // Satu simpul pohon kategori: turunkan anaknya, atau jadikan daun untuk dipindai.
    router.addHandler(LABELS.FACET, async ({ request, json, body, session, crawler, log }) => {
        const { category } = request.userData;
        const payload = json ?? safeJsonParse(body);

        if (!payload?.data) {
            session?.retire();
            throw new Error(`Facet kategori ${category.code} tidak terbaca.`);
        }

        const children = parseSubcategories(payload);
        const deeperChildren = children.filter((child) => (child.level ?? 0) > (category.level ?? 0));

        // Kategori tanpa anak yang lebih dalam sudah merupakan daun, sekalipun
        // levelnya belum mencapai target.
        if (!deeperChildren.length || (category.level ?? 0) >= config.categoryLevel) {
            await enqueueCategoryScan({ crawler, category, config, state, log });
            return;
        }

        await crawler.addRequests(deeperChildren.map((child) => facetRequest(child)));
    });

    // Satu halaman kandidat: 100 produk terlaris di kategori ini.
    router.addHandler(LABELS.CANDIDATES, async (context) => {
        const { request, json, body, session, crawler, log } = context;
        const { category, page } = request.userData;
        const payload = json ?? safeJsonParse(body);

        if (!payload?.data) {
            session?.retire();
            throw new Error(`Kandidat kategori ${category.code} halaman ${page} tidak terbaca.`);
        }

        const products = payload.data.products ?? [];
        const paging = payload.data.paging ?? {};

        if (page === 1) {
            const lastPage = Math.min(
                Math.ceil(config.candidatesPerCategory / ITEMS_PER_PAGE),
                paging.total_page || 1,
                MAX_PAGES_PER_QUERY,
            );

            state.scanned.set(category.code, {
                category,
                totalInCategory: paging.total_item ?? 0,
                candidatesRequested: Math.min(config.candidatesPerCategory, (paging.total_item ?? 0)),
            });

            const nextPages = [];
            for (let next = 2; next <= lastPage; next++) {
                nextPages.push(candidatesRequest({ category, page: next }));
            }
            if (nextPages.length) await crawler.addRequests(nextPages);
        }

        const taken = products.slice(0, Math.max(0, config.candidatesPerCategory - (page - 1) * ITEMS_PER_PAGE));

        await crawler.addRequests(taken
            .filter((product) => product?.url)
            .map((product) => ({
                url: new URL(product.url.split('?')[0], 'https://www.blibli.com').href,
                label: LABELS.PRODUCT,
                headers: pageHeaders(categoryPageUrl(category.code)),
                // Produk yang sama bisa jadi kandidat di dua kategori sekaligus;
                // tanpa kunci per-kategori, Crawlee membuang yang kedua.
                uniqueKey: `${product.sku}@${category.code}`,
                userData: { category, listingProduct: slimProduct(product) },
            })));

        log.debug(`[${category.code}] halaman ${page}: ${taken.length} kandidat diantrekan.`);
    });

    // Halaman produk: satu-satunya tempat peringkat "Paling Laris" resmi tersedia.
    router.addHandler(LABELS.PRODUCT, async ({ request, body, session, log }) => {
        const { category, listingProduct } = request.userData;

        const html = body.toString('utf-8');
        const summary = parseProductSummary(html);

        if (!summary) {
            // Halaman blokir tidak memuat variabel state sama sekali, sedangkan
            // halaman produk sungguhan yang gagal diurai memuatnya. Hanya kasus
            // pertama yang layak membuang sesi — membuangnya di kasus kedua
            // cuma memaksa pergantian IP tanpa alasan.
            const looksBlocked = !html.includes('__PRODUCT_DETAIL_INITIAL_STATE__');
            if (looksBlocked) session?.retire();

            throw new Error(
                `Halaman produk tidak terbaca (${looksBlocked ? 'diblokir' : 'state rusak'}): ${request.url}`,
            );
        }

        countScan(state, category.code);

        const entry = toLeaderboardEntry(summary, {
            categoryCode: category.code,
            listingProduct,
            scrapedAt: state.startedAt,
        });

        // Sebagian besar kandidat memang tidak berperingkat — itu hal biasa,
        // bukan kegagalan.
        if (!entry) return;

        if (!state.leaderboards.has(category.code)) state.leaderboards.set(category.code, []);
        state.leaderboards.get(category.code).push(entry);

        log.debug(`[${category.code}] #${entry.rank} ${entry.name}`);
    });

    return router;
}

/**
 * Jatah retry untuk permintaan daftar (akar, facet, kandidat).
 *
 * Blibli menolak sebagian IP proxy secara acak dengan 403, dan di cloud
 * satu permintaan pernah butuh 8 kali ganti IP. Kalau halaman kandidat
 * pertama gagal, seluruh kategori hilang — jauh lebih mahal daripada satu
 * halaman produk — jadi permintaan ini diberi ruang lebih lebar.
 */
const LISTING_MAX_RETRIES = 20;

export function rootCategoriesRequest() {
    return {
        url: CATEGORY_API,
        label: LABELS.ROOT_CATEGORIES,
        maxRetries: LISTING_MAX_RETRIES,
        headers: apiHeaders(),
    };
}

export function facetRequest(category) {
    return {
        url: buildFacetUrl(category.code),
        label: LABELS.FACET,
        maxRetries: LISTING_MAX_RETRIES,
        headers: apiHeaders(categoryPageUrl(category.code)),
        userData: { category },
    };
}

export function candidatesRequest({ category, page }) {
    return {
        url: buildCandidatesUrl({ categoryCode: category.code, page }),
        label: LABELS.CANDIDATES,
        maxRetries: LISTING_MAX_RETRIES,
        headers: apiHeaders(categoryPageUrl(category.code)),
        userData: { category, page },
    };
}

/** Mendaftarkan satu kategori daun untuk dipindai, selama kuota masih ada. */
async function enqueueCategoryScan({ crawler, category, config, state, log }) {
    if (state.selected.has(category.code)) return;

    if (state.selected.size >= config.maxCategories) {
        log.debug(`Kuota ${config.maxCategories} kategori tercapai; ${category.code} dilewati.`);
        return;
    }

    state.selected.set(category.code, category);
    await crawler.addRequests([candidatesRequest({ category, page: 1 })]);
}

function countScan(state, code) {
    state.productsScanned.set(code, (state.productsScanned.get(code) ?? 0) + 1);
}

/** Field listing yang masih berguna kalau halaman produk tidak memuatnya. */
function slimProduct(product) {
    return {
        sku: product.sku,
        name: product.name,
        brand: product.brand,
        images: product.images,
    };
}

function safeJsonParse(body) {
    try {
        return JSON.parse(body.toString('utf-8'));
    } catch {
        return null;
    }
}
