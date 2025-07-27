import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { VideoHeader } from "@/components/header/VideoHeader";
import { VideoSidebar } from "@/components/sidebar";
import { useToast } from "@/hooks/use-toast";
import { useVideoProgressWithPosition } from "@/hooks/useVideoProgress";
import { videoApi } from "@/services/videoApi";
import useAppStore from "@/stores/useAppStore";
import "@justinribeiro/lite-youtube";
import { CollapsibleDescription } from "./CollapsibleDescription";
import VideoTranscript from "./VideoTranscript";
import "./VideoViewer.css";
import { getVideoProgress } from "@/utils/progressUtils";

/**
 * VideoViewer component following patterns from PDFViewer and LessonViewer
 */
function VideoViewerContent() {
	const { videoId } = useParams();
	const navigate = useNavigate();
	const { toast } = useToast();

	// Zustand store - using stable selectors
	const isOpen = useAppStore((state) => state.preferences?.sidebarOpen ?? true);
	const toggleSidebar = useAppStore((state) => state.toggleSidebar);

	// Use unified progress hook
	const { updateVideoProgress: updateProgress } =
		useVideoProgressWithPosition(videoId);

	// Local state
	const [video, setVideo] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const [currentTime, setCurrentTime] = useState(0);
	const [duration, setDuration] = useState(0);

	// Refs
	const playerRef = useRef(null);
	const ytPlayerRef = useRef(null);
	const progressIntervalRef = useRef(null);
	const liteYoutubeEventListenerRef = useRef(null);

	// Load video data
	const loadVideo = useCallback(async () => {
		if (!videoId) {
			setError("No video ID provided");
			setLoading(false);
			return;
		}

		try {
			setLoading(true);
			setError(null);

			const data = await videoApi.getVideo(videoId);
			setVideo(data);

			// Set initial duration if available
			if (data.duration) {
				setDuration(data.duration);
			}

			// Set initial progress from server
			const savedProgress =
				data.progress?.lastPosition || data.lastPosition || 0;
			setCurrentTime(savedProgress);
		} catch (err) {
			console.error("Failed to load video:", err);
			setError(err.message || "Failed to load video");
			toast({
				title: "Error",
				description: err.message || "Failed to load video. Please try again.",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	}, [videoId, toast]);

	// Load video on mount
	useEffect(() => {
		loadVideo();
	}, [loadVideo]);

	// Initialize YouTube player when lite-youtube is ready
	useEffect(() => {
		if (!video || !playerRef.current) return;

		let _ytPlayer = null;
		let intervalId = null;

		const initializeYouTubePlayer = () => {
			// Wait for lite-youtube to load the iframe
			const checkIframe = setInterval(() => {
				const iframe = playerRef.current?.shadowRoot?.querySelector("iframe");
				if (iframe && window.YT && window.YT.Player) {
					clearInterval(checkIframe);

					// Create YouTube player instance
					_ytPlayer = new window.YT.Player(iframe, {
						events: {
							onReady: (event) => {
								console.log("YouTube player ready");
								ytPlayerRef.current = event.target;

								// Seek to saved position
								if (currentTime > 0) {
									event.target.seekTo(currentTime, true);
								}

								// Start progress tracking
								intervalId = setInterval(() => {
									if (
										ytPlayerRef.current &&
										typeof ytPlayerRef.current.getCurrentTime === "function"
									) {
										try {
											const time = ytPlayerRef.current.getCurrentTime();
											const totalDuration = ytPlayerRef.current.getDuration();

											if (typeof time === "number" && !Number.isNaN(time)) {
												setCurrentTime(time);
												if (totalDuration > 0) {
													setDuration(totalDuration);
												}
											}
										} catch (err) {
											console.error("Error getting video time:", err);
										}
									}
								}, 1000);
							},
							onStateChange: (event) => {
								console.log("Player state changed:", event.data);
							},
						},
					});
				}
			}, 100);
		};

		// Setup lite-youtube iframe loaded event listener
		const handleIframeLoaded = () => {
			console.log("lite-youtube iframe loaded");
			setTimeout(initializeYouTubePlayer, 500);
		};

		// Load YouTube IFrame API if not already loaded
		if (!window.YT) {
			const tag = document.createElement("script");
			tag.src = "https://www.youtube.com/iframe_api";
			const firstScriptTag = document.getElementsByTagName("script")[0];
			firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

			window.onYouTubeIframeAPIReady = initializeYouTubePlayer;
		} else {
			// If API is already loaded, check if iframe exists
			const iframe = playerRef.current?.shadowRoot?.querySelector("iframe");
			if (iframe) {
				initializeYouTubePlayer();
			} else {
				// Listen for iframe loaded event
				liteYoutubeEventListenerRef.current = handleIframeLoaded;
				playerRef.current.addEventListener(
					"liteYoutubeIframeLoaded",
					handleIframeLoaded,
				);
			}
		}

		// Cleanup
		return () => {
			if (intervalId) {
				clearInterval(intervalId);
			}
			if (progressIntervalRef.current) {
				clearInterval(progressIntervalRef.current);
			}
			if (playerRef.current && liteYoutubeEventListenerRef.current) {
				playerRef.current.removeEventListener(
					"liteYoutubeIframeLoaded",
					liteYoutubeEventListenerRef.current,
				);
			}
			ytPlayerRef.current = null;
		};
	}, [video, currentTime]); // Remove currentTime from deps to avoid re-initialization

	// Save progress periodically using useRef to avoid stale closures
	const progressDataRef = useRef({ currentTime: 0, duration: 0 });
	const lastSavedTimeRef = useRef(0);

	// Update ref whenever values change
	useEffect(() => {
		progressDataRef.current = { currentTime, duration };
	}, [currentTime, duration]);

	useEffect(() => {
		if (!video || !videoId) return;

		const saveProgress = () => {
			const { currentTime: time, duration: dur } = progressDataRef.current;
			// Only save if position changed by at least 5 seconds
			if (time > 0 && Math.abs(time - lastSavedTimeRef.current) >= 5) {
				updateProgress(Math.floor(time), dur);
				lastSavedTimeRef.current = time;
			}
		};

		// Save every 10 seconds (reduced frequency)
		const saveInterval = setInterval(saveProgress, 10000);

		return () => {
			clearInterval(saveInterval);
			// Save on unmount
			saveProgress();
		};
	}, [videoId, video, updateProgress]);

	// Save progress on page unload
	useEffect(() => {
		const handleBeforeUnload = () => {
			if (currentTime > 0 && video && videoId) {
				const data = JSON.stringify({
					progress_percentage:
						duration > 0 ? Math.round((currentTime / duration) * 100) : 0,
					metadata: {
						content_type: "video",
						lastPosition: Math.floor(currentTime),
						duration: duration,
					},
				});
				navigator.sendBeacon(
					`/api/v1/progress/${videoId}`,
					new Blob([data], { type: "application/json" }),
				);
			}
		};

		window.addEventListener("beforeunload", handleBeforeUnload);
		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload);
		};
	}, [currentTime, duration, video, videoId]);

	// Handle chapter/timestamp seeking
	const handleSeekToChapter = useCallback(
		(timestamp) => {
			if (
				ytPlayerRef.current &&
				typeof ytPlayerRef.current.seekTo === "function"
			) {
				ytPlayerRef.current.seekTo(timestamp, true);
				setCurrentTime(timestamp);
			} else {
				// If player not ready, try iframe postMessage
				const iframe = playerRef.current?.shadowRoot?.querySelector("iframe");
				if (iframe?.contentWindow) {
					iframe.contentWindow.postMessage(
						JSON.stringify({
							event: "command",
							func: "seekTo",
							args: [timestamp, true],
						}),
						"https://www.youtube.com",
					);
					setCurrentTime(timestamp);
				} else {
					toast({
						title: "Start video first",
						description: "Please click play on the video before seeking",
						variant: "default",
					});
				}
			}
		},
		[toast],
	);

	// Calculate progress percentage
	const progressPercentage =
		duration > 0
			? Math.round((currentTime / duration) * 100)
			: getVideoProgress(video);

	// Format duration helper
	const formatDuration = (seconds) => {
		if (!seconds || seconds === 0) return "0:00";

		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = Math.floor(seconds % 60);

		if (hours > 0) {
			return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
		}
		return `${minutes}:${secs.toString().padStart(2, "0")}`;
	};

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
		);
	}

	// Error state
	if (error || !video) {
		return (
			<div className={`h-screen ${isOpen ? "sidebar-open" : ""}`}>
				<VideoHeader />
				<div className="content-with-sidebar">
					<div className="video-error">
						<p>{error || "Video not found"}</p>
						<button
							type="button"
							onClick={() => navigate("/")}
							className="mt-4"
						>
							Back to Home
						</button>
					</div>
				</div>
			</div>
		);
	}

	// Main render
	return (
		<div className="flex h-screen bg-background">
			<VideoHeader
				video={video}
				onToggleSidebar={toggleSidebar}
				isSidebarOpen={isOpen}
			/>
			<VideoSidebar
				video={video}
				currentTime={currentTime}
				onSeek={handleSeekToChapter}
				progressPercentage={progressPercentage}
			/>
			<main
				className={`flex-1 transition-all duration-300 ${isOpen ? "ml-80" : "ml-0"} pt-16`}
			>
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
							{video.thumbnailUrl && (
								<img slot="image" src={video.thumbnailUrl} alt={video.title} />
							)}
						</lite-youtube>
					</div>

					<div className="video-info">
						<h1 className="video-title">{video.title}</h1>
						<div className="video-metadata">
							<span className="video-channel">{video.channel}</span>
							<span className="video-separator">•</span>
							<span className="video-duration">
								{formatDuration(duration || video.duration)}
							</span>
							<span className="video-separator">•</span>
							<span className="video-progress">
								{formatDuration(currentTime)} /{" "}
								{formatDuration(duration || video.duration)} (
								{progressPercentage}%)
							</span>
							{video.publishedAt && (
								<>
									<span className="video-separator">•</span>
									<span className="video-date">
										{new Date(video.publishedAt).toLocaleDateString()}
									</span>
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
				{video.description && (
					<CollapsibleDescription description={video.description} />
				)}
			</main>
		</div>
	);
}

/**
 * Main VideoViewer component
 */
export default function VideoViewer() {
	return <VideoViewerContent />;
}
