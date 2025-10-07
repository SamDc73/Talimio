/**
 * Course Creation Modal - Enhanced for document uploads and prompt-based creation
 *
 * This modal supports three modes:
 * 1. AI-generated courses from prompts (existing functionality)
 * 2. Document-based course creation (existing functionality)
 * 3. RAG-enhanced course creation with multiple documents (new functionality)
 */

import { AlertCircle, BookOpen, FileText, Sparkles, Upload, X } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "../../components/button"
import { useCourseNavigation } from "../../utils/navigationUtils"
import { useCourseService } from "./api/courseApi"
import { useDocumentsService } from "./api/documentsApi"
import { DocumentStatusSummary } from "./components/DocumentStatusBadge"
import DocumentUploader from "./components/DocumentUploader"

function CourseCreationModal({
	isOpen,
	onClose,
	onSuccess,
	defaultPrompt = "",
	defaultMode = "prompt", // "prompt", "document", or "rag"
}) {
	const [_creationMode, _setCreationMode] = useState(defaultMode)
	const [_prompt, _setPrompt] = useState(defaultPrompt)
	const [_isGenerating, _setIsGenerating] = useState(false)
	const [_error, setError] = useState("")

	// Document upload states (legacy single document)
	const [_selectedFile, setSelectedFile] = useState(null)
	const [_courseTitle, setCourseTitle] = useState("")
	const [_courseDescription, setCourseDescription] = useState("")
	const [_isExtractingMetadata, setIsExtractingMetadata] = useState(false)

	// RAG documents states (new multi-document support)
	const [ragDocuments, _setRagDocuments] = useState([])
	const [ragCourseTitle, _setRagCourseTitle] = useState("")
	const [_ragCourseDescription, _setRagCourseDescription] = useState("")
	const [_isUploadingDocuments, setIsUploadingDocuments] = useState(false)

	const [newCourseData, _setNewCourseData] = useState(null)

	const courseService = useCourseService()
	const documentsService = useDocumentsService(newCourseData?.id)
	const { goToCoursePreview } = useCourseNavigation()

	useEffect(() => {
		if (!newCourseData) return

		const uploadAndFinish = async () => {
			try {
				const uploadResults = await documentsService.uploadMultipleDocuments(
					ragDocuments.map((doc, index) => ({ ...doc, index }))
				)

				if (uploadResults.errors.length > 0) {
				} else {
				}

				if (onSuccess) onSuccess(newCourseData)
				goToCoursePreview(newCourseData.id)
				onClose()
			} catch (err) {
				setError(err.message || "Failed to upload documents. Please try again.")
			} finally {
				setIsUploadingDocuments(false)
			}
		}

		if (ragDocuments.length > 0) {
			uploadAndFinish()
		} else {
			if (onSuccess) onSuccess(newCourseData)
			goToCoursePreview(newCourseData.id)
			onClose()
			setIsUploadingDocuments(false)
		}
	}, [newCourseData, documentsService, goToCoursePreview, onClose, onSuccess, ragDocuments])

	// Handle file selection and metadata extraction
	const _handleFileChange = async (e) => {
		const file = e.target.files?.[0]
		if (!file) return

		// Validate file type
		const allowedTypes = ["application/pdf", "application/epub+zip"]
		if (!allowedTypes.includes(file.type)) {
			setError("Please select a PDF or EPUB file")
			return
		}

		setSelectedFile(file)
		setIsExtractingMetadata(true)
		setError("")

		try {
			// Extract metadata from the document using course service
			const metadata = await courseService.extractDocumentMetadata(file)

			// Pre-populate fields with extracted metadata
			if (metadata.title) {
				setCourseTitle(metadata.title)
			}
			if (metadata.description || metadata.summary) {
				setCourseDescription(metadata.description || metadata.summary)
			}
		} catch (_error) {
			// If extraction fails, use filename as title
			const titleFromFilename = file.name.replace(/\.[^/.]+$/, "")
			setCourseTitle(titleFromFilename)
		} finally {
			setIsExtractingMetadata(false)
		}
	}

	// Handle RAG documents change
	const handleRagDocumentsChange = (documents) => {
		setRagDocuments(documents)

		// Auto-suggest course title from first document if not set
		if (!ragCourseTitle && documents.length > 0) {
			setRagCourseTitle(documents[0].title || "New Course")
		}
	}

	// Handle RAG-enhanced course creation
	const handleRagSubmit = async (e) => {
		e.preventDefault()

		if (ragDocuments.length === 0 || !ragCourseTitle.trim()) {
			setError("Please add at least one document and provide a course title")
			return
		}

		setIsUploadingDocuments(true)
		setError("")

		try {
			// Step 1: Create the course with RAG enabled
			const courseData = await courseService.createCourse({
				prompt: ragCourseDescription.trim() || `Create a course based on uploaded documents: ${ragCourseTitle}`,
				title: ragCourseTitle.trim(),
				description: ragCourseDescription.trim(),
				rag_enabled: true, // Auto-enable RAG when documents are present
			})

			if (!courseData?.id) {
				throw new Error("Failed to create course - no response data")
			}

			setNewCourseData(courseData)
		} catch (err) {
			setError(err.message || "Failed to create course with documents. Please try again.")
			setIsUploadingDocuments(false)
		}
	}

	// Handle prompt-based course creation
	const handlePromptSubmit = async (e) => {
		e.preventDefault()

		if (!prompt.trim()) {
			setError("Please enter a description of what you want to learn")
			return
		}

		setIsGenerating(true)
		setError("")

		try {
			const response = await courseService.createCourse({
				prompt: prompt.trim(),
			})

			if (response?.id) {
				if (onSuccess) onSuccess(response)
				goToCoursePreview(response.id)
				onClose()
			} else {
				throw new Error("Failed to create course - no response data")
			}
		} catch (err) {
			setError(err.message || "Failed to create course. Please try again.")
		} finally {
			setIsGenerating(false)
		}
	}

	// Handle document-based course creation
	const handleDocumentSubmit = async (e) => {
		e.preventDefault()

		if (!selectedFile || !courseTitle.trim()) {
			setError("Please select a file and provide a course title")
			return
		}

		setIsGenerating(true)
		setError("")

		try {
			const formData = new FormData()
			formData.append("file", selectedFile)
			formData.append("title", courseTitle.trim())
			formData.append("description", courseDescription.trim())

			const courseData = await courseService.createCourseFromDocument(formData)

			if (onSuccess) onSuccess(courseData)
			goToCoursePreview(courseData.id)
			onClose()
		} catch (err) {
			// Handle specific error cases
			if (err.message?.includes("already exists")) {
			} else {
				setError(err.message || "Failed to create course from document. Please try again.")
			}
		} finally {
			setIsGenerating(false)
		}
	}

	const handleClose = () => {
		if (!isGenerating && !isExtractingMetadata && !isUploadingDocuments) {
			// Reset all states
			setPrompt("")
			setSelectedFile(null)
			setCourseTitle("")
			setCourseDescription("")
			setRagDocuments([])
			setRagCourseTitle("")
			setRagCourseDescription("")
			setError("")
			setCreationMode(defaultMode)
			onClose()
		}
	}

	const isProcessing = isGenerating || isExtractingMetadata || isUploadingDocuments

	if (!isOpen) return null

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
			<div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
				{/* Header */}
				<div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
					<h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Create New Course</h2>
					<button
						type="button"
						onClick={handleClose}
						disabled={isProcessing}
						className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50"
					>
						<X className="h-6 w-6" />
					</button>
				</div>

				{/* Mode Selection */}
				<div className="p-6 border-b border-gray-200 dark:border-gray-700">
					<div className="grid grid-cols-3 gap-1 bg-gray-100 dark:bg-gray-700 p-1 rounded-lg">
						<button
							type="button"
							onClick={() => setCreationMode("prompt")}
							disabled={isProcessing}
							className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-md text-sm font-medium transition-colors disabled:opacity-50 ${
								creationMode === "prompt"
									? "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm"
									: "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
							}`}
						>
							<Sparkles className="h-4 w-4" />
							<span>AI Generation</span>
						</button>
						<button
							type="button"
							onClick={() => setCreationMode("document")}
							disabled={isProcessing}
							className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-md text-sm font-medium transition-colors disabled:opacity-50 ${
								creationMode === "document"
									? "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm"
									: "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
							}`}
						>
							<Upload className="h-4 w-4" />
							<span>Single Document</span>
						</button>
						<button
							type="button"
							onClick={() => setCreationMode("rag")}
							disabled={isProcessing}
							className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-md text-sm font-medium transition-colors disabled:opacity-50 ${
								creationMode === "rag"
									? "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm"
									: "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
							}`}
						>
							<BookOpen className="h-4 w-4" />
							<span>Multi-Document RAG</span>
						</button>
					</div>
				</div>

				{/* Content */}
				<div className="p-6">
					{creationMode === "prompt" ? (
						<form onSubmit={handlePromptSubmit}>
							<div className="mb-4">
								<label
									htmlFor="course-prompt"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									What would you like to learn?
								</label>
								<textarea
									id="course-prompt"
									value={prompt}
									onChange={(e) => setPrompt(e.target.value)}
									placeholder="Describe what you want to learn... (e.g., 'Learn React and build modern web applications')"
									disabled={isProcessing}
									className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 resize-none disabled:opacity-50"
									rows={4}
									maxLength={500}
									spellCheck="true"
								/>
								<div className="text-right text-xs text-gray-500 mt-1">{prompt.length}/500 characters</div>
							</div>
							<div className="mb-6 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
								<p className="text-sm text-blue-700 dark:text-blue-300">
									<strong>AI will create:</strong> A structured course with modules and lessons tailored to your
									learning goals. You'll be able to customize it before starting.
								</p>
							</div>
						</form>
					) : creationMode === "document" ? (
						<form onSubmit={handleDocumentSubmit}>
							<div className="mb-4">
								<label
									htmlFor="document-upload"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									Upload Document
								</label>
								<div className="flex items-center justify-center w-full">
									<label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:hover:border-gray-500">
										<div className="flex flex-col items-center justify-center pt-5 pb-6">
											{selectedFile ? (
												<>
													<FileText className="w-8 h-8 mb-2 text-blue-500" />
													<p className="text-sm text-gray-600 dark:text-gray-400">{selectedFile.name}</p>
													<p className="text-xs text-gray-500">({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)</p>
												</>
											) : (
												<>
													<Upload className="w-8 h-8 mb-2 text-gray-400" />
													<p className="text-sm text-gray-600 dark:text-gray-400">
														<span className="font-semibold">Click to upload</span> or drag and drop
													</p>
													<p className="text-xs text-gray-500">PDF or EPUB files only</p>
												</>
											)}
										</div>
										<input
											id="document-upload"
											type="file"
											onChange={handleFileChange}
											accept=".pdf,.epub"
											disabled={isProcessing}
											className="hidden"
										/>
									</label>
								</div>
							</div>
							<div className="mb-4">
								<label
									htmlFor="course-title"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									Course Title *
								</label>
								<input
									id="course-title"
									type="text"
									value={courseTitle}
									onChange={(e) => setCourseTitle(e.target.value)}
									placeholder="Enter course title..."
									disabled={isProcessing}
									className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 disabled:opacity-50"
									maxLength={200}
								/>
							</div>
							<div className="mb-4">
								<label
									htmlFor="course-description"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									Course Description
								</label>
								<textarea
									id="course-description"
									value={courseDescription}
									onChange={(e) => setCourseDescription(e.target.value)}
									placeholder="Brief description of the course content..."
									disabled={isProcessing}
									className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 resize-none disabled:opacity-50"
									rows={3}
									maxLength={500}
									spellCheck="true"
								/>
							</div>
							<div className="mb-6 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md">
								<p className="text-sm text-green-700 dark:text-green-300">
									<strong>Document processing:</strong> Your document will be analyzed to create a structured course
									with modules and lessons based on the content.
								</p>
							</div>
						</form>
					) : (
						<form onSubmit={handleRagSubmit}>
							<div className="mb-6">
								<label
									htmlFor="document-uploader"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3"
								>
									Course Documents
								</label>
								<DocumentUploader
									id="document-uploader"
									onDocumentsChange={handleRagDocumentsChange}
									initialDocuments={ragDocuments}
									maxFiles={10}
									disabled={isProcessing}
									showPreview={true}
								/>
								{ragDocuments.length > 0 && (
									<div className="mt-3">
										<DocumentStatusSummary documents={ragDocuments} />
									</div>
								)}
							</div>
							<div className="mb-4">
								<label
									htmlFor="rag-course-title"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									Course Title *
								</label>
								<input
									id="rag-course-title"
									type="text"
									value={ragCourseTitle}
									onChange={(e) => setRagCourseTitle(e.target.value)}
									placeholder="Enter course title..."
									disabled={isProcessing}
									className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 disabled:opacity-50"
									maxLength={200}
								/>
							</div>
							<div className="mb-4">
								<label
									htmlFor="rag-course-description"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
								>
									Course Description (Optional)
								</label>
								<textarea
									id="rag-course-description"
									value={ragCourseDescription}
									onChange={(e) => setRagCourseDescription(e.target.value)}
									placeholder="Describe what the course should focus on, or leave blank to auto-generate from documents..."
									disabled={isProcessing}
									className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 resize-none disabled:opacity-50"
									rows={3}
									maxLength={500}
									spellCheck="true"
								/>
								<div className="text-right text-xs text-gray-500 mt-1">
									{ragCourseDescription.length}/500 characters
								</div>
							</div>
							<div className="mb-6 p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-md">
								<p className="text-sm text-purple-700 dark:text-purple-300">
									<strong>RAG-Enhanced Course:</strong> Your documents will be processed and integrated into an
									AI-powered course that can answer questions and generate lessons based on your content. Documents will
									be automatically searchable during lessons and assistant conversations.
								</p>
							</div>
						</form>
					)}

					{isExtractingMetadata && (
						<div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md">
							<div className="flex items-center space-x-2">
								<div className="w-4 h-4 border-2 border-yellow-600 border-t-transparent rounded-full animate-spin" />
								<p className="text-sm text-yellow-700 dark:text-yellow-300">
									Analyzing document and extracting metadata...
								</p>
							</div>
						</div>
					)}

					{isUploadingDocuments && (
						<div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
							<div className="flex items-center space-x-2">
								<div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
								<p className="text-sm text-blue-700 dark:text-blue-300">Creating course and uploading documents...</p>
							</div>
						</div>
					)}

					{error && (
						<div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
							<div className="flex items-center space-x-2">
								<AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
								<p className="text-sm text-red-600 dark:text-red-400">{error}</p>
							</div>
						</div>
					)}

					<div className="flex justify-end space-x-3 pt-4">
						<Button type="button" variant="outline" onClick={handleClose} disabled={isProcessing}>
							Cancel
						</Button>
						<Button
							type="submit"
							onClick={
								creationMode === "prompt"
									? handlePromptSubmit
									: creationMode === "document"
										? handleDocumentSubmit
										: handleRagSubmit
							}
							disabled={
								isProcessing ||
								(creationMode === "prompt" && !prompt.trim()) ||
								(creationMode === "document" && (!selectedFile || !courseTitle.trim())) ||
								(creationMode === "rag" && (ragDocuments.length === 0 || !ragCourseTitle.trim()))
							}
							className="min-w-[120px]"
						>
							{isProcessing ? (
								<div className="flex items-center space-x-2">
									<div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
									<span>
										{isExtractingMetadata ? "Analyzing..." : isUploadingDocuments ? "Uploading..." : "Creating..."}
									</span>
								</div>
							) : (
								"Create Course"
							)}
						</Button>
					</div>
				</div>
			</div>
		</div>
	)
}

export default CourseCreationModal
