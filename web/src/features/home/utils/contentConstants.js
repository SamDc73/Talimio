import { Calendar, Clock, FileText, Sparkles, TimerOff, Youtube } from "lucide-react"

export const VARIANTS = {
	course: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-course/10 text-course",
		grad: "from-course to-course-accent",
	},
	book: {
		label: "Book",
		icon: FileText,
		badge: "bg-book/10 text-book",
		grad: "from-book to-book-accent",
	},
	video: {
		label: "Video",
		icon: Youtube,
		badge: "bg-video/10 text-video",
		grad: "from-video to-video-accent",
	},
	youtube: {
		label: "Video",
		icon: Youtube,
		badge: "bg-video/10 text-video",
		grad: "from-video to-video-accent",
	},
}

export const STATES = [
	{
		key: "overdue",
		bg: "bg-overdue/10",
		txt: "text-overdue",
		icon: TimerOff,
		msg: "You're late – jump back in",
	},
	{
		key: "today",
		bg: "bg-due-today/10",
		txt: "text-due-today",
		icon: Clock,
		msg: "Due today — quick session",
	},
	{
		key: "upcoming",
		bg: "bg-upcoming/10",
		txt: "text-upcoming",
		icon: Calendar,
		msg: (d) => `Next check‑in ${d.toLocaleDateString("en-US", { weekday: "long" })}`,
	},
]
