import { version } from "$lib/api/client";

export const features = $state({
	runsEnabled: false,
	localMode: false,
	chatEnabled: false,
});

export async function initFeatures(): Promise<void> {
	const response = await version.get();
	features.runsEnabled = Boolean(response.runs_enabled);
	features.localMode = Boolean(response.local_mode);
	features.chatEnabled = !!(response as { chat_enabled?: boolean })
		.chat_enabled;
}
