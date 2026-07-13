<script lang="ts">
	import { cn } from "$lib/utils";
	import { CollapsibleTrigger } from "$lib/components/ui/collapsible/index.js";
	import { getReasoningContext } from "./reasoning-context.svelte.js";
	import BrainIcon from "@lucide/svelte/icons/brain";
	import ChevronDownIcon from "@lucide/svelte/icons/chevron-down";

	interface Props {
		class?: string;
		children?: import("svelte").Snippet;
	}

	let { class: className = "", children, ...props }: Props = $props();

	let reasoningContext = getReasoningContext();

	let getThinkingMessage = $derived.by(() => {
		let { isStreaming, duration } = reasoningContext;

		if (isStreaming) {
			return "Thinking...";
		}
		if (!duration) {
			return "Thought for a moment";
		}
		return `Thought for ${duration} seconds`;
	});
</script>

<CollapsibleTrigger
	class={cn(
		"text-foreground flex w-full min-w-0 items-center gap-2 text-sm transition-colors",
		className
	)}
	{...props}
>
	{#if children}
		{@render children()}
	{:else}
		<BrainIcon class="size-4 shrink-0" />
		<p class="min-w-0 flex-1 truncate text-left">{getThinkingMessage}</p>
		<ChevronDownIcon
			class={cn(
				"size-4 shrink-0 transition-transform",
				reasoningContext.isOpen ? "rotate-180" : "rotate-0"
			)}
		/>
	{/if}
</CollapsibleTrigger>
