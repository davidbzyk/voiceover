/**
 * The backend runs one conversion at a time, so the UI tracks one owner for every Convert button.
 */

/**
 * The conversion in progress: who started it ('preview' or a recording path; null when idle) and whether
 * Cancel can stop it. Shared, so a page that remounts mid-run can still show the run and its Cancel.
 */
export const activeConversion = $state<{ owner: string | null; cancellable: boolean }>({
	owner: null,
	cancellable: false
});

/** Run `work` as `owner`'s conversion; refuses while any conversion, even `owner`'s own, is running. */
export async function runExclusive<T>(owner: string, work: () => Promise<T>, cancellable = true): Promise<T> {
	// Same owner too: a card remounted mid-run would otherwise start a second run on the same staging file.
	if (activeConversion.owner) {
		throw new Error('Another conversion is running — wait for it to finish or cancel it first');
	}
	activeConversion.owner = owner;
	activeConversion.cancellable = cancellable;
	try {
		return await work();
	} finally {
		if (activeConversion.owner === owner) activeConversion.owner = null;
	}
}
