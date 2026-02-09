import useAppStore, { selectAssistantModel, selectAssistantSidebarPinned } from "@/stores/useAppStore"

export function useAssistantModel() {
	return useAppStore(selectAssistantModel)
}

export function useSetAssistantModel() {
	return useAppStore((state) => state.setAssistantModel)
}

export function useAssistantPinned() {
	return useAppStore(selectAssistantSidebarPinned)
}

export function useToggleAssistantPinned() {
	return useAppStore((state) => state.toggleAssistantSidebarPin)
}

export function useAssistantSidebarWidth() {
	return useAppStore((state) => state.preferences.assistantSidebarWidth)
}

export function useSetAssistantSidebarWidth() {
	return useAppStore((state) => state.setAssistantSidebarWidth)
}
