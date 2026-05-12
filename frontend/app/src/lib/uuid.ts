/**
 * UUIDv4 generator that works outside secure contexts.
 *
 * `crypto.randomUUID` is only defined in secure contexts (HTTPS, localhost,
 * 127.0.0.1). When the SPA is served over plain HTTP from a LAN IP it is
 * undefined; this helper falls back to `crypto.getRandomValues`, which is
 * available everywhere a `crypto` object exists.
 */
export function safeRandomUUID(): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	const bytes = new Uint8Array(16);
	crypto.getRandomValues(bytes);
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
