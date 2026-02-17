import { Link } from "@inertiajs/react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  CircleCheck,
  CircleX,
  CircleMinus,
  ShieldAlert,
  ShieldOff,
} from "lucide-react"
import type { Publisher, Permission } from "@/datatable/columns"

function permissionLabel(status: Permission["permission"]) {
  switch (status) {
    case "explicitly_permitted":
      return "Permitted"
    case "explicitly_prohibited":
      return "Prohibited"
    case "conditional_ambiguous":
      return "Conditional"
  }
}

function StatusRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  )
}

export function PublisherSheet({ publisher }: { publisher: Publisher }) {
  const permissions = publisher.tos_permissions ?? []
  const permitted = permissions.filter(p => p.permission === "explicitly_permitted").length
  const prohibited = permissions.filter(p => p.permission === "explicitly_prohibited").length
  const conditional = permissions.filter(p => p.permission === "conditional_ambiguous").length

  const bots = publisher.ai_bot_blocks
  const botEntries = bots ? Object.entries(bots) : []
  const blockedCount = botEntries.filter(([, b]) => b.blocked).length

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">Quick View</Button>
      </SheetTrigger>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{publisher.name}</SheetTitle>
          <SheetDescription>{publisher.domain}</SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-4">
          {/* WAF */}
          <div>
            <h4 className="text-sm font-medium mb-2">WAF Detection</h4>
            {publisher.waf_detected ? (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
                <ShieldAlert className="size-4 text-amber-600 shrink-0" />
                <span className="text-sm font-medium text-amber-900">{publisher.waf_type || "Detected"}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
                <ShieldOff className="size-4 text-muted-foreground shrink-0" />
                <span className="text-sm text-muted-foreground">No WAF detected</span>
              </div>
            )}
          </div>

          <Separator />

          {/* ToS */}
          <div>
            <h4 className="text-sm font-medium mb-2">Terms of Service</h4>
            {publisher.tos_url ? (
              <StatusRow
                label="URL"
                value={
                  <a href={publisher.tos_url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate max-w-[200px] inline-block">
                    View ToS
                  </a>
                }
              />
            ) : (
              <StatusRow label="URL" value={<span className="text-muted-foreground">Not found</span>} />
            )}
            {permissions.length > 0 && (
              <div className="mt-2 space-y-1">
                <StatusRow label="Permitted" value={permitted} />
                <StatusRow label="Prohibited" value={prohibited} />
                <StatusRow label="Conditional" value={conditional} />
              </div>
            )}
          </div>

          <Separator />

          {/* Robots.txt + AI Bot Blocking */}
          <div>
            <h4 className="text-sm font-medium mb-2">Robots.txt</h4>
            {publisher.robots_txt_found === null ? (
              <p className="text-sm text-muted-foreground">Not yet checked</p>
            ) : !publisher.robots_txt_found ? (
              <p className="text-sm text-muted-foreground">No robots.txt found</p>
            ) : (
              <>
                <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 mb-3">
                  <CircleCheck className="size-4 text-emerald-600 shrink-0" />
                  <span className="text-sm">robots.txt found</span>
                </div>
                {botEntries.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI Bot Blocking</span>
                      <span className="text-xs text-muted-foreground">{blockedCount}/{botEntries.length} blocked</span>
                    </div>
                    <div className="space-y-0.5">
                      {botEntries.map(([bot, info]) => (
                        <div key={bot} className="flex items-center justify-between py-0.5">
                          <span className="text-sm">
                            {bot} <span className="text-muted-foreground text-xs">({info.company})</span>
                          </span>
                          {info.blocked ? (
                            <CircleX className="size-3.5 text-red-500" />
                          ) : (
                            <CircleMinus className="size-3.5 text-gray-300" />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <Separator />

          {/* Discovery */}
          <div>
            <h4 className="text-sm font-medium mb-2">Discovery</h4>
            <StatusRow
              label="Sitemaps"
              value={publisher.sitemap_urls?.length ?? 0}
            />
            <StatusRow
              label="RSS Feeds"
              value={publisher.rss_urls?.length ?? 0}
            />
            <StatusRow
              label="RSL"
              value={
                publisher.rsl_detected === null
                  ? <span className="text-muted-foreground">Unknown</span>
                  : publisher.rsl_detected ? "Detected" : "None"
              }
            />
          </div>

          <Separator />

          <Button asChild className="w-full">
            <Link href={`/publishers/${publisher.id}`}>View Full Details</Link>
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
