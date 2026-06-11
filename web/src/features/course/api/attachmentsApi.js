/**
 * Course Attachments API - course-to-book links.
 *
 * A course grounds itself in library books through attachment rows.
 * Attaching never copies data; detaching never deletes the book.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/apiClient"

export const attachmentKeys = {
	all: ["course-attachments"],
	list: (courseId) => ["course-attachments", String(courseId)],
}

export async function fetchCourseAttachments(courseId, signal) {
	if (!courseId) throw new Error("Course ID required")
	return api.get(`/courses/${encodeURIComponent(String(courseId))}/attachments`, { signal })
}

export async function attachBooksToCourse(courseId, bookIds) {
	if (!courseId) throw new Error("Course ID required")
	if (!Array.isArray(bookIds) || bookIds.length === 0) {
		throw new Error("At least one book is required")
	}
	return api.post(`/courses/${encodeURIComponent(String(courseId))}/attachments`, { bookIds })
}

export async function detachBookFromCourse(courseId, attachmentId) {
	if (!courseId) throw new Error("Course ID required")
	if (!attachmentId) throw new Error("Attachment ID required")
	return api.delete(
		`/courses/${encodeURIComponent(String(courseId))}/attachments/${encodeURIComponent(String(attachmentId))}`
	)
}

const PROCESSING_STATUSES = new Set(["pending", "processing"])

export function isAttachmentProcessing(attachment) {
	return PROCESSING_STATUSES.has(attachment?.ragStatus)
}

export function useCourseAttachments(courseId) {
	return useQuery({
		queryKey: attachmentKeys.list(courseId),
		queryFn: ({ signal }) => fetchCourseAttachments(courseId, signal),
		enabled: Boolean(courseId),
		// Keep embedding status fresh while any attached book is still processing.
		refetchInterval: (query) => {
			const attachments = query.state.data
			return Array.isArray(attachments) && attachments.some((item) => isAttachmentProcessing(item)) ? 5000 : false
		},
	})
}

export function useAttachBooks(courseId) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (bookIds) => attachBooksToCourse(courseId, bookIds),
		// POST returns the full current list; seed the cache with it directly.
		onSuccess: (attachments) => {
			queryClient.setQueryData(attachmentKeys.list(courseId), attachments)
		},
	})
}

export function useDetachAttachment(courseId) {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (attachmentId) => detachBookFromCourse(courseId, attachmentId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: attachmentKeys.list(courseId) })
		},
	})
}
