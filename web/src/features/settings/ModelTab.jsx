import { Check, Loader2 } from "lucide-react"
import { useAssistantModelsQuery } from "@/features/assistant/api/useAssistantModelsQuery"
import { useAssistantModel, useSetAssistantModel } from "@/features/assistant/hooks/use-assistant-store"
import { cn } from "@/lib/utils"

export function ModelTab() {
	const { data, isLoading, isError } = useAssistantModelsQuery()
	const models = data?.models ?? []
	const assistantModel = useAssistantModel()
	const setAssistantModel = useSetAssistantModel()

	const selectedModelId = assistantModel ?? models[0]?.id

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-16">
				<Loader2 className="size-5 animate-spin text-muted-foreground" />
			</div>
		)
	}

	if (isError) {
		return (
			<div className="space-y-6">
				<div>
					<h2 className="text-lg font-semibold mb-1">Model</h2>
					<p className="text-sm text-muted-foreground">Choose the AI model for your conversations</p>
				</div>
				<div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
					Failed to load available models. Please try again later.
				</div>
			</div>
		)
	}

	return (
		<div className="space-y-6">
			<div>
				<h2 className="text-lg font-semibold mb-1">Model</h2>
				<p className="text-sm text-muted-foreground">
					{models.length > 1
						? "Choose the AI model for your assistant conversations"
						: "The AI model configured for this environment"}
				</p>
			</div>

			{models.length === 1 && (
				<div className="p-4 rounded-xl bg-muted/50 border border-border">
					<div className="flex items-center gap-3">
						<div className="size-4 rounded-full bg-primary/20 flex items-center justify-center">
							<Check className="size-3 text-primary" />
						</div>
						<div>
							<div className="font-medium">{models[0].displayName || models[0].id}</div>
							<div className="text-xs text-muted-foreground">Default model</div>
						</div>
					</div>
				</div>
			)}

			{models.length > 1 && (
				<div className="space-y-2">
					{models.map((model) => (
						<button
							key={model.id}
							type="button"
							onClick={() => setAssistantModel(model.id)}
							className={cn(
								"w-full p-4 rounded-xl text-left transition-all duration-200",
								"border",
								selectedModelId === model.id
									? "bg-primary/10 border-primary/30"
									: "bg-muted/30 border-border/50 hover:bg-muted/50 hover:border-border"
							)}
						>
							<div className="flex items-center gap-3">
								<div
									className={cn(
										"size-4 rounded-full flex items-center justify-center border transition-colors",
										selectedModelId === model.id ? "bg-primary border-primary" : "border-muted-foreground/30"
									)}
								>
									{selectedModelId === model.id && <Check className="size-3 text-primary-foreground" />}
								</div>
								<div className="flex-1">
									<div className="font-medium">{model.displayName || model.id}</div>
									{model.isDefault && <div className="text-xs text-muted-foreground">Default</div>}
								</div>
							</div>
						</button>
					))}
				</div>
			)}

			<div className="p-4 rounded-xl bg-muted/30 border border-border/50">
				<p className="text-xs text-muted-foreground">
					{models.length > 1
						? "Your model selection applies to assistant conversations. Course generation and other features use the system default."
						: "Contact your administrator to configure additional models."}
				</p>
			</div>
		</div>
	)
}
