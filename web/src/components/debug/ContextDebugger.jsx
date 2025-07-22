import { useEffect } from "react";
import { useCurrentContext } from "../../hooks/useCurrentContext";

/**
 * Debug component to verify context is being properly detected and passed
 * Only renders in development mode
 */
export function ContextDebugger() {
	const context = useCurrentContext();

	useEffect(() => {
		if (process.env.NODE_ENV === "development" && context) {
			console.log("[ContextDebugger] Current context:", {
				type: context.contextType,
				id: context.contextId,
				meta: context.contextMeta,
			});
		}
	}, [context]);

	// Only show in development
	if (process.env.NODE_ENV !== "development") {
		return null;
	}

	if (!context) {
		return null;
	}

	return (
		<div className="fixed bottom-4 left-4 bg-black/80 text-white text-xs p-2 rounded-md z-50 max-w-xs">
			<div className="font-semibold mb-1">Context Debug</div>
			<div>Type: {context.contextType}</div>
			<div>ID: {context.contextId}</div>
			<div>Meta: {JSON.stringify(context.contextMeta)}</div>
		</div>
	);
}
