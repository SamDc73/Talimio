import { AlertCircle, CheckCircle2, ChevronLeft, Loader2, Mail } from "lucide-react"
import { useState } from "react"

import AuthPageShell from "@/features/auth/components/AuthPageShell"
import { useAuth } from "@/hooks/use-auth"
import logger from "@/lib/logger"

function PasswordResetForm({ onBack }) {
	const [email, setEmail] = useState("")
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const { resetPassword } = useAuth()

	const handleSubmit = async (e) => {
		e.preventDefault()

		setError("")
		setSuccessMessage("")
		setLoading(true)

		try {
			const normalizedEmail = email.trim().toLowerCase()
			if (!normalizedEmail) {
				setError("Email is required")
				return
			}

			const result = await resetPassword(normalizedEmail)
			if (result.success) {
				setSuccessMessage("Password reset instructions sent to your email!")
				setEmail("")
			} else {
				setError(result.error || "Password reset is not available")
			}
		} catch (err) {
			logger.error("Password reset failed", err, { email })
			setError("An unexpected error occurred")
		} finally {
			setLoading(false)
		}
	}

	return (
		<AuthPageShell title="Reset Password" description="Enter your email and we'll send reset instructions.">
			<form onSubmit={handleSubmit} className="space-y-6">
				{error && (
					<div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
						<AlertCircle className="mt-0.5 size-4 shrink-0" />
						<span>{error}</span>
					</div>
				)}

				{successMessage && (
					<div className="flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
						<CheckCircle2 className="mt-0.5 size-4 shrink-0" />
						<span>{successMessage}</span>
					</div>
				)}

				<div className="space-y-2">
					<label htmlFor="email" className="block text-sm font-medium text-foreground">
						Email address
					</label>
					<div className="relative">
						<Mail className="absolute left-3 top-3.5 size-4 text-muted-foreground" />
						<input
							type="email"
							id="email"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							className="block w-full pl-10 pr-3 py-3 border border-border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200 hover:border-border/80"
							placeholder="Enter your email"
							disabled={loading}
							autoComplete="email"
						/>
					</div>
				</div>

				<button
					type="submit"
					disabled={loading}
					className="w-full bg-linear-to-r from-primary to-primary/90 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-primary/30 hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
				>
					{loading ? (
						<span className="inline-flex items-center justify-center">
							<Loader2 className="size-5 animate-spin mr-2" />
							Sending...
						</span>
					) : (
						"Send Reset Instructions"
					)}
				</button>

				<button
					type="button"
					onClick={onBack}
					className="w-full inline-flex items-center justify-center text-sm text-muted-foreground hover:text-foreground transition-colors pt-1"
				>
					<ChevronLeft className="size-4 mr-1" />
					Back to login
				</button>
			</form>
		</AuthPageShell>
	)
}

export default PasswordResetForm
