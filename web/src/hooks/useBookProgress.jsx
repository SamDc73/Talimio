import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { updateBookChapterStatus } from "../services/bookProgressService"
import { booksApi } from "../services/booksApi"
import useAppStore from "../stores/useAppStore"

const BookProgressContext = createContext(null)

export function BookProgressProvider({ children, bookId }) {
	const [chapterStatuses, setChapterStatuses] = useState({})
	const [bookProgress, setBookProgress] = useState({
		totalChapters: 0,
		completedChapters: 0,
		progressPercentage: 0,
	})
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)

	const fetchAllProgressData = useCallback(
		async (currentBookId) => {
			if (!currentBookId) {
				setChapterStatuses({})
				setBookProgress({
					totalChapters: 0,
					completedChapters: 0,
					progressPercentage: 0,
				})
				return
			}

			setIsLoading(true)
			setError(null)

			try {
				let book = useAppStore.getState().books.metadata[currentBookId]
				if (!book || !book.tableOfContents) {
					const data = await booksApi.getBook(currentBookId)
					useAppStore.getState().books.metadata[currentBookId] = data
					book = data
				}

				const chapterCompletion = useAppStore.getState().books.chapterCompletion[currentBookId] || {}

				const getAllChapters = (chapters) => {
					const allChapters = []
					for (const chapter of chapters) {
						allChapters.push(chapter)
						if (chapter.children && chapter.children.length > 0) {
							allChapters.push(...getAllChapters(chapter.children))
						}
					}
					return allChapters
				}

				const allChapters = getAllChapters(book.tableOfContents)

				const statusMap = {}
				for (const chapter of allChapters) {
					statusMap[chapter.id] = chapterCompletion[chapter.id] ? "completed" : "not_started"
				}
				setChapterStatuses(statusMap)

				const totalChapters = allChapters.length
				const completedChapters = allChapters.filter((chapter) => chapterCompletion[chapter.id]).length
				const progressPercentage = totalChapters > 0 ? Math.round((completedChapters / totalChapters) * 100) : 0

				setBookProgress({
					totalChapters,
					completedChapters,
					progressPercentage,
				})
			} catch (err) {
				setError(err)
				console.log("Error")
			} finally {
				setIsLoading(false)
			}
		},
		[]
	)

	useEffect(() => {
		fetchAllProgressData(bookId)
	}, [bookId, fetchAllProgressData])

	const toggleChapterCompletion = useCallback(
		async (chapterId) => {
			if (!bookId) return

			const originalChapterStatuses = { ...chapterStatuses }
			const originalBookProgress = { ...bookProgress }

			try {
				const currentStatus = chapterStatuses[chapterId] || "not_started"
				const newStatus = currentStatus === "completed" ? "not_started" : "completed"

				setChapterStatuses((prev) => ({
					...prev,
					[chapterId]: newStatus,
				}))

				const isCompleted = newStatus === "completed"
				useAppStore.getState().updateBookChapterStatus(bookId, chapterId, isCompleted)

				const completedDelta = newStatus === "completed" ? 1 : -1
				const newCompletedChapters = Math.max(0, bookProgress.completedChapters + completedDelta)
				const newPercentage = Math.round((newCompletedChapters / bookProgress.totalChapters) * 100)

				setBookProgress((prev) => ({
					...prev,
					completedChapters: newCompletedChapters,
					progressPercentage: newPercentage,
				}))

				const updatePromise = updateBookChapterStatus(bookId, chapterId, newStatus)

				updatePromise.catch((_err) => {
					setChapterStatuses(originalChapterStatuses)
					setBookProgress(originalBookProgress)
					console.log("Error updating chapter")
				})
			} catch (err) {
				setChapterStatuses(originalChapterStatuses)
				setBookProgress(originalBookProgress)
				console.log("Error updating chapter")
			}
		},
		[bookId, chapterStatuses, bookProgress]
	)

	const isChapterCompleted = useCallback(
		(chapterId) => {
			return chapterStatuses[chapterId] === "completed"
		},
		[chapterStatuses]
	)

	const value = {
		chapterStatuses,
		bookProgress,
		isLoading,
		error,
		toggleChapterCompletion,
		isChapterCompleted,
		fetchAllProgressData,
	}

	return <BookProgressContext.Provider value={value}>{children}</BookProgressContext.Provider>
}

export function useBookProgress() {
	const context = useContext(BookProgressContext)
	if (context === null) {
		throw new Error("useBookProgress must be used within a BookProgressProvider")
	}
	return context
}
