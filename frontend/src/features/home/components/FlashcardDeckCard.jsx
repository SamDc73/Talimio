import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, Layers } from "lucide-react"
import { KebabMenu } from "./KebabMenu"
import { deleteApi } from "@/services/deleteApi"

export function FlashcardDeckCard({ deck, onDelete }) {
  const [showMenu, setShowMenu] = useState(false)
  // Calculate progress percentage based on mastery
  const progressPercentage = (deck.masteryLevel / 5) * 100

  const handleDelete = async (itemType, itemId) => {
    try {
      await deleteApi.deleteItem(itemType, itemId)
      if (onDelete) {
        onDelete(itemId, itemType)
      }
    } catch (error) {
      console.error('Failed to delete flashcard deck:', error)
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
        <div className="flex items-center gap-1.5 text-amber-600">
          <Layers className="h-4 w-4" />
          <span className="text-sm">Flashcards</span>
        </div>
      </div>
      
      <KebabMenu
        showMenu={showMenu}
        onDelete={handleDelete}
        itemType="flashcard"
        itemId={deck.id}
        itemTitle={deck.title}
      />
      
      {/* Title */}
      <h3 className="text-xl font-semibold text-gray-900 mb-2">
        {deck.title}
      </h3>
      
      {/* Description */}
      <p className="text-gray-600 text-sm mb-4">
        {deck.description}
      </p>
      
      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-6">
        {deck.tags?.slice(0, 3).map((tag) => (
          <span 
            key={tag} 
            className="inline-flex items-center px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 text-xs"
          >
            {tag}
          </span>
        ))}
        {deck.tags?.length > 3 && (
          <span className="text-xs text-gray-500">
            +{deck.tags.length - 3}
          </span>
        )}
      </div>
      
      {/* Progress */}
      <div className="mb-6">
        <div className="text-sm text-gray-600 mb-2">Mastery Level</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-100 rounded-full h-2">
            <div 
              className="bg-teal-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <span className="text-sm text-gray-900 font-medium">Level {deck.masteryLevel}</span>
        </div>
      </div>
      
      {/* Footer */}
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">{deck.totalCards} cards • {deck.due} due</span>
        <Link to={`/flashcards/${deck.id}`} className="flex items-center gap-1 text-teal-600 hover:text-teal-700 text-sm font-medium">
          Review
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
