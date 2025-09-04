import { Eye, EyeOff, Loader2, Lock, Mail } from "lucide-react"
import React, { useState } from "react"

function LoginForm({
	onSignUp = () => {},
	onForgotPassword = () => {},
	onSubmit = async (_email, _password) => {
		await new Promise((resolve) => setTimeout(resolve, 2000))
	},
}) {
	const [email, setEmail] = useState("")
	const [password, setPassword] = useState("")
	const [showPassword, setShowPassword] = useState(false)
	const [isLoading, setIsLoading] = useState(false)
	const [errors, setErrors] = useState({})
	const [mounted, setMounted] = useState(false)

	React.useEffect(() => {
		setMounted(true)
	}, [])

	const validateEmail = (email) => {
		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
		return emailRegex.test(email)
	}

	const validateForm = () => {
		const newErrors = {}

		if (!email) {
			newErrors.email = "Email is required"
		} else if (!validateEmail(email)) {
			newErrors.email = "Please enter a valid email address"
		}

		if (!password) {
			newErrors.password = "Password is required"
		} else if (password.length < 6) {
			newErrors.password = "Password must be at least 6 characters"
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
		} catch (_error) {
		} finally {
			setIsLoading(false)
		}
	}

	if (!mounted) return null

	return (
		<div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-emerald-50 via-white to-emerald-50 p-4">
			<div className="w-full max-w-md bg-white rounded-2xl shadow-2xl shadow-emerald-100/50 border border-emerald-100 overflow-hidden transform transition-all duration-500 hover:shadow-xl hover:shadow-emerald-200/30 animate-slideUp">
				{/* Header */}
				<div className="px-8 pt-8 pb-6 text-center">
					<h1 className="text-2xl font-bold text-gray-900 mb-2">Welcome Back</h1>
					<p className="text-gray-100-foreground text-sm">Sign in to your account to continue</p>
				</div>

				{/* Form */}
				<div className="px-8 pb-8">
					<form onSubmit={handleSubmit} className="space-y-6">
						{/* Email Field */}
						<div className="space-y-2">
							<label htmlFor="email" className="block text-sm font-medium text-gray-900">
								Email Address
							</label>
							<div className="relative">
								<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
									<Mail className="h-5 w-5 text-gray-100-foreground" />
								</div>
								<input
									id="email"
									type="email"
									value={email}
									onChange={(e) => {
										setEmail(e.target.value)
										if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
									}}
									className={`block w-full pl-10 pr-3 py-3 border rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
										errors.email
											? "border-red-500/50 focus:ring-red-500 bg-red-500/5"
											: "border-gray-200 focus:ring-green-500 hover:border-gray-200/80"
									}`}
									placeholder="Enter your email"
								/>
							</div>
							{errors.email && <p className="text-red-500 text-xs mt-1 animate-fadeIn">{errors.email}</p>}
						</div>

						{/* Password Field */}
						<div className="space-y-2">
							<label htmlFor="password" className="block text-sm font-medium text-gray-900">
								Password
							</label>
							<div className="relative">
								<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
									<Lock className="h-5 w-5 text-gray-100-foreground" />
								</div>
								<input
									id="password"
									type={showPassword ? "text" : "password"}
									value={password}
									onChange={(e) => {
										setPassword(e.target.value)
										if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
									}}
									className={`block w-full pl-10 pr-12 py-3 border rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
										errors.password
											? "border-red-500/50 focus:ring-red-500 bg-red-500/5"
											: "border-gray-200 focus:ring-green-500 hover:border-gray-200/80"
									}`}
									placeholder="Enter your password"
								/>
								<button
									type="button"
									onClick={() => setShowPassword(!showPassword)}
									className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-100-foreground hover:text-gray-900 transition-colors"
								>
									{showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
								</button>
							</div>
							{errors.password && <p className="text-red-500 text-xs mt-1 animate-fadeIn">{errors.password}</p>}
						</div>

						{/* Forgot Password - Only show in multi-user mode */}
						{import.meta.env.VITE_ENABLE_AUTH === "true" && (
							<div className="flex justify-end">
								<button
									type="button"
									onClick={onForgotPassword}
									className="text-sm text-green-500 hover:text-green-500/80 font-medium transition-colors"
								>
									Forgot password?
								</button>
							</div>
						)}

						{/* Submit Button */}
						<button
							type="submit"
							disabled={isLoading}
							className="w-full bg-gradient-to-r from-green-500 to-green-500/90 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-green-500/20 hover:from-green-500/90 hover:to-green-500/80 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
						>
							{isLoading ? (
								<div className="flex items-center justify-center">
									<Loader2 className="w-5 h-5 animate-spin mr-2" />
									Signing in...
								</div>
							) : (
								"Sign In"
							)}
						</button>

						{/* Divider */}
						<div className="relative flex items-center py-2">
							<div className="flex-grow border-t border-gray-200"></div>
							<span className="flex-shrink mx-4 text-sm text-gray-100-foreground">or</span>
							<div className="flex-grow border-t border-gray-200"></div>
						</div>

						{/* Social Login */}
						<button
							type="button"
							className="w-full flex items-center justify-center gap-3 py-3 px-4 border border-gray-200 rounded-xl text-gray-900 font-medium hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all duration-200"
						>
							<svg className="w-5 h-5" viewBox="0 0 24 24" role="img" aria-label="Google logo">
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

						{/* Sign Up Link */}
						<div className="text-center pt-4">
							<p className="text-sm text-gray-100-foreground">
								Don't have an account?{" "}
								<button
									type="button"
									onClick={onSignUp}
									className="text-green-500 hover:text-green-500/80 font-medium transition-colors"
								>
									Sign up
								</button>
							</p>
						</div>
					</form>
				</div>
			</div>
		</div>
	)
}

export default LoginForm
