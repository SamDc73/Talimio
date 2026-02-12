import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, Lock } from "lucide-react"
import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { LoginHeader } from "@/components/header/LoginHeader"
import AuthPageShell from "@/features/auth/components/AuthPageShell"
import PasswordStrengthMeter from "@/features/auth/components/PasswordStrengthMeter"
import { useAuth } from "@/hooks/use-auth"
import logger from "@/lib/logger"
import { getPasswordStrength } from "./passwordStrength"

const REQUIRED_FIELD_MESSAGE = "This field is required"

function ResetPasswordPage() {
	const [searchParams] = useSearchParams()
	const token = searchParams.get("token") || ""

	const [newPassword, setNewPassword] = useState("")
	const [confirmPassword, setConfirmPassword] = useState("")
	const [showPassword, setShowPassword] = useState(false)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const [errors, setErrors] = useState({ newPassword: undefined, confirm: undefined })
	const passwordStrength = getPasswordStrength(newPassword)

	const navigate = useNavigate()
	const { applyPasswordReset } = useAuth()

	const handleSubmit = async (e) => {
		e.preventDefault()

		setError("")
		setSuccessMessage("")

		if (!token) {
			setError("Missing reset token. Please use the link from your email.")
			return
		}

		const newErrors = {}

		if (!newPassword) {
			newErrors.newPassword = REQUIRED_FIELD_MESSAGE
		}

		if (!confirmPassword) {
			newErrors.confirm = REQUIRED_FIELD_MESSAGE
		} else if (newPassword !== confirmPassword) {
			newErrors.confirm = "Passwords do not match"
		}

		setErrors(newErrors)
		if (Object.keys(newErrors).length > 0) return

		setLoading(true)
		try {
			const result = await applyPasswordReset(token, newPassword)
			if (!result.success) {
				setError(result.error || "Password reset failed")
				return
			}

			setSuccessMessage("Password updated. Redirecting to sign in…")
			setTimeout(() => navigate("/auth"), 1200)
		} catch (err) {
			logger.error("Reset password failed", err)
			setError("An unexpected error occurred")
		} finally {
			setLoading(false)
		}
	}

	return (
		<>
			<LoginHeader />

			<AuthPageShell title="Set a new password" description="Choose a new password for your account">
				{!token && (
					<div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
						Missing reset token. Please use the link from your email.
					</div>
				)}

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
						<label htmlFor="newPassword" className="block text-sm font-medium text-foreground">
							New password
						</label>
						<div className="relative">
							<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
								<Lock className="size-5 text-muted-foreground" />
							</div>
							<input
								id="newPassword"
								type={showPassword ? "text" : "password"}
								value={newPassword}
								onChange={(e) => {
									setNewPassword(e.target.value)
									if (errors.newPassword) setErrors((prev) => ({ ...prev, newPassword: undefined }))
								}}
								className={`block w-full pl-10 pr-12 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
									errors.newPassword
										? "border-destructive/50 focus:ring-destructive bg-destructive/5"
										: "border-border focus:ring-ring hover:border-border/80"
								}`}
								placeholder="Enter a new password"
								disabled={loading}
								autoComplete="new-password"
							/>
							<button
								type="button"
								onClick={() => setShowPassword((prev) => !prev)}
								className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground transition-colors"
								disabled={loading}
							>
								{showPassword ? <EyeOff className="size-5 " /> : <Eye className="size-5 " />}
							</button>
						</div>
						{errors.newPassword && <p className="text-destructive text-xs mt-1">{errors.newPassword}</p>}
						<PasswordStrengthMeter passwordStrength={passwordStrength} meterIdPrefix="reset-password-strength" />
					</div>

					<div className="space-y-2">
						<label htmlFor="confirmPassword" className="block text-sm font-medium text-foreground">
							Confirm password
						</label>
						<div className="relative">
							<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
								<Lock className="size-5 text-muted-foreground" />
							</div>
							<input
								id="confirmPassword"
								type={showPassword ? "text" : "password"}
								value={confirmPassword}
								onChange={(e) => {
									setConfirmPassword(e.target.value)
									if (errors.confirm) setErrors((prev) => ({ ...prev, confirm: undefined }))
								}}
								className={`block w-full pl-10 pr-12 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
									errors.confirm
										? "border-destructive/50 focus:ring-destructive bg-destructive/5"
										: "border-border focus:ring-ring hover:border-border/80"
								}`}
								placeholder="Confirm your new password"
								disabled={loading}
								autoComplete="new-password"
							/>
							<button
								type="button"
								onClick={() => setShowPassword((prev) => !prev)}
								className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground transition-colors"
								disabled={loading}
							>
								{showPassword ? <EyeOff className="size-5 " /> : <Eye className="size-5 " />}
							</button>
						</div>
						{errors.confirm && <p className="text-destructive text-xs mt-1">{errors.confirm}</p>}
					</div>

					<button
						type="submit"
						disabled={loading || !token}
						className="w-full bg-linear-to-r from-primary to-primary/90 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-primary/30 hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
					>
						{loading ? (
							<div className="flex items-center justify-center">
								<Loader2 className="size-5 animate-spin mr-2" />
								Updating password...
							</div>
						) : (
							"Update password"
						)}
					</button>

					<div className="text-center pt-2">
						<button
							type="button"
							onClick={() => navigate("/auth")}
							className="text-sm text-muted-foreground hover:text-foreground transition-colors"
							disabled={loading}
						>
							Back to sign in
						</button>
					</div>
				</form>
			</AuthPageShell>
		</>
	)
}

export default ResetPasswordPage
