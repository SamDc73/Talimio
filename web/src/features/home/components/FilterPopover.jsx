import { SlidersHorizontal } from "lucide-react"

import { Button } from "@/components/button"
import { Input } from "@/components/input"
import { Label } from "@/components/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover"
import { RadioGroup, RadioGroupItem } from "@/components/radio-group"
import { Separator } from "@/components/separator"

const FilterPopover = ({
	filterOptions,
	sortOptions,
	activeFilter,
	setActiveFilter,
	archiveFilter,
	setArchiveFilter,
	tagFilter,
	setTagFilter,
	activeSort,
	setActiveSort,
	sortDirection,
	toggleSortDirection,
}) => {
	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button variant="outline" size="sm" className="flex items-center gap-1">
					<SlidersHorizontal className="h-3.5 w-3.5 mr-1" />
					Filters
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-80" align="end">
				<div className="space-y-4">
					<div>
						<h4 className="font-medium mb-2 text-sm">Content Type</h4>
						<RadioGroup value={activeFilter} onValueChange={setActiveFilter} className="flex flex-col gap-2">
							{filterOptions.map((option) => (
								<div key={option.id} className="flex items-center space-x-2">
									<RadioGroupItem value={option.id} id={`filter-${option.id}`} />
									<Label for={`filter-${option.id}`} className="flex items-center cursor-pointer">
										{option.icon}
										{option.label}
									</Label>
								</div>
							))}
						</RadioGroup>
					</div>

					<Separator />

					<div>
						<h4 className="font-medium text-sm mb-2">Archive Status</h4>
						<RadioGroup value={archiveFilter} onValueChange={setArchiveFilter} className="flex flex-col gap-2">
							<div className="flex items-center space-x-2">
								<RadioGroupItem value="active" id="archive-active" />
								<Label for="archive-active" className="cursor-pointer">
									Active Content
								</Label>
							</div>
							<div className="flex items-center space-x-2">
								<RadioGroupItem value="archived" id="archive-archived" />
								<Label for="archive-archived" className="cursor-pointer">
									Archived Content
								</Label>
							</div>
							<div className="flex items-center space-x-2">
								<RadioGroupItem value="all" id="archive-all" />
								<Label for="archive-all" className="cursor-pointer">
									All Content
								</Label>
							</div>
						</RadioGroup>
					</div>

					<Separator />

					<div>
						<h4 className="font-medium text-sm mb-2">Filter by Tag</h4>
						<Input
							placeholder="Filter by tag..."
							value={tagFilter}
							onChange={(e) => setTagFilter(e.target.value)}
							className="text-sm"
						/>
					</div>

					<Separator />

					<div>
						<div className="flex justify-between items-center mb-2">
							<h4 className="font-medium text-sm">Sort By</h4>
							<Button variant="ghost" size="sm" onClick={toggleSortDirection} className="h-8 px-2 text-xs">
								{sortDirection === "desc" ? "Newest First" : "Oldest First"}
							</Button>
						</div>
						<RadioGroup value={activeSort} onValueChange={setActiveSort} className="flex flex-col gap-2">
							{sortOptions.map((option) => (
								<div key={option.id} className="flex items-center space-x-2">
									<RadioGroupItem value={option.id} id={`sort-${option.id}`} />
									<Label for={`sort-${option.id}`} className="flex items-center cursor-pointer">
										{option.icon}
										{option.label}
									</Label>
								</div>
							))}
						</RadioGroup>
					</div>
				</div>
			</PopoverContent>
		</Popover>
	)
}

export default FilterPopover
