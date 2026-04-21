import { Loader2 } from "lucide-react"
import { useId, useState } from "react"
import { useNavigate } from "react-router-dom"
import { changePassword, deleteAccount } from "@/api/authApi"
import { Button } from "@/components/Button"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Separator } from "@/components/Separator"
import { useAuth } from "@/hooks/use-auth"

export function AccountTab() {
	const { user } = useAuth()
	const navigate = useNavigate()
	const [isChangingPassword, setIsChangingPassword] = useState(false)
	const [isDeleting, setIsDeleting] = useState(false)
	const [currentPassword, setCurrentPassword] = useState("")
	const [newPassword, setNewPassword] = useState("")
	const [confirmPassword, setConfirmPassword] = useState("")
	const [error, setError] = useState("")
	const [success, setSuccess] = useState("")
	const currentPasswordId = useId()
	const newPasswordId = useId()
	const confirmPasswordId = useId()

	const handlePasswordChange = async (e) => {
		e.preventDefault()
		setError("")
		setSuccess("")

		if (newPassword !== confirmPassword) {
			setError("New passwords do not match")
			return
		}

		if (newPassword.length < 8) {
			setError("New password must be at least 8 characters")
			return
		}

		setIsChangingPassword(true)
		try {
			await changePassword(currentPassword, newPassword)
			setSuccess("Password updated. Please sign in again.")
			setCurrentPassword("")
			setNewPassword("")
			setConfirmPassword("")
			setTimeout(() => {
				navigate("/auth")
			}, 2000)
		} catch (err) {
			setError(err.data?.detail || err.message || "Failed to change password")
		} finally {
			setIsChangingPassword(false)
		}
	}

	const handleDeleteAccount = async () => {
		if (!window.confirm("Are you sure you want to delete your account? This action cannot be undone.")) {
			return
		}
		if (!window.confirm("This will permanently delete all your data. Type 'DELETE' to confirm.")) {
			return
		}

		setIsDeleting(true)
		try {
			await deleteAccount()
			navigate("/auth")
		} catch (err) {
			setError(err.data?.detail || err.message || "Failed to delete account")
			setIsDeleting(false)
		}
	}

	return (
		<div className="space-y-8">
			<div>
				<h2 className="text-lg font-semibold mb-1">Account</h2>
				<p className="text-sm text-muted-foreground">Manage your account settings and security</p>
			</div>

			<div className="space-y-4">
				<div className="grid gap-2">
					<Label className="text-muted-foreground">Email</Label>
					<div className="text-sm">{user?.email}</div>
				</div>
				{user?.username && (
					<div className="grid gap-2">
						<Label className="text-muted-foreground">Username</Label>
						<div className="text-sm">{user.username}</div>
					</div>
				)}
			</div>

			<Separator />

			<form onSubmit={handlePasswordChange} className="space-y-4">
				<div>
					<h3 className="font-medium mb-1">Change Password</h3>
					<p className="text-sm text-muted-foreground mb-4">Update your password to keep your account secure</p>
				</div>

				{error && (
					<div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
						{error}
					</div>
				)}
				{success && (
					<div className="rounded-lg border border-completed/20 bg-completed/10 p-3 text-sm text-completed">
						{success}
					</div>
				)}

				<div className="grid gap-3">
					<div className="grid gap-2">
						<Label htmlFor={currentPasswordId}>Current Password</Label>
						<Input
							id={currentPasswordId}
							type="password"
							value={currentPassword}
							onChange={(e) => setCurrentPassword(e.target.value)}
							placeholder="Enter current password"
							required
							className="h-10"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor={newPasswordId}>New Password</Label>
						<Input
							id={newPasswordId}
							type="password"
							value={newPassword}
							onChange={(e) => setNewPassword(e.target.value)}
							placeholder="Enter new password"
							required
							minLength={8}
							className="h-10"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor={confirmPasswordId}>Confirm New Password</Label>
						<Input
							id={confirmPasswordId}
							type="password"
							value={confirmPassword}
							onChange={(e) => setConfirmPassword(e.target.value)}
							placeholder="Confirm new password"
							required
							className="h-10"
						/>
					</div>
				</div>

				<Button type="submit" disabled={isChangingPassword || !currentPassword || !newPassword || !confirmPassword}>
					{isChangingPassword ? <Loader2 className="size-4 animate-spin" /> : "Update Password"}
				</Button>
			</form>

			<Separator />

			<div className="space-y-4">
				<div>
					<h3 className="font-medium text-destructive mb-1">Delete Account</h3>
					<p className="text-sm text-muted-foreground">Permanently delete your account and all associated data</p>
				</div>
				<Button variant="destructive" onClick={handleDeleteAccount} disabled={isDeleting}>
					{isDeleting ? <Loader2 className="size-4 animate-spin" /> : "Delete Account"}
				</Button>
			</div>
		</div>
	)
}
