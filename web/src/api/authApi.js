import { api } from "@/lib/apiClient"

export async function changePassword(currentPassword, newPassword) {
	return api.post("/auth/change-password", {
		current_password: currentPassword,
		new_password: newPassword,
	})
}

export async function deleteAccount() {
	return api.delete("/auth/account")
}
