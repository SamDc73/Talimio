import { motion } from "framer-motion"
import { Loader2, Youtube } from "lucide-react"
import { useState } from "react"

import { createVideo } from "@/api/videosApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"

export function YouTubeDialog({ open, onOpenChange, onVideoAdded }) {
	const [youtubeUrl, setYoutubeUrl] = useState("")
	const [isAddingVideo, setIsAddingVideo] = useState(false)

	const trimmedUrl = youtubeUrl.trim()
	const isValidUrl = Boolean(trimmedUrl) && (trimmedUrl.includes("youtube.com") || trimmedUrl.includes("youtu.be"))

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
			const response = await createVideo(youtubeUrl)

			// Reset and close
			setYoutubeUrl("")
			onOpenChange(false)

			if (onVideoAdded) onVideoAdded(response)
		} catch (_error) {
			// Intentionally quiet – parent surfaces toast if needed
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
							<div className="rounded-lg bg-gradient-to-br from-video/90 to-video p-2.5">
								<Youtube className="h-5 w-5 text-white" />
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
							className="min-w-[140px] bg-video hover:bg-video-accent text-white"
						>
							{isAddingVideo ? (
								<div className="flex items-center gap-2">
									<Loader2 className="h-4 w-4 animate-spin" />
									<span>Adding…</span>
								</div>
							) : (
								<div className="flex items-center gap-2">
									<Youtube className="h-4 w-4" />
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
