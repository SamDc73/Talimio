import { useState } from "react"

export const useDialogStates = () => {
	const [showUploadDialog, setShowUploadDialog] = useState(false)
	const [showYoutubeDialog, setShowYoutubeDialog] = useState(false)
	const [showFlashcardDialog, setShowFlashcardDialog] = useState(false)
	const [showRoadmapModal, setShowRoadmapModal] = useState(false)
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isExtractingMetadata, setIsExtractingMetadata] = useState(false)
	const [isUploadingBook, setIsUploadingBook] = useState(false)
	const [youtubeUrl, setYoutubeUrl] = useState("")
	const [isAddingVideo, setIsAddingVideo] = useState(false)
	const [newDeckTitle, setNewDeckTitle] = useState("")
	const [newDeckDescription, setNewDeckDescription] = useState("")
	const [newCards, setNewCards] = useState("")

	const resetUploadDialog = () => {
		setShowUploadDialog(false)
		setSelectedFile(null)
		setBookTitle("")
		setBookAuthor("")
		setIsExtractingMetadata(false)
	}

	const resetYoutubeDialog = () => {
		setShowYoutubeDialog(false)
		setYoutubeUrl("")
	}

	const resetFlashcardDialog = () => {
		setShowFlashcardDialog(false)
		setNewDeckTitle("")
		setNewDeckDescription("")
		setNewCards("")
	}

	return {
		// Upload dialog states
		showUploadDialog,
		setShowUploadDialog,
		selectedFile,
		setSelectedFile,
		bookTitle,
		setBookTitle,
		bookAuthor,
		setBookAuthor,
		isExtractingMetadata,
		setIsExtractingMetadata,
		isUploadingBook,
		setIsUploadingBook,
		resetUploadDialog,

		// YouTube dialog states
		showYoutubeDialog,
		setShowYoutubeDialog,
		youtubeUrl,
		setYoutubeUrl,
		isAddingVideo,
		setIsAddingVideo,
		resetYoutubeDialog,

		// Flashcard dialog states
		showFlashcardDialog,
		setShowFlashcardDialog,
		newDeckTitle,
		setNewDeckTitle,
		newDeckDescription,
		setNewDeckDescription,
		newCards,
		setNewCards,
		resetFlashcardDialog,

		// Roadmap modal states
		showRoadmapModal,
		setShowRoadmapModal,
	}
}
