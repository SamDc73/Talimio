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
				className="mb-xl"
			>
				<div className="mb-md flex items-center gap-2xs">
					<Pin className="size-md text-completed" />

					<h2 className="text-xl font-semibold">Pinned</h2>
				</div>
				<div className="grid grid-cols-1 gap-lg md:grid-cols-2 lg:grid-cols-3">
					<AnimatePresence mode="popLayout">
						{pinnedItems.map((item, index) => renderCard(item, index))}
					</AnimatePresence>
				</div>
				<div className="my-xl border-b border-border" />
			</motion.section>
		</AnimatePresence>
	)
}
