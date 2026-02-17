import { useState } from "react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ExternalLink, ChevronRight } from "lucide-react"

export function UrlList({ urls, emptyText = "None found" }: { urls: string[], emptyText?: string }) {
  const [open, setOpen] = useState(false)
  const hasUrls = urls && urls.length > 0

  if (!hasUrls) {
    return <p className="text-sm text-muted-foreground pl-7">{emptyText}</p>
  }

  if (urls.length <= 3) {
    return (
      <ul className="space-y-1 pl-7">
        {urls.map((url, i) => (
          <li key={i} className="text-sm text-muted-foreground break-all flex items-center gap-1.5">
            <a href={url} target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">
              {url}
            </a>
            <ExternalLink className="size-3 shrink-0 text-muted-foreground/50" />
          </li>
        ))}
      </ul>
    )
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <ul className="space-y-1 pl-7">
        {urls.slice(0, 2).map((url, i) => (
          <li key={i} className="text-sm text-muted-foreground break-all flex items-center gap-1.5">
            <a href={url} target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">
              {url}
            </a>
            <ExternalLink className="size-3 shrink-0 text-muted-foreground/50" />
          </li>
        ))}
      </ul>
      <CollapsibleContent>
        <ul className="space-y-1 pl-7 mt-1">
          {urls.slice(2).map((url, i) => (
            <li key={i} className="text-sm text-muted-foreground break-all flex items-center gap-1.5">
              <a href={url} target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">
                {url}
              </a>
              <ExternalLink className="size-3 shrink-0 text-muted-foreground/50" />
            </li>
          ))}
        </ul>
      </CollapsibleContent>
      <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground pl-7 mt-1.5 flex items-center gap-1 transition-colors">
        <ChevronRight className={`size-3 transition-transform ${open ? "rotate-90" : ""}`} />
        {open ? "Show less" : `${urls.length - 2} more`}
      </CollapsibleTrigger>
    </Collapsible>
  )
}
