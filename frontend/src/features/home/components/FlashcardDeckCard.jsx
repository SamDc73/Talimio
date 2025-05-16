import { useState } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { ChevronRight, Layers, Crown, Brain } from "lucide-react"
import { Button } from "@/components/button"
import { KebabMenu } from "./KebabMenu"
import { TagList } from "./TagList"

export function FlashcardDeckCard({ deck, index }) {
  const [showMenu, setShowMenu] = useState(false)

  // Helper function to render mastery level crown
  const renderMasteryLevel = (level) => {
    const colors = [
      "text-slate-400", // Level 0
      "text-slate-600", // Level 1
      "text-amber-400", // Level 2
      "text-amber-500", // Level 3
      "text-amber-600", // Level 4
      "text-amber-700", // Level 5
    ]

    return (
      <div className="flex items-center">
        <Crown className={`h-5 w-5 ${colors[level]}`} />
        <span className="ml-1 text-xs font-medium text-slate-700">Level {level}</span>
      </div>
    )
  }

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
          <div className="bg-amber-50 text-amber-600 text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1">
            <Layers className="h-3 w-3" />
            <span>Flashcards</span>
          </div>
        </div>

        <Link to={`/flashcards/${deck.id}`}>
          <h3 className="text-xl font-bold text-slate-900 mb-2 line-clamp-2 cursor-pointer hover:text-amber-600 transition-colors">
            {deck.title}
          </h3>
        </Link>
        <p className="text-slate-600 text-sm mb-4 line-clamp-2">{deck.description}</p>

        <TagList tags={deck.tags} colorClass="bg-amber-50 text-amber-600" />

        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="bg-amber-50 rounded-lg p-2 text-center">
            <div className="text-amber-600 font-semibold text-lg">{deck.due}</div>
            <div className="text-xs text-slate-600">Due</div>
          </div>
          <div className="bg-blue-50 rounded-lg p-2 text-center">
            <div className="text-blue-600 font-semibold text-lg">{deck.retention}%</div>
            <div className="text-xs text-slate-600">Retention</div>
          </div>
          <div className="bg-slate-50 rounded-lg p-2 text-center flex flex-col items-center justify-center">
            {renderMasteryLevel(deck.masteryLevel)}
          </div>
        </div>

        <div className="flex justify-between items-center">
          <div className="text-xs text-slate-500 flex items-center gap-1">
            <Brain className="h-3 w-3" />
            <span>{deck.totalCards} cards total</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-amber-600 hover:text-amber-700 p-0 h-auto font-medium text-right"
          >
            Review <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <KebabMenu showMenu={showMenu} onMouseEnter={() => setShowMenu(true)} onMouseLeave={() => setShowMenu(false)} />
    </motion.div>
  )
}
