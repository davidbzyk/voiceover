<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	const navItems = [
		{ path: '/', label: 'Record', icon: '🎙️' },
		{ path: '/library', label: 'Library', icon: '📁' },
		{ path: '/settings', label: 'Settings', icon: '⚙️' }
	];

	function isActive(itemPath: string, currentPath: string): boolean {
		if (itemPath === '/') {
			return currentPath === '/' || currentPath.startsWith('/preview');
		}
		return currentPath.startsWith(itemPath);
	}
</script>

<nav class="sidebar">
	<div class="sidebar-logo">🎙️ VoiceOver</div>
	<div class="sidebar-nav">
		{#each navItems as item}
			<button
				class="nav-item"
				class:active={isActive(item.path, $page.url.pathname)}
				onclick={() => goto(item.path)}
			>
				<span class="nav-icon">{item.icon}</span>
				<span class="nav-label">{item.label}</span>
			</button>
		{/each}
	</div>
</nav>

<style>
	.sidebar {
		width: 200px;
		background: #0f172a;
		border-right: 1px solid #1e293b;
		display: flex;
		flex-direction: column;
		padding: 16px 0;
		flex-shrink: 0;
	}
	.sidebar-logo {
		font-size: 16px;
		font-weight: 700;
		color: #f97316;
		padding: 0 20px 20px;
	}
	.sidebar-nav {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.nav-item {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 20px;
		border: none;
		background: transparent;
		color: #94a3b8;
		font-size: 13px;
		cursor: pointer;
		border-left: 3px solid transparent;
		transition: all 0.15s;
		text-align: left;
	}
	.nav-item:hover {
		color: #cbd5e1;
		background: rgba(30, 41, 59, 0.5);
	}
	.nav-item.active {
		color: #f1f5f9;
		background: #1e293b;
		border-left-color: #f97316;
	}
	.nav-icon {
		font-size: 15px;
		width: 20px;
		text-align: center;
	}
	.nav-label {
		font-weight: 500;
	}
</style>
