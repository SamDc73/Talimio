import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { VideoHeader } from "@/components/header/VideoHeader";
import { VideoSidebar } from "@/components/sidebar";
import { useToast } from "@/hooks/use-toast";
import { videoApi } from "@/services/videoApi";
import useAppStore from "@/stores/useAppStore";
import "@justinribeiro/lite-youtube";
import { CollapsibleDescription } from "./CollapsibleDescription";
import "./VideoViewer.css";
import VideoTranscript from "./VideoTranscript";

/**
 * Enhanced VideoViewer using Zustand for state management
 * Replaces direct localStorage usage with unified store
 */
function VideoViewerContentV2() {
	const { videoId } = useParams();
	const navigate = useNavigate();
	const { toast } = useToast();
	const isOpen = useAppStore((state) => state.preferences.sidebarOpen);
	const toggleSidebar = useAppStore((state) => state.toggleSidebar);
	const [video, setVideo] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const playerRef = useRef(null);

	// Zustand store selectors
	const videoProgress = useAppStore((state) => state.getVideoProgress(videoId));
	const updateVideoProgress = useAppStore((state) => state.updateVideoProgress);
	const setAppLoading = useAppStore((state) => state.setLoading);
	const addError = useAppStore((state) => state.addError);

	// Local state derived from store
	const [currentTime, setCurrentTime] = useState(
		videoProgress.currentTime || 0,
	);

	/**
	 * Load video data and initialize progress
	 */
	useEffect(() => {
		const loadVideo = async () => {
			if (!videoId) {
				setError("No video ID provided");
				setLoading(false);
				return;
			}

			try {
				setLoading(true);
				setAppLoading("video-fetch", true);
				setError(null);

				const data = await videoApi.getVideo(videoId);
				setVideo(data);

				// Initialize video duration in store if not already set
				if (!videoProgress.duration && data.duration) {
					updateVideoProgress(videoId, {
						duration: data.duration,
						totalDuration: data.duration,
					});
				}

				// Use stored progress or server progress
				const serverProgress =
					data.progress?.lastPosition || data.lastPosition || 0;
				const localProgress = videoProgress.currentTime || 0;

				// Use more recent progress
				const initialTime =
					localProgress > serverProgress ? localProgress : serverProgress;
				setCurrentTime(initialTime);
			} catch (err) {
				console.error("Failed to load video:", err);
				setError(err.message || "Failed to load video");
				addError(`Failed to load video: ${err.message}`);
				toast({
					title: "Error",
					description: err.message || "Failed to load video. Please try again.",
					variant: "destructive",
				});
			} finally {
				setLoading(false);
				setAppLoading("video-fetch", false);
			}
		};

		loadVideo();
	}, [
		videoId,
		toast,
		updateVideoProgress,
		addError,
		setAppLoading,
		videoProgress.currentTime,
		videoProgress.duration,
	]);

	/**
	 * Handle progress updates with store synchronization
	 */
	const handleProgressUpdate = useCallback(
		async (newCurrentTime) => {
			if (!video) return;

			const progressData = {
				currentTime: Math.floor(newCurrentTime),
				lastPosition: Math.floor(newCurrentTime),
				duration: video.duration,
				lastAccessed: Date.now(),
			};

			// Update store immediately
			updateVideoProgress(videoId, progressData);

			// Also update local state for immediate UI feedback
			setCurrentTime(newCurrentTime);
		},
		[video, videoId, updateVideoProgress],
	);

	/**
	 * Initialize YouTube IFrame API for real-time updates
	 */
	useEffect(() => {
		if (!video) return;

		// Load YouTube IFrame API script
		if (!window.YT) {
			const tag = document.createElement("script");
			tag.src = "https://www.youtube.com/iframe_api";
			const firstScriptTag = document.getElementsByTagName("script")[0];
			firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
		}

		let ytPlayer = null;
		let intervalId = null;

		// Wait for lite-youtube to load the iframe
		const handleIframeLoaded = async (_event) => {
			console.log("lite-youtube iframe loaded");

			// Wait a bit for YouTube API to be ready
			setTimeout(() => {
				try {
					// Get the iframe from the shadow DOM
					const iframe = playerRef.current?.shadowRoot?.querySelector("iframe");
					if (!iframe || !window.YT || !window.YT.Player) {
						console.warn("YouTube API or iframe not ready");
						return;
					}

					// Create YouTube player instance
					ytPlayer = new window.YT.Player(iframe, {
						events: {
							onReady: () => {
								console.log("YouTube player ready");

								// Start polling for time updates
								intervalId = setInterval(() => {
									if (
										ytPlayer &&
										typeof ytPlayer.getCurrentTime === "function"
									) {
										try {
											const time = ytPlayer.getCurrentTime();
											if (typeof time === "number" && !Number.isNaN(time)) {
												setCurrentTime(time);
											}
										} catch (err) {
											console.error("Error getting current time:", err);
										}
									}
								}, 100); // Poll every 100ms
							},
							onStateChange: (event) => {
								console.log("Player state changed:", event.data);
							},
						},
					});
				} catch (err) {
					console.error("Failed to create YouTube player:", err);
				}
			}, 1000);
		};

		// Listen for lite-youtube iframe loaded event
		if (playerRef.current) {
			playerRef.current.addEventListener(
				"liteYoutubeIframeLoaded",
				handleIframeLoaded,
			);
		}

		// Cleanup
		return () => {
			if (intervalId) {
				clearInterval(intervalId);
			}
			if (playerRef.current) {
				playerRef.current.removeEventListener(
					"liteYoutubeIframeLoaded",
					handleIframeLoaded,
				);
			}
		};
	}, [video]);

	/**
	 * Save progress on page unload using beacon API
	 */
	useEffect(() => {
		const saveProgressOnUnload = () => {
			if (currentTime > 0 && video) {
				// Use sendBeacon for reliable delivery during page unload
				const data = JSON.stringify({
					lastPosition: Math.floor(currentTime),
				});
				navigator.sendBeacon(
					`/api/v1/videos/${videoId}/progress`,
					new Blob([data], { type: "application/json" }),
				);
			}
		};

		const handleBeforeUnload = () => {
			saveProgressOnUnload();
		};

		window.addEventListener("beforeunload", handleBeforeUnload);

		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload);
			// Also save progress when component unmounts
			saveProgressOnUnload();
		};
	}, [currentTime, video, videoId]);

	/**
	 * Handle seeking to specific chapter/timestamp
	 */
	const handleSeekToChapter = useCallback(
		(timestamp) => {
			const iframe = playerRef.current?.querySelector("iframe");

			// Check if iframe exists (player is activated)
			if (iframe?.contentWindow) {
				console.log("Seeking to timestamp:", timestamp);
				// Use postMessage to control YouTube player
				iframe.contentWindow.postMessage(
					JSON.stringify({
						event: "command",
						func: "seekTo",
						args: [timestamp, true],
					}),
					"https://www.youtube.com",
				);

				// Update both local state and store
				setCurrentTime(timestamp);
				handleProgressUpdate(timestamp);
			} else {
				console.warn(
					"YouTube player not ready yet. Please start playing the video first.",
				);
				toast({
					title: "Start video first",
					description: "Please click play on the video before seeking",
					variant: "default",
				});
			}
		},
		[handleProgressUpdate, toast],
	);

	/**
	 * Calculate progress percentage
	 */
	const progressPercentage =
		video?.duration > 0 ? Math.round((currentTime / video.duration) * 100) : 0;

	/**
	 * Render loading state
	 */
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

	/**
	 * Render error state
	 */
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

	return (
		<div className="flex h-screen bg-background">
			<VideoHeader
				video={video}
				currentTime={currentTime}
				progressPercentage={progressPercentage}
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
								{formatDuration(video.duration)}
							</span>
							<span className="video-separator">•</span>
							<span className="video-progress">
								{formatDuration(currentTime)} / {formatDuration(video.duration)}{" "}
								({progressPercentage}%)
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
					key={video.uuid} // Force re-mount on video change
					videoUuid={video.uuid}
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
 * Format duration in HH:MM:SS or MM:SS format
 */
function formatDuration(seconds) {
	if (!seconds) return "Unknown duration";

	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = seconds % 60;

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Main VideoViewer component
 */
export default function VideoViewerV2() {
	return <VideoViewerContentV2 />;
}
