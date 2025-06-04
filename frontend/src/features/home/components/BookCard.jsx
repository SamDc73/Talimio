import { useState } from "react"
import { Link } from "react-router-dom"
import { BookOpen, ChevronRight } from "lucide-react"
import { KebabMenu } from "./KebabMenu"
import { deleteApi } from "@/services/deleteApi"

export function BookCard({ book, onDelete }) {
  const [showMenu, setShowMenu] = useState(false)
  const currentPage = book.currentPage || 0
  const totalPages = book.pageCount || 0
  const readingProgress = totalPages > 0 ? (currentPage / totalPages) * 100 : 0

  const handleDelete = async (itemType, itemId) => {
    try {
      await deleteApi.deleteItem(itemType, itemId)
      if (onDelete) {
        onDelete(itemId, itemType)
      }
    } catch (error) {
      console.error('Failed to delete book:', error)
    }
  }
  
  return (
    <div 
      className="bg-white rounded-2xl shadow-sm hover:shadow-md transition-all p-6 relative"
      onMouseEnter={() => setShowMenu(true)}
      onMouseLeave={() => setShowMenu(false)}
    >
      {/* Header with badge and menu */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-1.5 text-indigo-600">
          <BookOpen className="h-4 w-4" />
          <span className="text-sm">Book</span>
        </div>
      </div>
      
      <KebabMenu
        showMenu={showMenu}
        onDelete={handleDelete}
        itemType="book"
        itemId={book.id}
        itemTitle={book.title || "Untitled Book"}
      />
      
      {/* Title */}
      <h3 className="text-xl font-semibold text-gray-900 mb-2">
        {book.title || "Untitled Book"}
      </h3>
      
      {/* Description */}
      <p className="text-gray-600 text-sm mb-4">
        {book.author || "Unknown Author"}
      </p>
      
      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-6">
        {book.tags?.slice(0, 3).map((tag) => (
          <span 
            key={tag} 
            className="inline-flex items-center px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 text-xs"
          >
            {tag}
          </span>
        ))}
        {book.tags?.length > 3 && (
          <span className="text-xs text-gray-500">
            +{book.tags.length - 3}
          </span>
        )}
      </div>
      
      {/* Progress */}
      <div className="mb-6">
        <div className="text-sm text-gray-600 mb-2">Reading Progress</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-100 rounded-full h-2">
            <div 
              className="bg-teal-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${readingProgress}%` }}
            />
          </div>
          <span className="text-sm text-gray-900 font-medium">{Math.round(readingProgress)}%</span>
        </div>
      </div>
      
      {/* Footer */}
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">{currentPage}/{totalPages} pages</span>
        <Link to={`/books/${book.id}`} className="flex items-center gap-1 text-teal-600 hover:text-teal-700 text-sm font-medium">
          Read
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}