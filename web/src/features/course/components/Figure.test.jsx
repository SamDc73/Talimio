import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Figure } from "@/features/course/components/Figure"
import { MdxRenderer } from "@/features/course/components/MdxRenderer"

describe("Figure", () => {
	afterEach(() => {
		cleanup()
	})

	it("renders the image, caption, and attribution", () => {
		render(
			<Figure
				src="https://upload.wikimedia.org/wikipedia/commons/7/72/neuroplasticity.png"
				caption="Cellular changes underlying neuroplasticity"
				attribution="Rodolfo Gabriel Gatto"
				license="CC BY-SA 4.0"
				sourcePage="https://commons.wikimedia.org/wiki/File:neuroplasticity.png"
			/>
		)

		const image = screen.getByRole("img")
		expect(image).toHaveAttribute("src", "https://upload.wikimedia.org/wikipedia/commons/7/72/neuroplasticity.png")
		expect(image).toHaveAttribute("loading", "lazy")
		// alt falls back to caption when not provided
		expect(image).toHaveAttribute("alt", "Cellular changes underlying neuroplasticity")

		expect(screen.getByText("Cellular changes underlying neuroplasticity")).toBeInTheDocument()
		const attributionLink = screen.getByRole("link", { name: "Rodolfo Gabriel Gatto" })
		expect(attributionLink).toHaveAttribute("href", "https://commons.wikimedia.org/wiki/File:neuroplasticity.png")
		expect(screen.getByText(/CC BY-SA 4\.0/)).toBeInTheDocument()
	})

	it("renders nothing without a src", () => {
		const { container } = render(<Figure caption="orphan caption" />)
		expect(container).toBeEmptyDOMElement()
	})

	it("renders escaped figure props through MDX", async () => {
		render(
			<MdxRenderer
				content={[
					"<Figure",
					'src={"https://upload.wikimedia.org/wikipedia/commons/7/72/neuroplasticity.png"}',
					'alt={"Neuron \\"synapse\\" diagram"}',
					'caption={"A \\"synapse\\" diagram with vesicles"}',
					'attribution={"Photo by \\"Jane Doe\\""}',
					'license={"CC BY 4.0"}',
					'sourcePage={"https://commons.wikimedia.org/wiki/File:neuroplasticity.png"}',
					"/>",
				].join("\n")}
				lessonId="lesson-1"
				courseId="course-1"
			/>
		)

		const image = await screen.findByRole("img", { name: 'Neuron "synapse" diagram' })
		expect(image).toHaveAttribute("src", "https://upload.wikimedia.org/wikipedia/commons/7/72/neuroplasticity.png")
		expect(screen.queryByText("Content Error")).not.toBeInTheDocument()
		expect(screen.getByText('A "synapse" diagram with vesicles')).toBeInTheDocument()
		expect(screen.getByRole("link", { name: 'Photo by "Jane Doe"' })).toHaveAttribute(
			"href",
			"https://commons.wikimedia.org/wiki/File:neuroplasticity.png"
		)
	})
})
