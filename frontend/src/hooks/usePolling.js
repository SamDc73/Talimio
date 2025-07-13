import { useCallback, useEffect, useRef, useState } from "react";

// Custom hook for polling
export function usePolling(callback, interval, dependencies = []) {
	const [isPolling, setIsPolling] = useState(false);
	const timeoutIdRef = useRef(null);
	const callbackRef = useRef(callback);

	// Update callback ref when it changes
	useEffect(() => {
		callbackRef.current = callback;
	}, [callback]);

	const startPolling = useCallback(() => {
		setIsPolling(true);
		const poll = async () => {
			await callbackRef.current();
			timeoutIdRef.current = setTimeout(poll, interval);
		};
		poll();
	}, [interval]);

	const stopPolling = useCallback(() => {
		setIsPolling(false);
		if (timeoutIdRef.current) {
			clearTimeout(timeoutIdRef.current);
			timeoutIdRef.current = null;
		}
	}, []);

	useEffect(() => {
		return () => {
			stopPolling();
		};
	}, [stopPolling]);

	return { isPolling, startPolling, stopPolling };
}
