import { useState } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { ChevronRight, Youtube, Play } from "lucide-react"
import { Button } from "@/components/button"
import { KebabMenu } from "./KebabMenu"
import { TagList } from "./TagList"

export function YoutubeCard({ video, index }) {
  const [showMenu, setShowMenu] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 * index }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all border border-slate-100 relative group"
      onMouseEnter={() => setShowMenu(true)}
      onMouseLeave={() => setShowMenu(false)}
    >
      <div className="p-6">
        <div className="flex justify-between items-start mb-4">
          <div className="bg-red-50 text-red-600 text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1">
            <Youtube className="h-3 w-3" />
            <span>Video</span>
          </div>
        </div>

        <Link to={`/videos/${video.id}`}>
          <h3 className="text-xl font-bold text-slate-900 mb-2 line-clamp-2 cursor-pointer hover:text-red-600 transition-colors">
            {video.title}
          </h3>
        </Link>
        <p className="text-slate-600 text-sm mb-4 line-clamp-2">
          {video.channelName} • {video.duration}
        </p>

        <TagList tags={video.tags} colorClass="bg-red-50 text-red-600" />

        <div className="mb-4">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Watched</span>
            <span>{video.progress}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div
              className="bg-gradient-to-r from-red-500 to-red-600 h-2.5 rounded-full"
              style={{ width: `${video.progress}%` }}
            />
          </div>
        </div>

        <div className="flex justify-between items-center">
          <div className="text-xs text-slate-500 flex items-center">
            <Play className="h-3 w-3 mr-1" /> YouTube
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-red-600 hover:text-red-700 p-0 h-auto font-medium text-right"
          >
            Watch <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <KebabMenu showMenu={showMenu} onMouseEnter={() => setShowMenu(true)} onMouseLeave={() => setShowMenu(false)} />
    </motion.div>
  )
}
