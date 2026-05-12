import { version } from '$lib/api/client';

export const features = $state({ runsEnabled: false, chatEnabled: false });

export async function initFeatures(): Promise<void> {
  try {
    const response = await version.get();
    features.runsEnabled =
      ((response.snakedispatch_backends as string[] | undefined) ?? []).length > 0;
    features.chatEnabled = !!(response as { chat_enabled?: boolean }).chat_enabled;
  } catch {
    features.runsEnabled = false;
    features.chatEnabled = false;
  }
}
