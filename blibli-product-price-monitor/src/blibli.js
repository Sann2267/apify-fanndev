/**
 * Lapisan akses data Blibli.
 *
 * Semua fungsi di sini murni (tanpa I/O) supaya gampang diuji dan dipakai ulang
 * oleh handler crawler di `routes.js`.
 */

export const ORIGIN = 'https://www.blibli.com';
export const SEARCH_API = `${ORIGIN}/backend/search/products`;

/** Blibli membatasi hasil di 20 halaman per query, berapa pun `itemPerPage`-nya. */
export const MAX_PAGES_PER_QUERY = 20;
/** Halaman terbesar yang masih dilayani API pencarian. */
export const ITEMS_PER_PAGE = 100;
/** Turunan dari dua batas di atas: plafon keras hasil per query. */
export const MAX_ITEMS_PER_QUERY = MAX_PAGES_PER_QUERY * ITEMS_PER_PAGE;

/** Label sort di UI Blibli -> nilai parameter `sort` di API. */
export const SORT_OPTIONS = {
    relevance: 0,
    newest: 1,
    cheapest: 3,
    expensive: 4,
    popular: 7,
    bestSelling: 16,
};

/**
 * Header yang menentukan lolos-tidaknya request.
 *
 * Blibli menolak (403 + halaman blokir HTML) request yang cuma bawa User-Agent.
 * Kombinasi `Sec-Fetch-*` + `Referer` yang konsisten dengan XHR browser sungguhan
 * sudah cukup untuk lolos — tanpa cookie dan tanpa browser headless.
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

/**
 * Menyusun URL API pencarian untuk satu halaman.
 *
 * Mode kata kunci dan mode kategori memakai endpoint yang sama; bedanya cuma
 * `searchTerm` versus `category`.
 */
export function buildSearchUrl({
    searchTerm,
    categoryId,
    page = 1,
    itemsPerPage = ITEMS_PER_PAGE,
    sort = 0,
    minPrice,
    maxPrice,
}) {
    const url = new URL(SEARCH_API);
    const params = url.searchParams;

    if (searchTerm) params.set('searchTerm', searchTerm);
    if (categoryId) params.set('category', categoryId);

    params.set('page', String(page));
    params.set('start', String((page - 1) * itemsPerPage));
    params.set('itemPerPage', String(itemsPerPage));
    params.set('channelId', 'web');
    params.set('showFacet', 'false');
    params.set('sort', String(sort));

    if (Number.isFinite(minPrice)) params.set('minPrice', String(minPrice));
    if (Number.isFinite(maxPrice)) params.set('maxPrice', String(maxPrice));

    return url.href;
}

/** Referer yang masuk akal untuk sebuah query. */
export function refererForQuery(query) {
    if (query.kind === 'search') {
        return `${ORIGIN}/cari/${encodeURIComponent(query.value)}`;
    }
    return `${ORIGIN}/c/${query.value}`;
}

/**
 * Menerima ID kategori mentah (`ME-1000006`) maupun URL kategori penuh
 * (`https://www.blibli.com/c3/memory-card/ME-1000006`) dan mengembalikan ID-nya.
 */
export function parseCategoryId(input) {
    const raw = String(input ?? '').trim();
    if (!raw) return null;

    if (!raw.includes('/')) return raw;

    let pathname = raw;
    try {
        pathname = new URL(raw.startsWith('http') ? raw : `${ORIGIN}/${raw}`).pathname;
    } catch {
        return null;
    }

    // URL kategori berbentuk /c1|/c2|/c3/<slug>/<categoryId>
    const segments = pathname.split('/').filter(Boolean);
    return segments.length ? segments[segments.length - 1] : null;
}

const toNumber = (value) => (Number.isFinite(value) ? value : null);

const isEmptyObject = (value) => value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).length === 0;

/**
 * Meratakan satu produk dari API pencarian menjadi baris dataset.
 *
 * `review.absoluteRating` adalah rating desimal (mis. 4.8) sementara
 * `review.rating` sudah dibulatkan ke bintang penuh, jadi keduanya disimpan.
 */
export function normalizeProduct(raw, { query, position, scrapedAt }) {
    const price = raw.price ?? {};
    const review = raw.review ?? {};
    const badge = raw.badge ?? {};
    const tags = Array.isArray(raw.tags) ? raw.tags : [];

    return {
        // Identitas
        productSku: raw.sku ?? raw.id ?? null,
        itemSku: raw.itemSku ?? null,
        name: raw.name ?? null,
        brand: raw.brand ?? null,
        url: raw.url ? new URL(raw.url, ORIGIN).href.split('?')[0] : null,
        imageUrl: Array.isArray(raw.images) && raw.images.length ? raw.images[0] : null,

        // Harga & diskon
        salePrice: toNumber(price.salePrice ?? price.minPrice),
        listPrice: toNumber(price.listPrice),
        discountPercentage: toNumber(price.discount),
        discountAmount: toNumber(price.discountPrice),
        priceDisplay: price.priceDisplay ?? null,
        listPriceDisplay: price.strikeThroughPriceDisplay ?? null,
        isPriceRange: Boolean(price.isPriceRange),
        currency: 'IDR',

        // Rating & ulasan
        rating: toNumber(review.absoluteRating),
        ratingRounded: toNumber(review.rating),
        reviewCount: toNumber(review.count),

        // Stok & penjualan
        stockStatus: raw.status ?? null,
        inStock: raw.status === 'AVAILABLE',
        stockQuantity: null, // hanya terisi kalau fetchProductDetails aktif
        soldCount: toNumber(raw.soldCountTotal),
        soldLabel: raw.monthlySoldCountLabel ?? null,

        // Penjual
        merchantName: raw.merchantName ?? null,
        merchantCode: raw.merchantCode ?? null,
        merchantBadge: badge.merchantBadge ?? null,
        merchantRating: toNumber(review.sellerRating),
        location: raw.location ?? null,

        // Kategori
        categoryId: raw.rootCategory?.id ?? null,
        categoryName: raw.rootCategory?.name ?? null,
        categoryHierarchy: Array.isArray(raw.categoryNameHierarchy) ? raw.categoryNameHierarchy : [],

        // Sinyal promosi
        tags,
        isFreeShipping: tags.includes('FREE_SHIPPING'),
        isBestSelling: tags.includes('BEST_SELLING'),
        deliveryEstimate: raw.deliveryEstimate ?? null,

        // Asal-usul baris ini
        queryType: query.kind,
        query: query.value,
        rankInQuery: position,
        scrapedAt,
    };
}

const BACKSLASH = String.fromCharCode(92);

/**
 * Mengambil objek JSON yang ditanam di halaman produk.
 *
 * Halaman produk menyertakan `window.__PRODUCT_DETAIL_INITIAL_STATE__ = {...};`
 * diikuti statement lain di blok <script> yang sama, jadi JSON.parse atas sisa
 * teks pasti gagal. Kurung kurawal ditelusuri secara berimbang — sambil
 * mengabaikan kurawal yang ada di dalam string — untuk memotong tepat di ujung
 * objek.
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

/** Menarik ringkasan produk dari HTML halaman produk. */
export function parseProductDetail(html) {
    const state = extractEmbeddedState(html);
    return state?.['productDetail.product/summary'] ?? null;
}

/**
 * Menggabungkan detail halaman produk ke atas baris hasil pencarian.
 *
 * Halaman produk lebih otoritatif soal stok dan harga — indeks pencarian bisa
 * tertinggal beberapa menit — jadi nilainya menimpa, tapi hanya kalau ada.
 */
export function mergeProductDetail(item, summary) {
    if (!summary) return item;

    const price = summary.price ?? {};
    const review = summary.review ?? {};
    const stats = summary.statistics ?? {};
    const merchant = summary.merchant ?? {};
    const categories = Array.isArray(summary.categories) ? summary.categories : [];

    const stock = toNumber(summary.stock);
    const detailPrice = toNumber(price.offered);

    // Indeks pencarian bisa tertinggal dari halaman produk. Selisihnya bukan
    // gangguan melainkan justru sinyal yang dicari saat memantau harga, jadi
    // harga listing tetap disimpan dan perbedaannya ditandai.
    const priceMovedSinceListing = detailPrice !== null
        && item.salePrice !== null
        && detailPrice !== item.salePrice;

    return {
        ...item,
        name: summary.name ?? item.name,
        brand: summary.brand?.name ?? item.brand,

        salePrice: detailPrice ?? item.salePrice,
        listingSalePrice: item.salePrice,
        priceMovedSinceListing,
        listPrice: toNumber(price.listed) ?? item.listPrice,
        discountPercentage: toNumber(price.totalDiscount ?? price.listDiscount) ?? item.discountPercentage,

        rating: toNumber(review.decimalRating) ?? item.rating,
        ratingRounded: toNumber(review.rating) ?? item.ratingRounded,
        reviewCount: toNumber(review.count) ?? item.reviewCount,

        stockQuantity: stock,
        inStock: stock === null ? item.inStock : stock > 0,
        stockStatus: stock === null ? item.stockStatus : (stock > 0 ? 'AVAILABLE' : 'OUT_OF_STOCK'),

        soldCount: toNumber(stats.sold) ?? item.soldCount,
        seenCount: toNumber(stats.seen),
        bestSellingRank: toNumber(stats.bestSelling?.rank),

        merchantName: merchant.name ?? item.merchantName,
        merchantCode: merchant.code ?? item.merchantCode,
        merchantBadge: merchant.rating?.badge ?? item.merchantBadge,
        merchantRating: toNumber(merchant.rating?.review) ?? item.merchantRating,
        merchantIsOfficial: merchant.official ?? null,
        merchantReviewCount: toNumber(merchant.rating?.reviewCount),

        categoryHierarchy: categories.length ? categories.map((c) => c.name) : item.categoryHierarchy,
        uniqueSellingPoint: summary.uniqueSellingPoint ?? null,
        warranty: isEmptyObject(summary.warranty) ? null : (summary.warranty ?? null),
        hasDetail: true,
    };
}
