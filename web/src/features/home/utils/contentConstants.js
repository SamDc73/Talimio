import { Calendar, Clock, FileText, Layers, Sparkles, TimerOff, Youtube } from "lucide-react"

export const VARIANTS = {
	course: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-course/10 text-course-text",
		grad: "from-course to-course-accent",
	},
	book: {
		label: "PDF",
		icon: FileText,
		badge: "bg-book/10 text-book-text",
		grad: "from-book to-book-accent",
	},
	video: {
		label: "Video",
		icon: Youtube,
		badge: "bg-video/10 text-video-text",
		grad: "from-video to-video-accent",
	},
	youtube: {
		label: "Video",
		icon: Youtube,
		badge: "bg-video/10 text-video-text",
		grad: "from-video to-video-accent",
	},
	flashcards: {
		label: "Flashcards",
		icon: Layers,
		badge: "bg-flashcard/10 text-flashcard-text",
		grad: "from-flashcard to-flashcard-accent",
	},
	roadmap: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-course/10 text-course-text",
		grad: "from-course to-course-accent",
	},
}

export const STATES = [
	{
		key: "overdue",
		bg: "bg-overdue/10",
		txt: "text-overdue-text",
		icon: TimerOff,
		msg: "You're late – jump back in",
	},
	{
		key: "today",
		bg: "bg-due-today/10",
		txt: "text-due-today-text",
		icon: Clock,
		msg: "Due today — quick session",
	},
	{
		key: "upcoming",
		bg: "bg-upcoming/10",
		txt: "text-upcoming-text",
		icon: Calendar,
		msg: (d) => `Next check‑in ${d.toLocaleDateString("en-US", { weekday: "long" })}`,
	},
]
