import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"
import LoginForm from "./LoginForm"
import PasswordResetForm from "./PasswordResetForm"
import SignupForm from "./SignupForm"

const AuthPage = () => {
	const [view, setView] = useState("login") // "login", "signup", "reset"
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")
	const navigate = useNavigate()
	const [searchParams] = useSearchParams()
	const authContext = useAuth()
	const { login, signup, isAuthenticated } = authContext

	// Debug logging
	useEffect(() => {}, [])

	// Get redirect URL from query params
	const redirectUrl = searchParams.get("redirect") || "/"

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

	const handleSignup = async (email, password, username) => {
		setError("")
		setSuccessMessage("")
		const result = await signup(email, password, username)

		if (result.success) {
			if (result.emailConfirmationRequired) {
				setSuccessMessage(result.message)
				// Optionally switch to login form after showing message
				setTimeout(() => {
					setView("login")
					setSuccessMessage("")
				}, 5000)
			} else {
				navigate(redirectUrl)
			}
		} else {
			setError(result.error)
		}
	}

	return (
		<>
			{error && (
				<div className="fixed top-4 right-4 bg-destructive text-destructive-foreground px-4 py-2 rounded-lg shadow-lg animate-slideDown z-50">
					{error}
				</div>
			)}

			{successMessage && (
				<div className="fixed top-4 right-4 bg-primary text-primary-foreground px-4 py-2 rounded-lg shadow-lg animate-slideDown z-50">
					{successMessage}
				</div>
			)}

			{view === "login" && (
				<LoginForm
					onSignUp={() => setView("signup")}
					onForgotPassword={() => setView("reset")}
					onSubmit={handleLogin}
				/>
			)}

			{view === "signup" && <SignupForm onSignIn={() => setView("login")} onSubmit={handleSignup} />}

			{view === "reset" && <PasswordResetForm onBack={() => setView("login")} />}
		</>
	)
}

export default AuthPage
