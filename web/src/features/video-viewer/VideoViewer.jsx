import { Loader2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { getVideo } from "@/api/videosApi"
import { VideoHeader } from "@/components/header/VideoHeader"
import { VideoSidebar } from "@/components/sidebar"
import { useVideoProgress, useVideoProgressWithPosition } from "@/features/video-viewer/hooks/useVideoProgress"
import useAppStore, { selectSidebarOpen, selectToggleSidebar } from "@/stores/useAppStore"
import { useVideoProgressSaving } from "./hooks/useVideoProgressSaving"
import { VideoContentTabs } from "./VideoContentTabs"
import { YouTubePlayer } from "./YouTubePlayer"

import "./video-overrides.css" // Only for third-party overrides

/**
 * VideoViewer component with high-performance YouTube player and transcript sync
 */
function VideoViewerContent() {
	const { videoId } = useParams()
	const navigate = useNavigate()

	// Zustand store - using stable selectors
	const isOpen = useAppStore(selectSidebarOpen)
	const toggleSidebar = useAppStore(selectToggleSidebar)

	// Use unified progress hooks
	const { updateVideoProgress: updateProgress } = useVideoProgressWithPosition(videoId)
	const { progress: chapterProgress } = useVideoProgress(videoId)

	// Local state
	const [video, setVideo] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const [currentTime, setCurrentTime] = useState(0)
	const [duration, setDuration] = useState(0)
	const [isPlaying, setIsPlaying] = useState(false)

	// High-performance YouTube player ref
	const youtubePlayerRef = useRef(null)

	// Load video on mount
	useEffect(() => {
		const loadVideo = async () => {
			if (!videoId) {
				setError("No video ID provided")
				setLoading(false)
				return
			}

			try {
				setLoading(true)
				setError(null)

				const data = await getVideo(videoId)
				setVideo(data)

				// Set initial duration if available
				if (data.duration) {
					setDuration(data.duration)
				}

				// Set initial progress from server
				const savedProgress = data.progress?.lastPosition || data.lastPosition || 0
				setCurrentTime(savedProgress)
			} catch (err) {
				setError(err.message || "Failed to load video")
			} finally {
				setLoading(false)
			}
		}

		if (videoId) {
			loadVideo()
		}
	}, [videoId])

	// Handle YouTube player ready - memoized to prevent recreating player
	const handlePlayerReady = useCallback(() => {
		// Seek to saved position if available
		const savedPosition = video?.progress?.lastPosition || video?.lastPosition || 0
		if (savedPosition > 0 && youtubePlayerRef.current) {
			youtubePlayerRef.current.seekTo(savedPosition)
		}

		// Get initial duration on player ready
		if (youtubePlayerRef.current) {
			const dur = youtubePlayerRef.current.getDuration()
			if (dur) setDuration(dur)

			// Get initial time position
			const time = youtubePlayerRef.current.getCurrentTime()
			if (typeof time === "number" && !Number.isNaN(time)) {
				setCurrentTime(time)
			}
		}

		// Note: Time updates now come from VideoTranscriptSync through onTimeUpdate
		// This eliminates competing polling loops and ensures single source of truth
	}, [video]) // Only depend on video object

	// Handle player state changes - memoized to prevent recreating player
	const handleStateChange = useCallback((event) => {
		// Polling state changes are handled automatically by YouTubeTimeProvider
		// This ensures the sync engine gets accurate timing data
		// 1 = YT.PlayerState.PLAYING

		// Update playing state for transcript sync
		// Treat both PLAYING (1) and BUFFERING (3) as "playing" so transcript keeps updating
		setIsPlaying(event.data === 1 || event.data === 3)

		// Update our local state for progress tracking
		if (youtubePlayerRef.current) {
			// Always try to get current time on state change
			const time = youtubePlayerRef.current.getCurrentTime()
			if (typeof time === "number" && !Number.isNaN(time)) {
				setCurrentTime(time)
			}

			// Also get duration if available
			const dur = youtubePlayerRef.current.getDuration()
			if (typeof dur === "number" && !Number.isNaN(dur) && dur > 0) {
				setDuration(dur)
			}
		}
	}, []) // No dependencies - setters are stable

	// Use hook for progress saving
	useVideoProgressSaving({
		video,
		videoId,
		currentTime,
		duration,
		updateProgress,
	})

	// Clean up polling on unmount
	useEffect(() => {
		const playerRef = youtubePlayerRef.current
		return () => {
			// Stop UI polling when component unmounts
			if (playerRef) {
				playerRef.stopPolling()
			}
		}
	}, [])

	// Handle chapter/timestamp seeking - memoized
	const handleSeekToChapter = useCallback((timestamp) => {
		if (youtubePlayerRef.current) {
			youtubePlayerRef.current.seekTo(timestamp, true)
			setCurrentTime(timestamp) // Update immediately for responsive UI
		} else {
		}
	}, [])

	// Memoize time update callback
	const handleTimeUpdate = useCallback((time) => {
		// Get time updates from sync engine for progress tracking
		setCurrentTime(time)
	}, [])

	// Memoize playerVars to prevent recreation
	const playerVars = useMemo(
		() => ({
			autoplay: 0,
			modestbranding: 1,
			rel: 0,
			iv_load_policy: 3,
			cc_load_policy: 0,
			fs: 1,
			playsinline: 1,
			start: Math.floor(video?.progress?.lastPosition || video?.lastPosition || 0), // Use initial saved position from video data
		}),
		[video?.progress?.lastPosition, video?.lastPosition]
	)

	// Calculate progress percentage
	const timeBased =
		duration > 0
			? Math.round((currentTime / duration) * 100)
			: Math.round(video?.progress || video?.completionPercentage || 0)
	const chapterBased = Math.round(chapterProgress?.percentage || 0)
	const progressPercentage = Math.max(chapterBased, timeBased)

	// Format duration helper
	const formatDuration = (seconds) => {
		const hours = Math.floor(seconds / 3600)
		const minutes = Math.floor((seconds % 3600) / 60)
		const secs = Math.floor(seconds % 60)

		if (hours > 0) {
			return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
		}
		return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
	}

	// Loading state
	if (loading) {
		return (
			<div className="h-screen">
				<VideoHeader />
				<div
					className={`flex flex-col transition-all duration-300 min-h-[calc(100vh-4rem)] bg-gradient-to-b from-background to-muted/40 pt-16 ${isOpen ? "ml-80" : "ml-0"}`}
				>
					<div className="flex flex-col items-center justify-center min-h-[30rem] gap-4 text-muted-foreground p-12">
						<Loader2 className="h-8 w-8 animate-spin" />
						<p className="mt-2 text-sm font-medium opacity-80">Loading video...</p>
					</div>
				</div>
			</div>
		)
	}

	// Error state
	if (error || !video) {
		return (
			<div className="h-screen">
				<VideoHeader />
				<div
					className={`flex flex-col transition-all duration-300 min-h-[calc(100vh-4rem)] bg-gradient-to-b from-background to-muted/40 pt-16 ${isOpen ? "ml-80" : "ml-0"}`}
				>
					<div className="flex flex-col items-center justify-center min-h-[30rem] gap-4 p-12 bg-gradient-to-br from-destructive/5 to-transparent rounded-2xl border border-destructive/10">
						<p className="text-base font-medium text-destructive text-center max-w-[30rem]">
							{error || "Video not found"}
						</p>
						<button
							type="button"
							onClick={() => navigate("/")}
							className="mt-4 px-5 py-2.5 bg-video text-white rounded-lg text-sm font-medium transition-colors hover:bg-video-accent focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
						>
							Back to Home
						</button>
					</div>
				</div>
			</div>
		)
	}

	// Main render
	return (
		<div className="flex h-screen bg-background">
			<VideoHeader video={video} onToggleSidebar={toggleSidebar} isSidebarOpen={isOpen} />
			<VideoSidebar
				video={video}
				currentTime={currentTime}
				onSeek={handleSeekToChapter}
				progressPercentage={progressPercentage}
			/>
			<main className={`flex-1 transition-all duration-300 ${isOpen ? "ml-80" : "ml-0"} pt-16`}>
				<div className="flex-1 flex flex-col overflow-y-auto p-8 max-w-7xl mx-auto w-full scroll-smooth">
					{/* Video Player Container */}
					<div className="video-player relative w-full pb-[56.25%] bg-black rounded-xl overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.1)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.3)]">
						<YouTubePlayer
							ref={youtubePlayerRef}
							videoId={video.youtubeId}
							onReady={handlePlayerReady}
							onStateChange={handleStateChange}
							width="100%"
							height="100%"
							playerVars={playerVars}
						/>
					</div>

					{/* Video Info */}
					<div className="mt-6 p-0">
						<h1 className="text-[1.75rem] font-bold leading-9 tracking-tight mb-3 text-foreground">{video.title}</h1>
						<div className="flex items-center flex-wrap gap-3 text-sm text-muted-foreground mb-6">
							<span className="font-semibold text-video">{video.channel}</span>
							<span className="opacity-30">•</span>
							<span className="tabular-nums">{formatDuration(duration || video.duration)}</span>
							<span className="opacity-30">•</span>
							<span className="text-video font-semibold tabular-nums">
								{formatDuration(currentTime)} / {formatDuration(duration || video.duration)} ({progressPercentage}%)
							</span>
							{video.publishedAt && (
								<>
									<span className="opacity-30">•</span>
									<span className="text-[0.8125rem] opacity-80">
										{new Date(video.publishedAt).toLocaleDateString()}
									</span>
								</>
							)}
						</div>
					</div>

					<VideoContentTabs
						video={video}
						youtubePlayerRef={youtubePlayerRef}
						onSeek={handleSeekToChapter}
						isPlaying={isPlaying}
						onTimeUpdate={handleTimeUpdate}
					/>
				</div>
			</main>
		</div>
	)
}

/**
 * Main VideoViewer component
 */
export function VideoViewer() {
	return <VideoViewerContent />
}
