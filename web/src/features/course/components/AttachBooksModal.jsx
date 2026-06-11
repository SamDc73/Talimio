/**
 * AttachBooksModal Component
 *
 * Library picker for attaching existing books to a course. Books are never
 * uploaded here — new files become books through the library or the course
 * creation dialog. Archived books are attachable and flagged as such.
 */

import { useQuery } from "@tanstack/react-query"
import { Archive, BookOpen, Check, Search } from "lucide-react"
import { useMemo, useState } from "react"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { api } from "@/lib/apiClient"

function buildBookListUrl(search) {
	const params = new URLSearchParams({
		content_type: "book",
		status: "all",
		page: "1",
		page_size: "100",
	})
	if (search?.trim()) {
		params.set("search", search.trim())
	}
	return `/content?${params.toString()}`
}

function AttachBooksModal({ isOpen, onClose, attachedBookIds, onAttach, isAttaching = false }) {
	const [search, setSearch] = useState("")
	const [selectedIds, setSelectedIds] = useState([])

	const { data, isLoading } = useQuery({
		queryKey: ["library-books", search],
		queryFn: ({ signal }) => api.get(buildBookListUrl(search), { signal }),
		enabled: isOpen,
	})

	const books = useMemo(() => data?.items ?? [], [data])
	const attachedSet = useMemo(() => new Set((attachedBookIds || []).map(String)), [attachedBookIds])

	const toggleBook = (bookId) => {
		setSelectedIds((previous) =>
			previous.includes(bookId) ? previous.filter((id) => id !== bookId) : [...previous, bookId]
		)
	}

	const handleAttach = async () => {
		if (selectedIds.length === 0) return
		await onAttach(selectedIds)
		setSelectedIds([])
		onClose()
	}

	const handleOpenChange = (open) => {
		if (!open) {
			setSelectedIds([])
			onClose()
		}
	}

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[520px]">
				<DialogHeader>
					<DialogTitle>Attach books</DialogTitle>
					<DialogDescription>
						Ground this course in books from your library. Attaching links the book — nothing is copied or re-uploaded.
					</DialogDescription>
				</DialogHeader>

				<div className="relative">
					<Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
					<Input
						value={search}
						onChange={(event) => setSearch(event.target.value)}
						placeholder="Search your library..."
						className="pl-9"
					/>
				</div>

				<div className="max-h-72 overflow-y-auto rounded-md border border-border">
					{isLoading && <p className="p-4 text-sm text-muted-foreground">Loading your library...</p>}
					{!isLoading && books.length === 0 && (
						<p className="p-4 text-sm text-muted-foreground">No books found. Upload books from your library first.</p>
					)}
					<ul className="divide-y divide-border">
						{books.map((book) => {
							const bookId = String(book.id)
							const alreadyAttached = attachedSet.has(bookId)
							const selected = selectedIds.includes(bookId)
							return (
								<li key={bookId}>
									<button
										type="button"
										onClick={() => !alreadyAttached && toggleBook(bookId)}
										disabled={alreadyAttached}
										className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors ${
											alreadyAttached ? "cursor-default opacity-50" : "hover:bg-muted/60"
										}`}
									>
										<span className="flex min-w-0 items-center gap-3">
											<BookOpen className="size-4 shrink-0 text-muted-foreground" />
											<span className="truncate text-sm text-foreground">{book.title}</span>
											{book.status === "archived" && (
												<span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
													<Archive className="size-3" />
													Archived
												</span>
											)}
										</span>
										{alreadyAttached ? (
											<span className="shrink-0 text-xs text-muted-foreground">Attached</span>
										) : (
											<span
												className={`flex size-5 shrink-0 items-center justify-center rounded border ${
													selected ? "border-primary bg-primary text-primary-foreground" : "border-border"
												}`}
											>
												{selected && <Check className="size-3.5" />}
											</span>
										)}
									</button>
								</li>
							)
						})}
					</ul>
				</div>

				<DialogFooter className="gap-2">
					<Button variant="outline" onClick={() => handleOpenChange(false)} className="flex-1">
						Cancel
					</Button>
					<Button onClick={handleAttach} disabled={selectedIds.length === 0 || isAttaching} className="flex-1">
						{isAttaching ? "Attaching..." : `Attach ${selectedIds.length || ""}`.trim()}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	)
}

export default AttachBooksModal
