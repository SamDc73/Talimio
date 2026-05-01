export const contentKeys = {
	all: ["content"],
	list: (filters) => [...contentKeys.all, "list", filters],
	item: (id) => [...contentKeys.all, "item", id],
}

export const contentQueryHasItem = (data, itemId) => {
	return Boolean(data?.items?.some((item) => item.id === itemId || item.uuid === itemId))
}

export const patchContentItemInCache = (queryClient, itemId, patchItem) => {
	queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => {
		if (!contentQueryHasItem(old, itemId)) return old

		return {
			...old,
			items: old.items.map((item) => (item.id === itemId || item.uuid === itemId ? patchItem(item) : item)),
		}
	})
}
