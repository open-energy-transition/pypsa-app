<script lang="ts">
	import { cn } from "$lib/lib/utils";
	import { CollapsibleContent } from "$lib/components/ui/collapsible/index.js";

	interface Props {
		class?: string;
		children?: import("svelte").Snippet;
	}

	let { class: className = "", children, ...props }: Props = $props();
</script>

<CollapsibleContent
	class={cn(
		"mt-4 text-sm",
		"data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2 text-muted-foreground data-[state=closed]:animate-out data-[state=open]:animate-in outline-none",
		className
	)}
	{...props}
>
	<div
		class="prose prose-sm dark:prose-invert prose-p:my-1.5 prose-li:my-0.5 prose-ul:my-1.5 prose-ul:pl-5 prose-ol:my-1.5 prose-ol:pl-5 prose-headings:my-2 prose-h1:text-base prose-h2:text-sm prose-h3:text-sm grid max-w-none min-w-0 grid-cols-[minmax(0,1fr)] gap-2 [&_:where(p,li,h1,h2,h3,h4,h5,h6,strong,em,code,blockquote)]:text-muted-foreground"
	>
		{@render children?.()}
	</div>
</CollapsibleContent>
