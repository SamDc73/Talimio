import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import ErrorBoundary from "@/components/ErrorBoundary"

// Debug logging for Radix UI component initialization
if (import.meta.env.VITE_DEBUG_MODE === 'true') {
  console.log("[Debug] Initializing Radix UI components in HomePage");
}
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
  MoreHorizontal,
  Check,
  Pin,
  Calendar,
  AlertCircle,
  Pause,
  ChevronUp,
  ChevronDown,
  Info,
  TimerOff,
  Code,
} from "lucide-react"
import { Input } from "@/components/input"
import { Button } from "@/components/button"
import { Label } from "@/components/label"
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from "@/components/tooltip"
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
import { videoApi } from "@/services/videoApi"
import { deleteApi } from "@/services/deleteApi"
import { MainHeader } from "@/components/header/MainHeader"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"

const VARIANTS = {
  course: { label: "Course", icon: Sparkles, badge: "bg-cyan-50 text-cyan-600", grad: "from-cyan-400 to-cyan-500" },
  book: { label: "PDF", icon: FileText, badge: "bg-blue-50 text-blue-600", grad: "from-blue-400 to-blue-500" },
  youtube: {
    label: "Video",
    icon: Youtube,
    badge: "bg-violet-50 text-violet-600",
    grad: "from-violet-400 to-violet-500",
  },
  flashcards: {
    label: "Flashcards",
    icon: Layers,
    badge: "bg-lime-100 text-lime-700",
    grad: "from-lime-500 to-lime-600",
  },
  roadmap: {
    label: "Course",
    icon: Sparkles,
    badge: "bg-cyan-50 text-cyan-600",
    grad: "from-cyan-400 to-cyan-500",
  },
}

const STATES = [
  {
    key: "overdue",
    bg: "bg-orange-50",
    txt: "text-orange-700",
    icon: TimerOff,
    msg: "You're late – jump back in",
    btn: true,
  },
  { key: "today", bg: "bg-amber-50", txt: "text-amber-700", icon: Clock, msg: "Due today — quick session" },
  {
    key: "upcoming",
    bg: "bg-blue-50",
    txt: "text-blue-700",
    icon: Calendar,
    msg: (d) => `Next check‑in ${d.toLocaleDateString("en-US", { weekday: "long" })}`,
  },
]

const TagChip = ({ tag }) => (
  <div className="bg-slate-100 text-slate-700 text-xs font-medium px-2 py-1 rounded-full">{tag}</div>
)

const DueDateChip = ({ dueDate, isPaused, progress, type, dueCount = 0, overdue = 0, onSnooze }) => {
  if (progress === 100 || (type === "flashcards" && dueCount === 0 && overdue === 0))
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-emerald-50 text-emerald-700 text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
      >
        <Check className="h-3 w-3" />
        <span>Great streak!</span>
      </motion.div>
    )
  if (isPaused)
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-100 text-slate-600 text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
      >
        <Pause className="h-3 w-3" />
        <span>On hold – resume when free</span>
      </motion.div>
    )
  if (!dueDate) return null
  const diffHrs = (new Date(dueDate) - Date.now()) / 36e5
  const stateIdx = diffHrs < 0 ? 0 : diffHrs < 24 ? 1 : 2
  const state = STATES[stateIdx]
  const base = `${state.bg} ${state.txt} text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap`
  const msg = typeof state.msg === "function" ? state.msg(new Date(dueDate)) : state.msg
  return (
    <div className="flex items-center gap-2">
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className={base}>
        <state.icon className="h-3 w-3" />
        <span>{msg}</span>
      </motion.div>
      {state.btn && (
        <Button onClick={onSnooze} variant="outline" size="sm" className="h-6 text-xs px-3">
          Reschedule
        </Button>
      )}
    </div>
  )
}

const BaseCard = ({ item, pinned, onTogglePin, onDelete, index, onClick }) => {
  const [hover, setHover] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  
  if (import.meta.env.VITE_DEBUG_MODE === 'true') {
    console.log("[DEBUG] BaseCard received item:", item)
  }
  
  const V = VARIANTS[item.type]
  const isFlashcard = item.type === "flashcards"
  const progressValue = isFlashcard
    ? item.totalCards > 0 ? ((item.totalCards - (item.due || 0) - (item.overdue || 0)) / item.totalCards) * 100 : 0
    : item.progress || item.completion_percentage || 0

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = async () => {
    try {
      const itemType = item.type === "youtube" ? "video" : 
                       item.type === "flashcards" ? "flashcard" : 
                       item.type
      await deleteApi.deleteItem(itemType, item.id || item.uuid)
      if (onDelete) {
        onDelete(item.id || item.uuid, itemType)
      }
    } catch (error) {
      console.error('Failed to delete item:', error)
    }
  }

  return (
    <div>
      <motion.div
        layout
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 * index }}
        whileHover={{ y: -5, transition: { duration: 0.2 } }}
        className={`bg-white rounded-2xl overflow-hidden relative flex flex-col h-full cursor-pointer ${
          pinned ? "shadow-md border-2 border-primary/10 bg-primary/5" : "shadow-sm hover:shadow-md border border-slate-100"
        }`}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onClick={onClick}
      >
      {pinned && <div className="absolute top-0 left-6 w-6 h-1 bg-primary rounded-b-full" />}
      <div className="p-6 flex flex-col justify-between h-full">
        <div className="flex justify-between items-start mb-4">
          <div className={`${V.badge} text-xs font-medium px-3 py-1 rounded-full flex items-center gap-2`}>
            <V.icon className="h-3 w-3" />
            <span>{V.label}</span>
          </div>
        </div>
        <h3 className="text-xl font-bold text-slate-900 hover:underline line-clamp-2 mb-1">{item.title}</h3>
        
        {/* Video metadata */}
        {item.type === "youtube" && (
          <p className="text-slate-600 text-sm mb-4">
            by {item.channel_name || item.channelName || "Unknown Channel"} • {formatDuration(item.duration)}
          </p>
        )}
        
        {/* Book metadata */}
        {item.type === "book" && (
          <p className="text-slate-600 text-sm mb-4">
            by {item.author || "Unknown Author"} • {item.pageCount || item.pages || "Unknown"} pages
          </p>
        )}
        
        {/* Description for other types */}
        {item.type !== "youtube" && item.type !== "book" && item.description && (
          <p className="text-slate-600 text-sm line-clamp-2 mb-4">{item.description}</p>
        )}
        
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {item.tags?.slice(0, 2).map((t) => (
            <TagChip key={t} tag={t} />
          ))}
          {item.tags?.length > 2 && (
            <span className="inline-flex text-xs font-medium bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
              +{item.tags.length - 2}
            </span>
          )}
          <DueDateChip
            dueDate={item.dueDate}
            isPaused={item.isPaused}
            progress={progressValue}
            type={item.type}
            dueCount={item.due || item.dueCount}
            overdue={item.overdue}
            onSnooze={(e) => {
              e.stopPropagation()
              alert(`Rescheduled: ${item.title}`)
            }}
          />
        </div>
        <div>
          {isFlashcard && (
            <div className="flex justify-between text-xs text-slate-500 mb-2">
              <span>
                {item.overdue > 0 && (
                  <>
                    <span className="text-orange-600 font-medium">{item.overdue} overdue</span>
                    <span className="text-slate-400 mx-1">•</span>
                  </>
                )}
                <span>{item.totalCards || item.cardCount || 0} cards</span>
              </span>
            </div>
          )}
          {!isFlashcard && progressValue != null && progressValue !== "" && (
            <div className="flex justify-between text-xs text-slate-500 mb-2">
              <span>{Math.round(progressValue)}%</span>
            </div>
          )}
          <div className="w-full bg-slate-100 rounded-full h-2">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progressValue}%` }}
              transition={{ duration: 0.6 }}
              className={`h-2 rounded-full bg-gradient-to-r ${V.grad}`}
            />
          </div>
        </div>
      </div>
      {hover && (
        <div className="absolute top-4 right-4 z-10">
          <Popover>
            <PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-40 p-0">
              <div className="flex flex-col text-sm">
                {["Pin", "Edit Tags", "Archive", "sep", "Pause", "Delete"].map((action) =>
                  action === "sep" ? (
                    <Separator key="separator" />
                  ) : (
                    <Button
                      key={action}
                      variant="ghost"
                      size="sm"
                      className={`justify-start ${action === "Delete" ? "text-red-600 hover:bg-red-50" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (action === "Pin") onTogglePin()
                        else if (action === "Delete") handleDeleteClick()
                        else if (action === "Archive") console.log("Archive functionality - placeholder")
                        else if (action === "Pause") console.log("Pause functionality - placeholder")
                        else if (action === "Edit Tags") console.log("Edit Tags functionality - placeholder")
                      }}
                    >
                      {action === "Pin" ? (pinned ? "Unpin" : "Pin") : action}
                    </Button>
                  ),
                )}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      )}
    </motion.div>
    
    <ConfirmationDialog
      open={showDeleteConfirm}
      onOpenChange={setShowDeleteConfirm}
      title="Delete Item"
      description="This action cannot be undone. This item will be permanently removed from your library."
      itemName={item.title}
      onConfirm={handleConfirmDelete}
    />
  </div>
  )
}

function formatDuration(seconds) {
  if (!seconds) return "Unknown duration"
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

export default function HomePage() {
  if (import.meta.env.VITE_DEBUG_MODE === 'true') {
    console.log("[Debug] Rendering HomePage component");
  }
  const api = useApi()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState("")
  const [isGenerateMode, setIsGenerateMode] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [showYoutubeDialog, setShowYoutubeDialog] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [bookTitle, setBookTitle] = useState("")
  const [bookAuthor, setBookAuthor] = useState("")
  const [isExtractingMetadata, setIsExtractingMetadata] = useState(false)
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [isAddingVideo, setIsAddingVideo] = useState(false)
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
  const [pins, setPins] = useState({})
  const [showAll, setShowAll] = useState(false)

  // Fetch content data on component mount
  useEffect(() => {
    async function loadContentData() {
      setIsLoading(true)
      try {
        const data = await fetchContentData()
        const { content, filterOptions: options, sortOptions: sortOpts } = processContentData(data)

        // Transform data to match new structure
        const transformedContent = content.map(item => ({
          ...item,
          // Add mock due dates and states for demonstration
          dueDate: Math.random() > 0.7 ? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString() : null,
          isPaused: Math.random() > 0.9,
          // For flashcards, map the existing fields
          totalCards: item.cardCount,
          due: item.dueCount || Math.floor(Math.random() * 10),
          overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
        }))

        setContentItems(transformedContent)

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
        
        // Initialize pins state
        const initialPins = {}
        transformedContent.forEach(item => {
          if (!initialPins[item.type]) initialPins[item.type] = []
        })
        setPins(initialPins)
      } catch (error) {
        console.error("Error loading content data:", error)
        toast({
          title: "Error",
          description: "Failed to load content. Please refresh the page.",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    loadContentData()
  }, [toast])

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
        return title.includes(query) || (item.author?.toLowerCase().includes(query)) || tags
      }
      if (item.type === "youtube") {
        const channelName = item.channel_name || item.channelName || ""
        return title.includes(query) || (channelName?.toLowerCase().includes(query)) || tags
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
      setContentItems(content.map(item => ({
        ...item,
        dueDate: Math.random() > 0.7 ? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString() : null,
        isPaused: Math.random() > 0.9,
        totalCards: item.cardCount,
        due: item.dueCount || Math.floor(Math.random() * 10),
        overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
      })))
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

  const toggleSortDirection = () => {
    setSortDirection(sortDirection === "asc" ? "desc" : "asc")
  }

  const getActiveFilterLabel = () => {
    return filterOptions.find((option) => option.id === activeFilter)?.label || "All Content"
  }

  const getActiveSortLabel = () => {
    return sortOptions.find((option) => option.id === activeSort)?.label || "Last Opened"
  }

  const togglePin = (type, id) =>
    setPins((p) => ({ ...p, [type]: p[type].includes(id) ? p[type].filter((x) => x !== id) : [...p[type], id] }))

  const priority = (i) => {
    if (i.progress === 100 || (i.type === "flashcards" && i.due === 0 && i.overdue === 0)) return 5
    if (i.isPaused) return 3
    if (!i.dueDate) return 4
    const h = (new Date(i.dueDate) - Date.now()) / 36e5
    return h < 0 ? 1 : h < 24 ? 2 : 4
  }

  const unpinned = filteredAndSortedContent.filter((i) => !pins[i.type]?.includes(i.id))
  const visible = showAll ? unpinned : unpinned.slice(0, 3)

  const [celebrate, setCelebrate] = useState(false)
  useEffect(() => {
    if (unpinned.length && unpinned.every((i) => priority(i) === 5)) {
      setCelebrate(true)
      const t = setTimeout(() => setCelebrate(false), 5000)
      return () => clearTimeout(t)
    }
  }, [unpinned, priority])

  const handleCardClick = (item) => {
    // Navigate to the appropriate page based on item type
    if (item.type === "course") {
      navigate(`/courses/${item.id}`)
    } else if (item.type === "youtube") {
      navigate(`/videos/${item.uuid || item.id}`)
    } else if (item.type === "book") {
      navigate(`/books/${item.id}`)
    } else if (item.type === "roadmap") {
      navigate(`/roadmap/${item.id}`)
    } else if (item.type === "flashcards") {
      navigate(`/flashcards/${item.id}`)
    }
  }

  const handleDeleteItem = (itemId, itemType) => {
    // Remove the item from content state
    setContentItems(prevContent => prevContent.filter(item => 
      (item.id !== itemId && item.uuid !== itemId)
    ))
    
    // Remove from pins if it was pinned
    setPins(prevPins => {
      const newPins = { ...prevPins }
      Object.keys(newPins).forEach(type => {
        newPins[type] = newPins[type].filter(id => id !== itemId)
      })
      return newPins
    })

    // Show success toast
    toast({
      title: "Item deleted",
      description: `${itemType} has been successfully deleted.`,
    })
  }

  const renderCard = (item, i) => (
    <BaseCard
      key={item.id}
      item={item}
      index={i}
      pinned={pins[item.type]?.includes(item.id)}
      onTogglePin={() => togglePin(item.type, item.id)}
      onDelete={handleDeleteItem}
      onClick={() => handleCardClick(item)}
    />
  )

  const pinnedItems = Object.entries(pins).flatMap(([type, ids]) =>
    filteredAndSortedContent.filter((x) => x.type === type && ids.includes(x.id)),
  )


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
        
        // Pre-populate fields with extracted metadata
        if (metadata.title) {
          setBookTitle(metadata.title)
        }
        if (metadata.author) {
          setBookAuthor(metadata.author)
        }
        
        toast({
          title: "Metadata Extracted",
          description: "Book information has been auto-populated. You can edit if needed.",
        })
        
      } catch (error) {
        console.error("Failed to extract metadata:", error)
        // If extraction fails, use filename as title
        const titleFromFilename = file.name.replace(/\.[^/.]+$/, "")
        setBookTitle(titleFromFilename)
      } finally {
        setIsExtractingMetadata(false)
      }
    }
  }

  const handleUpload = async () => {
    if (!selectedFile || !bookTitle.trim() || !bookAuthor.trim()) return

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
            title: "Duplicate Book",
            description: errorData.detail || "This book already exists in your library.",
            variant: "destructive",
          })
          return
        }
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
      }
      
      toast({
        title: "Book Uploaded!",
        description: `"${bookTitle}" by ${bookAuthor} has been added to your library.`,
      })
      
      setSelectedFile(null)
      setBookTitle("")
      setBookAuthor("")
      setShowUploadDialog(false)
      
      // Refresh content list
      const data = await fetchContentData()
      const { content } = processContentData(data)
      setContentItems(content.map(item => ({
        ...item,
        dueDate: Math.random() > 0.7 ? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString() : null,
        isPaused: Math.random() > 0.9,
        totalCards: item.cardCount,
        due: item.dueCount || Math.floor(Math.random() * 10),
        overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
      })))
    } catch (error) {
      toast({
        title: "Error",
        description: error.message || "Failed to upload book. Please try again.",
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

    if (isAddingVideo) return // Prevent duplicate submissions

    setIsAddingVideo(true)
    try {
      const response = await videoApi.createVideo(youtubeUrl)
      
      toast({
        title: "Video Added!",
        description: `"${response.title}" has been added to your library.`,
      })
      
      setYoutubeUrl("")
      setSearchQuery("")
      setShowYoutubeDialog(false)
      setIsYoutubeMode(false)
      
      // Refresh content list
      const data = await fetchContentData()
      const { content } = processContentData(data)
      setContentItems(content.map(item => ({
        ...item,
        dueDate: Math.random() > 0.7 ? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString() : null,
        isPaused: Math.random() > 0.9,
        totalCards: item.cardCount,
        due: item.dueCount || Math.floor(Math.random() * 10),
        overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
      })))
    } catch (error) {
      toast({
        title: "Error",
        description: error.message || "Failed to add video. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsAddingVideo(false)
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
      setContentItems(content.map(item => ({
        ...item,
        dueDate: Math.random() > 0.7 ? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString() : null,
        isPaused: Math.random() > 0.9,
        totalCards: item.cardCount,
        due: item.dueCount || Math.floor(Math.random() * 10),
        overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
      })))
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create flashcard deck. Please try again.",
        variant: "destructive",
      })
    }
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
            <AnimatePresence>
              {pinnedItems.length > 0 && (
                <motion.section
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-8"
                >
                  <div className="flex items-center gap-2 mb-4">
                    <Pin className="h-4 w-4 text-primary" />
                    <h2 className="text-xl font-semibold">Pinned</h2>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">{pinnedItems.map(renderCard)}</div>
                  <div className="border-b border-slate-200 my-8" />
                </motion.section>
              )}
            </AnimatePresence>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {isLoading ? (
                  // Show skeleton cards while loading
                  Array.from({ length: 6 }).map((_, index) => (
                    <div key={`skeleton-${index}`} className="animate-pulse">
                      <div className="bg-gray-200 dark:bg-gray-700 rounded-xl h-64" />
                    </div>
                  ))
                ) : filteredAndSortedContent.length > 0 ? (
                  visible.map(renderCard)
                ) : (
                  <div className="col-span-full text-center py-12">
                    <p className="text-slate-500">No content found matching your criteria.</p>
                    <div className="flex justify-center gap-4 mt-4 flex-wrap">
                      <Button variant="outline" onClick={() => setIsGenerateMode(true)}>
                        Generate a new course
                      </Button>
                      <Button variant="outline" onClick={() => {
                        setShowUploadDialog(true)
                        setSelectedFile(null)
                        setBookTitle("")
                        setBookAuthor("")
                        setIsExtractingMetadata(false)
                      }}>
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
              
              {!isLoading && unpinned.length > 3 && (
                <div className="mt-6 text-center">
                  <Button
                    variant="outline"
                    onClick={() => setShowAll(!showAll)}
                    className="h-10 min-w-[120px] flex items-center gap-2"
                  >
                    {showAll ? (
                      <>
                        <ChevronUp className="h-4 w-4" />
                        Show Less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        See {unpinned.length - 3} More
                      </>
                    )}
                  </Button>
                </div>
              )}
              
              {!isLoading && filteredAndSortedContent.length === 0 && (
                <div className="text-center py-12">
                  <div className="inline-block bg-emerald-50 p-4 rounded-full mb-4">
                    <Check className="h-8 w-8 text-emerald-600" />
                  </div>
                  <h3 className="text-xl font-bold text-emerald-700 mb-2">All Caught Up!</h3>
                  <p className="text-slate-600">You've completed all your learning tasks. Great job!</p>
                </div>
              )}
          </motion.div>
        </div>
        {celebrate && (
          <div className="fixed inset-0 pointer-events-none z-50">
            {Array.from({ length: 100 }).map((_, i) => (
              <div
                key={i}
                className="absolute animate-confetti"
                style={{
                  left: `${Math.random() * 100}%`,
                  top: "-5%",
                  width: `${Math.random() * 10 + 5}px`,
                  height: `${Math.random() * 10 + 5}px`,
                  background: ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ff8000", "#8000ff"][
                    Math.floor(Math.random() * 8)
                  ],
                  transform: `rotate(${Math.random() * 360}deg)`,
                  animationDuration: `${Math.random() * 3 + 2}s`,
                  animationDelay: `${Math.random() * 2}s`,
                }}
              />
            ))}
          </div>
        )}
        

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
              {isExtractingMetadata && (
                <div className="flex items-center justify-center py-4">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500 mr-2" />
                  <span className="text-sm text-gray-600">Extracting book information...</span>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="book-title">Title *</Label>
                <Input
                  id="book-title"
                  type="text"
                  placeholder="Enter book title"
                  value={bookTitle}
                  onChange={(e) => setBookTitle(e.target.value)}
                  disabled={isExtractingMetadata}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="book-author">Author *</Label>
                <Input
                  id="book-author"
                  type="text"
                  placeholder="Enter author name"
                  value={bookAuthor}
                  onChange={(e) => setBookAuthor(e.target.value)}
                  disabled={isExtractingMetadata}
                />
              </div>
            </div>
            <SheetFooter>
              <Button variant="outline" onClick={() => setShowUploadDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleUpload} 
                disabled={!selectedFile || !bookTitle.trim() || !bookAuthor.trim()}
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
                disabled={!youtubeUrl.trim() || isAddingVideo}
                className="bg-red-500 hover:bg-red-600 text-white"
              >
                {isAddingVideo ? "Adding..." : "Add Video"}
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
                        toast({
                          title: "Coming Soon",
                          description: "Course generation will be available soon!",
                        })
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
                        setBookTitle("")
                        setBookAuthor("")
                        setIsExtractingMetadata(false)
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
        
        <style jsx global>{`
          @keyframes confetti {
            0% {
              transform: translateY(0) rotate(0deg);
              opacity: 1;
            }
            100% {
              transform: translateY(100vh) rotate(720deg);
              opacity: 0;
            }
          }
          .animate-confetti {
            animation: confetti 5s ease-in-out forwards;
          }
        `}</style>
          </div>
        </ErrorBoundary>
      </TooltipProvider>
    </ErrorBoundary>
  )
}
