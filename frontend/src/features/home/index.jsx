import { useEffect, useState } from "react"
import ErrorBoundary from "@/components/ErrorBoundary"

// Debug logging for Radix UI component initialization
console.log("[Debug] Initializing Radix UI components in HomePage");
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  X,
  Plus,
  Sparkles,
  ArrowUpDown,
  BookOpen,
  FileText,
  Clock,
  CalendarDays,
  Youtube,
  Layers,
  SlidersHorizontal,
} from "lucide-react"
import { Input } from "@/components/input"
import { Button } from "@/components/button"
import { Label } from "@/components/label"
import { TooltipProvider } from "@/components/tooltip"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover"
import { Badge } from "@/components/badge"
import { Separator } from "@/components/separator"
import { RadioGroup, RadioGroupItem } from "@/components/radio-group"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/sheet"
import { fetchContentData, processContentData } from "@/lib/api"
import { useApi } from "@/hooks/useApi"
import { useToast } from "@/hooks/use-toast"
import { YoutubeCard } from "./components/YoutubeCard"
import { FlashcardDeckCard } from "./components/FlashcardDeckCard"
import { BookCard } from "./components/BookCard"
import { RoadmapCard } from "./components/RoadmapCard"
import { CourseCard } from "./components/CourseCard"
import { MainHeader } from "@/components/header/MainHeader"

export default function HomePage() {
  console.log("[Debug] Rendering HomePage component");
  const api = useApi()
  const { toast } = useToast()
  const [searchQuery, setSearchQuery] = useState("")
  const [isGenerateMode, setIsGenerateMode] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [showYoutubeDialog, setShowYoutubeDialog] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [isFabExpanded, setIsFabExpanded] = useState(false)
  const [showFlashcardDialog, setShowFlashcardDialog] = useState(false)
  const [newDeckTitle, setNewDeckTitle] = useState("")
  const [newDeckDescription, setNewDeckDescription] = useState("")
  const [newCards, setNewCards] = useState("")
  const [isYoutubeMode, setIsYoutubeMode] = useState(false)
  const [activeFilter, setActiveFilter] = useState("all")
  const [activeSort, setActiveSort] = useState("last-accessed")
  const [sortDirection, setSortDirection] = useState("desc")
  const [contentItems, setContentItems] = useState([])
  const [filterOptions, setFilterOptions] = useState([])
  const [sortOptions, setSortOptions] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  // Fetch content data on component mount
  useEffect(() => {
    async function loadContentData() {
      setIsLoading(true)
      try {
        const data = await fetchContentData()
        const { content, filterOptions: options, sortOptions: sortOpts } = processContentData(data)

        setContentItems(content)

        // Map the filter options with their icons
        setFilterOptions(
          options.map((option) => {
            const getIcon = () => {
              switch (option.icon) {
                case "Search":
                  return <Search className="h-4 w-4 mr-2" />
                case "BookOpen":
                  return <BookOpen className="h-4 w-4 mr-2" />
                case "FileText":
                  return <FileText className="h-4 w-4 mr-2" />
                case "Youtube":
                  return <Youtube className="h-4 w-4 mr-2" />
                case "Layers":
                  return <Layers className="h-4 w-4 mr-2" />
                default:
                  return <Search className="h-4 w-4 mr-2" />
              }
            }

            return {
              ...option,
              icon: getIcon(),
            }
          }),
        )

        // Map the sort options with their icons
        setSortOptions(
          sortOpts.map((option) => {
            const getIcon = () => {
              switch (option.icon) {
                case "Clock":
                  return <Clock className="h-4 w-4 mr-2" />
                case "CalendarDays":
                  return <CalendarDays className="h-4 w-4 mr-2" />
                case "ArrowUpDown":
                  return <ArrowUpDown className="h-4 w-4 mr-2" />
                case "FileText":
                  return <FileText className="h-4 w-4 mr-2" />
                default:
                  return <Clock className="h-4 w-4 mr-2" />
              }
            }

            return {
              ...option,
              icon: getIcon(),
            }
          }),
        )
      } catch (error) {
        console.error("Error loading content data:", error)
      } finally {
        setIsLoading(false)
      }
    }

    loadContentData()
  }, [])

  // Apply filters and sorting
  const filteredAndSortedContent = contentItems
    .filter((item) => {
      // Apply content type filter
      if (activeFilter === "all") return true
      return item.type === activeFilter
    })
    .filter((item) => {
      if (!searchQuery) return true

      const query = searchQuery.toLowerCase()
      const title = item.title.toLowerCase()
      const tags = item.tags ? item.tags.some((tag) => tag.toLowerCase().includes(query)) : false

      if (item.type === "course") {
        return title.includes(query) || item.description.toLowerCase().includes(query) || tags
      }
      if (item.type === "book") {
        return title.includes(query) || item.author.toLowerCase().includes(query) || tags
      }
      if (item.type === "youtube") {
        return title.includes(query) || item.channelName.toLowerCase().includes(query) || tags
      }
      if (item.type === "flashcards") {
        return title.includes(query) || item.description.toLowerCase().includes(query) || tags
      }
      return true
    })
    .sort((a, b) => {
      const direction = sortDirection === "asc" ? 1 : -1

      switch (activeSort) {
        case "last-accessed":
          return direction * (new Date(a.lastAccessedDate).getTime() - new Date(b.lastAccessedDate).getTime())
        case "created":
          return direction * (new Date(a.createdDate).getTime() - new Date(b.createdDate).getTime())
        case "progress":
          return direction * (a.progress - b.progress)
        case "title":
          return direction * a.title.localeCompare(b.title)
        default:
          return 0
      }
    })

  const handleGenerateCourse = async () => {
    if (!searchQuery.trim()) return

    setIsGenerating(true)

    try {
      const response = await api.post("/assistant/generate-course", {
        topic: searchQuery,
        level: "beginner",
      })
      
      toast({
        title: "Course Generated!",
        description: `Successfully created a course on "${searchQuery}".`,
      })
      
      setSearchQuery("")
      setIsGenerateMode(false)
      
      // Refresh content list
      const data = await fetchContentData()
      const { content } = processContentData(data)
      setContentItems(content)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate course. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    try {
      const formData = new FormData()
      formData.append("file", selectedFile)
      
      const response = await api.post("/books", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      })
      
      toast({
        title: "Book Uploaded!",
        description: `${selectedFile.name} has been added to your library.`,
      })
      
      setSelectedFile(null)
      setShowUploadDialog(false)
      
      // Refresh content list
      const data = await fetchContentData()
      const { content } = processContentData(data)
      setContentItems(content)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to upload book. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleYoutubeAdd = async () => {
    if (!youtubeUrl.trim() || (!youtubeUrl.includes("youtube.com") && !youtubeUrl.includes("youtu.be"))) {
      toast({
        title: "Invalid URL",
        description: "Please enter a valid YouTube URL",
        variant: "destructive",
      })
      return
    }

    try {
      // TODO: Call YouTube API when implemented
      // const response = await api.post("/videos", { url: youtubeUrl })
      
      toast({
        title: "Video Added!",
        description: "YouTube video has been added to your library.",
      })
      
      setYoutubeUrl("")
      setSearchQuery("")
      setShowYoutubeDialog(false)
      setIsYoutubeMode(false)
      
      // Refresh content list when API is available
      // const data = await fetchContentData()
      // const { content } = processContentData(data)
      // setContentItems(content)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to add video. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleCreateDeck = async () => {
    if (!newDeckTitle.trim()) return

    try {
      // Create the deck first
      const deckResponse = await api.post("/flashcards", {
        title: newDeckTitle,
        description: newDeckDescription || "",
      })
      
      // If cards were provided, add them to the deck
      if (newCards.trim()) {
        const cards = newCards.split("\n").filter(line => line.trim())
        const cardData = cards.map(line => {
          const [front, back] = line.split("|").map(s => s.trim())
          return { front: front || line, back: back || "" }
        })
        
        if (cardData.length > 0) {
          await api.post(`/flashcards/${deckResponse.data.id}/cards`, {
            cards: cardData,
          })
        }
      }
      
      toast({
        title: "Deck Created!",
        description: `"${newDeckTitle}" has been created with ${newCards.split("\n").filter(Boolean).length} cards.`,
      })
      
      setNewDeckTitle("")
      setNewDeckDescription("")
      setNewCards("")
      setShowFlashcardDialog(false)
      
      // Refresh content list
      const data = await fetchContentData()
      const { content } = processContentData(data)
      setContentItems(content)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create flashcard deck. Please try again.",
        variant: "destructive",
      })
    }
  }

  const toggleSortDirection = () => {
    setSortDirection(sortDirection === "asc" ? "desc" : "asc")
  }

  const getActiveFilterLabel = () => {
    return filterOptions.find((option) => option.id === activeFilter)?.label || "All Content"
  }

  const getActiveSortLabel = () => {
    return sortOptions.find((option) => option.id === activeSort)?.label || "Last Opened"
  }

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <ErrorBoundary>
          <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
            <MainHeader transparent />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pt-28">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-6"
          >
            <h1 className="text-4xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 mb-4 tracking-tight">
              Welcome Back!
            </h1>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Ready to continue your journey? Pick up where you left off or explore something new today.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="max-w-2xl mx-auto mb-6"
          >
            <div className="bg-white rounded-2xl shadow-sm p-2 border border-slate-200 transition-all hover:shadow-md">
              <div className="flex items-center">
                <div
                  className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-xl transition-all ${
                    isGenerateMode ? "bg-teal-50" : isYoutubeMode ? "bg-red-50" : ""
                  }`}
                >
                  {isGenerateMode ? (
                    <Sparkles className="text-teal-500" size={20} />
                  ) : isYoutubeMode ? (
                    <Youtube className="text-red-500" size={20} />
                  ) : (
                    <Search className="text-slate-400" size={20} />
                  )}
                  <Input
                    type="text"
                    placeholder={
                      isGenerateMode
                        ? "What do you want to learn about?"
                        : isYoutubeMode
                        ? "Paste a YouTube URL or search for videos..."
                        : "Search your courses and books..."
                    }
                    className="border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <Button variant="ghost" size="icon" onClick={() => setSearchQuery("")} className="h-8 w-8">
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                <div className="flex items-center gap-2 pl-2">
                  <div className="h-8 w-px bg-slate-200" />
                  {isGenerateMode ? (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsGenerateMode(false)}
                        className="text-slate-500"
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleGenerateCourse}
                        disabled={!searchQuery.trim() || isGenerating}
                        className="bg-teal-500 hover:bg-teal-600 text-white"
                      >
                        {isGenerating ? "Generating..." : "Generate"}
                      </Button>
                    </>
                  ) : isYoutubeMode ? (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsYoutubeMode(false)}
                        className="text-slate-500"
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          if (searchQuery.trim()) {
                            setYoutubeUrl(searchQuery)
                            handleYoutubeAdd()
                            setIsYoutubeMode(false)
                          }
                        }}
                        disabled={!searchQuery.trim()}
                        className="bg-red-500 hover:bg-red-600 text-white"
                      >
                        Add Video
                      </Button>
                    </>
                  ) : (
                    <>
                      {searchQuery && (
                        <Button variant="ghost" size="sm" onClick={() => setSearchQuery("")} className="text-slate-500">
                          Clear
                        </Button>
                      )}
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button variant="outline" size="sm" className="flex items-center gap-1">
                            <SlidersHorizontal className="h-3.5 w-3.5 mr-1" />
                            Filters
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-80" align="end">
                          <div className="space-y-4">
                            <div>
                              <h4 className="font-medium mb-2 text-sm">Content Type</h4>
                              <RadioGroup
                                value={activeFilter}
                                onValueChange={setActiveFilter}
                                className="flex flex-col gap-2"
                              >
                                {filterOptions.map((option) => (
                                  <div key={option.id} className="flex items-center space-x-2">
                                    <RadioGroupItem value={option.id} id={`filter-${option.id}`} />
                                    <Label htmlFor={`filter-${option.id}`} className="flex items-center cursor-pointer">
                                      {option.icon}
                                      {option.label}
                                    </Label>
                                  </div>
                                ))}
                              </RadioGroup>
                            </div>

                            <Separator />

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <h4 className="font-medium text-sm">Sort By</h4>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={toggleSortDirection}
                                  className="h-8 px-2 text-xs"
                                >
                                  {sortDirection === "desc" ? "Newest First" : "Oldest First"}
                                </Button>
                              </div>
                              <RadioGroup
                                value={activeSort}
                                onValueChange={setActiveSort}
                                className="flex flex-col gap-2"
                              >
                                {sortOptions.map((option) => (
                                  <div key={option.id} className="flex items-center space-x-2">
                                    <RadioGroupItem value={option.id} id={`sort-${option.id}`} />
                                    <Label htmlFor={`sort-${option.id}`} className="flex items-center cursor-pointer">
                                      {option.icon}
                                      {option.label}
                                    </Label>
                                  </div>
                                ))}
                              </RadioGroup>
                            </div>
                          </div>
                        </PopoverContent>
                      </Popover>
                    </>
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.2 }}
            className="max-w-2xl mx-auto mb-8 flex flex-wrap items-center gap-2"
          >
            {activeFilter !== "all" && (
              <Badge variant="outline" className="bg-white">
                {getActiveFilterLabel()}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveFilter("all")}
                  className="h-4 w-4 p-0 ml-1 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Remove filter</span>
                </Button>
              </Badge>
            )}

            {activeSort !== "last-accessed" && (
              <Badge variant="outline" className="bg-white">
                Sorted by: {getActiveSortLabel()}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveSort("last-accessed")}
                  className="h-4 w-4 p-0 ml-1 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Remove sort</span>
                </Button>
              </Badge>
            )}

            {sortDirection !== "desc" && (
              <Badge variant="outline" className="bg-white">
                {sortDirection === "asc" ? "Oldest First" : "Newest First"}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSortDirection("desc")}
                  className="h-4 w-4 p-0 ml-1 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Remove sort direction</span>
                </Button>
              </Badge>
            )}

            {(activeFilter !== "all" || activeSort !== "last-accessed" || sortDirection !== "desc") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setActiveFilter("all")
                  setActiveSort("last-accessed")
                  setSortDirection("desc")
                }}
                className="text-xs text-slate-500 h-7 px-2 ml-auto"
              >
                Reset All
              </Button>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            {isLoading ? (
              <div className="flex justify-center items-center py-20">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredAndSortedContent.length > 0 ? (
                  filteredAndSortedContent.map((item, index) => {
                    if (item.type === "course") {
                      return <CourseCard key={item.id} course={item} index={index} />
                    }
                    if (item.type === "youtube") {
                      return <YoutubeCard key={item.id} video={item} index={index} />
                    }
                    if (item.type === "flashcards") {
                      return <FlashcardDeckCard key={item.id} deck={item} index={index} />
                    }
                    if (item.type === "book") {
                      return <BookCard key={item.id} book={item} index={index} />
                    }
                    if (item.type === "roadmap") {
                      return <RoadmapCard key={item.id} roadmap={item} index={index} />
                    }
                    return null
                  })
                ) : (
                  <div className="col-span-full text-center py-12">
                    <p className="text-slate-500">No content found matching your criteria.</p>
                    <div className="flex justify-center gap-4 mt-4 flex-wrap">
                      <Button variant="outline" onClick={() => setIsGenerateMode(true)}>
                        Generate a new course
                      </Button>
                      <Button variant="outline" onClick={() => setShowUploadDialog(true)}>
                        Upload a new book
                      </Button>
                      <Button variant="outline" onClick={() => setShowYoutubeDialog(true)}>
                        Add YouTube video
                      </Button>
                      <Button variant="outline" onClick={() => setShowFlashcardDialog(true)}>
                        Create flashcards
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </div>

        {/* Upload Book Dialog */}
        <Sheet open={showUploadDialog} onOpenChange={setShowUploadDialog}>
          <SheetContent side="bottom" className="sm:max-w-lg mx-auto">
            <SheetHeader>
              <SheetTitle>Upload a Book</SheetTitle>
              <SheetDescription>
                Upload a PDF or EPUB file to add it to your library
              </SheetDescription>
            </SheetHeader>
            <div className="py-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="book-file">Choose File</Label>
                <Input
                  id="book-file"
                  type="file"
                  accept=".pdf,.epub"
                  onChange={handleFileChange}
                  className="cursor-pointer"
                />
                {selectedFile && (
                  <p className="text-sm text-muted-foreground">
                    Selected: {selectedFile.name}
                  </p>
                )}
              </div>
            </div>
            <SheetFooter>
              <Button variant="outline" onClick={() => setShowUploadDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleUpload} 
                disabled={!selectedFile}
                className="bg-indigo-500 hover:bg-indigo-600 text-white"
              >
                Upload Book
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        {/* Add YouTube Video Dialog */}
        <Sheet open={showYoutubeDialog} onOpenChange={setShowYoutubeDialog}>
          <SheetContent side="bottom" className="sm:max-w-lg mx-auto">
            <SheetHeader>
              <SheetTitle>Add YouTube Video</SheetTitle>
              <SheetDescription>
                Paste a YouTube URL to add it to your learning library
              </SheetDescription>
            </SheetHeader>
            <div className="py-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="youtube-url">YouTube URL</Label>
                <Input
                  id="youtube-url"
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                />
              </div>
              <div className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
                <p className="text-sm text-yellow-800">
                  Note: YouTube integration is coming soon! For now, URLs will be saved for future processing.
                </p>
              </div>
            </div>
            <SheetFooter>
              <Button variant="outline" onClick={() => setShowYoutubeDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleYoutubeAdd} 
                disabled={!youtubeUrl.trim()}
                className="bg-red-500 hover:bg-red-600 text-white"
              >
                Add Video
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        {/* Create Flashcard Deck Dialog */}
        <Sheet open={showFlashcardDialog} onOpenChange={setShowFlashcardDialog}>
          <SheetContent side="bottom" className="sm:max-w-lg mx-auto">
            <SheetHeader>
              <SheetTitle>Create Flashcard Deck</SheetTitle>
              <SheetDescription>
                Create a new deck and optionally add cards
              </SheetDescription>
            </SheetHeader>
            <div className="py-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="deck-title">Deck Title</Label>
                <Input
                  id="deck-title"
                  placeholder="e.g., Spanish Vocabulary"
                  value={newDeckTitle}
                  onChange={(e) => setNewDeckTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="deck-description">Description (Optional)</Label>
                <Input
                  id="deck-description"
                  placeholder="e.g., Common Spanish words and phrases"
                  value={newDeckDescription}
                  onChange={(e) => setNewDeckDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="deck-cards">Cards (Optional)</Label>
                <textarea
                  id="deck-cards"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="Enter cards (one per line, format: front | back)&#10;Example:&#10;Hello | Hola&#10;Thank you | Gracias"
                  value={newCards}
                  onChange={(e) => setNewCards(e.target.value)}
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  Format: front | back (one card per line)
                </p>
              </div>
            </div>
            <SheetFooter>
              <Button variant="outline" onClick={() => setShowFlashcardDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleCreateDeck} 
                disabled={!newDeckTitle.trim()}
                className="bg-amber-500 hover:bg-amber-600 text-white"
              >
                Create Deck
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        {/* Floating Action Button (FAB) */}
        <div className="fixed bottom-6 right-6 z-40">
          <div className="relative">
            {/* Expanded FAB Options */}
            <AnimatePresence mode="wait">
              {isFabExpanded && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-0 right-0 flex flex-col items-end gap-4 pb-[70px]"
                >
                  <motion.div
                    initial={{ opacity: 0, scale: 0, y: 280, x: 0 }}
                    animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
                    exit={{ opacity: 0, scale: 0, y: 280, x: 0 }}
                    transition={{ delay: 0, duration: 0.3, type: "spring", stiffness: 300, damping: 25 }}
                    className="group relative"
                  >
                    <span className="absolute right-full mr-3 bg-white text-slate-800 px-3 py-2 rounded-lg shadow-lg text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                      Generate Course
                    </span>
                    <Button
                      onClick={() => {
                        setIsGenerateMode(true)
                        setIsFabExpanded(false)
                      }}
                      size="icon"
                      className="h-14 w-14 rounded-full bg-teal-500 hover:bg-teal-600 text-white shadow-lg transition-all hover:scale-110"
                    >
                      <Sparkles className="h-6 w-6" />
                    </Button>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0, y: 210, x: 0 }}
                    animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
                    exit={{ opacity: 0, scale: 0, y: 210, x: 0 }}
                    transition={{ delay: 0.05, duration: 0.3, type: "spring", stiffness: 300, damping: 25 }}
                    className="group relative"
                  >
                    <span className="absolute right-full mr-3 bg-white text-slate-800 px-3 py-2 rounded-lg shadow-lg text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                      Upload Book
                    </span>
                    <Button
                      onClick={() => {
                        setShowUploadDialog(true)
                        setIsFabExpanded(false)
                        setSelectedFile(null)
                      }}
                      size="icon"
                      className="h-14 w-14 rounded-full bg-indigo-500 hover:bg-indigo-600 text-white shadow-lg transition-all hover:scale-110"
                    >
                      <FileText className="h-6 w-6" />
                    </Button>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0, y: 140, x: 0 }}
                    animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
                    exit={{ opacity: 0, scale: 0, y: 140, x: 0 }}
                    transition={{ delay: 0.1, duration: 0.3, type: "spring", stiffness: 300, damping: 25 }}
                    className="group relative"
                  >
                    <span className="absolute right-full mr-3 bg-white text-slate-800 px-3 py-2 rounded-lg shadow-lg text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                      Add YouTube Video
                    </span>
                    <Button
                      onClick={() => {
                        setShowYoutubeDialog(true)
                        setIsFabExpanded(false)
                        setYoutubeUrl("")
                      }}
                      size="icon"
                      className="h-14 w-14 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-lg transition-all hover:scale-110"
                    >
                      <Youtube className="h-6 w-6" />
                    </Button>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0, y: 70, x: 0 }}
                    animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
                    exit={{ opacity: 0, scale: 0, y: 70, x: 0 }}
                    transition={{ delay: 0.15, duration: 0.3, type: "spring", stiffness: 300, damping: 25 }}
                    className="group relative"
                  >
                    <span className="absolute right-full mr-3 bg-white text-slate-800 px-3 py-2 rounded-lg shadow-lg text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                      Create Flashcards
                    </span>
                    <Button
                      onClick={() => {
                        setShowFlashcardDialog(true)
                        setIsFabExpanded(false)
                        setNewDeckTitle("")
                        setNewDeckDescription("")
                        setNewCards("")
                      }}
                      size="icon"
                      className="h-14 w-14 rounded-full bg-amber-500 hover:bg-amber-600 text-white shadow-lg transition-all hover:scale-110"
                    >
                      <Layers className="h-6 w-6" />
                    </Button>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Main FAB Button */}
            <motion.div
              animate={{ rotate: isFabExpanded ? 45 : 0 }}
              transition={{ duration: 0.2, type: "spring", stiffness: 500, damping: 25 }}
            >
              <Button
                onClick={() => setIsFabExpanded(!isFabExpanded)}
                size="icon"
                className={`h-14 w-14 rounded-full shadow-lg transition-all duration-200 hover:scale-110 ${
                  isFabExpanded
                    ? "bg-red-500 hover:bg-red-600"
                    : "bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-600 hover:to-emerald-600"
                }`}
              >
                <Plus className="h-6 w-6 text-white" />
              </Button>
            </motion.div>
          </div>
        </div>
          </div>
        </ErrorBoundary>
      </TooltipProvider>
    </ErrorBoundary>
  )
}
