import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { WikiReferenceLink } from "./WikiReferenceLink"

function renderWithProviders(ui) {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	})

	return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("WikiReferenceLink", () => {
	afterEach(() => {
		vi.restoreAllMocks()
		vi.unstubAllGlobals()
	})

	it("fetches and renders a Wikipedia preview when opened", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				title: "Leibniz's notation",
				extract: "A notation for derivatives and integrals introduced by Gottfried Wilhelm Leibniz.",
				thumbnail: { source: "https://upload.wikimedia.org/example.png" },
				content_urls: {
					desktop: { page: "https://en.wikipedia.org/wiki/Leibniz%27s_notation" },
				},
			}),
		})

		vi.stubGlobal("fetch", fetchMock)

		renderWithProviders(
			<p>
				<WikiReferenceLink href="wiki:Leibniz's_notation">Leibniz's notation</WikiReferenceLink>
			</p>
		)

		const trigger = screen.getByRole("button", { name: /learn more about leibniz's notation/i })

		fireEvent.focus(trigger)

		expect(await screen.findByRole("heading", { name: "Leibniz's notation" })).toBeInTheDocument()
		expect(
			screen.getByText("A notation for derivatives and integrals introduced by Gottfried Wilhelm Leibniz.")
		).toBeInTheDocument()
		expect(screen.getByRole("img", { name: "Leibniz's notation" })).toHaveAttribute(
			"src",
			"https://upload.wikimedia.org/example.png"
		)
		expect(screen.getByRole("link", { name: "Read on Wikipedia" })).toHaveAttribute(
			"href",
			"https://en.wikipedia.org/wiki/Leibniz%27s_notation"
		)
		expect(fetchMock).toHaveBeenCalledWith(
			expect.stringContaining("/page/summary/Leibniz's_notation"),
			expect.objectContaining({
				headers: { Accept: "application/json" },
				signal: expect.any(AbortSignal),
			})
		)
	})
})
