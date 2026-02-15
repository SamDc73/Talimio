import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { LoginHeader } from "@/components/header/LoginHeader"
import { useAuthOptions } from "@/features/auth/hooks/use-auth-options"
import { useAuth } from "@/hooks/use-auth"
import { getApiUrl } from "@/lib/apiBase"
import LoginForm from "./components/LoginForm"
import PasswordResetForm from "./components/PasswordResetForm"
import SignupForm from "./components/SignupForm"

function AuthPage() {
	const [view, setView] = useState("login") // "login", "signup", "reset"
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const navigate = useNavigate()
	const [searchParams] = useSearchParams()
	const { login, signup, resendVerification, isAuthenticated } = useAuth()
	const { authOptions } = useAuthOptions()

	// Get redirect URL from query params
	const redirectUrl = searchParams.get("redirect") || "/"

	const switchView = (nextView) => {
		setError("")
		setSuccessMessage("")
		setView(nextView)
	}

	// If already authenticated, redirect immediately
	useEffect(() => {
		if (isAuthenticated) {
			navigate(redirectUrl)
		}
	}, [isAuthenticated, navigate, redirectUrl])

	const handleLogin = async (email, password) => {
		setError("")
		setSuccessMessage("")
		const result = await login(email, password)

		if (result.success) {
			navigate(redirectUrl)
		} else {
			setError(result.error)
		}
	}

	const handleSignup = async (fullName, email, password, username) => {
		setError("")
		setSuccessMessage("")
		const result = await signup(fullName, email, password, username)

		if (result.success) {
			if (result.emailConfirmationRequired) {
				setSuccessMessage(result.message)
				setTimeout(() => {
					switchView("login")
					setSuccessMessage("")
				}, 5000)
			} else {
				navigate(redirectUrl)
			}
		} else {
			setError(result.error)
		}
	}

	const handleGoogleOAuth = () => {
		window.location.href = getApiUrl("/auth/google/authorize")
	}

	const showGoogleOAuth = Boolean(authOptions?.googleOauthAvailable)

	return (
		<>
			<LoginHeader />

			{view === "login" && (
				<LoginForm
					onSignUp={() => switchView("signup")}
					onForgotPassword={() => switchView("reset")}
					onSubmit={handleLogin}
					showGoogleOAuth={showGoogleOAuth}
					onGoogle={handleGoogleOAuth}
					errorMessage={error}
					successMessage={successMessage}
					onResendVerification={resendVerification}
				/>
			)}

			{view === "signup" && (
				<SignupForm
					onSignIn={() => switchView("login")}
					onSubmit={handleSignup}
					showGoogleOAuth={showGoogleOAuth}
					onGoogle={handleGoogleOAuth}
					errorMessage={error}
					successMessage={successMessage}
					passwordPolicy={authOptions?.passwordPolicy}
				/>
			)}

			{view === "reset" && <PasswordResetForm onBack={() => switchView("login")} />}
		</>
	)
}

export default AuthPage
