import { ArrowUpDown, BookOpen, CalendarDays, Clock, FileText, Search, SlidersHorizontal, Youtube } from "lucide-react"

import { Button } from "@/components/Button"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/Popover"
import { RadioGroup, RadioGroupItem } from "@/components/RadioGroup"
import { Separator } from "@/components/Separator"

function FilterPopover({
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
}) {
	const getIcon = (iconName) => {
		switch (iconName) {
			case "Search": {
				return Search
			}
			case "BookOpen": {
				return BookOpen
			}
			case "Youtube": {
				return Youtube
			}
			case "FileText": {
				return FileText
			}
			case "Clock": {
				return Clock
			}
			case "CalendarDays": {
				return CalendarDays
			}
			case "ArrowUpDown": {
				return ArrowUpDown
			}
			default: {
				return Search
			}
		}
	}
	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button variant="outline" size="sm" className="flex items-center gap-1">
					<SlidersHorizontal className="size-3.5  mr-1" />
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
									<Label htmlFor={`filter-${option.id}`} className="flex items-center cursor-pointer">
										{(() => {
											const Icon = getIcon(option.icon)
											return <Icon className="size-4  mr-2" />
										})()}
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
								<Label htmlFor="archive-active" className="cursor-pointer">
									Active Content
								</Label>
							</div>
							<div className="flex items-center space-x-2">
								<RadioGroupItem value="archived" id="archive-archived" />
								<Label htmlFor="archive-archived" className="cursor-pointer">
									Archived Content
								</Label>
							</div>
							<div className="flex items-center space-x-2">
								<RadioGroupItem value="all" id="archive-all" />
								<Label htmlFor="archive-all" className="cursor-pointer">
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
									<Label htmlFor={`sort-${option.id}`} className="flex items-center cursor-pointer">
										{(() => {
											const Icon = getIcon(option.icon)
											return <Icon className="size-4  mr-2" />
										})()}
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
