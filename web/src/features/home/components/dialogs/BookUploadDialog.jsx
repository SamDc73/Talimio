import { useState } from "react"

import { Button } from "@/components/button"
import { Input } from "@/components/input"
import { Label } from "@/components/label"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/sheet"
import { useToast } from "@/hooks/use-toast"

export function BookUploadDialog({ open, onOpenChange, onBookUploaded }) {
	const { toast } = useToast()
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isExtractingMetadata, setIsExtractingMetadata] = useState(false)
	const [isUploadingBook, setIsUploadingBook] = useState(false)

	const handleFileChange = async (e) => {
		const file = e.target.files?.[0]
		if (file) {
			setSelectedFile(file)
			setIsExtractingMetadata(true)

			// Extract metadata from the file
			try {
				const formData = new FormData()
				formData.append("file", file)

				const response = await fetch("/api/v1/books/extract-metadata", {
					method: "POST",
					body: formData,
				})

				if (!response.ok) {
					throw new Error(`HTTP error! status: ${response.status}`)
				}

				const metadata = await response.json()

				if (metadata.title) {
					setBookTitle(metadata.title)
				}
				if (metadata.author) {
					setBookAuthor(metadata.author)
				}
			} catch (_error) {
				toast({
					title: "Error extracting metadata",
					description: "Please enter the book details manually.",
					variant: "destructive",
				})
			} finally {
				setIsExtractingMetadata(false)
			}
		}
	}

	const handleUpload = async () => {
		if (!selectedFile || !bookTitle.trim() || !bookAuthor.trim()) return

		setIsUploadingBook(true)
		try {
			const formData = new FormData()
			formData.append("file", selectedFile)
			formData.append("title", bookTitle)
			formData.append("author", bookAuthor)
			formData.append("tags", JSON.stringify([]))

			const response = await fetch("/api/v1/books", {
				method: "POST",
				body: formData,
			})

			if (!response.ok) {
				const errorData = await response.json()
				if (response.status === 409) {
					// Duplicate file error
					toast({
						title: "Book Already Exists",
						description: errorData.detail || "This book is already in your library.",
						variant: "destructive",
					})
				} else {
					throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
				}
				return
			}

			const newBook = await response.json()

			toast({
				title: "Book Added!",
				description: `"${newBook.title}" has been added to your library.`,
			})

			// Reset form
			setSelectedFile(null)
			setBookTitle("")
			setBookAuthor("")

			// Close dialog and notify parent
			onOpenChange(false)
			if (onBookUploaded) {
				onBookUploaded(newBook)
			}
		} catch (error) {
			toast({
				title: "Upload Failed",
				description: error.message || "Something went wrong. Please try again.",
				variant: "destructive",
			})
		} finally {
			setIsUploadingBook(false)
		}
	}

	const handleClose = () => {
		if (!isUploadingBook) {
			setSelectedFile(null)
			setBookTitle("")
			setBookAuthor("")
			onOpenChange(false)
		}
	}

	return (
		<Sheet open={open} onOpenChange={handleClose}>
			<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
				{isUploadingBook && (
					<div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg">
						<div className="flex flex-col items-center gap-4">
							<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-book" />
							<p className="text-lg font-medium">Uploading your book...</p>
						</div>
					</div>
				)}
				<SheetHeader>
					<SheetTitle>Upload a Book</SheetTitle>
					<SheetDescription>Upload a PDF to start learning from it.</SheetDescription>
				</SheetHeader>
				<div className="py-4">
					<div className="grid gap-4">
						<div className="grid gap-2">
							<Label for="book-file">Book File</Label>
							<Input id="book-file" type="file" accept=".pdf" onChange={handleFileChange} />
						</div>
						{selectedFile && (
							<div className="grid gap-2">
								<Label for="book-title">Title</Label>
								<Input
									id="book-title"
									value={bookTitle}
									onChange={(e) => setBookTitle(e.target.value)}
									placeholder="e.g. The Hitchhiker's Guide to the Galaxy"
									disabled={isExtractingMetadata}
								/>
							</div>
						)}
						{selectedFile && (
							<div className="grid gap-2">
								<Label for="book-author">Author</Label>
								<Input
									id="book-author"
									value={bookAuthor}
									onChange={(e) => setBookAuthor(e.target.value)}
									placeholder="e.g. Douglas Adams"
									disabled={isExtractingMetadata}
								/>
							</div>
						)}
					</div>
				</div>
				<SheetFooter>
					<Button variant="outline" onClick={handleClose}>
						Cancel
					</Button>
					<Button onClick={handleUpload} disabled={!selectedFile || !bookTitle || !bookAuthor}>
						Upload
					</Button>
				</SheetFooter>
			</SheetContent>
		</Sheet>
	)
}
