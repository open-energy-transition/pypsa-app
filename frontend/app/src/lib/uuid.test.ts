import { describe, it, expect, afterEach } from 'vitest';
import { safeRandomUUID } from './uuid';

const UUID_V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('safeRandomUUID', () => {
	const originalCrypto = globalThis.crypto;

	afterEach(() => {
		Object.defineProperty(globalThis, 'crypto', { value: originalCrypto, configurable: true });
	});

	it('returns a UUIDv4-shaped string when crypto.randomUUID is available', () => {
		const id = safeRandomUUID();
		expect(id).toMatch(UUID_V4_RE);
	});

	it('falls back to crypto.getRandomValues when crypto.randomUUID is undefined (plain-HTTP context)', () => {
		Object.defineProperty(globalThis, 'crypto', {
			value: { getRandomValues: originalCrypto.getRandomValues.bind(originalCrypto) },
			configurable: true,
		});
		const id = safeRandomUUID();
		expect(id).toMatch(UUID_V4_RE);
	});

	it('produces unique ids across calls', () => {
		const ids = new Set(Array.from({ length: 50 }, () => safeRandomUUID()));
		expect(ids.size).toBe(50);
	});
});
