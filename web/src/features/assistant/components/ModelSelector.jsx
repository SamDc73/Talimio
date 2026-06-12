"use client"

import { useAssistantApi } from "@assistant-ui/react"
import * as SelectPrimitive from "@radix-ui/react-select"
import { CheckIcon } from "lucide-react"
import { createContext, memo, useContext, useEffect, useMemo } from "react"
import { useAssistantModelsQuery } from "@/features/assistant/api/useAssistantModelsQuery"
import { SelectContent, SelectRoot, SelectTrigger } from "@/features/assistant/components/Select"
import { useAssistantModel, useSetAssistantModel } from "@/features/assistant/hooks/use-assistant-store"
import { cn } from "@/lib/utils"

const ModelSelectorContext = createContext(null)

function useModelSelectorContext() {
	const ctx = useContext(ModelSelectorContext)
	if (!ctx) {
		throw new Error("ModelSelector sub-components must be used within ModelSelector.Root")
	}
	return ctx
}

function ModelSelectorRoot({ models, value, onValueChange, children }) {
	const selectProps = {}
	if (value !== undefined) selectProps.value = value
	if (onValueChange) selectProps.onValueChange = onValueChange

	return (
		<ModelSelectorContext.Provider value={{ models }}>
			<SelectRoot {...selectProps}>{children}</SelectRoot>
		</ModelSelectorContext.Provider>
	)
}

function ModelSelectorTrigger({ className, variant, size, children, ...props }) {
	return (
		<SelectTrigger
			data-slot="model-selector-trigger"
			variant={variant}
			size={size}
			className={cn("aui-model-selector-trigger", className)}
			{...props}
		>
			{children ?? <SelectPrimitive.Value />}
		</SelectTrigger>
	)
}

function ModelSelectorContent({ className, children, ...props }) {
	const { models } = useModelSelectorContext()

	return (
		<SelectContent data-slot="model-selector-content" className={cn("min-w-[180px]", className)} {...props}>
			{children ??
				models.map((model) => (
					<ModelSelectorItem key={model.id} model={model} {...(model.disabled ? { disabled: true } : undefined)} />
				))}
		</SelectContent>
	)
}

function ModelSelectorItem({ model, className, ...props }) {
	return (
		<SelectPrimitive.Item
			data-slot="model-selector-item"
			value={model.id}
			textValue={model.name}
			className={cn(
				"relative flex w-full cursor-default select-none items-center gap-2 rounded-lg py-2 pr-9 pl-3 text-sm outline-none",
				"focus:bg-accent focus:text-accent-foreground",
				"data-disabled:pointer-events-none data-disabled:opacity-50",
				className
			)}
			{...props}
		>
			<span className="absolute right-3 flex size-4 items-center justify-center">
				<SelectPrimitive.ItemIndicator>
					<CheckIcon className="size-4" />
				</SelectPrimitive.ItemIndicator>
			</span>
			<SelectPrimitive.ItemText>
				<span className="flex items-center gap-2">
					{model.icon && (
						<span className="flex size-4 shrink-0 items-center justify-center [&_svg]:size-4">{model.icon}</span>
					)}
					<span className="truncate font-medium">{model.name}</span>
				</span>
			</SelectPrimitive.ItemText>
			{model.description && <span className="truncate text-muted-foreground text-xs">{model.description}</span>}
		</SelectPrimitive.Item>
	)
}

function ModelSelectorImpl({ variant = "outline", size = "sm", contentClassName, className }) {
	const { data, isLoading, isError } = useAssistantModelsQuery()
	const models = useMemo(() => data?.models ?? [], [data?.models])
	const modelIds = useMemo(() => new Set(models.map((model) => model.id)), [models])
	const assistantModel = useAssistantModel()
	const setAssistantModel = useSetAssistantModel()
	const api = useAssistantApi()

	const modelOptions = useMemo(() => {
		if (isLoading) {
			return [{ id: "__loading", name: "Loading models...", disabled: true }]
		}
		if (isError) {
			return [{ id: "__error", name: "Failed to load models", disabled: true }]
		}
		if (models.length === 0) {
			return [{ id: "__empty", name: "No models available", disabled: true }]
		}
		return models.map((model) => ({
			id: model.id,
			name: model.displayName || model.id,
			description: model.isDefault ? "Default" : undefined,
		}))
	}, [isLoading, isError, models])

	const isSelectable = !isLoading && !isError && models.length > 0
	const fallbackModelId = isSelectable ? models[0]?.id : undefined
	const selectedModelId =
		isSelectable && assistantModel && modelIds.has(assistantModel) ? assistantModel : fallbackModelId
	const value = isSelectable ? selectedModelId : modelOptions[0]?.id
	const shouldHideSelector = !isLoading && !isError && models.length === 1

	useEffect(() => {
		if (!isSelectable || !selectedModelId || assistantModel === selectedModelId) return
		setAssistantModel(selectedModelId)
	}, [assistantModel, isSelectable, selectedModelId, setAssistantModel])

	useEffect(() => {
		if (!isSelectable || !selectedModelId) return
		const config = { config: { modelName: selectedModelId } }
		return api.modelContext().register({
			getModelContext: () => config,
		})
	}, [api, isSelectable, selectedModelId])

	if (shouldHideSelector) {
		return null
	}

	return (
		<ModelSelectorRoot
			models={modelOptions}
			value={value}
			onValueChange={(nextValue) => {
				if (!isSelectable || !modelIds.has(nextValue)) return
				setAssistantModel(nextValue)
			}}
		>
			<ModelSelectorTrigger variant={variant} size={size} className={className} />
			<ModelSelectorContent className={contentClassName} />
		</ModelSelectorRoot>
	)
}

const ModelSelector = memo(ModelSelectorImpl)

ModelSelector.displayName = "ModelSelector"

export { ModelSelector }
