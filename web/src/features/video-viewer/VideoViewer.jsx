import { Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { VideoHeader } from "@/components/header/VideoHeader"
import { VideoSidebar } from "@/components/sidebar"
import { useToast } from "@/hooks/use-toast"
import { useVideoProgressWithPosition } from "@/hooks/useVideoProgress"
import { useYouTubeTimeTracking } from "@/hooks/useYouTubeTimeTracking"
import { getVideo } from "@/services/videosService"
import useAppStore from "@/stores/useAppStore"
import { CollapsibleDescription } from "./CollapsibleDescription"
import VideoTranscript from "./VideoTranscript"
import "@justinribeiro/lite-youtube"

import "./VideoViewer.css"
import { getVideoProgress } from "@/utils/progressUtils"

/**
 * VideoViewer component following patterns from PDFViewer and LessonViewer
 */
function VideoViewerContent() {
	const { videoId } = useParams()
	const navigate = useNavigate()
	const { toast } = useToast()

	// Zustand store - using stable selectors
	const isOpen = useAppStore((state) => state.preferences?.sidebarOpen ?? true)
	const toggleSidebar = useAppStore((state) => state.toggleSidebar)

	// Use unified progress hook
	const { updateVideoProgress: updateProgress } = useVideoProgressWithPosition(videoId)

	// Local state
	const [video, setVideo] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const [currentTime, setCurrentTime] = useState(0)
	const [duration, setDuration] = useState(0)

	// Use the robust YouTube time tracking hook with postMessage
	const { playerRef, seekTo } = useYouTubeTimeTracking({
		video,
		onTimeUpdate: setCurrentTime,
		onDurationUpdate: setDuration,
	})

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
				toast({
					title: "Error",
					description: err.message || "Failed to load video. Please try again.",
					variant: "destructive",
				})
			} finally {
				setLoading(false)
			}
		}

		if (videoId) {
			loadVideo()
		}
	}, [videoId, toast]) // Only depend on videoId, toast is stable

	// Save progress periodically using useRef to avoid stale closures
	const progressDataRef = useRef({ currentTime: 0, duration: 0 })
	const lastSavedTimeRef = useRef(0)

	// Update ref whenever values change
	useEffect(() => {
		progressDataRef.current = { currentTime, duration }
	}, [currentTime, duration])

	useEffect(() => {
		if (!video || !videoId) return

		const saveProgress = () => {
			const { currentTime: time, duration: dur } = progressDataRef.current
			// Only save if position changed by at least 5 seconds
			if (time > 0 && Math.abs(time - lastSavedTimeRef.current) >= 5) {
				updateProgress(Math.floor(time), dur)
				lastSavedTimeRef.current = time
			}
		}

		// Save every 10 seconds (reduced frequency)
		const saveInterval = setInterval(saveProgress, 10000)

		return () => {
			clearInterval(saveInterval)
			// Save on unmount
			saveProgress()
		}
	}, [videoId, video, updateProgress])

	// Save progress on page unload
	useEffect(() => {
		const handleBeforeUnload = () => {
			if (currentTime > 0 && video && videoId) {
				const data = JSON.stringify({
					progress_percentage: duration > 0 ? Math.round((currentTime / duration) * 100) : 0,
					metadata: {
						content_type: "video",
						lastPosition: Math.floor(currentTime),
						duration: duration,
					},
				})
				navigator.sendBeacon(`/api/v1/progress/${videoId}`, new Blob([data], { type: "application/json" }))
			}
		}

		window.addEventListener("beforeunload", handleBeforeUnload)
		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload)
		}
	}, [currentTime, duration, video, videoId])

	// Handle chapter/timestamp seeking
	const handleSeekToChapter = (timestamp) => {
		const success = seekTo(timestamp)
		if (!success) {
			toast({
				title: "Start video first",
				description: "Please click play on the video before seeking",
				variant: "default",
			})
		}
	}

	// Calculate progress percentage
	const progressPercentage = duration > 0 ? Math.round((currentTime / duration) * 100) : getVideoProgress(video)

	// Format duration helper
	const formatDuration = (seconds) => {
		if (!seconds || seconds === 0) return "0:00"

		const hours = Math.floor(seconds / 3600)
		const minutes = Math.floor((seconds % 3600) / 60)
		const secs = Math.floor(seconds % 60)

		if (hours > 0) {
			return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
		}
		return `${minutes}:${secs.toString().padStart(2, "0")}`
	}

	// Loading state
	if (loading) {
		return (
			<div className={`h-screen ${isOpen ? "sidebar-open" : ""}`}>
				<VideoHeader />
				<div className="content-with-sidebar">
					<div className="video-loading">
						<Loader2 className="h-8 w-8 animate-spin" />
						<p>Loading video...</p>
					</div>
				</div>
			</div>
		)
	}

	// Error state
	if (error || !video) {
		return (
			<div className={`h-screen ${isOpen ? "sidebar-open" : ""}`}>
				<VideoHeader />
				<div className="content-with-sidebar">
					<div className="video-error">
						<p>{error || "Video not found"}</p>
						<button type="button" onClick={() => navigate("/")} className="mt-4">
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
				<div className="video-player-section">
					<div className="video-player">
						<lite-youtube
							ref={playerRef}
							videoid={video.youtubeId}
							videotitle={video.title}
							posterquality="hqdefault"
							params="rel=0&modestbranding=1&enablejsapi=1&iv_load_policy=3&cc_load_policy=0&fs=0&playsinline=1&disablekb=0"
							autoload
							nocookie
							privacy
						>
							{video.thumbnailUrl && <img slot="image" src={video.thumbnailUrl} alt={video.title} />}
						</lite-youtube>
					</div>

					<div className="video-info">
						<h1 className="video-title">{video.title}</h1>
						<div className="video-metadata">
							<span className="video-channel">{video.channel}</span>
							<span className="video-separator">•</span>
							<span className="video-duration">{formatDuration(duration || video.duration)}</span>
							<span className="video-separator">•</span>
							<span className="video-progress">
								{formatDuration(currentTime)} / {formatDuration(duration || video.duration)} ({progressPercentage}%)
							</span>
							{video.publishedAt && (
								<>
									<span className="video-separator">•</span>
									<span className="video-date">{new Date(video.publishedAt).toLocaleDateString()}</span>
								</>
							)}
						</div>
					</div>
				</div>
				{/* Video Transcript */}
				<VideoTranscript
					key={video.id} // Force re-mount on video change
					videoId={video.id}
					currentTime={currentTime}
					onSeek={handleSeekToChapter}
				/>
				{video.description && <CollapsibleDescription description={video.description} />}
			</main>
		</div>
	)
}

/**
 * Main VideoViewer component
 */
export default function VideoViewer() {
	return <VideoViewerContent />
}
