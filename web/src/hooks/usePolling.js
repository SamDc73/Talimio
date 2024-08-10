import { useEffect, useRef, useState } from "react"

// Custom hook for polling
export function usePolling(callback, interval, _dependencies = []) {
	const [isPolling, setIsPolling] = useState(false)
	const timeoutIdRef = useRef(null)
	const callbackRef = useRef(callback)

	// Update callback ref when it changes
	useEffect(() => {
		callbackRef.current = callback
	}, [callback])

	const startPolling = () => {
		setIsPolling(true)
		const poll = async () => {
			await callbackRef.current()
			timeoutIdRef.current = setTimeout(poll, interval)
		}
		poll()
	}

	const stopPolling = () => {
		setIsPolling(false)
		if (timeoutIdRef.current) {
			clearTimeout(timeoutIdRef.current)
			timeoutIdRef.current = null
		}
	}

	useEffect(() => {
		return () => {
			stopPolling()
		}
	}, [stopPolling])

	return { isPolling, startPolling, stopPolling }
}
