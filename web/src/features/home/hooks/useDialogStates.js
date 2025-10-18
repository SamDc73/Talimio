import { useState } from "react"

export const useDialogStates = () => {
	const [showUploadDialog, setShowUploadDialog] = useState(false)
	const [showYoutubeDialog, setShowYoutubeDialog] = useState(false)
	const [showCourseModal, setShowCourseModal] = useState(false)
	const [selectedFile, setSelectedFile] = useState(null)
	const [bookTitle, setBookTitle] = useState("")
	const [bookAuthor, setBookAuthor] = useState("")
	const [isExtractingMetadata, setIsExtractingMetadata] = useState(false)
	const [isUploadingBook, setIsUploadingBook] = useState(false)
	const [youtubeUrl, setYoutubeUrl] = useState("")
	const [isAddingVideo, setIsAddingVideo] = useState(false)
	const [_newDeckTitle, _setNewDeckTitle] = useState("")
	const [_newDeckDescription, _setNewDeckDescription] = useState("")
	const [_newCards, _setNewCards] = useState("")

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

		// Course modal states
		showCourseModal,
		setShowCourseModal,
	}
}
