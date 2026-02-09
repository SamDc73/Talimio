import BookSidebar from "@/components/sidebar/BookSidebar"
import { useBookChaptersApi } from "@/features/book-viewer/hooks/use-book-chapters-api"
import { useBookProgress } from "@/features/book-viewer/hooks/use-book-progress"

export default function BookSidebarContainer(props) {
	const { bookId } = props
	const chaptersApi = useBookChaptersApi(bookId)
	const progressApi = useBookProgress(bookId)

	return <BookSidebar {...props} chaptersApi={chaptersApi} progressApi={progressApi} />
}
