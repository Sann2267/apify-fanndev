import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
    buildCandidatesUrl,
    extractEmbeddedState,
    parseCategoryCode,
    parseSubcategories,
    toLeaderboardEntry,
} from '../src/blibli.js';
import { STATUS, assembleLeaderboard, diffLeaderboard, toSnapshot } from '../src/leaderboard.js';

describe('parseCategoryCode', () => {
    it('menerima kode mentah', () => {
        assert.equal(parseCategoryCode('ME-1000006'), 'ME-1000006');
    });

    it('mengambil kode dari URL kategori', () => {
        assert.equal(parseCategoryCode('https://www.blibli.com/c3/memory-card/ME-1000006'), 'ME-1000006');
    });

    it('menerima kode numerik level 1', () => {
        assert.equal(parseCategoryCode('/c1/komputer-laptop/53270'), '53270');
    });

    it('mengembalikan null untuk kosong', () => {
        assert.equal(parseCategoryCode(''), null);
    });
});

describe('buildCandidatesUrl', () => {
    it('mengurutkan berdasarkan terlaris dan menurunkan offset', () => {
        const url = new URL(buildCandidatesUrl({ categoryCode: 'ME-1000006', page: 3 }));
        assert.equal(url.searchParams.get('category'), 'ME-1000006');
        assert.equal(url.searchParams.get('sort'), '16');
        assert.equal(url.searchParams.get('start'), '200');
    });
});

describe('parseSubcategories', () => {
    it('membaca anak kategori dari facet', () => {
        const payload = {
            data: {
                filters: [
                    { parameter: 'brand', data: [{ value: 'x', label: 'X' }] },
                    {
                        parameter: 'category',
                        data: [
                            { value: 'SS-1000001', label: 'SSD', level: 3 },
                            { value: 'ME-1000006', label: 'Memory Card', level: 3 },
                        ],
                    },
                ],
            },
        };
        assert.deepEqual(parseSubcategories(payload), [
            { code: 'SS-1000001', name: 'SSD', level: 3 },
            { code: 'ME-1000006', name: 'Memory Card', level: 3 },
        ]);
    });

    it('mengembalikan array kosong kalau facet kategori tidak ada', () => {
        assert.deepEqual(parseSubcategories({ data: { filters: [] } }), []);
        assert.deepEqual(parseSubcategories(null), []);
    });
});

describe('extractEmbeddedState', () => {
    it('berhenti di ujung objek meski ada statement setelahnya', () => {
        const html = 'window.__PRODUCT_DETAIL_INITIAL_STATE__ = {"a":{"b":1}};window.__X__={"c":2};';
        assert.deepEqual(extractEmbeddedState(html), { a: { b: 1 } });
    });

    it('mengabaikan kurawal di dalam string', () => {
        const html = 'window.__PRODUCT_DETAIL_INITIAL_STATE__ = {"n":"paket {A} }"};sisa';
        assert.deepEqual(extractEmbeddedState(html), { n: 'paket {A} }' });
    });
});

describe('toLeaderboardEntry', () => {
    const base = {
        productSku: 'BLL-1',
        name: 'Produk A',
        price: { offered: 100, listed: 120, totalDiscount: 17 },
        review: { decimalRating: 4.8, count: 12 },
        stock: 5,
        statistics: { sold: 300, bestSelling: { rank: 3, salesCategoryCode: 'ME-1000006', salesCategoryLabel: 'Memory Card' } },
        merchant: { code: 'BLL-70058', name: 'Toko A' },
    };
    const meta = { categoryCode: 'ME-1000006', listingProduct: {}, scrapedAt: 'T' };

    it('menyusun entri untuk produk berperingkat', () => {
        const entry = toLeaderboardEntry(base, meta);
        assert.equal(entry.rank, 3);
        assert.equal(entry.salePrice, 100);
        assert.equal(entry.rating, 4.8);
        assert.equal(entry.stockQuantity, 5);
        assert.equal(entry.inStock, true);
        assert.equal(entry.categoryName, 'Memory Card');
    });

    it('mengabaikan produk tanpa peringkat', () => {
        const summary = { ...base, statistics: { sold: 9000, bestSelling: null } };
        assert.equal(toLeaderboardEntry(summary, meta), null);
    });

    it('mengabaikan peringkat milik kategori penjualan lain', () => {
        const summary = { ...base, statistics: { bestSelling: { rank: 1, salesCategoryCode: 'LAIN-1' } } };
        assert.equal(toLeaderboardEntry(summary, meta), null);
    });
});

describe('assembleLeaderboard', () => {
    const entry = (rank, sku) => ({ rank, productSku: sku });

    it('mengurutkan dan menandai daftar rapat sebagai lengkap', () => {
        const r = assembleLeaderboard([entry(3, 'c'), entry(1, 'a'), entry(2, 'b')]);
        assert.deepEqual(r.entries.map((e) => e.rank), [1, 2, 3]);
        assert.equal(r.isComplete, true);
        assert.deepEqual(r.missingRanks, []);
        assert.equal(r.highestRank, 3);
    });

    it('melaporkan peringkat yang bolong', () => {
        const r = assembleLeaderboard([entry(1, 'a'), entry(4, 'd')]);
        assert.equal(r.isComplete, false);
        assert.deepEqual(r.missingRanks, [2, 3]);
    });

    it('menangani kategori tanpa daftar sama sekali', () => {
        const r = assembleLeaderboard([]);
        assert.equal(r.size, 0);
        assert.equal(r.isComplete, false);
        assert.equal(r.highestRank, null);
    });

    it('mempertahankan entri pertama saat peringkat kembar', () => {
        const r = assembleLeaderboard([entry(1, 'a'), entry(1, 'b')]);
        assert.equal(r.size, 1);
        assert.equal(r.entries[0].productSku, 'a');
    });
});

describe('diffLeaderboard', () => {
    const cur = [
        { rank: 1, productSku: 'a', name: 'A' },
        { rank: 2, productSku: 'new', name: 'Baru' },
        { rank: 3, productSku: 'c', name: 'C' },
    ];
    const prev = [
        { rank: 1, productSku: 'a', name: 'A' },
        { rank: 2, productSku: 'c', name: 'C' },
        { rank: 3, productSku: 'gone', name: 'Hilang' },
    ];

    it('menandai semuanya BASELINE saat belum ada snapshot', () => {
        const rows = diffLeaderboard(cur, null);
        assert.equal(rows.length, 3);
        assert.ok(rows.every((r) => r.status === STATUS.BASELINE));
        assert.ok(rows.every((r) => r.previousRank === null));
    });

    it('membedakan MASUK, TETAP, dan TURUN', () => {
        const rows = diffLeaderboard(cur, prev);
        const bySku = Object.fromEntries(rows.map((r) => [r.productSku, r]));
        assert.equal(bySku.a.status, STATUS.SAME);
        assert.equal(bySku.new.status, STATUS.NEW);
        assert.equal(bySku.c.status, STATUS.DOWN);
        assert.equal(bySku.c.rankChange, -1);
        assert.equal(bySku.c.previousRank, 2);
    });

    it('menghitung kenaikan sebagai selisih positif', () => {
        const rows = diffLeaderboard(
            [{ rank: 1, productSku: 'x' }],
            [{ rank: 5, productSku: 'x' }],
        );
        assert.equal(rows[0].status, STATUS.UP);
        assert.equal(rows[0].rankChange, 4);
    });

    it('tetap melaporkan produk yang keluar dari daftar', () => {
        const rows = diffLeaderboard(cur, prev);
        const gone = rows.find((r) => r.productSku === 'gone');
        assert.equal(gone.status, STATUS.DROPPED_OUT);
        assert.equal(gone.rank, null);
        assert.equal(gone.previousRank, 3);
    });
});

describe('toSnapshot', () => {
    it('hanya menyimpan field yang dibutuhkan perbandingan', () => {
        const snap = toSnapshot([{
            rank: 1, productSku: 'a', name: 'A', url: 'u', merchantCode: 'm', merchantName: 'M',
            salePrice: 10, categoryCode: 'c', categoryName: 'C',
            seenCount: 999, stockQuantity: 5, rating: 4.5,
        }]);
        assert.deepEqual(Object.keys(snap[0]).sort(), [
            'categoryCode', 'categoryName', 'merchantCode', 'merchantName',
            'name', 'productSku', 'rank', 'salePrice', 'url',
        ]);
    });
});
