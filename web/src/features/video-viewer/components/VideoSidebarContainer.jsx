import VideoSidebar from "@/components/sidebar/VideoSidebar"
import { useVideoProgress } from "@/features/video-viewer/hooks/use-video-progress"

export default function VideoSidebarContainer(props) {
	const { video } = props
	const progressApi = useVideoProgress(video?.id)

	return <VideoSidebar {...props} progressApi={progressApi} />
}
