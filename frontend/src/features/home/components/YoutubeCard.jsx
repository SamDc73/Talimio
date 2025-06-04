import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, Youtube } from "lucide-react"
import { KebabMenu } from "./KebabMenu"
import { deleteApi } from "@/services/deleteApi"

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

export function YoutubeCard({ video, onDelete }) {
  const [showMenu, setShowMenu] = useState(false)

  const handleDelete = async (itemType, itemId) => {
    try {
      await deleteApi.deleteItem(itemType, itemId)
      if (onDelete) {
        onDelete(itemId, itemType)
      }
    } catch (error) {
      console.error('Failed to delete video:', error)
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
        <div className="flex items-center gap-1.5 text-red-600">
          <Youtube className="h-4 w-4" />
          <span className="text-sm">Video</span>
        </div>
      </div>
      
      <KebabMenu
        showMenu={showMenu}
        onDelete={handleDelete}
        itemType="video"
        itemId={video.uuid || video.id}
        itemTitle={video.title}
      />
      
      {/* Title */}
      <h3 className="text-xl font-semibold text-gray-900 mb-2">
        {video.title}
      </h3>
      
      {/* Description */}
      <p className="text-gray-600 text-sm mb-4">
        {video.channel_name || video.channel} • {formatDuration(video.duration)}
      </p>
      
      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-6">
        {video.tags?.slice(0, 3).map((tag) => (
          <span 
            key={tag} 
            className="inline-flex items-center px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 text-xs"
          >
            {tag}
          </span>
        ))}
        {video.tags?.length > 3 && (
          <span className="text-xs text-gray-500">
            +{video.tags.length - 3}
          </span>
        )}
      </div>
      
      {/* Progress */}
      <div className="mb-6">
        <div className="text-sm text-gray-600 mb-2">Progress</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-100 rounded-full h-2">
            <div 
              className="bg-teal-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${video.completion_percentage || 0}%` }}
            />
          </div>
          <span className="text-sm text-gray-900 font-medium">{Math.round(video.completion_percentage || 0)}%</span>
        </div>
      </div>
      
      {/* Footer */}
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">YouTube</span>
        <Link to={`/videos/${video.uuid || video.id}`} className="flex items-center gap-1 text-teal-600 hover:text-teal-700 text-sm font-medium">
          Watch
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
