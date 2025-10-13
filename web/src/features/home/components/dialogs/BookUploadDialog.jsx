import { useState } from "react"

import { Button } from "@/components/Button"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/Sheet"

export function BookUploadDialog({ open, onOpenChange, onBookUploaded }) {
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isUploadingBook, setIsUploadingBook] = useState(false)

	const handleFileChange = (e) => {
		const file = e.target.files?.[0]
		if (file) {
			setSelectedFile(file)
			// Extract filename-based hints for title
			const filename = file.name.replace(/\.(pdf|epub)$/i, "")
			setBookTitle(filename)
		}
	}

	const handleUpload = async () => {
		if (!selectedFile || !bookTitle.trim()) return

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
				credentials: "include", // Include auth cookies
			})

			if (!response.ok) {
				const errorData = await response.json()
				if (response.status === 409) {
					// Duplicate file error
					console.log("Book Already Exists")
				} else {
					throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
				}
				return
			}

			const newBook = await response.json()

			console.log("Action completed")

			// Reset form
			setSelectedFile(null)
			setBookTitle("")
			setBookAuthor("")

			// Close dialog and notify parent
			onOpenChange(false)
			if (onBookUploaded) {
				onBookUploaded(newBook)
			}
		} catch (_error) {
			console.log("Upload Failed")
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
					<div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg">
						<div className="flex flex-col items-center gap-4">
							<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-book" />
							<p className="text-lg font-medium">Uploading your book...</p>
						</div>
					</div>
				)}
				<SheetHeader>
					<SheetTitle>Upload a Book</SheetTitle>
					<SheetDescription>Upload a PDF or EPUB to start learning from it.</SheetDescription>
				</SheetHeader>
				<div className="py-4">
					<div className="grid gap-4">
						<div className="grid gap-2">
							<Label htmlFor="book-file">Book File</Label>
							<Input id="book-file" type="file" accept=".pdf,.epub" onChange={handleFileChange} />
						</div>
						{selectedFile && (
							<div className="grid gap-2">
								<Label htmlFor="book-title">Title</Label>
								<Input
									id="book-title"
									value={bookTitle}
									onChange={(e) => setBookTitle(e.target.value)}
									placeholder="e.g. The Hitchhiker's Guide to the Galaxy"
								/>
							</div>
						)}
						{selectedFile && (
							<div className="grid gap-2">
								<Label htmlFor="book-author">Author</Label>
								<Input
									id="book-author"
									value={bookAuthor}
									onChange={(e) => setBookAuthor(e.target.value)}
									placeholder="e.g. Douglas Adams"
								/>
							</div>
						)}
					</div>
				</div>
				<SheetFooter>
					<Button variant="outline" onClick={handleClose}>
						Cancel
					</Button>
					<Button onClick={handleUpload} disabled={!selectedFile || !bookTitle}>
						Upload
					</Button>
				</SheetFooter>
			</SheetContent>
		</Sheet>
	)
}
