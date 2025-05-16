import { useState } from "react"
import { MoreHorizontal } from "lucide-react"
import { Button } from "@/components/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover"

export function KebabMenu({ onMouseEnter, onMouseLeave, showMenu = false }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="absolute top-3 right-3 z-10" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className={`h-10 w-10 rounded-full shadow-sm flex items-center justify-center transition-opacity duration-200 ${
              showMenu ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-40 p-0" align="end">
          <div className="flex flex-col">
            <Button variant="ghost" size="sm" className="justify-start font-normal">
              Pin
            </Button>
            <Button variant="ghost" size="sm" className="justify-start font-normal">
              Edit Tags
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
