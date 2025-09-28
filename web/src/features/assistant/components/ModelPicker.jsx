import { Check, ChevronDown } from "lucide-react"
import { useEffect, useMemo } from "react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/drop-menu"
import { Button } from "@/components/ui/button"
import { useAssistantModelsQuery } from "@/features/assistant/api/useAssistantModelsQuery"
import { useAssistantModel, useSetAssistantModel } from "@/features/assistant/hooks/assistant-store"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"

export function ModelPicker({ className }) {
	const { data, isLoading, isError, error } = useAssistantModelsQuery()
	const models = useMemo(() => data?.models ?? [], [data?.models])
	const assistantModel = useAssistantModel()
	const setAssistantModel = useSetAssistantModel()

	useEffect(() => {
		if (isError) {
			logger.error("Failed to fetch available models", error)
		}
	}, [isError, error])

	// Default to the primary model (first item) if none selected yet
	useEffect(() => {
		if (!assistantModel && models.length > 0) {
			setAssistantModel(models[0].id)
		}
	}, [models, assistantModel, setAssistantModel])

	const currentModel = models.find((m) => m.id === assistantModel) || {
		id: assistantModel || "Select Model",
	}

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="ghost"
					className={cn(
						"h-9 px-3 gap-2 font-normal",
						"text-sm text-gray-700 hover:text-gray-900",
						"hover:bg-gray-50 transition-all duration-150",
						"rounded-lg border border-gray-200",
						className
					)}
				>
					<span>{currentModel.displayName || currentModel.id}</span>
					<ChevronDown className="h-4 w-4 text-gray-500" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent
				align="start"
				className={cn("w-56 p-2", "bg-white/95 backdrop-blur-lg", "border border-gray-200 shadow-lg", "rounded-xl")}
			>
				{isLoading ? (
					<DropdownMenuItem disabled className="text-gray-500 text-sm">
						Loading models...
					</DropdownMenuItem>
				) : isError ? (
					<DropdownMenuItem disabled className="text-red-600 text-sm">
						Failed to load models
					</DropdownMenuItem>
				) : models.length > 0 ? (
					models.map((model) => {
						const isSelected = model.id === assistantModel

						return (
							<DropdownMenuItem
								key={model.id}
								onClick={() => setAssistantModel(model.id)}
								className={cn(
									"relative flex items-center justify-between",
									"px-3 py-2.5 rounded-lg cursor-pointer",
									"transition-all duration-150",
									isSelected && "bg-gray-50",
									!isSelected && "hover:bg-gray-50"
								)}
							>
								<div className="flex items-center gap-3">
									{isSelected && <Check className="h-4 w-4 text-gray-700 shrink-0" />}
									<div className={cn("flex flex-col", !isSelected && "ml-7")}>
										<span className={cn("text-sm", isSelected ? "text-gray-900 font-medium" : "text-gray-700")}>
											{model.displayName || model.id}
										</span>
									</div>
								</div>
								<div className="flex items-center gap-2">
									{model.isDefault && <span className="text-xs text-gray-500">Default</span>}
								</div>
							</DropdownMenuItem>
						)
					})
				) : (
					<DropdownMenuItem disabled className="text-gray-500 text-sm">
						No models available
					</DropdownMenuItem>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	)
}
