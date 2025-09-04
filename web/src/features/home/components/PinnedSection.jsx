import { AnimatePresence, motion } from "framer-motion"
import { Pin } from "lucide-react"

export default function PinnedSection({ pinnedItems, renderCard }) {
	if (pinnedItems.length === 0) return null

	return (
		<AnimatePresence>
			<motion.section
				initial={{ opacity: 0, height: 0 }}
				animate={{ opacity: 1, height: "auto" }}
				exit={{ opacity: 0, height: 0 }}
				className="mb-8"
			>
				<div className="flex items-center gap-2 mb-4">
					<Pin className="h-4 w-4 text-green-500" />
					<h2 className="text-xl font-semibold">Pinned</h2>
				</div>
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
					<AnimatePresence mode="popLayout">{pinnedItems.map(renderCard)}</AnimatePresence>
				</div>
				<div className="border-b border-gray-200 my-8" />
			</motion.section>
		</AnimatePresence>
	)
}
