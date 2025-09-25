import { BookUploadDialog } from "./BookUploadDialog"
import { YouTubeDialog } from "./YouTubeDialog"

export function DialogsContainer({ dialogs, onBookUploaded, onVideoAdded }) {
	return (
		<>
			<BookUploadDialog
				open={dialogs.showUploadDialog}
				onOpenChange={dialogs.setShowUploadDialog}
				onBookUploaded={onBookUploaded}
			/>

			<YouTubeDialog
				open={dialogs.showYoutubeDialog}
				onOpenChange={dialogs.setShowYoutubeDialog}
				onVideoAdded={onVideoAdded}
			/>
		</>
	)
}
