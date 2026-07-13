import Message from "./core/Message.svelte";
import MessageContent from "./core/MessageContent.svelte";
import MessageActions from "./actions/MessageActions.svelte";
import MessageAction from "./actions/MessageAction.svelte";

export * from "./context/message-context.svelte.js";

export {
	Message,
	MessageContent,
	MessageActions,
	MessageAction,

	// Aliases
	Message as Root,
	MessageContent as Content,
	MessageActions as Actions,
	MessageAction as Action,
};
