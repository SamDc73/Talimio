/**
 * DocumentUploader Component
 *
 * Provides a unified interface for uploading documents to courses:
 * - PDF file uploads with drag-and-drop
 * - URL document uploads
 * - Multiple document support
 * - Upload progress tracking
 * - Error handling and validation
 */

import { AlertCircle, CheckCircle2, FileText, Link2, Upload, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/button"
import { Card } from "@/components/card"
import { Input } from "@/components/input"
import { Label } from "@/components/label"

function DocumentUploader({
	onDocumentsChange,
	initialDocuments = [],
	maxFiles = 10,
	disabled = false,
	showPreview = true,
}) {
	const [documents, setDocuments] = useState(initialDocuments)
	const [dragActive, setDragActive] = useState(false)
	const [urlInput, setUrlInput] = useState("")
	const [urlTitle, setUrlTitle] = useState("")
	const [isExtractingTitle, setIsExtractingTitle] = useState(false)
	const [justAdded, setJustAdded] = useState(false)
	const fileInputRef = useRef(null)
	const documentsRef = useRef(null)

	// Auto-scroll to documents when they're added
	useEffect(() => {
		if (justAdded && documentsRef.current) {
			documentsRef.current.scrollIntoView({
				behavior: "smooth",
				block: "start",
			})
			setJustAdded(false)
		}
	}, [justAdded])

	// Notify parent of document changes
	const updateDocuments = useCallback(
		(newDocuments) => {
			const wasEmpty = documents.length === 0
			setDocuments(newDocuments)
			onDocumentsChange?.(newDocuments)

			// Trigger auto-scroll if documents were just added
			if (wasEmpty && newDocuments.length > 0) {
				setJustAdded(true)
			}
		},
		[onDocumentsChange, documents.length]
	)

	// Handle file selection
	const handleFiles = useCallback(
		(files) => {
			if (disabled) return

			const newDocuments = Array.from(files).map((file, index) => ({
				id: `file-${Date.now()}-${index}`,
				type: "pdf",
				file,
				title: file.name.replace(/\.[^/.]+$/, ""), // Remove extension
				size: file.size,
				status: "pending",
			}))

			const totalDocuments = documents.length + newDocuments.length
			if (totalDocuments > maxFiles) {
				alert(`Maximum ${maxFiles} documents allowed. Please remove some documents first.`)
				return
			}

			updateDocuments([...documents, ...newDocuments])
		},
		[documents, maxFiles, disabled, updateDocuments]
	)

	// Handle drag and drop
	const handleDrag = useCallback((e) => {
		e.preventDefault()
		e.stopPropagation()
		if (e.type === "dragenter" || e.type === "dragover") {
			setDragActive(true)
		} else if (e.type === "dragleave") {
			setDragActive(false)
		}
	}, [])

	const handleDrop = useCallback(
		(e) => {
			e.preventDefault()
			e.stopPropagation()
			setDragActive(false)

			if (disabled) return

			const files = Array.from(e.dataTransfer.files).filter(
				(file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
			)

			if (files.length === 0) {
				alert("Please drop only PDF files.")
				return
			}

			handleFiles(files)
		},
		[disabled, handleFiles]
	)

	// Handle file input click
	const handleFileInputClick = () => {
		if (!disabled) {
			fileInputRef.current?.click()
		}
	}

	const handleFileInputChange = (e) => {
		if (e.target.files?.length > 0) {
			handleFiles(e.target.files)
			e.target.value = "" // Reset input
		}
	}

	// Extract title from URL
	const extractTitle = async (url) => {
		setIsExtractingTitle(true)
		try {
			const formData = new FormData()
			formData.append("url", url)

			const response = await fetch("/api/v1/extract-title", {
				method: "POST",
				body: formData,
			})

			const data = await response.json()
			const title = data.title || "Untitled Document"
			setUrlTitle(title)
			return title
		} catch (_error) {
			const title = "Untitled Document"
			setUrlTitle(title)
			return title
		} finally {
			setIsExtractingTitle(false)
		}
	}

	// Handle URL input change
	const handleUrlInputChange = (e) => {
		const url = e.target.value
		setUrlInput(url)

		// Clear title when URL is cleared
		if (!url.trim()) {
			setUrlTitle("")
		}
	}

	// Handle URL document addition
	const handleAddUrl = async () => {
		if (!urlInput.trim() || disabled || isExtractingTitle) return

		try {
			new URL(urlInput) // Validate URL
		} catch {
			alert("Please enter a valid URL.")
			return
		}

		if (documents.length >= maxFiles) {
			alert(`Maximum ${maxFiles} documents allowed.`)
			return
		}

		// Extract title if not already done
		let finalTitle = urlTitle
		if (!finalTitle) {
			// Wait for title extraction to complete and get the returned title
			finalTitle = await extractTitle(urlInput.trim())
		}

		const newDocument = {
			id: `url-${Date.now()}`,
			type: "url",
			url: urlInput.trim(),
			title: finalTitle,
			status: "pending",
		}

		updateDocuments([...documents, newDocument])
		setUrlInput("")
		setUrlTitle("")
	}

	// Remove document
	const removeDocument = (documentId) => {
		if (disabled) return
		updateDocuments(documents.filter((doc) => doc.id !== documentId))
	}

	// Update document title
	const updateDocumentTitle = (documentId, newTitle) => {
		if (disabled) return
		updateDocuments(documents.map((doc) => (doc.id === documentId ? { ...doc, title: newTitle } : doc)))
	}

	// Format file size
	const formatFileSize = (bytes) => {
		if (bytes === 0) return "0 Bytes"
		const k = 1024
		const sizes = ["Bytes", "KB", "MB", "GB"]
		const i = Math.floor(Math.log(bytes) / Math.log(k))
		return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`
	}

	// Get status icon
	const getStatusIcon = (status) => {
		switch (status) {
			case "completed":
			case "embedded":
				return <CheckCircle2 className="w-4 h-4 text-green-500" />
			case "failed":
				return <AlertCircle className="w-4 h-4 text-red-500" />
			case "processing":
				return <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
			default:
				return <FileText className="w-4 h-4 text-gray-400" />
		}
	}

	return (
		<div className="space-y-4">
			{/* Document Preview List - Move to top when documents exist */}
			{showPreview && documents.length > 0 && (
				<Card
					ref={documentsRef}
					className="border-green-200/60 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/10 dark:to-emerald-900/10 shadow-sm"
				>
					<div className="p-5">
						<div className="flex items-center justify-between mb-4">
							<div className="flex items-center space-x-2">
								<div className="w-2 h-2 bg-green-500 rounded-full" />
								<span className="text-sm font-semibold text-green-900 dark:text-green-100">Ready to Upload</span>
								<span className="text-xs bg-green-100 dark:bg-green-800 text-green-700 dark:text-green-200 px-2 py-0.5 rounded-full font-medium">
									{documents.length}
								</span>
							</div>
							<div className="text-xs text-green-600/80 dark:text-green-400/80 font-medium">
								{(documents.reduce((acc, doc) => acc + (doc.size || 0), 0) / 1024 / 1024).toFixed(1)}
								MB total
							</div>
						</div>

						<div className="space-y-2">
							{documents.map((doc, index) => (
								<div
									key={doc.id}
									className="group flex items-center space-x-4 p-3 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-lg border border-white/50 dark:border-gray-700/50 hover:bg-white dark:hover:bg-gray-800 hover:shadow-sm transition-all duration-200"
									style={{ animationDelay: `${index * 50}ms` }}
								>
									<div className="flex-shrink-0 w-6 flex justify-center">{getStatusIcon(doc.status)}</div>

									<div className="flex-1 min-w-0">
										<Input
											type="text"
											value={doc.title}
											onChange={(e) => updateDocumentTitle(doc.id, e.target.value)}
											disabled={disabled}
											className="text-sm font-medium border-0 bg-transparent p-0 focus:ring-0 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 hover:bg-gray-50/50 dark:hover:bg-gray-700/50 rounded px-1 -mx-1 transition-colors"
											placeholder="Enter document title"
										/>

										<div className="flex items-center space-x-4 mt-1.5">
											<span className="inline-flex items-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
												{doc.type}
											</span>

											{doc.type === "pdf" && doc.size && (
												<span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">
													{formatFileSize(doc.size)}
												</span>
											)}

											{doc.type === "url" && (
												<span className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-48">{doc.url}</span>
											)}
										</div>
									</div>

									<Button
										type="button"
										variant="ghost"
										size="sm"
										onClick={() => removeDocument(doc.id)}
										disabled={disabled}
										className="flex-shrink-0 w-8 h-8 p-0 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-all duration-200"
									>
										<X className="w-4 h-4" />
									</Button>
								</div>
							))}
						</div>

						{documents.length >= maxFiles && (
							<div className="mt-3 p-2 bg-amber-100 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-700 dark:text-amber-300">
								Maximum documents reached ({maxFiles}). Remove some to add more.
							</div>
						)}
					</div>
				</Card>
			)}

			{/* File Upload Area - Compact when documents exist */}
			<Card
				className={`border-dashed ${dragActive ? "border-blue-500 bg-blue-50" : "border-gray-300"} ${documents.length > 0 ? "border-gray-200" : ""}`}
			>
				<section
					className={`${documents.length > 0 ? "p-4" : "p-6"} text-center transition-colors ${
						disabled ? "opacity-50" : "hover:bg-gray-50"
					}`}
					aria-label="File upload area"
					onDragEnter={handleDrag}
					onDragLeave={handleDrag}
					onDragOver={handleDrag}
					onDrop={handleDrop}
				>
					<Upload className={`mx-auto ${documents.length > 0 ? "h-8 w-8" : "h-12 w-12"} text-gray-400 mb-2`} />
					<p className={`${documents.length > 0 ? "text-base" : "text-lg"} font-medium text-gray-900 mb-2`}>
						{documents.length > 0 ? "Add More PDFs" : "Upload PDF Documents"}
					</p>
					{documents.length === 0 && (
						<p className="text-sm text-gray-600 mb-4">Drag and drop PDF files here, or click to browse</p>
					)}
					<Button
						type="button"
						variant="outline"
						disabled={disabled}
						size={documents.length > 0 ? "sm" : "default"}
						className="mx-auto"
						onClick={handleFileInputClick}
					>
						Choose Files
					</Button>

					<input
						ref={fileInputRef}
						type="file"
						multiple
						accept=".pdf,application/pdf"
						onChange={handleFileInputChange}
						className="hidden"
						disabled={disabled}
					/>
				</section>
			</Card>

			{/* URL Input - Compact when documents exist */}
			<Card className={documents.length > 0 ? "border-gray-200" : ""}>
				<div className={documents.length > 0 ? "p-3" : "p-4"}>
					<Label className={`${documents.length > 0 ? "text-xs" : "text-sm"} font-medium text-gray-900 mb-3 block`}>
						Add Article from URL
					</Label>
					<div className="space-y-3">
						<div className="space-y-2">
							<Input
								type="url"
								placeholder="https://example.com/article"
								value={urlInput}
								onChange={handleUrlInputChange}
								disabled={disabled}
								className="w-full"
								onBlur={() => {
									if (urlInput.trim() && !urlTitle) {
										extractTitle(urlInput.trim())
									}
								}}
							/>
							{urlTitle && (
								<div className="flex items-center space-x-2 p-2 bg-gray-50 dark:bg-gray-800 rounded">
									<FileText className="w-4 h-4 text-gray-500" />
									<span className="text-sm text-gray-700 dark:text-gray-300 flex-1 truncate">{urlTitle}</span>
								</div>
							)}
						</div>
						<Button
							type="button"
							onClick={handleAddUrl}
							disabled={disabled || !urlInput.trim() || isExtractingTitle}
							size="sm"
							className="w-full"
						>
							{isExtractingTitle ? (
								<>
									<div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
									Extracting Title...
								</>
							) : (
								<>
									<Link2 className="w-4 h-4 mr-2" />
									Add Article
								</>
							)}
						</Button>
						<p className="text-xs text-gray-500 dark:text-gray-400 text-center">
							Title will be automatically extracted from the webpage
						</p>
					</div>
				</div>
			</Card>
		</div>
	)
}

export default DocumentUploader
