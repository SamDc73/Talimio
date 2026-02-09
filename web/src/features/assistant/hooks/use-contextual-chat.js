import { useCurrentContext } from "@/features/assistant/hooks/use-current-context"

export const useContextualChat = () => {
	const currentContext = useCurrentContext()

	return {
		showAttachments: currentContext?.contextType === "course",
		contextData: currentContext || {},
	}
}
