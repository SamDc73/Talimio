import { Button } from "@/components/Button"

export default function EmptyState({ onGenerateCourse, onUploadBook, onAddYoutube }) {
	return (
		<div className="col-span-full text-center py-12">
			<p className="text-gray-100-foreground">No content found matching your criteria.</p>
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
			</div>
		</div>
	)
}
