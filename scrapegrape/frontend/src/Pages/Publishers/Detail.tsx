import { Link } from "@inertiajs/react"
import { useState } from "react"
import AppLayout from "@/Layouts/AppLayout"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  CircleCheck,
  CircleX,
  CircleAlert,
  Shield,
  FileText,
  Bot,
  Map,
  Rss,
  ExternalLink,
  ChevronRight,
  Globe,
  Clock,
  Zap,
  Scale,
  FileCode,
} from "lucide-react"
import type { ReactNode } from "react"

interface ArticleData {
  id: string
  article_url: string
  has_jsonld: boolean
  has_opengraph: boolean
  has_microdata: boolean
  has_twitter_cards: boolean
  paywall_status: string
  metadata_profile: string
  created_at: string
}

type Permission = {
  notes: string
  activity: string
  permission: "explicitly_permitted" | "explicitly_prohibited" | "conditional_ambiguous"
}

interface PublisherData {
  id: number
  name: string
  domain: string
  url: string
  waf_detected: boolean
  waf_type: string
  tos_url: string
  tos_permissions: Permission[] | null
  robots_txt_found: boolean | null
  sitemap_urls: string[]
  rss_urls: string[]
  rsl_detected: boolean | null
  ai_bot_blocks: Record<string, { company: string; blocked: boolean }> | null
  fetch_strategy: string
  last_checked_at: string | null
}

function PermissionStatus({ permission }: { permission: Permission["permission"] }) {
  switch (permission) {
    case "explicitly_permitted":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleCheck className="size-4 text-emerald-600" />
          Permitted
        </span>
      )
    case "explicitly_prohibited":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleX className="size-4 text-red-500" />
          Prohibited
        </span>
      )
    case "conditional_ambiguous":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleAlert className="size-4 text-amber-500" />
          Conditional
        </span>
      )
  }
}

function StatusIndicator({ label, value, icon: Icon, tooltip }: {
  label: string
  value: string
  icon: React.ElementType
  tooltip?: string
}) {
  const content = (
    <div className="flex items-center gap-3 py-3 px-4">
      <Icon className="size-4 text-muted-foreground shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium truncate">{value}</p>
      </div>
    </div>
  )

  if (!tooltip) return content

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          {content}
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function UrlList({ urls, emptyText = "None found" }: { urls: string[], emptyText?: string }) {
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

function FormatBadge({ label, present }: { label: string; present: boolean }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${present ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-400'}`}>
      {label}
    </span>
  )
}

function PaywallBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    free: 'bg-emerald-50 text-emerald-700',
    paywalled: 'bg-red-50 text-red-700',
    metered: 'bg-amber-50 text-amber-700',
    unknown: 'bg-gray-100 text-gray-500',
  }
  const labels: Record<string, string> = {
    free: 'Free',
    paywalled: 'Paywalled',
    metered: 'Metered',
    unknown: 'Unknown',
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {labels[status] ?? status}
    </span>
  )
}

function Detail({ publisher, articles = [] }: { publisher: PublisherData; articles?: ArticleData[] }) {
  const permissions = publisher.tos_permissions ?? []
  const permitted = permissions.filter(p => p.permission === "explicitly_permitted").length
  const prohibited = permissions.filter(p => p.permission === "explicitly_prohibited").length

  return (
    <div className="container mx-auto py-10 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground mb-8">
        <Link href="/" className="hover:text-foreground transition-colors">Publishers</Link>
        <ChevronRight className="size-3" />
        <span className="text-foreground">{publisher.name}</span>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">{publisher.name}</h1>
        <div className="flex items-center gap-3 mt-2">
          <a
            href={`https://${publisher.domain}`}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
          >
            <Globe className="size-3.5" />
            {publisher.domain}
          </a>
          {publisher.fetch_strategy && (
            <>
              <span className="text-border">|</span>
              <span className="text-muted-foreground inline-flex items-center gap-1.5">
                <Zap className="size-3.5" />
                {publisher.fetch_strategy}
              </span>
            </>
          )}
          {publisher.last_checked_at && (
            <>
              <span className="text-border">|</span>
              <span className="text-muted-foreground inline-flex items-center gap-1.5">
                <Clock className="size-3.5" />
                {new Date(publisher.last_checked_at).toLocaleDateString()}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Status overview */}
      <Card className="mb-6">
        <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-gray-300">
          <StatusIndicator
            icon={Shield}
            label="WAF"
            value={publisher.waf_detected ? (publisher.waf_type || "Detected") : "None"}
            tooltip={publisher.waf_detected ? "Web Application Firewall detected" : "No WAF detected"}
          />
          <StatusIndicator
            icon={Bot}
            label="Robots.txt"
            value={
              publisher.robots_txt_found === null
                ? "Unknown"
                : publisher.robots_txt_found
                  ? "Found"
                  : "Not found"
            }
          />
          <StatusIndicator
            icon={FileText}
            label="ToS"
            value={
              permissions.length === 0
                ? "Unknown"
                : prohibited > 0
                  ? `${prohibited} prohibited`
                  : `${permitted} permitted`
            }
          />
          <StatusIndicator
            icon={Scale}
            label="RSL"
            value={publisher.rsl_detected === null ? "Unknown" : publisher.rsl_detected ? "Detected" : "None"}
            tooltip={publisher.rsl_detected ? "Rights & Syndication License detected" : "No RSL licensing detected"}
          />
          <StatusIndicator
            icon={Rss}
            label="Feeds"
            value={`${publisher.sitemap_urls?.length ?? 0} sitemaps, ${publisher.rss_urls?.length ?? 0} RSS`}
          />
        </div>
      </Card>

      {/* ToS Permissions */}
      <Collapsible>
        <Card className="mb-6">
          <CollapsibleTrigger className="w-full group">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ChevronRight className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                  <CardTitle>Terms of Service</CardTitle>
                </div>
                {publisher.tos_url && (
                  <a
                    href={publisher.tos_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View source
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              {permissions.length > 0 ? (
                <div className="rounded-lg border border-gray-300 overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30 hover:bg-muted/30">
                        <TableHead className="font-medium">Activity</TableHead>
                        <TableHead className="font-medium w-[140px]">Status</TableHead>
                        <TableHead className="font-medium">Notes</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {permissions.map((p, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium">{p.activity}</TableCell>
                          <TableCell><PermissionStatus permission={p.permission} /></TableCell>
                          <TableCell className="text-sm text-muted-foreground">{p.notes}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No permissions data available.</p>
              )}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Discovery */}
      <Collapsible>
        <Card>
          <CollapsibleTrigger className="w-full group">
            <CardHeader>
              <div className="flex items-center gap-2">
                <ChevronRight className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                <CardTitle>Discovery</CardTitle>
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Map className="size-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">Sitemaps</h4>
              <span className="text-xs text-muted-foreground">({publisher.sitemap_urls?.length ?? 0})</span>
            </div>
            <UrlList urls={publisher.sitemap_urls ?? []} />
          </div>

          <div>
            <div className="flex items-center gap-2 mb-2">
              <Rss className="size-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">RSS Feeds</h4>
              <span className="text-xs text-muted-foreground">({publisher.rss_urls?.length ?? 0})</span>
            </div>
            <UrlList urls={publisher.rss_urls ?? []} />
          </div>

          {publisher.ai_bot_blocks && Object.keys(publisher.ai_bot_blocks).length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="size-4 text-muted-foreground" />
                <h4 className="text-sm font-medium">AI Bot Blocking</h4>
                <span className="text-xs text-muted-foreground">
                  ({Object.values(publisher.ai_bot_blocks).filter(b => b.blocked).length}/{Object.keys(publisher.ai_bot_blocks).length} blocked)
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 pl-7">
                {Object.entries(publisher.ai_bot_blocks).map(([bot, info]) => (
                  <div key={bot} className="flex items-center gap-1.5 text-sm">
                    {info.blocked ? (
                      <CircleX className="size-3.5 text-red-500 shrink-0" />
                    ) : (
                      <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
                    )}
                    <span className={info.blocked ? "text-foreground" : "text-muted-foreground"}>
                      {bot}
                    </span>
                    <span className="text-xs text-muted-foreground">({info.company})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 pt-1">
            <FileText className="size-4 text-muted-foreground" />
            <span className="text-sm font-medium">RSL</span>
            <span className="text-sm text-muted-foreground">
              {publisher.rsl_detected === null ? "Unknown" : publisher.rsl_detected ? "Detected" : "Not detected"}
            </span>
          </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Article Metadata */}
      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Article Metadata</CardTitle>
            <span className="text-xs text-muted-foreground">{articles.length} article{articles.length !== 1 ? 's' : ''} analyzed</span>
          </div>
        </CardHeader>
        <CardContent>
          {articles.length > 0 ? (
            <div className="space-y-4">
              {articles.map((article) => (
                <div key={article.id} className="rounded-lg border border-gray-300 p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <a
                      href={article.article_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium hover:text-foreground transition-colors break-all inline-flex items-start gap-1.5"
                    >
                      {article.article_url}
                      <ExternalLink className="size-3 shrink-0 mt-0.5 text-muted-foreground/50" />
                    </a>
                    <PaywallBadge status={article.paywall_status} />
                  </div>

                  <div className="flex items-center gap-1.5 mb-2">
                    <FileCode className="size-3.5 text-muted-foreground" />
                    <FormatBadge label="JSON-LD" present={article.has_jsonld} />
                    <FormatBadge label="OpenGraph" present={article.has_opengraph} />
                    <FormatBadge label="Microdata" present={article.has_microdata} />
                    <FormatBadge label="Twitter" present={article.has_twitter_cards} />
                  </div>

                  {article.metadata_profile && (
                    <p className="text-xs text-muted-foreground leading-relaxed">{article.metadata_profile}</p>
                  )}

                  <p className="text-xs text-muted-foreground/60 mt-2">
                    {new Date(article.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No articles analyzed yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

Detail.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Detail
