import { AlertCircle, CheckCircle2, Loader2, MailCheck } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { LoginHeader } from "@/components/header/LoginHeader"
import AuthPageShell from "@/features/auth/components/AuthPageShell"
import { api } from "@/lib/apiClient"

function VerifyEmailPage() {
	const [searchParams] = useSearchParams()
	const token = searchParams.get("token") || ""
	const navigate = useNavigate()

	const [isVerifying, setIsVerifying] = useState(false)
	const [error, setError] = useState("")
	const [successMessage, setSuccessMessage] = useState("")

	useEffect(() => {
		let isMounted = true

		const verify = async () => {
			if (!token) {
				setError("Missing verification token. Please use the link from your email.")
				return
			}

			setIsVerifying(true)
			setError("")
			setSuccessMessage("")

			try {
				const response = await api.post("/auth/verify", { token })
				if (!isMounted) return
				setSuccessMessage(response?.message || "Email verified")
			} catch (requestError) {
				if (!isMounted) return
				setError(requestError?.data?.detail || "Verification link is invalid or expired")
			} finally {
				if (isMounted) {
					setIsVerifying(false)
				}
			}
		}

		verify()

		return () => {
			isMounted = false
		}
	}, [token])

	return (
		<>
			<LoginHeader />
			<AuthPageShell
				title="Verify your email"
				description="We are confirming your account now."
				icon={<MailCheck className="size-6" />}
				contentClassName="px-8 pb-8 space-y-5"
			>
				{isVerifying && (
					<div className="flex items-center gap-2 rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
						<Loader2 className="size-4 animate-spin" />
						<span>Verifying your email...</span>
					</div>
				)}

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

				<button
					type="button"
					onClick={() => navigate("/auth")}
					className="w-full bg-linear-to-r from-primary to-primary/90 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-primary/30 hover:from-primary/90 hover:to-primary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
				>
					Continue to sign in
				</button>
			</AuthPageShell>
		</>
	)
}

export default VerifyEmailPage
