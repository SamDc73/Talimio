import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import LoginForm from "./LoginForm";
import SignupForm from "./SignupForm";

const AuthPage = () => {
	const [isLogin, setIsLogin] = useState(true);
	const [error, setError] = useState("");
	const [successMessage, setSuccessMessage] = useState("");
	const navigate = useNavigate();
	const { login, signup } = useAuth();

	const handleLogin = async (email, password) => {
		setError("");
		setSuccessMessage("");
		const result = await login(email, password);

		if (result.success) {
			navigate("/");
		} else {
			setError(result.error);
		}
	};

	const handleSignup = async (email, password, username) => {
		setError("");
		setSuccessMessage("");
		const result = await signup(email, password, username);

		if (result.success) {
			if (result.emailConfirmationRequired) {
				setSuccessMessage(result.message);
				// Optionally switch to login form after showing message
				setTimeout(() => {
					setIsLogin(true);
					setSuccessMessage("");
				}, 5000);
			} else {
				navigate("/");
			}
		} else {
			setError(result.error);
		}
	};

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

			{isLogin ? (
				<LoginForm onSignUp={() => setIsLogin(false)} onSubmit={handleLogin} />
			) : (
				<SignupForm onSignIn={() => setIsLogin(true)} onSubmit={handleSignup} />
			)}
		</>
	);
};

export default AuthPage;
