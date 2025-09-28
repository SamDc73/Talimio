import { useQuery } from "@tanstack/react-query"
import { assistantApi } from "./assistantApi"

export function useAssistantModelsQuery() {
	return useQuery({
		queryKey: ["assistant", "models"],
		queryFn: () => assistantApi.getAvailableModels(),
		staleTime: 5 * 60 * 1000, // 5 minutes
		gcTime: 10 * 60 * 1000, // 10 minutes
		retry: 1,
	})
}
