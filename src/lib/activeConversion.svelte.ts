/**
 * The backend runs one conversion at a time, so the UI tracks one owner for every Convert button.
 */

/** Who started the conversion in progress: 'preview' or a recording path; null when idle. */
export const activeConversion = $state<{ owner: string | null }>({ owner: null });

/** Run `work` as `owner`'s conversion; refuses while any conversion, even `owner`'s own, is running. */
export async function runExclusive<T>(owner: string, work: () => Promise<T>): Promise<T> {
	// Same owner too: a card remounted mid-run would otherwise start a second run on the same staging file.
	if (activeConversion.owner) {
		throw new Error('Another conversion is running — wait for it to finish or cancel it first');
	}
	activeConversion.owner = owner;
	try {
		return await work();
	} finally {
		if (activeConversion.owner === owner) activeConversion.owner = null;
	}
}
