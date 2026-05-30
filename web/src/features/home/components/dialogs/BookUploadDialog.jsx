import { motion } from "framer-motion"
import { BookOpen, Loader2, Upload } from "lucide-react"
import { useId, useRef, useState } from "react"

import { Button } from "@/components/Button"
import { Dialog, DialogContent } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { DialogIconHeader } from "@/features/home/components/dialogs/DialogIconHeader"
import { api } from "@/lib/apiClient"
import logger from "@/lib/logger"

function getBookContentType(file) {
	if (file.type) return file.type
	if (file.name.toLowerCase().endsWith(".epub")) return "application/epub+zip"
	return "application/pdf"
}

export function BookUploadDialog({ open, onOpenChange, onBookUploaded }) {
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isUploadingBook, setIsUploadingBook] = useState(false)
	const [dragActive, setDragActive] = useState(false)
	const fileInputRef = useRef(null)
	const fileInputId = useId()
	const fileButtonId = useId()

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
		} catch (error) {
			logger.error("Failed to reset file input", error)
		}
	}

	const handleUpload = async () => {
		if (!selectedFile || !bookTitle.trim() || isUploadingBook) return

		setIsUploadingBook(true)
		try {
			const contentType = getBookContentType(selectedFile)
			const uploadSession = await api.post("/upload-sessions", {
				filename: selectedFile.name,
				contentType,
				fileSize: selectedFile.size,
			})

			const response = await fetch(uploadSession.uploadUrl, {
				method: uploadSession.method || "PUT",
				headers: {
					...(uploadSession.headers || {}),
					"Content-Type": contentType,
				},
				body: selectedFile,
			})

			if (!response.ok) {
				const errorText = await response.text().catch(() => "")
				throw new Error(`Upload failed: ${response.status} ${errorText || response.statusText}`)
			}

			const newBook = await api.post("/books", {
				title: bookTitle,
				author: bookAuthor,
				tags: [],
				filePath: uploadSession.filePath,
				storageProvider: uploadSession.storageProvider,
				fileSize: selectedFile.size,
				processInBackground: true,
			})

			setSelectedFile(null)
			setBookTitle("")
			setBookAuthor("")
			onOpenChange(false)
			if (onBookUploaded) onBookUploaded(newBook)
		} catch (error) {
			logger.error("Failed to upload book", error)
		} finally {
			setIsUploadingBook(false)
		}
	}

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="gap-lg sm:max-w-container-lg">
				<div className="relative">
					{isUploadingBook && (
						<div className="absolute inset-0 z-50 flex items-center justify-center rounded-xs bg-background/75 backdrop-blur-sm">
							<div className="subheading flex items-center gap-xs">
								<Loader2 className="size-md animate-spin text-book" />
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
						className="space-y-lg"
					>
						<DialogIconHeader title="Upload Book" icon={BookOpen} tone="book" />

						<div className="space-y-md">
							<button
								id={fileButtonId}
								type="button"
								className={`w-full rounded-xs border border-dashed ${
									dragActive ? "border-book bg-book/10" : "border-border"
								} p-lg text-center transition-colors hover:bg-muted/60`}
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
								<Upload className="mx-auto mb-xs size-xl text-muted-foreground/70" />
								<p className="subheading-bold text-foreground">
									{selectedFile ? "Replace file" : "Drag PDF/EPUB here"}
								</p>
								<p className="caption mt-3xs text-muted-foreground">or click to browse</p>
								{selectedFile && (
									<p className="caption mt-xs text-muted-foreground">
										Selected: <span className="font-medium text-foreground">{selectedFile.name}</span>
									</p>
								)}
								<input
									id={fileInputId}
									ref={fileInputRef}
									type="file"
									accept=".pdf,.epub,application/pdf,application/epub+zip"
									onChange={handleFileInputChange}
									className="hidden"
									disabled={isUploadingBook}
								/>
							</button>

							{selectedFile && (
								<Input
									value={bookTitle}
									onChange={(e) => setBookTitle(e.target.value)}
									placeholder="Title (e.g. The Pragmatic Programmer)"
									disabled={isUploadingBook}
								/>
							)}

							{selectedFile && (
								<Input
									value={bookAuthor}
									onChange={(e) => setBookAuthor(e.target.value)}
									placeholder="Author (e.g. Andrew Hunt, David Thomas)"
									disabled={isUploadingBook}
								/>
							)}
						</div>

						<div className="flex justify-end gap-xs pt-md">
							<Button type="button" variant="outline" onClick={handleClose} disabled={isUploadingBook}>
								Cancel
							</Button>
							<Button
								type="button"
								onClick={handleUpload}
								disabled={!selectedFile || !bookTitle.trim() || isUploadingBook}
								className="min-w-3xl bg-book text-book-text hover:bg-book-accent"
							>
								{isUploadingBook ? (
									<div className="flex items-center gap-2xs">
										<Loader2 className="size-md animate-spin" />
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
