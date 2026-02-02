import { AlertCircle, CheckCircle2, FileText, Link2, Upload, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { api } from "@/lib/apiClient"
import logger from "@/lib/logger"

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

	useEffect(() => {
		if (justAdded && documentsRef.current) {
			documentsRef.current.scrollIntoView({
				behavior: "smooth",
				block: "start",
			})
			setJustAdded(false)
		}
	}, [justAdded])

	const updateDocuments = useCallback(
		(newDocuments) => {
			const wasEmpty = documents.length === 0
			setDocuments(newDocuments)
			onDocumentsChange?.(newDocuments)

			if (wasEmpty && newDocuments.length > 0) {
				setJustAdded(true)
			}
		},
		[onDocumentsChange, documents.length]
	)

	const handleFiles = useCallback(
		(files) => {
			if (disabled) return

			const newDocuments = [...files].map((file, index) => ({
				id: `file-${Date.now()}-${index}`,
				type: "pdf",
				file,
				title: file.name.replace(/\.[^/.]+$/, ""),
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

			const files = [...e.dataTransfer.files].filter(
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

	const handleFileInputClick = () => {
		if (!disabled) {
			fileInputRef.current?.click()
		}
	}

	const handleFileInputChange = (e) => {
		if (e.target.files?.length > 0) {
			handleFiles(e.target.files)
			e.target.value = ""
		}
	}

	const extractTitle = async (url) => {
		setIsExtractingTitle(true)
		try {
			const formData = new FormData()
			formData.append("url", url)

			const data = await api.post("/extract-title", formData)
			const title = data.title || "Untitled Document"
			setUrlTitle(title)
			return title
		} catch (error) {
			logger.error("Failed to extract document title", error, { url })
			const title = "Untitled Document"
			setUrlTitle(title)
			return title
		} finally {
			setIsExtractingTitle(false)
		}
	}

	const handleUrlInputChange = (e) => {
		const url = e.target.value
		setUrlInput(url)

		if (!url.trim()) {
			setUrlTitle("")
		}
	}

	const handleAddUrl = async () => {
		if (!urlInput.trim() || disabled || isExtractingTitle) return

		try {
			new URL(urlInput)
		} catch {
			alert("Please enter a valid URL.")
			return
		}

		if (documents.length >= maxFiles) {
			alert(`Maximum ${maxFiles} documents allowed.`)
			return
		}

		let finalTitle = urlTitle
		if (!finalTitle) {
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

	const removeDocument = (documentId) => {
		if (disabled) return
		updateDocuments(documents.filter((doc) => doc.id !== documentId))
	}

	const updateDocumentTitle = (documentId, newTitle) => {
		if (disabled) return
		updateDocuments(documents.map((doc) => (doc.id === documentId ? { ...doc, title: newTitle } : doc)))
	}

	const formatFileSize = (bytes) => {
		if (bytes === 0) return "0 Bytes"
		const k = 1024
		const sizes = ["Bytes", "KB", "MB", "GB"]
		const i = Math.floor(Math.log(bytes) / Math.log(k))
		return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`
	}

	const getStatusIcon = (status) => {
		switch (status) {
			case "completed":
			case "embedded": {
				return <CheckCircle2 className="size-4  text-primary" />
			}
			case "failed": {
				return <AlertCircle className="size-4  text-destructive" />
			}
			case "processing": {
				return <div className="size-4  animate-spin rounded-full border-2 border-course border-t-transparent" />
			}
			default: {
				return <FileText className="size-4  text-muted-foreground" />
			}
		}
	}

	return (
		<div className="space-y-4">
			{showPreview && documents.length > 0 && (
				<Card
					ref={documentsRef}
					className="border-primary/30 bg-linear-to-r from-primary/10 to-primary/5 dark:from-primary/10 dark:to-primary/5 shadow-sm"
				>
					<div className="p-5">
						<div className="flex items-center justify-between mb-4">
							<div className="flex items-center space-x-2">
								<div className="size-2  bg-green-500 rounded-full" />
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
									className="group flex items-center space-x-4 p-3 bg-background/80 dark:bg-background/80 backdrop-blur-sm rounded-lg border border-border/40 dark:border-border/40 hover:bg-card dark:hover:bg-background/80 hover:shadow-sm transition-all duration-200"
									style={{ animationDelay: `${index * 50}ms` }}
								>
									<div className="shrink-0 w-6 flex justify-center">{getStatusIcon(doc.status)}</div>

									<div className="flex-1 min-w-0">
										<Input
											type="text"
											value={doc.title}
											onChange={(e) => updateDocumentTitle(doc.id, e.target.value)}
											disabled={disabled}
											className="text-sm font-medium border-0 bg-transparent p-0 focus:ring-0 text-foreground dark:text-foreground placeholder:text-muted-foreground/70 hover:bg-muted/60 dark:hover:bg-background/70 rounded-sm px-1 -mx-1 transition-colors"
											placeholder="Enter document title"
										/>

										<div className="flex items-center space-x-4 mt-1.5">
											<span className="inline-flex items-center text-xs font-medium text-muted-foreground dark:text-muted-foreground/70 uppercase tracking-wide">
												{doc.type}
											</span>

											{doc.type === "pdf" && doc.size > 0 && (
												<span className="text-xs text-muted-foreground dark:text-muted-foreground/70 bg-muted dark:bg-background/70 px-2 py-0.5 rounded-sm">
													{formatFileSize(doc.size)}
												</span>
											)}

											{doc.type === "url" && (
												<span className="text-xs text-muted-foreground dark:text-muted-foreground/70 truncate max-w-48">
													{doc.url}
												</span>
											)}
										</div>
									</div>

									<Button
										type="button"
										variant="ghost"
										size="sm"
										onClick={() => removeDocument(doc.id)}
										disabled={disabled}
										className="shrink-0 size-8  p-0 text-muted-foreground/70 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-all duration-200"
									>
										<X className="size-4 " />
									</Button>
								</div>
							))}
						</div>

						{documents.length >= maxFiles && (
							<div className="mt-3 p-2 bg-amber-100 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-sm text-xs text-amber-700 dark:text-amber-300">
								Maximum documents reached ({maxFiles}). Remove some to add more.
							</div>
						)}
					</div>
				</Card>
			)}

			<Card
				className={`border-dashed ${dragActive ? "border-course bg-course/10" : "border-border"} ${documents.length > 0 ? "border-border" : ""}`}
			>
				<section
					className={`${documents.length > 0 ? "p-4" : "p-6"} text-center transition-colors ${
						disabled ? "opacity-50" : "hover:bg-muted/60"
					}`}
					aria-label="File upload area"
					onDragEnter={handleDrag}
					onDragLeave={handleDrag}
					onDragOver={handleDrag}
					onDrop={handleDrop}
				>
					<Upload
						className={`mx-auto ${documents.length > 0 ? "size-8 " : "size-12 "} text-muted-foreground/70 mb-2`}
					/>
					<p className={`${documents.length > 0 ? "text-base" : "text-lg"} font-medium text-foreground mb-2`}>
						{documents.length > 0 ? "Add More PDFs" : "Upload PDF Documents"}
					</p>
					{documents.length === 0 && (
						<p className="text-sm text-muted-foreground mb-4">Drag and drop PDF files here, or click to browse</p>
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

			<Card className={documents.length > 0 ? "border-border" : ""}>
				<div className={documents.length > 0 ? "p-3" : "p-4"}>
					<Label className={`${documents.length > 0 ? "text-xs" : "text-sm"} font-medium text-foreground mb-3 block`}>
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
								<div className="flex items-center space-x-2 p-2 bg-muted/40 dark:bg-background rounded-sm">
									<FileText className="size-4  text-muted-foreground" />
									<span className="text-sm text-foreground dark:text-muted-foreground flex-1 truncate">{urlTitle}</span>
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
									<div className="size-4  border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
									Extracting Title...
								</>
							) : (
								<>
									<Link2 className="size-4  mr-2" />
									Add Article
								</>
							)}
						</Button>
						<p className="text-xs text-muted-foreground dark:text-muted-foreground/70 text-center">
							Title will be automatically extracted from the webpage
						</p>
					</div>
				</div>
			</Card>
		</div>
	)
}

export default DocumentUploader
