import { createContext, useContext, useMemo } from "react"

export const WorkspaceRegistryContext = createContext(null)

export function useWorkspaceRegistry() {
	const ctx = useContext(WorkspaceRegistryContext)
	if (!ctx) {
		throw new Error("WorkspaceRegistryProvider is missing in the tree")
	}
	return ctx
}

export function useWorkspaceState(workspaceId) {
	const { getWorkspaceState, version } = useWorkspaceRegistry()

	// Compute workspace snapshot and files when version changes
	// This encapsulates the mutation-tracking so consumers don't need version
	// biome-ignore lint/correctness/useExhaustiveDependencies: version triggers re-read (workspace is mutated in place)
	const { workspace, files } = useMemo(() => {
		const ws = getWorkspaceState(workspaceId)
		return {
			workspace: ws,
			files: ws ? Array.from(ws.files.values()) : [],
		}
	}, [getWorkspaceState, workspaceId, version])

	return { workspace, files }
}
