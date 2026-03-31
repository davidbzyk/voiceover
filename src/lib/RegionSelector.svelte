<script lang="ts">
	import { mapSelectionToSource, type RegionRect } from './recorder.svelte';

	const MIN_SELECTION = 50; // minimum CSS pixels to avoid accidental micro-selections

	let {
		screenshotUrl,
		onSelect,
		onCancel
	}: {
		screenshotUrl: string;
		onSelect: (rect: RegionRect) => void;
		onCancel: () => void;
	} = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let imgEl: HTMLImageElement | undefined = $state();
	let isDragging = $state(false);
	let startX = $state(0);
	let startY = $state(0);
	let currentX = $state(0);
	let currentY = $state(0);
	let hasSelection = $state(false);

	// Normalized selection rect (always positive width/height)
	const selRect = $derived({
		x: Math.min(startX, currentX),
		y: Math.min(startY, currentY),
		width: Math.abs(currentX - startX),
		height: Math.abs(currentY - startY)
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onCancel();
		}
	}

	function handleMouseDown(e: MouseEvent) {
		if (!containerEl) return;
		const rect = containerEl.getBoundingClientRect();
		startX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
		startY = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
		currentX = startX;
		currentY = startY;
		isDragging = true;
		hasSelection = false;
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging || !containerEl) return;
		const rect = containerEl.getBoundingClientRect();
		currentX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
		currentY = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
	}

	function handleMouseUp() {
		if (!isDragging) return;
		isDragging = false;

		if (selRect.width < MIN_SELECTION || selRect.height < MIN_SELECTION) {
			hasSelection = false;
			return;
		}
		hasSelection = true;
	}

	function confirmSelection() {
		if (!imgEl || !containerEl) return;

		onSelect(mapSelectionToSource(
			selRect,
			containerEl.clientWidth,
			containerEl.clientHeight,
			imgEl.naturalWidth,
			imgEl.naturalHeight
		));
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="region-overlay"
	bind:this={containerEl}
	onmousedown={handleMouseDown}
	onmousemove={handleMouseMove}
	onmouseup={handleMouseUp}
>
	<img bind:this={imgEl} src={screenshotUrl} alt="Screen capture" class="screenshot" draggable="false" />

	<!-- Semi-transparent dark overlay (cutout effect is produced by the selection-cutout element below) -->
	<div class="dimmer"></div>

	{#if (isDragging || hasSelection) && selRect.width > 0 && selRect.height > 0}
		<!-- Bright cutout showing the selected region -->
		<div
			class="selection-cutout"
			style="left:{selRect.x}px; top:{selRect.y}px; width:{selRect.width}px; height:{selRect.height}px;"
		>
			<img
				src={screenshotUrl}
				alt=""
				class="cutout-img"
				style="width:{containerEl?.clientWidth ?? 0}px; height:{containerEl?.clientHeight ?? 0}px; left:-{selRect.x}px; top:-{selRect.y}px;"
				draggable="false"
			/>
		</div>

		<!-- Selection border -->
		<div
			class="selection-border"
			style="left:{selRect.x}px; top:{selRect.y}px; width:{selRect.width}px; height:{selRect.height}px;"
		></div>

		<!-- Dimensions label -->
		<div
			class="dimensions"
			style="left:{selRect.x + selRect.width / 2}px; top:{selRect.y + selRect.height + 8}px;"
		>
			{Math.round(selRect.width)} &times; {Math.round(selRect.height)}
		</div>
	{/if}

	{#if hasSelection && !isDragging}
		<!-- stopPropagation prevents mousedown from bubbling to the overlay and starting a new drag -->
		<div class="actions" style="left:{selRect.x + selRect.width / 2}px; top:{selRect.y < 56 ? selRect.y + selRect.height + 8 : selRect.y - 48}px;" onmousedown={(e) => e.stopPropagation()}>
			<button class="action-btn confirm" onclick={confirmSelection}>Record Region</button>
			<button class="action-btn cancel" onclick={onCancel}>Cancel</button>
		</div>
	{/if}

	{#if !isDragging && !hasSelection}
		<div class="instructions">
			Click and drag to select a region &middot; Press Escape to cancel
		</div>
	{/if}
</div>

<style>
	.region-overlay {
		position: fixed;
		inset: 0;
		z-index: 9999;
		cursor: crosshair;
		overflow: hidden;
	}

	.screenshot {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: fill;
		pointer-events: none;
		user-select: none;
	}

	.dimmer {
		position: absolute;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		pointer-events: none;
	}

	.selection-cutout {
		position: absolute;
		overflow: hidden;
		pointer-events: none;
		z-index: 1;
	}

	.cutout-img {
		position: absolute;
		object-fit: fill;
		pointer-events: none;
		user-select: none;
	}

	.selection-border {
		position: absolute;
		border: 2px solid #3b82f6;
		border-radius: 2px;
		pointer-events: none;
		z-index: 2;
		box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.3);
	}

	.dimensions {
		position: absolute;
		transform: translateX(-50%);
		background: rgba(0, 0, 0, 0.75);
		color: #e2e8f0;
		padding: 4px 10px;
		border-radius: 4px;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		pointer-events: none;
		z-index: 3;
		white-space: nowrap;
	}

	.actions {
		position: absolute;
		transform: translateX(-50%);
		display: flex;
		gap: 8px;
		z-index: 3;
	}

	.action-btn {
		padding: 8px 16px;
		border-radius: 6px;
		border: none;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s;
	}

	.action-btn.confirm {
		background: #3b82f6;
		color: white;
	}
	.action-btn.confirm:hover {
		background: #2563eb;
	}

	.action-btn.cancel {
		background: #334155;
		color: #94a3b8;
	}
	.action-btn.cancel:hover {
		background: #475569;
		color: #f1f5f9;
	}

	.instructions {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: rgba(0, 0, 0, 0.75);
		color: #e2e8f0;
		padding: 12px 24px;
		border-radius: 8px;
		font-size: 14px;
		pointer-events: none;
		z-index: 3;
		white-space: nowrap;
	}
</style>
