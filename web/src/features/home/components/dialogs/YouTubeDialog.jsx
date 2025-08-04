import { useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetFooter,
	SheetHeader,
	SheetTitle,
} from "@/components/sheet";
import { useToast } from "@/hooks/use-toast";
import { createVideo } from "@/services/videosService";

export function YouTubeDialog({ open, onOpenChange, onVideoAdded }) {
	const { toast } = useToast();
	const [youtubeUrl, setYoutubeUrl] = useState("");
	const [isAddingVideo, setIsAddingVideo] = useState(false);

	const handleYoutubeAdd = async () => {
		if (
			!youtubeUrl.trim() ||
			(!youtubeUrl.includes("youtube.com") && !youtubeUrl.includes("youtu.be"))
		) {
			toast({
				title: "Invalid URL",
				description: "Please enter a valid YouTube URL",
				variant: "destructive",
			});
			return;
		}

		if (isAddingVideo) return; // Prevent duplicate submissions

		setIsAddingVideo(true);
		try {
			const response = await createVideo(youtubeUrl);

			toast({
				title: response.alreadyExists ? "Video Found!" : "Video Added!",
				description: response.alreadyExists
					? `"${response.title}" was already in your library.`
					: `"${response.title}" has been added to your library.`,
			});

			// Reset form and close dialog
			setYoutubeUrl("");
			onOpenChange(false);

			// Notify parent
			if (onVideoAdded) {
				onVideoAdded(response);
			}
		} catch (error) {
			console.error("Failed to add video:", error);

			let errorMessage = "Failed to add video. Please try again.";
			if (error.message?.includes("503")) {
				errorMessage =
					"YouTube service is temporarily unavailable. Please try again in a few moments.";
			} else if (error.message?.includes("Invalid YouTube URL")) {
				errorMessage = "The URL you entered is not a valid YouTube video URL.";
			}

			toast({
				title: "Error",
				description: errorMessage,
				variant: "destructive",
			});
		} finally {
			setIsAddingVideo(false);
		}
	};

	const handleClose = () => {
		if (!isAddingVideo) {
			setYoutubeUrl("");
			onOpenChange(false);
		}
	};

	return (
		<Sheet open={open} onOpenChange={handleClose}>
			<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
				{isAddingVideo && (
					<div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg">
						<div className="flex flex-col items-center gap-4">
							<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-video" />
							<p className="text-lg font-medium">Adding your video...</p>
						</div>
					</div>
				)}
				<SheetHeader>
					<SheetTitle>Add a YouTube Video</SheetTitle>
					<SheetDescription>
						Paste a YouTube URL to start learning from it.
					</SheetDescription>
				</SheetHeader>
				<div className="py-4">
					<div className="grid gap-2">
						<Label htmlFor="youtube-url">YouTube URL</Label>
						<Input
							id="youtube-url"
							value={youtubeUrl}
							onChange={(e) => setYoutubeUrl(e.target.value)}
							placeholder="https://www.youtube.com/watch?v=..."
						/>
					</div>
				</div>
				<SheetFooter>
					<Button variant="outline" onClick={handleClose}>
						Cancel
					</Button>
					<Button onClick={handleYoutubeAdd} disabled={!youtubeUrl.trim()}>
						Add Video
					</Button>
				</SheetFooter>
			</SheetContent>
		</Sheet>
	);
}
