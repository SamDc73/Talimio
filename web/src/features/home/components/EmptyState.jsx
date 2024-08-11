import { Button } from "@/components/button"

export default function EmptyState({ onGenerateCourse, onUploadBook, onAddYoutube, onCreateFlashcards }) {
	return (
		<div className="col-span-full text-center py-12">
			<p className="text-muted-foreground">No content found matching your criteria.</p>
			<div className="flex justify-center gap-4 mt-4 flex-wrap">
				<Button variant="outline" onClick={onGenerateCourse}>
					Generate a new course
				</Button>
				<Button variant="outline" onClick={onUploadBook}>
					Upload a new book
				</Button>
				<Button variant="outline" onClick={onAddYoutube}>
					Add YouTube video
				</Button>
				<Button variant="outline" onClick={onCreateFlashcards}>
					Create flashcards
				</Button>
			</div>
		</div>
	)
}
