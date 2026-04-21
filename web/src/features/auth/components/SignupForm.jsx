import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, Lock, Mail, User } from "lucide-react"
import { useId, useState } from "react"
import { GoogleMark } from "@/components/GoogleMark"
import AuthPageShell from "@/features/auth/components/AuthPageShell"
import PasswordStrengthMeter from "@/features/auth/components/PasswordStrengthMeter"
import { isValidEmail } from "@/features/auth/emailValidation"
import { getPasswordPolicyValidationMessage } from "@/features/auth/passwordPolicy"
import logger from "@/lib/logger"
import { getPasswordStrength } from "../passwordStrength"

const REQUIRED_FIELD_MESSAGE = "This field is required"
const USERNAME_MIN_LENGTH = 5
const USERNAME_MAX_LENGTH = 24
const USERNAME_ALLOWED_CHARS_PATTERN = /^[a-zA-Z0-9._]+$/
const USERNAME_START_END_PATTERN = /^[a-zA-Z0-9].*[a-zA-Z0-9]$/

function SignupForm({
	onSignIn = () => {},
	onSubmit = async (_fullName, _email, _password, _username) => {},
	showGoogleOAuth = false,
	onGoogle = () => {},
	errorMessage = "",
	successMessage = "",
	passwordPolicy = null,
}) {
	const [fullName, setFullName] = useState("")
	const [email, setEmail] = useState("")
	const [password, setPassword] = useState("")
	const [username, setUsername] = useState("")
	const [showPassword, setShowPassword] = useState(false)
	const [isLoading, setIsLoading] = useState(false)
	const [errors, setErrors] = useState({})
	const passwordStrength = getPasswordStrength(password, [fullName, email, username])
	const fullNameId = useId()
	const usernameId = useId()
	const emailId = useId()
	const passwordId = useId()

	const validateUsername = (value) => {
		if (!value) {
			return
		}

		if (value.length < USERNAME_MIN_LENGTH) {
			return `Username must be at least ${USERNAME_MIN_LENGTH} characters`
		}
		if (value.length > USERNAME_MAX_LENGTH) {
			return `Username must be at most ${USERNAME_MAX_LENGTH} characters`
		}
		if (!USERNAME_ALLOWED_CHARS_PATTERN.test(value)) {
			return "Username can only contain letters, numbers, underscores, and periods"
		}
		if (!USERNAME_START_END_PATTERN.test(value)) {
			return "Username must start and end with a letter or number"
		}
		if (value.includes("..") || value.includes("__")) {
			return "Username cannot contain repeated separators"
		}
	}

	const validateForm = () => {
		const newErrors = {}
		const normalizedFullName = fullName.trim()
		const normalizedUsername = username.trim()

		if (!normalizedFullName) {
			newErrors.fullName = "Full name is required"
		}

		if (!email) {
			newErrors.email = "Email is required"
		} else if (!isValidEmail(email)) {
			newErrors.email = "Please enter a valid email address"
		}

		if (password) {
			const passwordValidationMessage = getPasswordPolicyValidationMessage(password, passwordPolicy)
			if (passwordValidationMessage) {
				newErrors.password = passwordValidationMessage
			}
		} else {
			newErrors.password = REQUIRED_FIELD_MESSAGE
		}

		const usernameError = validateUsername(normalizedUsername)
		if (usernameError) {
			newErrors.username = usernameError
		}

		setErrors(newErrors)
		return Object.keys(newErrors).length === 0
	}

	const handleSubmit = async (e) => {
		e.preventDefault()

		if (!validateForm()) return

		setIsLoading(true)
		try {
			await onSubmit(fullName.trim(), email, password, username.trim())
		} catch (error) {
			logger.error("Signup failed", error)
		} finally {
			setIsLoading(false)
		}
	}

	return (
		<AuthPageShell title="Create Account" description="Sign up to start learning">
			<form onSubmit={handleSubmit} className="space-y-6">
				{errorMessage && (
					<div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
						<AlertCircle className="mt-0.5 size-4 shrink-0" />
						<span>{errorMessage}</span>
					</div>
				)}

				{successMessage && (
					<div className="flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
						<CheckCircle2 className="mt-0.5 size-4 shrink-0" />
						<span>{successMessage}</span>
					</div>
				)}

				<div className="space-y-2">
					<label htmlFor={fullNameId} className="block text-sm font-medium text-foreground">
						Full Name
					</label>
					<div className="relative">
						<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
							<User className="size-5 text-muted-foreground" />
						</div>
						<input
							id={fullNameId}
							type="text"
							value={fullName}
							onChange={(e) => {
								setFullName(e.target.value)
								if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: undefined }))
							}}
							className={`block w-full pl-10 pr-3 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
								errors.fullName
									? "border-destructive/50 focus:ring-destructive bg-destructive/5"
									: "border-border focus:ring-ring hover:border-border/80"
							}`}
							placeholder="Enter your full name"
						/>
					</div>
					{errors.fullName && <p className="text-destructive text-xs mt-1">{errors.fullName}</p>}
				</div>

				<div className="space-y-2">
					<label htmlFor={usernameId} className="block text-sm font-medium text-foreground">
						Username (Optional)
					</label>
					<div className="relative">
						<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
							<User className="size-5 text-muted-foreground" />
						</div>
						<input
							id={usernameId}
							type="text"
							value={username}
							onChange={(e) => {
								setUsername(e.target.value)
								if (errors.username) setErrors((prev) => ({ ...prev, username: undefined }))
							}}
							className={`block w-full pl-10 pr-3 py-3 border rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
								errors.username
									? "border-destructive/50 focus:ring-destructive bg-destructive/5"
									: "border-border focus:ring-ring hover:border-border/80"
							}`}
							placeholder="Leave blank to auto-generate"
						/>
					</div>
					{errors.username && <p className="text-destructive text-xs mt-1">{errors.username}</p>}
				</div>

				<div className="space-y-2">
					<label htmlFor={emailId} className="block text-sm font-medium text-foreground">
						Email Address
					</label>
					<div className="relative">
						<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
							<Mail className="size-5 text-muted-foreground" />
						</div>
						<input
							id={emailId}
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
					<label htmlFor={passwordId} className="block text-sm font-medium text-foreground">
						Password
					</label>
					<div className="relative">
						<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
							<Lock className="size-5 text-muted-foreground" />
						</div>
						<input
							id={passwordId}
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
							placeholder="Create a password"
							autoComplete="new-password"
						/>
						<button
							type="button"
							onClick={() => setShowPassword(!showPassword)}
							className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground transition-colors hover:text-foreground"
						>
							{showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
						</button>
					</div>
					{errors.password && <p className="text-destructive text-xs mt-1">{errors.password}</p>}
					<PasswordStrengthMeter passwordStrength={passwordStrength} />
				</div>

				<button
					type="submit"
					disabled={isLoading}
					className="w-full rounded-xl bg-linear-to-r from-primary to-primary/90 px-4 py-3 font-semibold text-primary-foreground shadow-lg shadow-primary/30 transition-all duration-200 hover:scale-[1.02] hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
				>
					{isLoading ? (
						<div className="flex items-center justify-center">
							<Loader2 className="mr-2 size-5 animate-spin" />
							Creating account...
						</div>
					) : (
						"Create Account"
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
					className="flex w-full items-center justify-center gap-3 rounded-xl border border-border px-4 py-3 font-medium text-foreground transition-all duration-200 hover:bg-muted/60 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
				>
					<GoogleMark className="size-5" />
					Sign up with Google
				</button>

				<div className="text-center pt-4">
					<p className="text-sm text-muted-foreground">
						Already have an account?{" "}
						<button
							type="button"
							onClick={onSignIn}
							className="text-primary hover:text-primary/80 font-medium transition-colors"
						>
							Sign in
						</button>
					</p>
				</div>
			</form>
		</AuthPageShell>
	)
}

export default SignupForm
