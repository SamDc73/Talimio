import { motion } from "framer-motion"
import { Loader2, Youtube } from "lucide-react"
import { useState } from "react"

import { createVideo } from "@/api/videosApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import logger from "@/lib/logger"

const YOUTUBE_VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/
const YOUTUBE_HOSTS = new Set([
	"youtube.com",
	"www.youtube.com",
	"m.youtube.com",
	"music.youtube.com",
	"youtube-nocookie.com",
	"www.youtube-nocookie.com",
])

function extractYouTubeVideoId(rawUrl) {
	let parsedUrl
	try {
		parsedUrl = new URL(rawUrl)
	} catch {
		return null
	}

	if (parsedUrl.protocol !== "https:" && parsedUrl.protocol !== "http:") {
		return null
	}

	const hostname = parsedUrl.hostname.toLowerCase()
	const pathSegments = parsedUrl.pathname.split("/").filter(Boolean)
	let candidateId = null

	if (hostname === "youtu.be" || hostname === "www.youtu.be") {
		candidateId = pathSegments[0] ?? null
	} else if (YOUTUBE_HOSTS.has(hostname)) {
		if (parsedUrl.pathname === "/watch") {
			candidateId = parsedUrl.searchParams.get("v")
		} else if (pathSegments.length >= 2 && ["embed", "v", "shorts", "live"].includes(pathSegments[0])) {
			candidateId = pathSegments[1]
		}
	}

	if (!candidateId || !YOUTUBE_VIDEO_ID_PATTERN.test(candidateId)) {
		return null
	}
	return candidateId
}

export function YouTubeDialog({ open, onOpenChange, onVideoAdded }) {
	const [youtubeUrl, setYoutubeUrl] = useState("")
	const [isAddingVideo, setIsAddingVideo] = useState(false)

	const trimmedUrl = youtubeUrl.trim()
	const isValidUrl = Boolean(extractYouTubeVideoId(trimmedUrl))

	const handleOpenChange = (nextOpen) => {
		if (!nextOpen) handleClose()
	}

	const handleClose = () => {
		if (isAddingVideo) return
		setYoutubeUrl("")
		onOpenChange(false)
	}

	const handleYoutubeAdd = async () => {
		if (!isValidUrl || isAddingVideo) return

		setIsAddingVideo(true)
		try {
			const response = await createVideo(trimmedUrl)

			// Reset and close
			setYoutubeUrl("")
			onOpenChange(false)

			if (onVideoAdded) onVideoAdded(response)
		} catch (error) {
			logger.error("Failed to add YouTube video", error)
		} finally {
			setIsAddingVideo(false)
		}
	}

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[560px] gap-5">
				<motion.div
					aria-busy={isAddingVideo}
					initial={{ opacity: 0, y: 8 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -8 }}
					transition={{ duration: 0.18 }}
					className="space-y-5"
				>
					<DialogHeader className="space-y-2">
						<div className="flex items-center gap-3">
							<div className="rounded-lg bg-linear-to-br from-video/90 to-video p-2.5">
								<Youtube className="size-5 text-video-text" />
							</div>
							<DialogTitle className="text-2xl">Add a YouTube Video</DialogTitle>
						</div>
					</DialogHeader>

					<div className="space-y-2">
						<Label htmlFor="youtube-url" className="text-base">
							YouTube URL
						</Label>
						<Input
							id="youtube-url"
							type="url"
							value={youtubeUrl}
							onChange={(e) => setYoutubeUrl(e.target.value)}
							placeholder="https://www.youtube.com/watch?v=..."
							autoFocus
							autoCapitalize="none"
							autoCorrect="off"
							spellCheck={false}
							disabled={isAddingVideo}
							className="focus:outline-none focus:ring-2 focus:ring-video/20 focus:border-video focus-visible:ring-video focus-visible:ring-offset-2"
						/>
						<p className="text-xs text-muted-foreground">Paste any YouTube video link.</p>
					</div>

					<div className="flex justify-end gap-2.5 pt-2.5">
						<Button type="button" variant="outline" onClick={handleClose} disabled={isAddingVideo}>
							Cancel
						</Button>
						<Button
							type="button"
							onClick={handleYoutubeAdd}
							disabled={!isValidUrl || isAddingVideo}
							className="min-w-[140px] bg-video text-video-text hover:bg-video-accent"
						>
							{isAddingVideo ? (
								<div className="flex items-center gap-2">
									<Loader2 className="size-4  animate-spin" />
									<span>Adding…</span>
								</div>
							) : (
								<div className="flex items-center gap-2">
									<Youtube className="size-4 " />
									<span>Add Video</span>
								</div>
							)}
						</Button>
					</div>
				</motion.div>
			</DialogContent>
		</Dialog>
	)
}
