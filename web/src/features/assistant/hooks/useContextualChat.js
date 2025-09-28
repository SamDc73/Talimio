import { useCurrentContext } from "@/hooks/useCurrentContext"

export const useContextualChat = () => {
	const currentContext = useCurrentContext()

	return {
		showAttachments: currentContext?.contextType === "course",
		contextData: currentContext || {},
	}
}
