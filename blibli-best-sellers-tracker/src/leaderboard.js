/**
 * Menyusun leaderboard "Paling Laris" dan membandingkannya dengan run terakhir.
 */

/** Status pergerakan sebuah produk terhadap snapshot sebelumnya. */
export const STATUS = {
    BASELINE: 'BASELINE',
    NEW: 'NEW',
    UP: 'UP',
    DOWN: 'DOWN',
    SAME: 'SAME',
    DROPPED_OUT: 'DROPPED_OUT',
};

/**
 * Mengurutkan entri dan menilai kelengkapannya.
 *
 * Peringkat resmi Blibli berupa deret rapat 1..N. Kalau ada nomor yang bolong,
 * berarti produk pemegang nomor itu ada di luar kandidat yang dipindai — bukan
 * berarti nomornya tidak ada. Celah tersebut dilaporkan apa adanya supaya
 * snapshot parsial tidak tersamar sebagai snapshot penuh.
 */
export function assembleLeaderboard(entries) {
    const byRank = new Map();
    for (const entry of entries) {
        // Kalau dua produk mengaku peringkat sama, yang pertama dipertahankan.
        if (!byRank.has(entry.rank)) byRank.set(entry.rank, entry);
    }

    const ranked = [...byRank.values()].sort((a, b) => a.rank - b.rank);

    if (!ranked.length) {
        return { entries: [], size: 0, highestRank: null, missingRanks: [], isComplete: false };
    }

    const highestRank = ranked[ranked.length - 1].rank;
    const present = new Set(ranked.map((e) => e.rank));
    const missingRanks = [];
    for (let rank = 1; rank <= highestRank; rank++) {
        if (!present.has(rank)) missingRanks.push(rank);
    }

    return {
        entries: ranked,
        size: ranked.length,
        highestRank,
        missingRanks,
        isComplete: missingRanks.length === 0,
    };
}

/**
 * Membandingkan leaderboard sekarang dengan snapshot sebelumnya.
 *
 * Produk yang hilang dari daftar tetap dikeluarkan sebagai baris berstatus
 * DROPPED_OUT — bagi penjual, keluar dari daftar justru kabar yang paling
 * perlu diketahui, dan baris itu akan lenyap tanpa jejak kalau hanya
 * leaderboard baru yang dilaporkan.
 */
export function diffLeaderboard(currentEntries, previousEntries) {
    const hasPrevious = Array.isArray(previousEntries) && previousEntries.length > 0;
    const previousBySku = new Map((previousEntries ?? []).map((e) => [e.productSku, e]));

    const rows = currentEntries.map((entry) => {
        if (!hasPrevious) {
            return { ...entry, status: STATUS.BASELINE, previousRank: null, rankChange: null };
        }

        const previous = previousBySku.get(entry.productSku);
        if (!previous) {
            return { ...entry, status: STATUS.NEW, previousRank: null, rankChange: null };
        }

        // Peringkat kecil berarti lebih baik, jadi selisih positif = naik.
        const rankChange = previous.rank - entry.rank;
        const status = rankChange > 0 ? STATUS.UP : (rankChange < 0 ? STATUS.DOWN : STATUS.SAME);

        return { ...entry, status, previousRank: previous.rank, rankChange };
    });

    if (!hasPrevious) return rows;

    const currentSkus = new Set(currentEntries.map((e) => e.productSku));
    const droppedOut = previousEntries
        .filter((previous) => !currentSkus.has(previous.productSku))
        .map((previous) => ({
            ...previous,
            rank: null,
            previousRank: previous.rank,
            rankChange: null,
            status: STATUS.DROPPED_OUT,
        }));

    return [...rows, ...droppedOut];
}

/**
 * Memadatkan leaderboard menjadi snapshot untuk run berikutnya.
 *
 * Hanya field yang dibutuhkan perbandingan yang disimpan, supaya rekaman tetap
 * kecil meski dijadwalkan berjalan tiap hari.
 */
export function toSnapshot(entries) {
    return entries.map((e) => ({
        rank: e.rank,
        productSku: e.productSku,
        name: e.name,
        url: e.url,
        merchantCode: e.merchantCode,
        merchantName: e.merchantName,
        salePrice: e.salePrice,
        categoryCode: e.categoryCode,
        categoryName: e.categoryName,
    }));
}
