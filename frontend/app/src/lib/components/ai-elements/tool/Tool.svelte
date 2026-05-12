<script lang="ts">
	import { Collapsible } from "$lib/components/ui/collapsible/index.js";
	import { cn } from "$lib/lib/utils";
	import type { Snippet } from "svelte";

	interface ToolProps {
		class?: string;
		children?: Snippet;
		[key: string]: any;
	}

	let { class: className = "", children, ...restProps }: ToolProps = $props();

	import { safeRandomUUID } from "$lib/uuid";
	let id = $derived.by(() => safeRandomUUID());
</script>

<Collapsible {id} class={cn("not-prose mb-4 w-full rounded-md border", className)} {...restProps}>
	{@render children?.()}
</Collapsible>
