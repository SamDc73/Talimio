import BookSidebar from "@/components/sidebar/BookSidebar"
import { useBookChaptersApi } from "@/features/book-viewer/hooks/useBookChaptersApi"
import { useBookProgress } from "@/features/book-viewer/hooks/useBookProgress"

export default function BookSidebarContainer(props) {
	const { bookId } = props
	const chaptersApi = useBookChaptersApi(bookId)
	const progressApi = useBookProgress(bookId)

	return <BookSidebar {...props} chaptersApi={chaptersApi} progressApi={progressApi} />
}
