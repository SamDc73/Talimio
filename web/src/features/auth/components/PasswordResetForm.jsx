import { AlertCircle, CheckCircle2, ChevronLeft, Loader2, Mail } from "lucide-react"
import { useId, useState } from "react"

import AuthPageShell from "@/features/auth/components/AuthPageShell"
import { useAuth } from "@/hooks/use-auth"
import logger from "@/lib/logger"

function PasswordResetForm({ onBack }) {
	const [email, setEmail] = useState("")
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const { resetPassword } = useAuth()
	const emailId = useId()

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
					<label htmlFor={emailId} className="block text-sm font-medium text-foreground">
						Email address
					</label>
					<div className="relative">
						<Mail className="absolute left-3 top-3.5 size-4 text-muted-foreground" />
						<input
							type="email"
							id={emailId}
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
					className="w-full rounded-xl bg-linear-to-r from-primary to-primary/90 px-4 py-3 font-semibold text-primary-foreground shadow-lg shadow-primary/30 transition-all duration-200 hover:scale-[1.02] hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
				>
					{loading ? (
						<span className="inline-flex items-center justify-center">
							<Loader2 className="mr-2 size-5 animate-spin" />
							Sending...
						</span>
					) : (
						"Send Reset Instructions"
					)}
				</button>

				<button
					type="button"
					onClick={onBack}
					className="inline-flex w-full items-center justify-center pt-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
				>
					<ChevronLeft className="mr-1 size-4" />
					Back to login
				</button>
			</form>
		</AuthPageShell>
	)
}

export default PasswordResetForm
