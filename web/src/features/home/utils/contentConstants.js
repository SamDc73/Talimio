import { Calendar, Clock, FileText, Sparkles, TimerOff, Youtube } from "lucide-react"

export const VARIANTS = {
	course: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-teal-50 text-teal-600",
		grad: "from-cyan-400 to-cyan-500",
	},
	book: {
		label: "Book",
		icon: FileText,
		badge: "bg-blue-50 text-blue-600",
		grad: "from-blue-400 to-blue-500",
	},
	video: {
		label: "Video",
		icon: Youtube,
		badge: "bg-violet-50 text-violet-600",
		grad: "from-violet-400 to-violet-500",
	},
	youtube: {
		label: "Video",
		icon: Youtube,
		badge: "bg-violet-50 text-violet-600",
		grad: "from-violet-400 to-violet-500",
	},
	roadmap: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-teal-50 text-teal-600",
		grad: "from-cyan-400 to-cyan-500",
	},
}

export const STATES = [
	{
		key: "overdue",
		bg: "bg-orange-50",
		txt: "text-orange-700",
		icon: TimerOff,
		msg: "You're late – jump back in",
	},
	{
		key: "today",
		bg: "bg-amber-50",
		txt: "text-amber-700",
		icon: Clock,
		msg: "Due today — quick session",
	},
	{
		key: "upcoming",
		bg: "bg-blue-50",
		txt: "text-blue-700",
		icon: Calendar,
		msg: (d) => `Next check‑in ${d.toLocaleDateString("en-US", { weekday: "long" })}`,
	},
]
