import { Actor } from 'apify';
import { HttpCrawler, log } from 'crawlee';

import { parseCategoryCode } from './blibli.js';
import { STATUS, assembleLeaderboard, diffLeaderboard, toSnapshot } from './leaderboard.js';
import { LABELS, candidatesRequest, createRouter, facetRequest, rootCategoriesRequest } from './routes.js';

const SNAPSHOT_KEY = 'SNAPSHOT';

/**
 * Event pay-per-event yang ditagih actor ini.
 *
 * Biaya sesungguhnya actor ini ditentukan jumlah kategori, bukan jumlah baris:
 * satu kategori berarti ratusan permintaan halaman produk tapi hanya belasan
 * baris hasil. Menagih per baris akan salah harga secara serius, jadi yang
 * ditagih adalah kategori.
 *
 * Event `apify-actor-start` sengaja tidak disebut di sini — platform
 * menagihnya otomatis, dan menagihnya sendiri dari kode justru gagal.
 */
const CHARGE_EVENT = 'category-tracked';

await Actor.init();

const input = (await Actor.getInput()) ?? {};

const {
    categories = [],
    discoverCategories = false,
    rootCategories = [],
    categoryLevel = 3,
    maxCategories = 10,
    candidatesPerCategory = 300,
    trackChanges = true,
    stateStoreName = 'blibli-best-sellers-state',
    watchMerchantCodes = [],
    maxConcurrency = 10,
    maxRunSeconds,
    proxyConfiguration: proxyInput,
} = input;

const explicitCategories = asArray(categories)
    .map((entry) => parseCategoryCode(typeof entry === 'object' && entry ? (entry.url ?? entry.value) : entry))
    .filter(Boolean)
    .map((code) => ({ code, name: code, level: categoryLevel }));

if (!explicitCategories.length && !discoverCategories) {
    await Actor.fail(
        'Tidak ada kategori untuk dipantau. Isi "categories" dengan URL/kode kategori Blibli, '
        + 'atau aktifkan "discoverCategories" agar actor menelusuri sendiri pohon kategorinya.',
    );
}

// Memindai kategori yang tak sanggup ditagih berarti membuang ratusan
// permintaan percuma, jadi anggaran pengguna dipakai sebagai pagu sejak awal.
const affordableCategories = resolveCategoryBudget();

if (affordableCategories === 0) {
    await Actor.fail(
        'Anggaran run ini tidak cukup untuk satu kategori pun. Naikkan batas biaya maksimum '
        + 'run di Apify Console lalu jalankan lagi.',
    );
}

const config = {
    categoryLevel,
    maxCategories: Math.min(Math.max(1, maxCategories), affordableCategories),
    candidatesPerCategory: Math.max(1, candidatesPerCategory),
    rootCategoryCodes: asArray(rootCategories).map((c) => parseCategoryCode(c)).filter(Boolean),
};

if (config.maxCategories < Math.max(1, maxCategories)) {
    log.warning(
        `Anggaran run hanya menutup ${config.maxCategories} kategori, `
        + `bukan ${maxCategories}. Naikkan batas biaya maksimum run untuk memindai lebih banyak.`,
    );
}

const state = {
    startedAt: new Date().toISOString(),
    selected: new Map(),        // kode kategori -> kategori yang dipindai
    scanned: new Map(),         // kode kategori -> metadata halaman kandidat
    productsScanned: new Map(), // kode kategori -> jumlah halaman produk terbaca
    failed: new Map(),          // kode kategori -> kandidat yang gagal permanen
    leaderboards: new Map(),    // kode kategori -> entri berperingkat
};

// Kategori yang disebut eksplisit tidak melewati penelusuran pohon, jadi
// kuotanya didaftarkan di muka.
for (const category of explicitCategories.slice(0, config.maxCategories)) {
    state.selected.set(category.code, category);
}

const proxyConfiguration = await Actor.createProxyConfiguration(proxyInput);

const crawler = new HttpCrawler({
    proxyConfiguration,
    maxConcurrency,
    // Kandidat yang gagal permanen langsung menghilangkan satu kursi di
    // leaderboard, jadi lebih baik mencoba beberapa kali lagi.
    maxRequestRetries: 8,
    requestHandlerTimeoutSecs: 90,
    additionalMimeTypes: ['application/json'],
    useSessionPool: true,
    persistCookiesPerSession: true,
    // Lewat proxy berputar, membuang sesi pada satu error justru merugikan:
    // tiap IP baru harus melewati pemeriksaan awal lagi. Sesi diberi ruang
    // untuk sekadar tersandung.
    sessionPoolOptions: { sessionOptions: { maxErrorScore: 3 } },
    preNavigationHooks: [
        // Blibli mencocokkan Sec-Fetch-*, sec-ch-ua, dan User-Agent satu sama
        // lain, jadi header dikunci ke satu profil Chrome desktop.
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
        // Kandidat yang gagal permanen bisa menyisakan lubang di leaderboard.
        // Lubang karena gagal-ambil dan lubang karena kurang dalam memindai
        // butuh tindakan berbeda, jadi keduanya dihitung terpisah.
        const code = request.userData?.category?.code;
        if (code) state.failed.set(code, (state.failed.get(code) ?? 0) + 1);

        log.error(`Menyerah pada ${request.url}: ${error.message}`);
    },
});

const startRequests = [
    ...explicitCategories
        .slice(0, config.maxCategories)
        .map((category) => candidatesRequest({ category, page: 1 })),
];

if (discoverCategories) {
    // Menyebut kategori awal sendiri berarti penelusuran boleh dimulai dari
    // simpul mana pun, bukan hanya dari 14 kategori teratas Blibli.
    startRequests.push(...(config.rootCategoryCodes.length
        ? config.rootCategoryCodes.map((code) => facetRequest({ code, name: code }))
        : [rootCategoriesRequest()]));
}

log.info(
    `Melacak "Paling Laris"${explicitCategories.length ? ` untuk ${explicitCategories.length} kategori` : ''}`
    + `${discoverCategories ? ' + penelusuran otomatis' : ''}`
    + ` — ${config.candidatesPerCategory} kandidat per kategori, maksimal ${config.maxCategories} kategori.`,
);

// Run yang kena timeout platform kehilangan semua hasilnya, karena baris baru
// ditulis setelah crawl selesai. Crawler dihentikan lebih dulu supaya tahap
// penyusunan dan penyimpanan tetap sempat berjalan.
const deadline = resolveDeadline();
const stopTimer = deadline
    ? setTimeout(() => {
        log.warning(
            'Batas waktu pemindaian tercapai — berhenti dan menyimpan hasil yang sudah terkumpul. '
            + 'Kategori yang belum tuntas ditandai leaderboardComplete=false.',
        );
        crawler.stop('batas waktu');
    }, Math.max(0, deadline - Date.now()))
    : null;

await crawler.run(startRequests);
if (stopTimer) clearTimeout(stopTimer);

// ---------------------------------------------------------------------------
// Menyusun leaderboard, membandingkan dengan run sebelumnya, lalu menyimpan.
// ---------------------------------------------------------------------------

const store = trackChanges ? await Actor.openKeyValueStore(stateStoreName) : null;
const previous = trackChanges ? (await store.getValue(SNAPSHOT_KEY)) ?? {} : {};
const previousCategories = previous.categories ?? {};

const watched = new Set(asArray(watchMerchantCodes).map((c) => String(c).trim()).filter(Boolean));
const nextSnapshot = { savedAt: state.startedAt, categories: {} };
const summaries = [];
let charged = 0;

for (const [code, category] of state.selected) {
    const leaderboard = assembleLeaderboard(state.leaderboards.get(code) ?? []);
    const scannedCount = state.productsScanned.get(code) ?? 0;
    const failedCount = state.failed.get(code) ?? 0;

    const rows = diffLeaderboard(
        leaderboard.entries,
        trackChanges ? previousCategories[code]?.entries : null,
    );

    for (const row of rows) {
        await Actor.pushData({
            ...row,
            categoryCode: row.categoryCode ?? code,
            categoryName: row.categoryName ?? category.name,
            isWatched: row.merchantCode ? watched.has(row.merchantCode) : false,
            leaderboardSize: leaderboard.size,
            leaderboardComplete: leaderboard.isComplete,
            candidatesScanned: scannedCount,
            candidatesFailed: failedCount,
            previousRunAt: previous.savedAt ?? null,
            runStartedAt: state.startedAt,
        });
    }

    if (leaderboard.size) {
        nextSnapshot.categories[code] = {
            scrapedAt: state.startedAt,
            entries: toSnapshot(leaderboard.entries),
        };

        // Ditagih setelah barisnya benar-benar tersimpan, supaya pengguna tidak
        // pernah dibebani kategori yang gagal dikirim.
        await chargeForCategory(code);
        charged++;
    }

    summaries.push({
        categoryCode: code,
        categoryName: leaderboard.entries[0]?.categoryName ?? category.name,
        leaderboardSize: leaderboard.size,
        highestRank: leaderboard.highestRank,
        isComplete: leaderboard.isComplete,
        missingRanks: leaderboard.missingRanks,
        candidatesScanned: scannedCount,
        candidatesFailed: failedCount,
        entered: rows.filter((r) => r.status === STATUS.NEW).length,
        droppedOut: rows.filter((r) => r.status === STATUS.DROPPED_OUT).length,
    });
}

if (trackChanges) await store.setValue(SNAPSHOT_KEY, nextSnapshot);
await Actor.setValue('RUN_SUMMARY', { runStartedAt: state.startedAt, categories: summaries });

reportSummary(summaries, Boolean(previous.savedAt));
log.info(`Kategori yang ditagih: ${charged} (kategori tanpa daftar tidak ditagih).`);

await Actor.exit();

// ---------------------------------------------------------------------------

function reportSummary(entries, hadPrevious) {
    const withList = entries.filter((s) => s.leaderboardSize > 0);
    const withoutList = entries.filter((s) => s.leaderboardSize === 0);
    const partial = withList.filter((s) => !s.isComplete);

    log.info(`Selesai. ${withList.length} dari ${entries.length} kategori punya daftar "Paling Laris".`);

    for (const s of withList) {
        const movement = hadPrevious ? `, ${s.entered} masuk, ${s.droppedOut} keluar` : '';
        log.info(
            `  ${s.categoryCode} (${s.categoryName}): ${s.leaderboardSize} produk`
            + `${s.isComplete ? '' : `, BELUM LENGKAP — peringkat hilang: ${s.missingRanks.join(', ')}`}`
            + `${movement}`,
        );
    }

    if (partial.length) {
        const blamesFetch = partial.filter((s) => s.candidatesFailed > 0);

        log.warning(
            `${partial.length} kategori belum lengkap. Naikkan "candidatesPerCategory" `
            + `(sekarang ${config.candidatesPerCategory}) agar produk berperingkat rendah ikut terpindai.`,
        );

        // Lubang yang muncul berbarengan dengan kandidat gagal-ambil punya obat
        // berbeda: perbaiki jaringan, bukan perdalam pemindaian.
        if (blamesFetch.length) {
            log.warning(
                `${blamesFetch.length} di antaranya juga punya kandidat yang gagal diambil `
                + `(${blamesFetch.map((s) => `${s.categoryCode}:${s.candidatesFailed}`).join(', ')}). `
                + 'Lubangnya mungkin karena kegagalan jaringan, bukan kedalaman — coba aktifkan proxy '
                + 'atau turunkan maxConcurrency lalu jalankan ulang.',
            );
        }
    }

    for (const s of withoutList) {
        log.info(
            `  ${s.categoryCode}: tidak ada produk berperingkat dari ${s.candidatesScanned} kandidat — `
            + 'kategori ini kemungkinan memang tidak punya daftar "Paling Laris".',
        );
    }
}

/**
 * Berapa kategori yang masih tertutup anggaran run ini.
 *
 * Di run non-PPE — uji lokal, atau actor yang belum dimonetisasi — tidak ada
 * anggaran untuk dibaca. Kasus itu harus berarti "tanpa batas", bukan "nol",
 * karena salah membacanya akan membuat actor berhenti tanpa memindai apa pun.
 */
function resolveCategoryBudget() {
    let manager;
    try {
        manager = Actor.getChargingManager();
    } catch {
        return Infinity;
    }

    if (typeof manager?.calculateMaxEventChargeCountWithinLimit !== 'function') return Infinity;

    try {
        const allowed = manager.calculateMaxEventChargeCountWithinLimit(CHARGE_EVENT);
        return Number.isInteger(allowed) && allowed >= 0 ? allowed : Infinity;
    } catch {
        return Infinity;
    }
}

/**
 * Menagih satu kategori yang benar-benar menghasilkan daftar.
 *
 * Kategori tanpa daftar "Paling Laris" — dan Blibli memang punya beberapa —
 * tidak ditagih, meski memindainya tetap memakan permintaan. Pengguna tidak
 * seharusnya membayar untuk jawaban kosong.
 */
async function chargeForCategory(code) {
    try {
        const result = await Actor.charge({ eventName: CHARGE_EVENT });
        if (result?.eventChargeLimitReached) {
            log.warning(`Batas biaya run tercapai saat menagih ${code}; sisa kategori tidak ditagih.`);
        }
    } catch (error) {
        // Run non-PPE tidak punya harga terpasang; itu wajar, bukan kegagalan.
        log.debug(`Penagihan dilewati untuk ${code}: ${error.message}`);
    }
}

/**
 * Kapan pemindaian harus berhenti, dalam milidetik epoch — atau null.
 *
 * Diambil yang paling awal antara batas pilihan pengguna dan timeout run
 * dikurangi cadangan untuk menyusun, membandingkan, dan menyimpan hasil.
 */
function resolveDeadline() {
    const RESERVE_MS = 45_000;
    const candidates = [];

    const seconds = Number(maxRunSeconds);
    if (Number.isFinite(seconds) && seconds > 0) {
        candidates.push(Date.parse(state.startedAt) + seconds * 1000);
    }

    const timeoutAt = Date.parse(process.env.ACTOR_TIMEOUT_AT ?? process.env.APIFY_TIMEOUT_AT ?? '');
    if (Number.isFinite(timeoutAt)) candidates.push(timeoutAt - RESERVE_MS);

    return candidates.length ? Math.min(...candidates) : null;
}

function asArray(value) {
    if (Array.isArray(value)) return value;
    if (value === undefined || value === null || value === '') return [];
    return [value];
}
