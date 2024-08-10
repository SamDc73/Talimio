import { useEffect, useRef, useState } from "react"

/**
 * A robust YouTube time tracking hook that uses postMessage API
 * This works with lite-youtube's shadow DOM by directly communicating with the iframe
 */
export function useYouTubeTimeTracking({ video, onTimeUpdate, onDurationUpdate }) {
	const playerRef = useRef(null)
	const [isReady, setIsReady] = useState(false)
	const intervalRef = useRef(null)
	const iframeRef = useRef(null)

	useEffect(() => {
		if (!video || !playerRef.current) return

		let checkInterval = null
		let timeInterval = null

		// Function to send commands to YouTube iframe
		const sendCommand = (func, args = []) => {
			if (iframeRef.current?.contentWindow) {
				iframeRef.current.contentWindow.postMessage(
					JSON.stringify({
						event: "command",
						func: func,
						args: args,
					}),
					"*"
				)
			}
		}

		// Function to poll for current time using postMessage
		const trackTime = () => {
			// Get iframe from shadow DOM
			const iframe = playerRef.current?.shadowRoot?.querySelector("iframe")
			if (iframe?.contentWindow) {
				iframeRef.current = iframe

				// Request current time and duration using postMessage
				// YouTube iframe will respond with time data
				iframe.contentWindow.postMessage(
					JSON.stringify({
						event: "listening",
						id: iframe.id || "player",
						channel: "widget",
					}),
					"*"
				)

				// Also try to get player state
				sendCommand("getPlayerState")
				sendCommand("getCurrentTime")
				sendCommand("getDuration")
			}
		}

		// Listen for messages from YouTube iframe
		const handleMessage = (event) => {
			// Only handle YouTube messages
			if (event.origin !== "https://www.youtube.com" && event.origin !== "https://www.youtube-nocookie.com") {
				return
			}

			try {
				const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data

				// Handle different message types
				if (data.event === "infoDelivery") {
					if (data.info?.currentTime !== undefined) {
						onTimeUpdate(data.info.currentTime)
					}
					if (data.info?.duration !== undefined) {
						onDurationUpdate(data.info.duration)
					}
					if (data.info?.playerState !== undefined) {
						// Player state 1 = playing
						if (data.info.playerState === 1 && !intervalRef.current) {
							// Start polling when playing
							intervalRef.current = setInterval(trackTime, 500) // Poll every 500ms for smoother sync
						} else if (data.info.playerState !== 1 && intervalRef.current) {
							// Stop polling when paused/stopped
							clearInterval(intervalRef.current)
							intervalRef.current = null
						}
					}
				} else if (data.event === "onReady") {
					setIsReady(true)
					// Start tracking immediately
					trackTime()
				}
			} catch (_err) {
				// Ignore non-JSON messages
			}
		}

		// Add message listener
		window.addEventListener("message", handleMessage)

		// Check for iframe periodically until it's loaded
		checkInterval = setInterval(() => {
			const iframe = playerRef.current?.shadowRoot?.querySelector("iframe")
			if (iframe) {
				iframeRef.current = iframe
				clearInterval(checkInterval)

				// Enable API and start listening
				iframe.contentWindow?.postMessage(
					JSON.stringify({
						event: "listening",
						id: iframe.id || "player",
						channel: "widget",
					}),
					"*"
				)

				// Start time tracking after a short delay
				setTimeout(() => {
					trackTime()
					// Set up periodic time tracking
					timeInterval = setInterval(trackTime, 1000)
				}, 1000)
			}
		}, 100)

		// Cleanup
		return () => {
			window.removeEventListener("message", handleMessage)
			if (checkInterval) clearInterval(checkInterval)
			if (timeInterval) clearInterval(timeInterval)
			if (intervalRef.current) clearInterval(intervalRef.current)
		}
	}, [video, onTimeUpdate, onDurationUpdate])

	// Seek function using postMessage
	const seekTo = (timestamp) => {
		if (iframeRef.current?.contentWindow) {
			iframeRef.current.contentWindow.postMessage(
				JSON.stringify({
					event: "command",
					func: "seekTo",
					args: [timestamp, true],
				}),
				"*"
			)
			// Update time immediately for responsive UI
			onTimeUpdate(timestamp)
			return true
		}
		return false
	}

	return {
		playerRef,
		seekTo,
		isReady,
	}
}
