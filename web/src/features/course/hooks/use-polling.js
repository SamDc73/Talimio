import { useCallback, useEffect, useRef, useState } from "react"

/**
 * Custom hook for polling functionality
 * Follows React best practices:
 * - Effects only for external system sync (timers)
 * - Proper cleanup patterns
 * - Stable function references with useCallback
 * - No unnecessary abstractions
 */
export function usePolling(callback, interval) {
	const [isPolling, setIsPolling] = useState(false)
	const timeoutIdRef = useRef(null)
	const callbackRef = useRef(callback)

	// Keep callback ref current without causing re-renders
	// This is synchronization with external reference, appropriate use of Effect
	useEffect(() => {
		callbackRef.current = callback
	}, [callback])

	const startPolling = useCallback(() => {
		// Avoid duplicate polling
		if (timeoutIdRef.current) {
			return
		}

		setIsPolling(true)

		const poll = async () => {
			try {
				await callbackRef.current()
			} catch {
				// Silently catch polling errors to prevent crashes
				// The callback should handle its own errors
			}

			// Schedule next poll only if still active
			if (timeoutIdRef.current !== null) {
				timeoutIdRef.current = setTimeout(poll, interval)
			}
		}

		// Start immediately
		poll()
	}, [interval])

	const stopPolling = useCallback(() => {
		setIsPolling(false)
		if (timeoutIdRef.current) {
			clearTimeout(timeoutIdRef.current)
			timeoutIdRef.current = null
		}
	}, [])

	// Cleanup on unmount - proper cleanup pattern as per React principles
	useEffect(() => {
		return () => {
			if (timeoutIdRef.current) {
				clearTimeout(timeoutIdRef.current)
				timeoutIdRef.current = null
			}
		}
	}, [])

	return { isPolling, startPolling, stopPolling }
}
