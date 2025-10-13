import { motion } from "framer-motion"
import { Check, Pause } from "lucide-react"

import { Button } from "@/components/Button"
import { STATES } from "@/features/home/utils/contentConstants"

function DueDateChip({ dueDate, isPaused, progress, type, dueCount = 0, overdue = 0, onSnooze }) {
	if (progress === 100)
		return (
			<motion.div
				initial={{ opacity: 0, scale: 0.9 }}
				animate={{ opacity: 1, scale: 1 }}
				className="bg-completed/10 text-completed-text text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
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
				className="bg-paused/10 text-paused-text text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
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

export default DueDateChip
