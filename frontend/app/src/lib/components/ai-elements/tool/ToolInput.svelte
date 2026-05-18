<script lang="ts">
	import { cn } from "$lib/utils";
	import { CopyButton } from "$lib/components/ai-elements/copy-button";

	interface ToolInputProps {
		class?: string;
		input: any;
		[key: string]: any;
	}

	let { class: className = "", input, ...restProps }: ToolInputProps = $props();

	let formattedInput = $derived.by(() => {
		return JSON.stringify(input, null, 2);
	});

	let id = $props.id();
</script>

<div {id} class={cn("space-y-2 overflow-hidden p-4", className)} {...restProps}>
	<h4 class="text-muted-foreground text-xs font-medium tracking-wide uppercase">Parameters</h4>
	<div class="bg-muted/50 rounded-md relative">
		<div class="absolute right-2 top-2 z-10">
			<CopyButton text={formattedInput} size="sm" variant="ghost" />
		</div>
		<pre class="overflow-x-auto p-3 pr-12 text-sm font-mono"><code>{formattedInput}</code></pre>
	</div>
</div>