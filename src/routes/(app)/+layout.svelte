<script lang="ts">
	import Sidebar from '$lib/Sidebar.svelte';
	import StatusBar from '$lib/StatusBar.svelte';

	let { children } = $props();
</script>

<div class="workspace">
	<Sidebar />
	<div class="content">
		{@render children()}
	</div>
	<StatusBar />
</div>

<style>
	.workspace {
		display: grid;
		grid-template-columns: 200px 1fr;
		grid-template-rows: 1fr auto;
		min-height: 100vh;
	}
	.workspace :global(.sidebar) {
		grid-column: 1;
		grid-row: 1;
	}
	.content {
		grid-column: 2;
		grid-row: 1;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
	}
	.workspace :global(.status-bar) {
		grid-column: 1 / -1;
		grid-row: 2;
	}
</style>
