import { motion } from "framer-motion"

export default function WelcomeHeader() {
	return (
		<motion.div
			initial={{ opacity: 0, y: -20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5 }}
			className="mb-lg text-center"
		>
			<h1 className="mb-md bg-linear-to-r from-foreground via-foreground/80 to-foreground bg-clip-text text-4xl font-bold tracking-tight text-transparent md:text-5xl">
				Welcome Back!
			</h1>
			<p className="mx-auto max-w-container-2xl text-lg text-muted-foreground">
				Ready to continue your journey? Pick up where you left off or explore something new today.
			</p>
		</motion.div>
	)
}
