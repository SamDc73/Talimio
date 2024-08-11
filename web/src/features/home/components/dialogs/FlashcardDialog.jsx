import { useState } from "react"

import { Button } from "@/components/button"
import { Input } from "@/components/input"
import { Label } from "@/components/label"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/sheet"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/lib/apiClient"

export function FlashcardDialog({ open, onOpenChange, onDeckCreated }) {
	const { toast } = useToast()
	const [newDeckTitle, setNewDeckTitle] = useState("")
	const [newDeckDescription, setNewDeckDescription] = useState("")
	const [newCards, setNewCards] = useState("")

	const handleCreateDeck = async () => {
		if (!newDeckTitle.trim()) return

		try {
			// Create the deck first
			const deckResponse = await api.post("/flashcards", {
				title: newDeckTitle,
				description: newDeckDescription || "",
			})

			// If cards were provided, add them to the deck
			if (newCards.trim()) {
				const cards = newCards.split("\n").filter((line) => line.trim())
				const cardData = cards.map((line) => {
					const [front, back] = line.split("|").map((s) => s.trim())
					return { front: front || line, back: back || "" }
				})

				if (cardData.length > 0) {
					await api.post(`/flashcards/${deckResponse.id}/cards`, {
						cards: cardData,
					})
				}
			}

			toast({
				title: "Deck Created!",
				description: `"${deckResponse.title}" has been created successfully.`,
			})

			// Reset form
			setNewDeckTitle("")
			setNewDeckDescription("")
			setNewCards("")

			// Close dialog and notify parent
			onOpenChange(false)
			if (onDeckCreated) {
				onDeckCreated(deckResponse)
			}
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to create flashcard deck. Please try again.",
				variant: "destructive",
			})
		}
	}

	const handleClose = () => {
		setNewDeckTitle("")
		setNewDeckDescription("")
		setNewCards("")
		onOpenChange(false)
	}

	return (
		<Sheet open={open} onOpenChange={handleClose}>
			<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
				<SheetHeader>
					<SheetTitle>Create a New Flashcard Deck</SheetTitle>
					<SheetDescription>Create a new deck of flashcards to start studying.</SheetDescription>
				</SheetHeader>
				<div className="py-4">
					<div className="grid gap-4">
						<div className="grid gap-2">
							<Label for="deck-title">Deck Title</Label>
							<Input
								id="deck-title"
								value={newDeckTitle}
								onChange={(e) => setNewDeckTitle(e.target.value)}
								placeholder="e.g. React Hooks"
							/>
						</div>
						<div className="grid gap-2">
							<Label for="deck-description">Description</Label>
							<Input
								id="deck-description"
								value={newDeckDescription}
								onChange={(e) => setNewDeckDescription(e.target.value)}
								placeholder="A brief summary of the deck's content"
							/>
						</div>
						<div className="grid gap-2">
							<Label for="new-cards">Cards (Front | Back)</Label>
							<textarea
								id="new-cards"
								value={newCards}
								onChange={(e) => setNewCards(e.target.value)}
								placeholder="useState | Hook for state management
useEffect | Hook for side effects"
								className="w-full h-32 p-2 border rounded-md"
							/>
						</div>
					</div>
				</div>
				<SheetFooter>
					<Button variant="outline" onClick={handleClose}>
						Cancel
					</Button>
					<Button onClick={handleCreateDeck} disabled={!newDeckTitle.trim()}>
						Create Deck
					</Button>
				</SheetFooter>
			</SheetContent>
		</Sheet>
	)
}
