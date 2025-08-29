// VideoTranscript.jsx
// 1. React imports
import { useEffect, useImperativeHandle, useRef, useState } from "react"

// 2. External libraries
import { ErrorBoundary } from "react-error-boundary"
import { HighlightToolbar } from "@/components/HighlightToolbar"
import { useWebHighlighter } from "@/hooks/useWebHighlighter"
import { cn } from "@/lib/utils"
import { getVideoTranscript } from "@/services/videosService"
import { useVideoTranscriptSync } from "./hooks/useVideoTranscriptSync"
// 3. Internal absolute imports
import "./video-overrides.css" // Only for third-party overrides

// Virtualization config for performance
const CONFIG = {
	rowHeight: 42, // Compact height for better density
	visibleBuffer: 5, // Extra items to render above/below viewport
}

// Helper function to format time
const formatTime = (seconds) => {
	const mins = Math.floor(seconds / 60)
	const secs = Math.floor(seconds % 60)
	return `${mins}:${secs.toString().padStart(2, "0")}`
}

// Internal virtualized transcript component for performance
function VirtualizedTranscriptList({ segments, activeIndex, onSegmentClick, containerHeight = 400, ref }) {
	const containerRef = useRef(null)
	const [visibleRange, setVisibleRange] = useState({ start: 0, end: 50 })
	const isFirefox = navigator.userAgent.toLowerCase().includes("firefox")

	// Expose scrollToItem method
	useImperativeHandle(ref, () => ({
		scrollToItem: (index, align = "center") => {
			if (!containerRef.current) return

			const container = containerRef.current
			const itemElement = container.querySelector(`[data-index="${index}"]`)

			if (itemElement) {
				// Use native smooth scrolling for better Firefox performance
				const behavior = isFirefox ? "auto" : "smooth"

				if (align === "center") {
					const elementTop = itemElement.offsetTop
					const elementHeight = CONFIG.rowHeight
					const containerHeight = container.clientHeight
					const scrollTo = elementTop - containerHeight / 2 + elementHeight / 2

					container.scrollTo({
						top: scrollTo,
						behavior: behavior,
					})
				} else {
					itemElement.scrollIntoView({
						behavior: behavior,
						block: align,
					})
				}
			}
		},
	}))

	// Use Intersection Observer for efficient visibility detection
	useEffect(() => {
		if (!containerRef.current) return

		const container = containerRef.current

		// Calculate visible range based on scroll position
		const updateVisibleRange = () => {
			const scrollTop = container.scrollTop
			const containerHeight = container.clientHeight

			const start = Math.max(0, Math.floor(scrollTop / CONFIG.rowHeight) - CONFIG.visibleBuffer)
			const end = Math.min(
				segments.length,
				Math.ceil((scrollTop + containerHeight) / CONFIG.rowHeight) + CONFIG.visibleBuffer
			)

			setVisibleRange({ start, end })
		}

		// Throttle scroll updates for Firefox
		let scrollTimeout
		const handleScroll = () => {
			if (scrollTimeout) clearTimeout(scrollTimeout)
			scrollTimeout = setTimeout(updateVisibleRange, isFirefox ? 50 : 16)
		}

		container.addEventListener("scroll", handleScroll, { passive: true })
		updateVisibleRange() // Initial calculation

		return () => {
			container.removeEventListener("scroll", handleScroll)
			if (scrollTimeout) clearTimeout(scrollTimeout)
		}
	}, [segments.length, isFirefox])

	// Calculate total height for scrollbar
	const totalHeight = segments.length * CONFIG.rowHeight

	// Only render visible segments
	const visibleSegments = []
	for (let i = visibleRange.start; i < visibleRange.end && i < segments.length; i++) {
		const segment = segments[i]
		const isActive = i === activeIndex

		visibleSegments.push(
			<button
				key={`${segment.startTime}-${i}`}
				data-index={i}
				type="button"
				className={cn(
					"transcript-segment", // Keep for performance optimizations in CSS
					"flex items-center gap-3 px-6 py-2 pl-6",
					"border-l-2 border-transparent cursor-pointer border-0 w-full text-left",
					"transition-all duration-150 ease-in-out",
					"bg-white select-text",
					"hover:bg-gray-50",
					"focus:outline-2 focus:outline-violet-600 focus:-outline-offset-2",
					"focus-visible:outline-2 focus-visible:outline-violet-600 focus-visible:outline-offset-2",
					isActive && ["border-l-violet-600 bg-violet-100", "font-medium"]
				)}
				style={{
					position: "absolute",
					top: i * CONFIG.rowHeight,
					height: CONFIG.rowHeight,
					width: "100%",
				}}
				onClick={() => onSegmentClick(segment.startTime, i)}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault()
						onSegmentClick(segment.startTime, i)
					}
				}}
				aria-label={`Jump to ${formatTime(segment.startTime)}: ${segment.text.slice(0, 50)}${segment.text.length > 50 ? "..." : ""}`}
			>
				<span
					className={cn(
						"flex-shrink-0 text-[11px] font-semibold tabular-nums",
						"min-w-[42px] px-1.5 py-0.5 rounded-md text-center",
						"bg-violet-500/15 text-violet-600",
						"hover:bg-violet-500/20",
						"select-none", // Make timestamp non-selectable
						isActive && "text-violet-600 font-semibold"
					)}
				>
					{formatTime(segment.startTime)}
				</span>
				<span
					className={cn(
						"flex-1 text-sm leading-normal",
						"text-foreground/85 break-words",
						"transition-colors duration-150 select-text",
						"hover:text-foreground",
						isActive && "text-foreground font-medium"
					)}
				>
					{segment.text}
				</span>
			</button>
		)
	}

	return (
		<div
			ref={containerRef}
			className="transcript-virtualized-container relative overflow-auto bg-white"
			style={{
				height: containerHeight,
				// Firefox-specific optimizations
				willChange: isFirefox ? "scroll-position" : "transform",
				// Disable smooth scrolling in Firefox for better performance
				scrollBehavior: isFirefox ? "auto" : "smooth",
			}}
		>
			<div
				style={{
					height: totalHeight,
					position: "relative",
				}}
			>
				{visibleSegments}
			</div>
		</div>
	)
}

// No default exports - following react_draft.md
export function VideoTranscript({ videoId, videoElement, youtubePlayerRef, onSeek, isPlaying = false, onTimeUpdate }) {
	const [transcript, setTranscript] = useState(null)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState(null)
	const [activeIndex, setActiveIndex] = useState(-1)
	const [userScrolling, setUserScrolling] = useState(false)
	const [playerReady, setPlayerReady] = useState(false)
	const transcriptRef = useRef(null)
	const scrollTimeoutRef = useRef(null)

	// Initialize highlighting for video transcripts
	const { highlights, deleteHighlight, toggleHighlights } = useWebHighlighter("video", videoId, {
		enabled: !!transcript && !!videoId,
		containerSelector: ".transcript-virtualized-container",
	})

	// Fetch transcript when component mounts
	useEffect(() => {
		const loadTranscript = async () => {
			if (!videoId) return

			setLoading(true)
			setError(null)

			try {
				const data = await getVideoTranscript(videoId)
				setTranscript(data)
			} catch (err) {
				console.error("Failed to load transcript:", err)
				setError("Failed to load transcript")
			} finally {
				setLoading(false)
			}
		}

		loadTranscript()
	}, [videoId])

	// Check if YouTube player is ready
	useEffect(() => {
		if (!youtubePlayerRef) {
			setPlayerReady(false)
			return
		}

		const checkReady = () => {
			if (youtubePlayerRef.current?.isReady?.()) {
				setPlayerReady(true)
				return true
			}
			return false
		}

		// Check immediately
		if (checkReady()) return

		// Poll for ready state
		const interval = setInterval(() => {
			if (checkReady()) {
				clearInterval(interval)
			}
		}, 100)

		return () => clearInterval(interval)
	}, [youtubePlayerRef])

	// Centralized scroll callback for virtualized list
	const scrollToIndex = (index) => {
		if (!userScrolling && index >= 0 && index < transcript?.segments?.length) {
			transcriptRef.current?.scrollToItem(index, "center")
		}
	}

	// High-performance sync engine with virtualized scrolling
	const syncEngine = useVideoTranscriptSync({
		videoElement,
		youtubePlayerRef: playerReady ? youtubePlayerRef : null,
		segments: transcript?.segments,
		onActiveIndexChange: (index) => {
			setActiveIndex(index)
			// Debounced scroll for virtualized list
			if (scrollTimeoutRef.current) {
				clearTimeout(scrollTimeoutRef.current)
			}
			scrollTimeoutRef.current = setTimeout(() => scrollToIndex(index), 100)
		},
		scrollToIndex: scrollToIndex, // Use centralized scrolling
		isPlaying, // Pass play/pause state
		onTimeUpdate, // Forward time updates to parent
	})

	// Note: User scrolling detection is handled differently with virtualized list
	// The VirtualizedTranscript component manages its own scroll behavior

	// Handle segment click for seeking
	const handleSegmentClick = (startTime) => {
		// Reset user scrolling flag when clicking
		setUserScrolling(false)

		// Immediate seek using sync engine
		if (syncEngine) {
			syncEngine.seek(startTime)
		}
		if (onSeek) {
			onSeek(startTime)
		}
	}

	if (loading) {
		return (
			<div className="p-12 text-center bg-transparent">
				<div className="flex items-center justify-center gap-3 text-sm font-medium text-violet-600">
					<span className="relative flex h-5 w-5">
						<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
						<span className="relative inline-flex rounded-full h-5 w-5 bg-violet-500" />
					</span>
					Loading transcript...
				</div>
			</div>
		)
	}

	if (error) {
		return (
			<div className="p-12 text-center bg-transparent">
				<div className="text-sm font-medium text-red-500">{error}</div>
			</div>
		)
	}

	if (!transcript?.segments || transcript.segments.length === 0) {
		return (
			<div className="p-12 text-center bg-transparent">
				<div className="text-sm italic text-muted-foreground">No transcript available for this video</div>
			</div>
		)
	}

	return (
		<div className="relative overflow-hidden bg-white">
			<VirtualizedTranscriptList
				ref={transcriptRef}
				segments={transcript.segments}
				activeIndex={activeIndex}
				onSegmentClick={handleSegmentClick}
				containerHeight={450} // Increased height for tab view
			/>
			{/* Highlight toolbar for managing selected highlights */}
			<HighlightToolbar highlights={highlights} onDelete={deleteHighlight} />
		</div>
	)
}

// Error fallback component following component-architecture.md patterns
function TranscriptErrorFallback({ error, resetErrorBoundary }) {
	return (
		<div className="p-4 border border-destructive rounded-md">
			<h2 className="text-lg font-semibold text-destructive">Transcript Error</h2>
			<pre className="mt-2 text-sm text-muted-foreground">{error.message}</pre>
			<button
				onClick={resetErrorBoundary}
				className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded"
				type="button"
			>
				Retry Loading Transcript
			</button>
		</div>
	)
}

// Wrap the VideoTranscript with ErrorBoundary for production use
export function VideoTranscriptWithErrorBoundary(props) {
	return (
		<ErrorBoundary FallbackComponent={TranscriptErrorFallback}>
			<VideoTranscript {...props} />
		</ErrorBoundary>
	)
}

// Export as default for backward compatibility
export default VideoTranscript
