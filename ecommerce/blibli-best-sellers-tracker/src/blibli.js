/**
 * Lapisan akses data Blibli — fungsi murni, tanpa I/O.
 *
 * Catatan hasil penelusuran yang mendasari modul ini:
 *
 * Daftar "Paling Laris" TIDAK sama dengan mengurutkan kategori berdasarkan
 * jumlah terjual. Pada kategori Memory Card, produk peringkat 1 terjual 1.899
 * unit sementara peringkat 8 terjual 4.262 unit. Peringkat resminya hanya ada
 * di halaman produk, pada `statistics.bestSelling.rank`, dan itulah angka yang
 * dipakai actor ini.
 */

export const ORIGIN = 'https://www.blibli.com';
export const SEARCH_API = `${ORIGIN}/backend/search/products`;
export const CATEGORY_API = `${ORIGIN}/backend/content-api/categories`;

/** Nilai parameter `sort` untuk "Terlaris". */
export const SORT_BEST_SELLING = 16;
/** Halaman terbesar yang dilayani API pencarian. */
export const ITEMS_PER_PAGE = 100;
/** Blibli berhenti melayani setelah 20 halaman, apa pun ukuran halamannya. */
export const MAX_PAGES_PER_QUERY = 20;

/**
 * Blibli menolak permintaan yang headernya tidak konsisten dengan XHR browser
 * sungguhan — User-Agent saja menghasilkan 403. Kombinasi di bawah ini lolos
 * tanpa cookie dan tanpa browser headless.
 */
export function apiHeaders(referer = `${ORIGIN}/`) {
    return {
        Accept: 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        Referer: referer,
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    };
}

/** Header untuk mengambil halaman produk (dokumen HTML, bukan XHR). */
export function pageHeaders(referer = `${ORIGIN}/`) {
    return {
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        Referer: referer,
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Upgrade-Insecure-Requests': '1',
    };
}

/** URL satu halaman kandidat untuk sebuah kategori, terurut terlaris. */
export function buildCandidatesUrl({ categoryCode, page = 1, itemsPerPage = ITEMS_PER_PAGE }) {
    const url = new URL(SEARCH_API);
    url.searchParams.set('category', categoryCode);
    url.searchParams.set('page', String(page));
    url.searchParams.set('start', String((page - 1) * itemsPerPage));
    url.searchParams.set('itemPerPage', String(itemsPerPage));
    url.searchParams.set('channelId', 'web');
    url.searchParams.set('showFacet', 'false');
    url.searchParams.set('sort', String(SORT_BEST_SELLING));
    return url.href;
}

/**
 * URL untuk membaca sub-kategori sebuah kategori.
 *
 * Daftar anak diambil dari facet "Kategori" pada respons pencarian, jadi cukup
 * minta satu produk saja — yang dibutuhkan hanya bagian facet-nya.
 */
export function buildFacetUrl(categoryCode) {
    const url = new URL(SEARCH_API);
    url.searchParams.set('category', categoryCode);
    url.searchParams.set('page', '1');
    url.searchParams.set('start', '0');
    url.searchParams.set('itemPerPage', '1');
    url.searchParams.set('channelId', 'web');
    url.searchParams.set('showFacet', 'true');
    url.searchParams.set('sort', '0');
    return url.href;
}

export function categoryPageUrl(categoryCode) {
    return `${ORIGIN}/c/${categoryCode}`;
}

/**
 * Menerima kode kategori mentah (`ME-1000006`) maupun URL kategori penuh
 * (`https://www.blibli.com/c3/memory-card/ME-1000006`).
 */
export function parseCategoryCode(input) {
    const raw = String(input ?? '').trim();
    if (!raw) return null;
    if (!raw.includes('/')) return raw;

    let pathname = raw;
    try {
        pathname = new URL(raw.startsWith('http') ? raw : `${ORIGIN}/${raw}`).pathname;
    } catch {
        return null;
    }

    const segments = pathname.split('/').filter(Boolean);
    return segments.length ? segments[segments.length - 1] : null;
}

/** Membaca daftar sub-kategori dari facet respons pencarian. */
export function parseSubcategories(payload) {
    const filters = payload?.data?.filters;
    if (!Array.isArray(filters)) return [];

    const categoryFacet = filters.find((f) => f?.parameter === 'category');
    if (!Array.isArray(categoryFacet?.data)) return [];

    return categoryFacet.data
        .filter((entry) => entry?.value)
        .map((entry) => ({
            code: entry.value,
            name: entry.label ?? entry.value,
            level: entry.level ?? null,
        }));
}

const BACKSLASH = String.fromCharCode(92);

/**
 * Mengambil objek JSON yang ditanam di halaman Blibli.
 *
 * Halaman menyertakan `window.<VAR> = {...};` diikuti statement lain di blok
 * <script> yang sama, jadi JSON.parse atas sisa teks pasti gagal. Kurung
 * kurawal ditelusuri berimbang — mengabaikan kurawal di dalam string — untuk
 * memotong tepat di ujung objek.
 */
export function extractEmbeddedState(html, variableName = '__PRODUCT_DETAIL_INITIAL_STATE__') {
    const marker = html.indexOf(`window.${variableName}`);
    if (marker < 0) return null;

    const start = html.indexOf('{', html.indexOf('=', marker));
    if (start < 0) return null;

    let depth = 0;
    let inString = false;
    let escaped = false;

    for (let i = start; i < html.length; i++) {
        const char = html[i];

        if (escaped) { escaped = false; continue; }
        if (char === BACKSLASH) { escaped = true; continue; }
        if (char === '"') { inString = !inString; continue; }
        if (inString) continue;

        if (char === '{') {
            depth++;
        } else if (char === '}') {
            depth--;
            if (depth === 0) {
                try {
                    return JSON.parse(html.slice(start, i + 1));
                } catch {
                    return null;
                }
            }
        }
    }

    return null;
}

export function parseProductSummary(html) {
    return extractEmbeddedState(html)?.['productDetail.product/summary'] ?? null;
}

const toNumber = (value) => (Number.isFinite(value) ? value : null);

/**
 * Menyusun satu entri leaderboard dari halaman produk.
 *
 * Mengembalikan `null` kalau produk tidak berperingkat, atau kalau peringkatnya
 * milik kategori penjualan lain — sebuah produk bisa terdaftar di beberapa
 * kategori tapi hanya diperingkat di satu.
 */
export function toLeaderboardEntry(summary, { categoryCode, listingProduct, scrapedAt }) {
    const bestSelling = summary?.statistics?.bestSelling;
    const rank = toNumber(bestSelling?.rank);

    if (!rank) return null;
    if (bestSelling.salesCategoryCode && bestSelling.salesCategoryCode !== categoryCode) return null;

    const price = summary.price ?? {};
    const review = summary.review ?? {};
    const stats = summary.statistics ?? {};
    const merchant = summary.merchant ?? {};
    const stock = toNumber(summary.stock);

    return {
        rank,
        productSku: summary.productSku ?? listingProduct?.sku ?? null,
        itemSku: summary.itemSku ?? null,
        name: summary.name ?? listingProduct?.name ?? null,
        brand: summary.brand?.name ?? listingProduct?.brand ?? null,
        url: summary.url ? summary.url.split('?')[0] : null,
        imageUrl: Array.isArray(listingProduct?.images) ? listingProduct.images[0] ?? null : null,

        salePrice: toNumber(price.offered),
        listPrice: toNumber(price.listed),
        discountPercentage: toNumber(price.totalDiscount ?? price.listDiscount),
        currency: 'IDR',

        rating: toNumber(review.decimalRating),
        reviewCount: toNumber(review.count),

        stockQuantity: stock,
        inStock: stock === null ? null : stock > 0,
        soldCount: toNumber(stats.sold),
        seenCount: toNumber(stats.seen),

        merchantCode: merchant.code ?? null,
        merchantName: merchant.name ?? null,
        merchantBadge: merchant.rating?.badge ?? null,
        merchantIsOfficial: merchant.official ?? null,

        categoryCode,
        categoryName: bestSelling.salesCategoryLabel ?? null,
        topSellingPageUrl: bestSelling.url ? new URL(bestSelling.url, ORIGIN).href : null,

        scrapedAt,
    };
}
