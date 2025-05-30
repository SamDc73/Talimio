import { useEffect, useState, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useToast } from "@/hooks/use-toast"
import { VideoHeader } from "@/components/header/VideoHeader"
import { VideoSidebar } from "@/components/sidebar"
import { videoApi } from "@/services/videoApi"
import { Loader2 } from "lucide-react"
import { SidebarProvider, useSidebar } from "@/features/navigation/SidebarContext"
import "@justinribeiro/lite-youtube"
import "./VideoViewer.css"

function VideoViewerContent() {
  const { videoId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const { isOpen } = useSidebar()
  const [video, setVideo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const playerRef = useRef(null)

  // First useEffect - load video
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
        console.log("Loading video with ID:", videoId)
        const data = await videoApi.getVideo(videoId)
        console.log("Video loaded:", data)
        setVideo(data)
      } catch (err) {
        console.error("Failed to load video:", err)
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
    
    loadVideo()
  }, [videoId, toast])

  // Second useEffect - Handle lite-youtube player
  useEffect(() => {
    if (!video || !playerRef.current) return

    const handleLiteYoutubeActivate = () => {
      // Player is activated (user clicked play)
      const iframe = playerRef.current.querySelector('iframe')
      if (iframe) {

        // Set up postMessage communication with the YouTube iframe
        const intervalId = setInterval(() => {
          iframe.contentWindow?.postMessage(
            JSON.stringify({
              event: 'listening',
              id: 1,
              channel: 'widget'
            }),
            '*'
          )
        }, 1000)

        // Handle messages from YouTube iframe
        const handleMessage = (event) => {
          if (event.origin !== 'https://www.youtube.com') return
          
          try {
            const data = JSON.parse(event.data)
            if (data.event === 'infoDelivery' && data.info && data.info.currentTime !== undefined) {
              setCurrentTime(Math.floor(data.info.currentTime))
            }
          } catch (e) {
            // Ignore non-JSON messages
          }
        }

        window.addEventListener('message', handleMessage)

        return () => {
          clearInterval(intervalId)
          window.removeEventListener('message', handleMessage)
        }
      }
    }

    // Listen for when lite-youtube activates
    playerRef.current.addEventListener('liteYoutubeActivate', handleLiteYoutubeActivate)

    return () => {
      playerRef.current?.removeEventListener('liteYoutubeActivate', handleLiteYoutubeActivate)
    }
  }, [video])

  // Handler functions
  const handleProgressUpdate = async (currentTime) => {
    if (!video) return
    
    try {
      await videoApi.updateProgress(videoId, {
        last_position: Math.floor(currentTime)
      })
    } catch (err) {
      console.error("Failed to update progress:", err)
    }
  }

  const handleSeekToChapter = (timestamp) => {
    const iframe = playerRef.current?.querySelector('iframe')
    if (iframe?.contentWindow) {
      // Use postMessage to control YouTube player
      iframe.contentWindow.postMessage(
        JSON.stringify({
          event: 'command',
          func: 'seekTo',
          args: [timestamp, true]
        }),
        '*'
      )
      setCurrentTime(timestamp)
    }
  }



  // Conditional returns after all hooks
  if (loading) {
    return (
      <div className={`h-screen ${isOpen ? 'sidebar-open' : ''}`}>
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

  if (error || !video) {
    return (
      <div className={`h-screen ${isOpen ? 'sidebar-open' : ''}`}>
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

  return (
    <div className={`h-screen ${isOpen ? 'sidebar-open' : ''}`}>
      <VideoHeader video={video} />
      <VideoSidebar
        video={video}
        currentTime={currentTime}
        onSeek={handleSeekToChapter}
      />
      <div className="content-with-sidebar">
        <div className="video-player-section">
          <div className="video-player">
            <lite-youtube
              ref={playerRef}
              videoid={video.youtube_id}
              videotitle={video.title}
              posterquality="hqdefault"
              params="rel=0&modestbranding=1&enablejsapi=1&iv_load_policy=3&cc_load_policy=0&fs=0&playsinline=1&disablekb=0"
              autoload
              nocookie
              privacy
            >
              {video.thumbnail_url && (
                <img slot="image" src={video.thumbnail_url} alt={video.title} />
              )}
            </lite-youtube>
          </div>
        
          <div className="video-info">
            <h1 className="video-title">{video.title}</h1>
            <div className="video-metadata">
              <span className="video-channel">{video.channel}</span>
              <span className="video-separator">•</span>
              <span className="video-duration">{formatDuration(video.duration)}</span>
              {video.published_at && (
                <>
                  <span className="video-separator">•</span>
                  <span className="video-date">
                    {new Date(video.published_at).toLocaleDateString()}
                  </span>
                </>
              )}
            </div>
            {video.description && (
              <div className="video-description">
                <h3>Description</h3>
                <p>{video.description}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function formatDuration(seconds) {
  if (!seconds) return "Unknown duration"
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// Wrapper component to provide sidebar context
export default function VideoViewer() {
  return (
    <SidebarProvider>
      <VideoViewerContent />
    </SidebarProvider>
  )
}