import { motion } from "framer-motion"
import { BookOpen, Loader2, Upload } from "lucide-react"
import { useRef, useState } from "react"

import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"

export function BookUploadDialog({ open, onOpenChange, onBookUploaded }) {
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isUploadingBook, setIsUploadingBook] = useState(false)
	const [dragActive, setDragActive] = useState(false)
	const fileInputRef = useRef(null)

	const handleOpenChange = (nextOpen) => {
		if (!nextOpen) handleClose()
	}

	const handleClose = () => {
		if (isUploadingBook) return
		setSelectedFile(null)
		setBookTitle("")
		setBookAuthor("")
		onOpenChange(false)
	}

	const processFile = (file) => {
		if (!file) return
		const lower = file.name.toLowerCase()
		if (
			!(
				lower.endsWith(".pdf") ||
				lower.endsWith(".epub") ||
				file.type === "application/pdf" ||
				file.type === "application/epub+zip"
			)
		) {
			return
		}
		setSelectedFile(file)
		const filename = file.name.replace(/\.(pdf|epub)$/i, "")
		setBookTitle(filename)
	}

	const handleDrag = (e) => {
		e.preventDefault()
		e.stopPropagation()
		if (e.type === "dragenter" || e.type === "dragover") {
			setDragActive(true)
		} else if (e.type === "dragleave") {
			setDragActive(false)
		}
	}

	const handleDrop = (e) => {
		e.preventDefault()
		e.stopPropagation()
		setDragActive(false)
		if (isUploadingBook) return
		const file = e.dataTransfer?.files?.[0]
		if (file) {
			processFile(file)
		}
	}

	const handleFileInputClick = () => {
		if (isUploadingBook) return
		fileInputRef.current?.click()
	}

	const handleFileInputChange = (e) => {
		const file = e.target.files?.[0]
		if (file) {
			processFile(file)
		}
		try {
			e.target.value = ""
		} catch (_e) {}
	}

	const handleUpload = async () => {
		if (!selectedFile || !bookTitle.trim() || isUploadingBook) return

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
				} else {
					throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
				}
				return
			}

			const newBook = await response.json()

			// Reset and close
			setSelectedFile(null)
			setBookTitle("")
			setBookAuthor("")
			onOpenChange(false)
			if (onBookUploaded) onBookUploaded(newBook)
		} catch (_error) {
			// Intentionally quiet – parent surfaces toast if needed
		} finally {
			setIsUploadingBook(false)
		}
	}

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[580px] gap-6">
				<div className="relative">
					{isUploadingBook && (
						<div className="absolute inset-0 z-50 flex items-center justify-center rounded-lg bg-background/75 backdrop-blur-sm">
							<div className="flex items-center gap-3 text-sm">
								<Loader2 className="h-5 w-5 animate-spin text-book" />
								<span className="font-medium">Uploading book…</span>
							</div>
						</div>
					)}

					<motion.div
						aria-busy={isUploadingBook}
						initial={{ opacity: 0, y: 8 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -8 }}
						transition={{ duration: 0.18 }}
						className="space-y-6"
					>
						<DialogHeader className="space-y-3">
							<div className="flex items-center gap-3">
								<div className="rounded-lg bg-gradient-to-br from-book/90 to-book p-2.5">
									<BookOpen className="h-5 w-5 text-white" />
								</div>
								<DialogTitle className="text-2xl">Upload Book</DialogTitle>
							</div>
						</DialogHeader>

						<div className="space-y-4">
							<div className="space-y-2">
								<Label htmlFor="book-file-input">Book File</Label>
								<button
									id="book-file"
									type="button"
									className={`w-full rounded-lg border border-dashed ${
										dragActive ? "border-book bg-book/10" : "border-border"
									} p-6 text-center transition-colors hover:bg-muted/60`}
									onDragEnter={handleDrag}
									onDragOver={handleDrag}
									onDragLeave={handleDrag}
									onDrop={handleDrop}
									onClick={handleFileInputClick}
									onKeyDown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											e.preventDefault()
											handleFileInputClick()
										}
									}}
								>
									<Upload className="mx-auto h-10 w-10 text-muted-foreground/70 mb-2" />
									<p className="text-sm font-medium text-foreground">
										{selectedFile ? "Replace file" : "Drag PDF/EPUB here"}
									</p>
									<p className="text-xs text-muted-foreground mt-1">or click to browse</p>
									{selectedFile && (
										<p className="mt-3 text-xs text-muted-foreground">
											Selected: <span className="font-medium text-foreground">{selectedFile.name}</span>
										</p>
									)}
									<input
										id="book-file-input"
										ref={fileInputRef}
										type="file"
										accept=".pdf,.epub,application/pdf,application/epub+zip"
										onChange={handleFileInputChange}
										className="hidden"
										disabled={isUploadingBook}
									/>
								</button>
							</div>

							{selectedFile && (
								<div className="space-y-2">
									<Label htmlFor="book-title">Title</Label>
									<Input
										id="book-title"
										value={bookTitle}
										onChange={(e) => setBookTitle(e.target.value)}
										placeholder="e.g. The Pragmatic Programmer"
										disabled={isUploadingBook}
									/>
								</div>
							)}

							{selectedFile && (
								<div className="space-y-2">
									<Label htmlFor="book-author">Author</Label>
									<Input
										id="book-author"
										value={bookAuthor}
										onChange={(e) => setBookAuthor(e.target.value)}
										placeholder="e.g. Andrew Hunt, David Thomas"
										disabled={isUploadingBook}
									/>
								</div>
							)}
						</div>

						<div className="flex justify-end gap-3 pt-2">
							<Button type="button" variant="outline" onClick={handleClose} disabled={isUploadingBook}>
								Cancel
							</Button>
							<Button
								type="button"
								onClick={handleUpload}
								disabled={!selectedFile || !bookTitle.trim() || isUploadingBook}
								className="min-w-[140px] bg-book hover:bg-book-accent text-white"
							>
								{isUploadingBook ? (
									<div className="flex items-center gap-2">
										<Loader2 className="h-4 w-4 animate-spin" />
										<span>Uploading…</span>
									</div>
								) : (
									<span>Upload</span>
								)}
							</Button>
						</div>
					</motion.div>
				</div>
			</DialogContent>
		</Dialog>
	)
}
