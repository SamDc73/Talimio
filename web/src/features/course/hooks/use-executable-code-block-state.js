import { useMutation } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { executeCode } from "@/features/course/api/codeExecutionApi"
import { buildStorageKey } from "@/features/course/utils/codeBlockUtils"
import logger from "@/lib/logger"

/**
 * Manages editor state, persistence, and execution lifecycle for executable code blocks.
 */
export function useExecutableCodeBlockState({ originalCode, language, runLanguage, lessonId, courseId }) {
	const storageKey = buildStorageKey({
		lessonId,
		language: runLanguage || language,
		codeSample: originalCode,
	})

	const [code, setCode] = useState(() => {
		try {
			const raw = sessionStorage.getItem(storageKey)
			if (raw) {
				const saved = JSON.parse(raw)
				if (typeof saved.code === "string") {
					return saved.code
				}
			}
		} catch (error) {
			logger.error("Failed to hydrate code from sessionStorage", error, { storageKey })
		}
		return originalCode
	})

	const [result, setResult] = useState(() => {
		try {
			const raw = sessionStorage.getItem(storageKey)
			if (raw) {
				const saved = JSON.parse(raw)
				if (saved.result !== undefined) {
					return saved.result
				}
			}
		} catch (error) {
			logger.error("Failed to hydrate result from sessionStorage", error, { storageKey })
		}
		return null
	})
	const [error, setError] = useState(null)

	const executeMutation = useMutation({
		mutationFn: executeCode,
		onSuccess: (executionResult, variables) => {
			setResult(executionResult)
			logger.track("code_execution_success", {
				language: variables.language,
				lessonId: variables.lessonId,
				status: executionResult?.status,
			})
		},
		onError: (err, variables) => {
			setResult(null)
			const message = err?.data?.message || err?.message || "Failed to execute code"
			setError(message)
			logger.error("Code execution failed", err, {
				language: variables?.language,
				lessonId: variables?.lessonId,
			})
		},
	})

	const handleCodeChange = (value) => {
		setCode(value)
	}

	const onReset = () => {
		setCode(originalCode)
		setResult(null)
		setError(null)
		executeMutation.reset()
		try {
			sessionStorage.removeItem(storageKey)
		} catch (err) {
			logger.error("Failed to clear sessionStorage", err, { storageKey })
		}
	}

	const onRun = async () => {
		const targetLanguage = runLanguage || language
		if (!targetLanguage) {
			setError("Language is not supported for execution.")
			return
		}
		setError(null)
		executeMutation.reset()
		logger.track("code_execution_started", { language: targetLanguage, lessonId, courseId })
		await executeMutation.mutateAsync({ code, language: targetLanguage, lessonId, courseId })
	}

	useEffect(() => {
		try {
			const payload = JSON.stringify({ code, result })
			sessionStorage.setItem(storageKey, payload)
		} catch (err) {
			logger.error("Failed to persist code state to sessionStorage", err, { storageKey })
		}
	}, [code, result, storageKey])

	return {
		code,
		result,
		error,
		isRunning: executeMutation.isPending,
		onRun,
		onReset,
		handleCodeChange,
	}
}
