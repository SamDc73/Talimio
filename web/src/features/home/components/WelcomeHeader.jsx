import { motion } from "framer-motion"

export default function WelcomeHeader() {
	return (
		<motion.div
			initial={{ opacity: 0, y: -20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5 }}
			className="text-center mb-6"
		>
			<h1 className="text-4xl md:text-5xl font-display font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 mb-4 tracking-tight">
				Welcome Back!
			</h1>
			<p className="text-lg text-muted-foreground max-w-2xl mx-auto">
				Ready to continue your journey? Pick up where you left off or explore something new today.
			</p>
		</motion.div>
	)
}
