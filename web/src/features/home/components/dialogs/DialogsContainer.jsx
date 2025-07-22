import { BookUploadDialog } from "./BookUploadDialog";
import { FlashcardDialog } from "./FlashcardDialog";
import { YouTubeDialog } from "./YouTubeDialog";

export function DialogsContainer({
	dialogs,
	onBookUploaded,
	onVideoAdded,
	onDeckCreated,
}) {
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

			<FlashcardDialog
				open={dialogs.showFlashcardDialog}
				onOpenChange={dialogs.setShowFlashcardDialog}
				onDeckCreated={onDeckCreated}
			/>
		</>
	);
}
