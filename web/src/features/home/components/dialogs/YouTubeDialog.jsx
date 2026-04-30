import { motion } from "framer-motion"
import { Loader2 } from "lucide-react"
import { useRef, useState } from "react"

import { createVideo } from "@/api/videosApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent } from "@/components/Dialog"
import { YouTubeMark } from "@/components/YouTubeMark"
import { DialogIconHeader } from "@/features/home/components/dialogs/DialogIconHeader"
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
const YOUTUBE_URL_FIELDSET_CLASS_NAME =
	"relative flex flex-col rounded-lg border border-border/70 bg-background/95 shadow-sm transition-all duration-200 hover:border-muted-foreground/30 focus-within:border-(--color-video) focus-within:ring-4 focus-within:ring-(--color-video)/10"

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
	const urlInputRef = useRef(null)

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

	const handleOpenAutoFocus = (event) => {
		event.preventDefault()
		urlInputRef.current?.focus()
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
			<DialogContent className="gap-lg sm:max-w-container-lg" onOpenAutoFocus={handleOpenAutoFocus}>
				<motion.div
					aria-busy={isAddingVideo}
					initial={{ opacity: 0, y: 8 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -8 }}
					transition={{ duration: 0.18 }}
					className="space-y-lg"
				>
					<DialogIconHeader title="Add a YouTube Video" icon={YouTubeMark} tone="video" wideLogo />

					<fieldset className={YOUTUBE_URL_FIELDSET_CLASS_NAME}>
						<input
							ref={urlInputRef}
							type="url"
							aria-label="YouTube video URL"
							value={youtubeUrl}
							onChange={(e) => setYoutubeUrl(e.target.value)}
							placeholder="https://www.youtube.com/watch?v=..."
							autoCapitalize="none"
							autoCorrect="off"
							spellCheck={false}
							disabled={isAddingVideo}
							className="w-full bg-transparent p-sm  subheading placeholder:text-muted-foreground/45 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
						/>
					</fieldset>

					<div className="flex justify-end gap-xs pt-md">
						<Button type="button" variant="outline" onClick={handleClose} disabled={isAddingVideo}>
							Cancel
						</Button>
						<Button
							type="button"
							onClick={handleYoutubeAdd}
							disabled={!isValidUrl || isAddingVideo}
							className="min-w-3xl bg-video text-video-text hover:bg-video-accent"
						>
							{isAddingVideo ? (
								<div className="flex items-center gap-2xs">
									<Loader2 className="size-md animate-spin" />
									<span>Adding…</span>
								</div>
							) : (
								"Add Video"
							)}
						</Button>
					</div>
				</motion.div>
			</DialogContent>
		</Dialog>
	)
}
