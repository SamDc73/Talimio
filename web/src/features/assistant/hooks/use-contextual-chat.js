import { useCurrentContext } from "@/features/assistant/hooks/use-current-context"

export const useContextualChat = () => {
	return useCurrentContext() || {}
}
