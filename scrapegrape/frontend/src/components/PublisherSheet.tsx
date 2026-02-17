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
            <StatusRow
              label="Status"
              value={publisher.waf_detected ? (publisher.waf_type || "Detected") : "None"}
            />
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

          {/* Robots */}
          <div>
            <h4 className="text-sm font-medium mb-2">Robots.txt</h4>
            <StatusRow
              label="Found"
              value={
                publisher.robots_txt_found === null
                  ? <span className="text-muted-foreground">Unknown</span>
                  : publisher.robots_txt_found ? "Yes" : "No"
              }
            />
            <StatusRow
              label="URL Allowed"
              value={
                publisher.robots_txt_url_allowed === null
                  ? <span className="text-muted-foreground">Unknown</span>
                  : publisher.robots_txt_url_allowed ? "Yes" : "No"
              }
            />
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
