/**
 * The backend runs one conversion at a time, so the UI tracks one owner for every Convert button.
 */

/**
 * The conversion in progress, shared so a page that remounts mid-run still shows it:
 * who started it ('preview' or a recording path; null when idle), whether Cancel can stop it,
 * its latest progress text, and the last run's failure (cleared when the next run starts).
 */
export const activeConversion = $state<{
	owner: string | null;
	cancellable: boolean;
	progress: string;
	failure: { owner: string; message: string } | null;
}>({ owner: null, cancellable: false, progress: '', failure: null });

/**
 * Run `work` as `owner`'s conversion; refuses while any conversion, even `owner`'s own, is running.
 *
 * `work` gets a `report` function for its progress text; a failure is recorded before it is rethrown.
 */
export async function runExclusive<T>(
	owner: string,
	work: (report: (progress: string) => void) => Promise<T>,
	cancellable = true
): Promise<T> {
	// Same owner too: a card remounted mid-run would otherwise start a second run on the same staging file.
	if (activeConversion.owner) {
		throw new Error('Another conversion is running — wait for it to finish or cancel it first');
	}
	activeConversion.owner = owner;
	activeConversion.cancellable = cancellable;
	activeConversion.progress = '';
	activeConversion.failure = null;
	try {
		return await work((progress) => {
			if (activeConversion.owner === owner) activeConversion.progress = progress;
		});
	} catch (err) {
		activeConversion.failure = { owner, message: err instanceof Error ? err.message : String(err) };
		throw err;
	} finally {
		if (activeConversion.owner === owner) {
			activeConversion.owner = null;
			activeConversion.progress = '';
		}
	}
}
