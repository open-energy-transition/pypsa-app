<script lang="ts">
	import { Streamdown, type StreamdownProps } from "svelte-streamdown";
	import { cn } from "$lib/utils";

	type Props = StreamdownProps & {
		class?: string;
	};

	let { class: className, ...restProps }: Props = $props();
</script>

<Streamdown
	class={cn(
		"prose prose-sm dark:prose-invert max-w-none min-w-0 break-words",
		"prose-pre:max-w-full prose-pre:overflow-x-auto",
		"prose-p:my-1.5 prose-li:my-0.5 prose-li:break-words prose-ul:my-1.5 prose-ul:pl-5 prose-ol:my-1.5 prose-ol:pl-5",
		"prose-headings:my-2 prose-h1:text-base prose-h2:text-sm prose-h3:text-sm",
		"[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
		className,
	)}
	baseTheme="shadcn"
	{...restProps}
/>