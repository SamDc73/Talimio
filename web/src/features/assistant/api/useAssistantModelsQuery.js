import { useQuery } from "@tanstack/react-query"
import logger from "@/lib/logger"
import { assistantApi } from "./assistantApi"

export function useAssistantModelsQuery() {
	return useQuery({
		queryKey: ["assistant", "models"],
		queryFn: async () => {
			try {
				return await assistantApi.getAvailableModels()
			} catch (error) {
				logger.error("Failed to fetch available models", error)
				throw error
			}
		},
		staleTime: 5 * 60 * 1000, // 5 minutes
		gcTime: 10 * 60 * 1000, // 10 minutes
		retry: 1,
	})
}
