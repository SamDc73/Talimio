import { ChevronLeft, Mail } from "lucide-react"
import { useEffect, useState } from "react"

import { useAuth } from "@/hooks/useAuth"

function PasswordResetForm({ onBack }) {
	const [email, setEmail] = useState("")
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const { resetPassword } = useAuth()

	// Check if auth is enabled
	const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"

	useEffect(() => {
		if (!authEnabled) {
			setError("Password reset is not available in single-user mode")
		}
	}, [])

	const handleSubmit = async (e) => {
		e.preventDefault()

		if (!authEnabled) {
			setError("Password reset is not available in single-user mode")
			return
		}

		setError("")
		setSuccessMessage("")
		setLoading(true)

		try {
			const result = await resetPassword(email)
			if (result.success) {
				setSuccessMessage("Password reset instructions sent to your email!")
				setEmail("")
			} else {
				setError(result.error || "Failed to send reset email")
			}
		} catch (_err) {
			setError("An unexpected error occurred")
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className="min-h-screen bg-background flex items-center justify-center p-4">
			<div className="w-full max-w-md">
				<div className="bg-card border border-border rounded-lg shadow-sm p-6 space-y-6">
					{/* Header */}
					<div className="text-center space-y-2">
						<h1 className="text-2xl font-bold">Reset Password</h1>
						<p className="text-muted-foreground">
							Enter your email address and we'll send you instructions to reset your password
						</p>
					</div>

					{/* Error/Success Messages */}
					{error && <div className="bg-destructive/10 text-destructive px-4 py-2 rounded-md text-sm">{error}</div>}

					{successMessage && (
						<div className="bg-primary/10 text-primary px-4 py-2 rounded-md text-sm">{successMessage}</div>
					)}

					{/* Form */}
					<form onSubmit={handleSubmit} className="space-y-4">
						<div>
							<label htmlFor="email" className="block text-sm font-medium mb-1">
								Email
							</label>
							<div className="relative">
								<Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
								<input
									type="email"
									id="email"
									value={email}
									onChange={(e) => setEmail(e.target.value)}
									className="w-full pl-10 pr-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
									placeholder="you@example.com"
									required
									disabled={loading}
								/>
							</div>
						</div>

						<button
							type="submit"
							disabled={loading}
							className="w-full bg-primary text-white py-2 rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{loading ? "Sending..." : "Send Reset Instructions"}
						</button>
					</form>

					{/* Back to login */}
					<div className="text-center">
						<button
							type="button"
							onClick={onBack}
							className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors"
						>
							<ChevronLeft className="h-4 w-4 mr-1" />
							Back to login
						</button>
					</div>
				</div>
			</div>
		</div>
	)
}

export default PasswordResetForm
