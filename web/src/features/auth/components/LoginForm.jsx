import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, Lock, Mail } from "lucide-react"
import { useEffect, useState } from "react"
import AuthPageShell from "@/features/auth/components/AuthPageShell"
import { isValidEmail } from "@/features/auth/emailValidation"
import logger from "@/lib/logger"

const REQUIRED_FIELD_MESSAGE = "This field is required"

function LoginForm({
	onSignUp = () => {},
	onForgotPassword = () => {},
	onSubmit = async (_email, _password) => {},
	onResendVerification = async (_email) => ({ success: false, error: "Resend is unavailable" }),
	showGoogleOAuth = false,
	onGoogle = () => {},
	errorMessage = "",
	successMessage = "",
}) {
	const [email, setEmail] = useState("")
	const [password, setPassword] = useState("")
	const [showPassword, setShowPassword] = useState(false)
	const [isLoading, setIsLoading] = useState(false)
	const [errors, setErrors] = useState({})
	const [resendMessage, setResendMessage] = useState("")
	const [resendError, setResendError] = useState("")
	const [resendLoading, setResendLoading] = useState(false)
	const [resendCooldownSeconds, setResendCooldownSeconds] = useState(0)
	const [showResendOption, setShowResendOption] = useState(false)

	useEffect(() => {
		if (
			errorMessage &&
			(errorMessage.toLowerCase().includes("verify") ||
				errorMessage.toLowerCase().includes("verification") ||
				errorMessage.toLowerCase().includes("activate") ||
				errorMessage.toLowerCase().includes("confirm"))
		) {
			setShowResendOption(true)
		}
	}, [errorMessage])

	useEffect(() => {
		if (resendCooldownSeconds <= 0) {
			return
		}

		const intervalId = setInterval(() => {
			setResendCooldownSeconds((previous) => {
				if (previous <= 1) {
					return 0
				}
				return previous - 1
			})
		}, 1000)

		return () => clearInterval(intervalId)
	}, [resendCooldownSeconds])

	const validateForm = () => {
		const newErrors = {}

		if (!email) {
			newErrors.email = "Email is required"
		} else if (!isValidEmail(email)) {
			newErrors.email = "Please enter a valid email address"
		}

		if (!password) {
			newErrors.password = REQUIRED_FIELD_MESSAGE
		}

		setErrors(newErrors)
		return Object.keys(newErrors).length === 0
	}

	const handleSubmit = async (e) => {
		e.preventDefault()

		if (!validateForm()) return

		setIsLoading(true)
		try {
			await onSubmit(email, password)
		} catch (error) {
			logger.error("Login failed", error)
		} finally {
			setIsLoading(false)
		}
	}

	const handleResendVerification = async () => {
		setResendMessage("")
		setResendError("")

		if (!email || !isValidEmail(email)) {
			setErrors((previous) => ({ ...previous, email: "Please enter a valid email address" }))
			setResendError("Enter your email above to resend verification.")
			return
		}

		setResendLoading(true)
		try {
			const result = await onResendVerification(email)
			if (result.success) {
				setResendMessage(result.message || "If the account exists, a verification email has been sent")
				setResendCooldownSeconds(result.cooldownSeconds || 60)
				return
			}

			const errorText = result.error || "Failed to resend verification email"
			setResendError(errorText)
			if (result.cooldownSeconds > 0) {
				setResendCooldownSeconds(result.cooldownSeconds)
			}
		} catch (error) {
			logger.error("Resend verification failed", error)
			setResendError("Failed to resend verification email")
		} finally {
			setResendLoading(false)
		}
	}

	let resendButtonText = "Resend verification email"
	if (resendLoading) {
		resendButtonText = "Sending verification email..."
	} else if (resendCooldownSeconds > 0) {
		resendButtonText = `Resend available in ${resendCooldownSeconds}s`
	}

	return (
		<AuthPageShell title="Welcome Back" description="Sign in to your account to continue">
			<form onSubmit={handleSubmit} className="space-y-6">
				{errorMessage && !showResendOption && (
					<div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive animate-in fade-in slide-in-from-top-2">
						<AlertCircle className="mt-0.5 size-4 shrink-0" />
						<span>{errorMessage}</span>
					</div>
				)}

				{successMessage && (
					<div className="flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary animate-in fade-in slide-in-from-top-2">
						<CheckCircle2 className="mt-0.5 size-4 shrink-0" />
						<span>{successMessage}</span>
					</div>
				)}

				<div className="space-y-2">
					<label htmlFor="email" className="block text-sm font-medium text-foreground">
						Email Address
					</label>
					<div className="relative">
						<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
							<Mail className="size-5  text-muted-foreground" />
						</div>
						<input
							id="email"
							type="email"
							value={email}
							onChange={(e) => {
								setEmail(e.target.value)
								if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
							}}
							className={`block w-full pl-10 pr-3 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
								errors.email
									? "border-destructive/50 focus:ring-destructive bg-destructive/5"
									: "border-border focus:ring-ring hover:border-border/80"
							}`}
							placeholder="Enter your email"
						/>
					</div>
					{errors.email && <p className="text-destructive text-xs mt-1">{errors.email}</p>}
				</div>

				<div className="space-y-2">
					<label htmlFor="password" className="block text-sm font-medium text-foreground">
						Password
					</label>
					<div className="relative">
						<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
							<Lock className="size-5  text-muted-foreground" />
						</div>
						<input
							id="password"
							type={showPassword ? "text" : "password"}
							value={password}
							onChange={(e) => {
								setPassword(e.target.value)
								if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
							}}
							className={`block w-full pl-10 pr-12 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
								errors.password
									? "border-destructive/50 focus:ring-destructive bg-destructive/5"
									: "border-border focus:ring-ring hover:border-border/80"
							}`}
							placeholder="Enter your password"
						/>
						<button
							type="button"
							onClick={() => setShowPassword(!showPassword)}
							className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground transition-colors"
						>
							{showPassword ? <EyeOff className="size-5 " /> : <Eye className="size-5 " />}
						</button>
					</div>
					{errors.password && <p className="text-destructive text-xs mt-1">{errors.password}</p>}
				</div>

				{!showResendOption && (
					<div className="flex justify-end">
						<button
							type="button"
							onClick={onForgotPassword}
							className="text-sm text-foreground/50 hover:text-foreground font-medium transition-colors"
						>
							Forgot password?
						</button>
					</div>
				)}

				{showResendOption && (
					<div className="flex flex-col items-center justify-center gap-2 py-2 animate-in fade-in slide-in-from-top-2 duration-700">
						<button
							type="button"
							onClick={handleResendVerification}
							disabled={resendLoading || resendCooldownSeconds > 0}
							className="text-sm font-medium text-foreground/80 hover:text-foreground transition-colors disabled:opacity-50"
						>
							{resendLoading ? (
								<span className="opacity-70">Sending verification email...</span>
							) : (
								<span className="border-b border-foreground/20 pb-0.5 hover:border-foreground/60 transition-colors">
									{resendButtonText}
								</span>
							)}
						</button>

						{(resendMessage || resendError) && (
							<p
								className={`text-[10px] tracking-wide ${resendError ? "text-destructive" : "text-emerald-500"} animate-in fade-in font-medium`}
							>
								{resendError || resendMessage}
							</p>
						)}
					</div>
				)}

				<button
					type="submit"
					disabled={isLoading}
					className="w-full bg-linear-to-r from-primary to-primary/90 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-primary/30 hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
				>
					{isLoading ? (
						<div className="flex items-center justify-center">
							<Loader2 className="size-5  animate-spin mr-2" />
							Signing in...
						</div>
					) : (
						"Sign In"
					)}
				</button>

				<div className="relative flex items-center py-2">
					<div className="grow border-t border-border" />
					<span className="shrink mx-4 text-sm text-muted-foreground">or</span>
					<div className="grow border-t border-border" />
				</div>

				<button
					type="button"
					onClick={() => {
						if (showGoogleOAuth) onGoogle()
					}}
					className="w-full flex items-center justify-center gap-3 py-3 px-4 border border-border rounded-xl text-foreground font-medium hover:bg-muted/60 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-all duration-200"
				>
					<svg className="size-5 " viewBox="0 0 24 24" role="img" aria-label="Google logo">
						<path
							fill="#4285F4"
							d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
						/>
						<path
							fill="#34A853"
							d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
						/>
						<path
							fill="#FBBC05"
							d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
						/>
						<path
							fill="#EA4335"
							d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
						/>
					</svg>
					Continue with Google
				</button>

				<div className="text-center pt-4">
					<p className="text-sm text-muted-foreground">
						Don't have an account?{" "}
						<button
							type="button"
							onClick={onSignUp}
							className="text-primary hover:text-primary/80 font-medium transition-colors"
						>
							Sign up
						</button>
					</p>
				</div>
			</form>
		</AuthPageShell>
	)
}

export default LoginForm
