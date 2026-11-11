import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
    buildSearchUrl,
    extractEmbeddedState,
    mergeProductDetail,
    normalizeProduct,
    parseCategoryId,
} from '../src/blibli.js';

describe('parseCategoryId', () => {
    it('menerima ID mentah apa adanya', () => {
        assert.equal(parseCategoryId('ME-1000006'), 'ME-1000006');
    });

    it('mengambil ID dari URL kategori penuh', () => {
        assert.equal(
            parseCategoryId('https://www.blibli.com/c3/memory-card/ME-1000006'),
            'ME-1000006',
        );
    });

    it('mengabaikan query string', () => {
        assert.equal(
            parseCategoryId('https://www.blibli.com/c2/media-penyimpanan/ME-1000002?sort=3'),
            'ME-1000002',
        );
    });

    it('menerima path tanpa origin', () => {
        assert.equal(parseCategoryId('/c1/komputer-gaming/53270'), '53270');
    });

    it('mengembalikan null untuk input kosong', () => {
        assert.equal(parseCategoryId('  '), null);
        assert.equal(parseCategoryId(undefined), null);
    });
});

describe('buildSearchUrl', () => {
    it('menurunkan offset "start" dari nomor halaman', () => {
        const url = new URL(buildSearchUrl({ searchTerm: 'laptop', page: 3, itemsPerPage: 100 }));
        assert.equal(url.searchParams.get('start'), '200');
        assert.equal(url.searchParams.get('page'), '3');
        assert.equal(url.searchParams.get('searchTerm'), 'laptop');
    });

    it('memakai parameter category untuk mode kategori', () => {
        const url = new URL(buildSearchUrl({ categoryId: 'ME-1000006' }));
        assert.equal(url.searchParams.get('category'), 'ME-1000006');
        assert.equal(url.searchParams.has('searchTerm'), false);
    });

    it('menghilangkan batas harga yang tidak diisi', () => {
        const url = new URL(buildSearchUrl({ searchTerm: 'x', minPrice: 50000 }));
        assert.equal(url.searchParams.get('minPrice'), '50000');
        assert.equal(url.searchParams.has('maxPrice'), false);
    });
});

describe('normalizeProduct', () => {
    const raw = {
        sku: 'BLL-70058-00122',
        itemSku: 'BLL-70058-00122-00001',
        name: 'SanDisk Ultra microSDXC 64GB',
        brand: 'SanDisk',
        status: 'AVAILABLE',
        url: '/p/sandisk-ultra/ps--BLL-70058-00122?ds=x&source=SEARCH',
        images: ['https://img/1.jpg'],
        price: {
            salePrice: 259000,
            listPrice: 299000,
            discount: 13,
            discountPrice: 40000,
            priceDisplay: 'Rp259.000',
            strikeThroughPriceDisplay: 'Rp299.000',
        },
        review: { rating: 4, absoluteRating: 4.8, count: 465, sellerRating: 4.9 },
        soldCountTotal: 4178,
        tags: ['FREE_SHIPPING', 'BEST_SELLING'],
        rootCategory: { id: '53270', name: 'Komputer & Gaming' },
    };
    const meta = { query: { kind: 'search', value: 'sandisk' }, position: 7, scrapedAt: 'T' };

    it('memisahkan rating desimal dari rating bulat', () => {
        const item = normalizeProduct(raw, meta);
        assert.equal(item.rating, 4.8);
        assert.equal(item.ratingRounded, 4);
        assert.equal(item.reviewCount, 465);
    });

    it('membuang parameter pelacakan dari URL produk', () => {
        const item = normalizeProduct(raw, meta);
        assert.equal(item.url, 'https://www.blibli.com/p/sandisk-ultra/ps--BLL-70058-00122');
    });

    it('menurunkan flag stok dan promosi', () => {
        const item = normalizeProduct(raw, meta);
        assert.equal(item.inStock, true);
        assert.equal(item.isFreeShipping, true);
        assert.equal(item.isBestSelling, true);
        assert.equal(item.stockQuantity, null);
    });

    it('menandai produk habis', () => {
        const item = normalizeProduct({ ...raw, status: 'OUT_OF_STOCK' }, meta);
        assert.equal(item.inStock, false);
    });

    it('tidak meledak saat blok harga dan ulasan hilang', () => {
        const item = normalizeProduct({ sku: 'X', name: 'Y' }, meta);
        assert.equal(item.salePrice, null);
        assert.equal(item.rating, null);
        assert.deepEqual(item.tags, []);
    });
});

describe('extractEmbeddedState', () => {
    it('berhenti di ujung objek meski ada statement setelahnya', () => {
        const html = '<script>window.__PRODUCT_DETAIL_INITIAL_STATE__ = {"a":{"b":1}};'
            + 'window.__LAIN__ = {"c":2};</script>';
        assert.deepEqual(extractEmbeddedState(html), { a: { b: 1 } });
    });

    it('mengabaikan kurung kurawal yang ada di dalam string', () => {
        const html = 'window.__PRODUCT_DETAIL_INITIAL_STATE__ = {"name":"Paket {besar} }"};rest';
        assert.deepEqual(extractEmbeddedState(html), { name: 'Paket {besar} }' });
    });

    it('mengabaikan tanda kutip yang di-escape', () => {
        const html = String.raw`window.__PRODUCT_DETAIL_INITIAL_STATE__ = {"n":"kabel \"USB\" 2m"};x`;
        assert.deepEqual(extractEmbeddedState(html), { n: 'kabel "USB" 2m' });
    });

    it('mengembalikan null kalau variabelnya tidak ada', () => {
        assert.equal(extractEmbeddedState('<html></html>'), null);
    });
});

describe('mergeProductDetail', () => {
    const item = {
        name: 'Nama listing',
        salePrice: 55999,
        listPrice: 60000,
        rating: 4,
        reviewCount: 10,
        stockStatus: 'AVAILABLE',
        inStock: true,
        stockQuantity: null,
        categoryHierarchy: ['A'],
        merchantName: 'Toko',
    };

    it('mempertahankan baris listing kalau detail gagal diurai', () => {
        assert.deepEqual(mergeProductDetail(item, null), item);
    });

    it('mengisi stok pasti dari halaman produk', () => {
        const merged = mergeProductDetail(item, { stock: 97 });
        assert.equal(merged.stockQuantity, 97);
        assert.equal(merged.inStock, true);
    });

    it('menganggap stok nol sebagai habis meski listing bilang tersedia', () => {
        const merged = mergeProductDetail(item, { stock: 0 });
        assert.equal(merged.inStock, false);
        assert.equal(merged.stockStatus, 'OUT_OF_STOCK');
    });

    it('menandai harga yang bergerak sejak listing dan menyimpan harga lama', () => {
        const merged = mergeProductDetail(item, { price: { offered: 42999, listed: 60000 } });
        assert.equal(merged.salePrice, 42999);
        assert.equal(merged.listingSalePrice, 55999);
        assert.equal(merged.priceMovedSinceListing, true);
    });

    it('tidak menandai apa pun saat harga sama', () => {
        const merged = mergeProductDetail(item, { price: { offered: 55999 } });
        assert.equal(merged.priceMovedSinceListing, false);
    });

    it('mengosongkan garansi kosong', () => {
        assert.equal(mergeProductDetail(item, { warranty: {} }).warranty, null);
    });
});
