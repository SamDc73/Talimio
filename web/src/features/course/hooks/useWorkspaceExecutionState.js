import { useMutation } from "@tanstack/react-query"
import { useMemo, useRef, useState } from "react"

import { executeCode } from "@/features/course/api/codeExecutionApi"

function createFileMap(files) {
	const map = {}
	for (const file of files) {
		map[file.filePath] = {
			filePath: file.filePath,
			initialCode: file.code,
			code: file.code,
			language: file.language || "text",
			isEntry: Boolean(file.isEntry),
			order: file.order ?? Number.MAX_SAFE_INTEGER,
		}
	}
	return map
}

function getDefaultActiveFile(fileMap) {
	const files = Object.values(fileMap)
	return files.find((f) => f.isEntry)?.filePath || files[0]?.filePath || null
}

export function useWorkspaceExecutionState({ workspaceId, lessonId, courseId, files }) {
	// Fingerprint to detect source file changes (not just array reference)
	const fingerprint = useMemo(
		() => JSON.stringify(files.map((f) => [f.filePath, f.code, f.language, f.isEntry])),
		[files]
	)

	const [fileState, setFileState] = useState(() => createFileMap(files))
	const [activeFilePath, setActiveFilePath] = useState(() => getDefaultActiveFile(createFileMap(files)))
	const [result, setResult] = useState(null)
	const [error, setError] = useState(null)

	// Reset state when source files change (render-time sync)
	const prevFingerprintRef = useRef(fingerprint)
	if (prevFingerprintRef.current !== fingerprint) {
		prevFingerprintRef.current = fingerprint
		const newFileMap = createFileMap(files)
		setFileState(newFileMap)
		setActiveFilePath(getDefaultActiveFile(newFileMap))
		setResult(null)
		setError(null)
	}

	const executeMutation = useMutation({
		mutationFn: executeCode,
		onSuccess: (executionResult) => {
			setResult(executionResult)
			setError(null)
		},
		onError: (err) => {
			setResult(null)
			setError(err?.data?.message || err?.message || "Execution failed")
		},
	})

	// Derived values (computed during render, not stored)
	const filesForDisplay = useMemo(() => Object.values(fileState).toSorted((a, b) => a.order - b.order), [fileState])
	const currentFile = fileState[activeFilePath] || filesForDisplay[0] || null
	const hasChanges = filesForDisplay.some((f) => f.code !== f.initialCode)

	// Event handlers
	const handleCodeChange = (path, newCode) => {
		setFileState((prev) => {
			const target = prev[path]
			if (!target || target.code === newCode) return prev
			return { ...prev, [path]: { ...target, code: newCode } }
		})
	}

	const handleSelectFile = (path) => {
		if (path && fileState[path]) {
			setActiveFilePath(path)
		}
	}

	const handleReset = () => {
		setFileState(createFileMap(files))
		setResult(null)
		setError(null)
		executeMutation.reset()
	}

	const handleRun = async () => {
		if (!currentFile) {
			setError("No files to run")
			return
		}
		const entryFile = filesForDisplay.find((f) => f.isEntry) || filesForDisplay[0]
		const payload = {
			code: entryFile.code,
			language: entryFile.language || "text",
			lessonId,
			courseId,
			workspaceId,
			entryFile: entryFile.filePath,
			files: filesForDisplay.map((f) => ({ path: f.filePath, content: f.code })),
		}
		setError(null)
		await executeMutation.mutateAsync(payload)
	}

	return {
		files: filesForDisplay,
		activeFile: currentFile,
		activePath: currentFile?.filePath || null,
		onSelectFile: handleSelectFile,
		onCodeChange: handleCodeChange,
		onRun: handleRun,
		onReset: handleReset,
		result,
		error,
		isRunning: executeMutation.isPending,
		canReset: hasChanges,
	}
}
