/** Stand-in for SvelteKit's $app/navigation in component tests; tests mock goto when they check it. */
export async function goto(_url: string): Promise<void> {}
