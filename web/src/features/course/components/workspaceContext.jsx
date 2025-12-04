import { useCallback, useRef, useState } from "react"
import { WorkspaceRegistryContext } from "@/features/course/hooks/use-workspace-registry"

export function WorkspaceRegistryProvider({ children }) {
	const registryRef = useRef(new Map())
	const [version, setVersion] = useState(0)

	const registerBlock = useCallback((block) => {
		const workspaceId = block.workspaceId || block.filePath
		if (!workspaceId || !block.filePath) {
			return { shouldRenderRunner: false }
		}

		const registry = registryRef.current
		let workspace = registry.get(workspaceId)
		if (!workspace) {
			workspace = {
				id: workspaceId,
				files: new Map(),
				runnerFilePath: null, // Track which file renders the runner
				label: block.workspaceLabel || workspaceId,
			}
			registry.set(workspaceId, workspace)
		}

		let changed = false
		// First file registered becomes the runner (stable across re-renders)
		if (workspace.runnerFilePath === null) {
			workspace.runnerFilePath = block.filePath
			changed = true
		}

		const nextFile = {
			filePath: block.filePath,
			code: block.code,
			language: block.language,
			isEntry: block.isEntry,
		}
		const prevFile = workspace.files.get(block.filePath)
		if (
			!prevFile ||
			prevFile.code !== nextFile.code ||
			prevFile.language !== nextFile.language ||
			prevFile.isEntry !== nextFile.isEntry
		) {
			workspace.files.set(block.filePath, nextFile)
			changed = true
		}

		if (block.workspaceLabel && workspace.label !== block.workspaceLabel) {
			workspace.label = block.workspaceLabel
			changed = true
		}

		if (changed) {
			setVersion((value) => value + 1)
		}

		// The file that first registered is the one that renders the runner
		return { shouldRenderRunner: workspace.runnerFilePath === block.filePath }
	}, [])

	const getWorkspaceState = useCallback((workspaceId) => registryRef.current.get(workspaceId) || null, [])

	return (
		<WorkspaceRegistryContext.Provider value={{ registerBlock, getWorkspaceState, version }}>
			{children}
		</WorkspaceRegistryContext.Provider>
	)
}
