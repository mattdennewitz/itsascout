import { useEffect, useState, useMemo } from 'react'
import { Link, router } from '@inertiajs/react'
import AppLayout from '@/Layouts/AppLayout'
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
    CircleCheck,
    CircleX,
    Shield,
    FileText,
    Bot,
    Map,
    Rss,
    ExternalLink,
    ChevronRight,
    Scale,
    FileCode,
    Globe,
    Newspaper,
    Clock,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { StatusIndicator } from '@/components/report/StatusIndicator'
import { PermissionStatus } from '@/components/report/PermissionStatus'
import { UrlList } from '@/components/report/UrlList'
import { FormatBadge } from '@/components/report/FormatBadge'
import { PaywallBadge } from '@/components/report/PaywallBadge'
import { ReadinessBadge } from '@/components/report/ReadinessBadge'
import { ConfidenceBadge } from '@/components/report/ConfidenceBadge'

interface PipelineEvent {
    step: string
    status: 'started' | 'completed' | 'failed' | 'skipped'
    data: Record<string, unknown>
}

type Permission = {
    notes: string
    activity: string
    permission: 'explicitly_permitted' | 'explicitly_prohibited' | 'conditional_ambiguous'
}

interface JobProps {
    job: {
        id: string
        status: string
        canonical_url: string
        submitted_url: string
        publisher_id: number
        publisher_name: string
        publisher_domain: string
        waf_result: Record<string, unknown> | null
        tos_result: Record<string, unknown> | null
        robots_result: Record<string, unknown> | null
        sitemap_result: Record<string, unknown> | null
        rss_result: Record<string, unknown> | null
        rsl_result: Record<string, unknown> | null
        cc_result: Record<string, unknown> | null
        sitemap_analysis_result: Record<string, unknown> | null
        frequency_result: Record<string, unknown> | null
        news_signals_result: Record<string, unknown> | null
        ai_bot_result: Record<string, unknown> | null
        metadata_result: Record<string, unknown> | null
        article_result: Record<string, unknown> | null
        created_at: string
    }
}

const PIPELINE_STEPS = [
    { key: 'publisher_details', label: 'Publisher Details', icon: '1' },
    { key: 'waf', label: 'WAF Detection', icon: '2' },
    { key: 'tos_discovery', label: 'ToS Discovery', icon: '3' },
    { key: 'tos_evaluation', label: 'ToS Evaluation', icon: '4' },
    { key: 'robots', label: 'robots.txt Analysis', icon: '5' },
    { key: 'ai_bot_blocking', label: 'AI Bot Blocking', icon: '6' },
    { key: 'sitemap', label: 'Sitemap Discovery', icon: '7' },
    { key: 'rss', label: 'RSS Feed Discovery', icon: '8' },
    { key: 'rsl', label: 'RSL Detection', icon: '9' },
    { key: 'cc', label: 'Common Crawl Presence', icon: '10' },
    { key: 'sitemap_analysis', label: 'Sitemap Analysis', icon: '11' },
    { key: 'frequency', label: 'Update Frequency', icon: '12' },
    { key: 'article_extraction', label: 'Article Metadata', icon: '13' },
    { key: 'paywall_detection', label: 'Paywall Detection', icon: '14' },
    { key: 'metadata_profile', label: 'Metadata Profile', icon: '15' },
    { key: 'google_news', label: 'Google News Readiness', icon: '16' },
] as const

function statusBadge(status: string) {
    const styles: Record<string, string> = {
        pending: 'bg-yellow-100 text-yellow-800',
        running: 'bg-blue-100 text-blue-800',
        completed: 'bg-green-100 text-green-800',
        failed: 'bg-red-100 text-red-800',
    }
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? 'bg-gray-100 text-gray-800'}`}>
            {status}
        </span>
    )
}

function truncateUrl(url: string, maxLen = 60): string {
    if (url.length <= maxLen) return url
    return url.slice(0, maxLen) + '...'
}

function SectionPlaceholder({ label, reason }: { label: string; reason: string }) {
    return (
        <p className="text-sm text-muted-foreground">
            {label}: <span className="italic">{reason}</span>
        </p>
    )
}

function stepDataSummary(step: string, data: Record<string, unknown>): string | null {
    if (!data || Object.keys(data).length === 0) return null

    if (step === 'publisher_details') {
        // Full details data (from metadata extraction)
        if (data.found && data.organization) {
            const org = data.organization as Record<string, unknown>
            const name = org.name ?? 'Unknown'
            const type = org.type ?? 'Organization'
            return `${name} (${type}, via ${data.source})`
        }
        if (data.found === false) return 'No structured organization data found'
        // Resolution data (just name/domain, shown while running)
        if (data.publisher_name) return `Resolved: ${data.publisher_name} (${data.domain ?? ''})`
        return null
    }
    if (step === 'waf') {
        if (data.waf_detected) return `Detected: ${data.waf_type ?? 'Unknown WAF'}`
        if (data.waf_detected === false) return 'No WAF detected'
        return null
    }
    if (step === 'tos_discovery') {
        if (data.tos_url) return `Found at: ${data.tos_url}`
        if (data.error) return `Error: ${String(data.error)}`
        return null
    }
    if (step === 'tos_evaluation') {
        if (data.error) return `Error: ${String(data.error)}`
        if (data.scraping_permitted !== undefined) {
            return data.scraping_permitted ? 'Scraping: Permitted' : 'Scraping: Restricted'
        }
        if (Array.isArray(data.permissions)) {
            const count = (data.permissions as unknown[]).length
            return `${count} activit${count === 1 ? 'y' : 'ies'} evaluated`
        }
        return null
    }
    if (step === 'robots') {
        if (data.robots_found === false) return 'No robots.txt found'
        if (data.url_allowed === true) return 'URL allowed by robots.txt'
        if (data.url_allowed === false) return 'URL disallowed by robots.txt'
        return null
    }
    if (step === 'ai_bot_blocking') {
        const blocked = data.blocked_count as number
        const total = data.total_count as number
        if (!data.robots_found) return 'No robots.txt available'
        if (blocked === 0) return 'No AI bots blocked'
        return `${blocked}/${total} AI bots blocked`
    }
    if (step === 'sitemap') {
        const count = data.count as number
        if (count > 0) return `Found ${count} sitemap(s)`
        return 'No sitemaps found'
    }
    if (step === 'rss') {
        const count = data.count as number
        if (count > 0) return `Found ${count} feed(s)`
        return 'No RSS/Atom feeds found'
    }
    if (step === 'rsl') {
        if (data.rsl_detected) return `RSL detected (${data.count} indicator(s))`
        return 'No RSL licensing detected'
    }
    if (step === 'cc') {
        if (data.available === false) return `Data unavailable: ${data.error ?? 'API error'}`
        if (data.in_index) {
            const pages = data.page_count as number
            const crawl = data.latest_crawl as string | undefined
            let summary = `In index (~${pages.toLocaleString()} pages)`
            if (crawl) summary += `, last crawled ${crawl}`
            return summary
        }
        if (data.in_index === false) return 'Not found in Common Crawl index'
        return null
    }
    if (step === 'article_extraction') {
        const formats = data.formats_found as string[] | undefined
        if (formats && formats.length > 0) return `Found: ${formats.join(', ')}`
        if (data.summary) return String(data.summary)
        return 'No structured data found'
    }
    if (step === 'paywall_detection') {
        const status = data.paywall_status as string | undefined
        if (status) {
            const label: Record<string, string> = {
                free: 'Free access',
                paywalled: 'Paywalled (hard)',
                metered: 'Metered access',
                unknown: 'Unknown',
            }
            let result = label[status] ?? status
            if (data.schema_accessible !== undefined && data.schema_accessible !== null) {
                result += ` (isAccessibleForFree: ${data.schema_accessible})`
            }
            return result
        }
        if (data.summary) return String(data.summary)
        return null
    }
    if (step === 'metadata_profile') {
        if (data.summary) return String(data.summary)
        return null
    }
    if (step === 'sitemap_analysis') {
        if (data.has_news_sitemap === true) return 'News sitemap detected'
        if (data.has_news_sitemap === false) return 'No news sitemap found'
        return null
    }
    if (step === 'frequency') {
        const label = data.frequency_label as string | undefined
        const confidence = data.confidence as string | undefined
        if (label) return `${label}${confidence ? ` (${confidence} confidence)` : ''}`
        if (data.error) return `Error: ${String(data.error)}`
        return 'Could not estimate frequency'
    }
    if (step === 'google_news') {
        const readiness = data.readiness as string | undefined
        const count = data.signal_count as number | undefined
        if (readiness) return `Readiness: ${readiness} (${count ?? 0}/3 signals)`
        if (data.error) return `Error: ${String(data.error)}`
        return null
    }
    if (data.reason) return String(data.reason)
    if (data.error) return `Error: ${String(data.error)}`
    return null
}

function StepCard({ step, event }: { step: typeof PIPELINE_STEPS[number]; event: PipelineEvent | undefined }) {
    let borderClass = 'border-gray-300'
    let bgClass = 'bg-white'
    let textClass = 'text-gray-400'
    let statusLabel = 'Pending'
    let animate = ''

    if (event) {
        switch (event.status) {
            case 'completed':
                borderClass = 'border-gray-300'
                bgClass = 'bg-green-50'
                textClass = 'text-green-800'
                statusLabel = 'Completed'
                break
            case 'started':
                borderClass = 'border-gray-300'
                bgClass = 'bg-blue-50'
                textClass = 'text-blue-800'
                statusLabel = 'Running'
                animate = 'animate-pulse'
                break
            case 'failed':
                borderClass = 'border-gray-300'
                bgClass = 'bg-red-50'
                textClass = 'text-red-800'
                statusLabel = 'Failed'
                break
            case 'skipped':
                borderClass = 'border-gray-300'
                bgClass = 'bg-gray-50'
                textClass = 'text-gray-500'
                statusLabel = 'Skipped'
                break
        }
    }

    const summary = event ? stepDataSummary(step.key, event.data) : null

    // Format badges for article_extraction step
    const formatBadges = step.key === 'article_extraction' && event?.status === 'completed' ? (
        <div className="flex items-center gap-1.5 mt-1.5">
            {(['json-ld', 'opengraph', 'microdata', 'twitter-cards'] as const).map((fmt) => {
                const formats = (event.data.formats_found as string[] | undefined) ?? []
                const present = formats.includes(fmt)
                const labels: Record<string, string> = { 'json-ld': 'JSON-LD', 'opengraph': 'OpenGraph', 'microdata': 'Microdata', 'twitter-cards': 'Twitter' }
                return (
                    <span key={fmt} className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${present ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-400'}`}>
                        {labels[fmt]}
                    </span>
                )
            })}
        </div>
    ) : null

    return (
        <div className={`border ${borderClass} ${bgClass} rounded-lg p-4 ${animate}`}>
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${event?.status === 'completed' ? 'bg-green-200 text-green-800' : event?.status === 'started' ? 'bg-blue-200 text-blue-800' : event?.status === 'failed' ? 'bg-red-200 text-red-800' : 'bg-gray-200 text-gray-600'}`}>
                        {step.icon}
                    </span>
                    <span className={`font-medium text-sm ${textClass}`}>{step.label}</span>
                </div>
                <span className={`text-xs ${textClass}`}>{statusLabel}</span>
            </div>
            {summary && (
                <p className={`text-xs mt-1 ${textClass}`}>{summary}</p>
            )}
            {formatBadges}
            {event?.status === 'skipped' && !summary && (
                <p className="text-xs mt-1 text-gray-500">Skipped (publisher recently checked)</p>
            )}
            {event?.status === 'failed' && !!event.data?.error && (
                <p className="text-xs mt-1 text-red-700">{String(event.data.error)}</p>
            )}
        </div>
    )
}

// ---------------------------------------------------------------------------
// Field Presence Table (shows which canonical fields exist per format)
// ---------------------------------------------------------------------------

const CANONICAL_FIELDS = [
    { label: 'Headline',       jsonld: 'headline',            og: 'headline',        micro: 'headline',            twitter: 'twitter:title' },
    { label: 'Author',         jsonld: 'author',              og: 'author',          micro: 'author',              twitter: null },
    { label: 'Date Published', jsonld: 'datePublished',       og: 'datePublished',   micro: 'datePublished',       twitter: null },
    { label: 'Date Modified',  jsonld: 'dateModified',        og: 'dateModified',    micro: 'dateModified',        twitter: null },
    { label: 'Image',          jsonld: 'image',               og: 'image',           micro: 'image',               twitter: 'twitter:image' },
    { label: 'Description',    jsonld: 'description',         og: 'description',     micro: 'description',         twitter: 'twitter:description' },
    { label: 'Language',       jsonld: 'inLanguage',          og: 'inLanguage',      micro: 'inLanguage',          twitter: null },
    { label: 'Section',        jsonld: 'articleSection',      og: 'articleSection',  micro: 'articleSection',      twitter: null },
    { label: 'Keywords',       jsonld: 'keywords',            og: 'keywords',        micro: 'keywords',            twitter: null },
    { label: 'Word Count',     jsonld: 'wordCount',           og: null,              micro: 'wordCount',           twitter: null },
    { label: 'Paywall Info',   jsonld: 'isAccessibleForFree', og: null,              micro: 'isAccessibleForFree', twitter: null },
] as const

function FieldPresenceTable({
    jsonldFields,
    opengraphFields,
    microdataFields,
    twitterCards,
}: {
    jsonldFields?: Record<string, unknown> | null
    opengraphFields?: Record<string, unknown> | null
    microdataFields?: Record<string, unknown> | null
    twitterCards?: Record<string, unknown> | null
}) {
    const formats = [
        { key: 'jsonld' as const, label: 'JSON-LD', data: jsonldFields },
        { key: 'og' as const, label: 'OpenGraph', data: opengraphFields },
        { key: 'micro' as const, label: 'Microdata', data: microdataFields },
        { key: 'twitter' as const, label: 'Twitter', data: twitterCards },
    ]

    // Show table if at least one format has data, but always show all columns
    const hasAnyData = formats.some(f => f.data != null)
    if (!hasAnyData) return null

    function hasField(data: Record<string, unknown> | null | undefined, fieldKey: string | null): boolean {
        if (!data || fieldKey == null) return false
        return data[fieldKey] !== undefined && data[fieldKey] !== null
    }

    return (
        <div className="pl-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Field Presence by Format
            </p>
            <div className="rounded-lg border border-gray-300 overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/30 hover:bg-muted/30">
                            <TableHead className="text-sm font-medium">Field</TableHead>
                            {formats.map(f => (
                                <TableHead key={f.key} className="text-sm font-medium">{f.label}</TableHead>
                            ))}
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {CANONICAL_FIELDS.map(field => (
                            <TableRow key={field.label}>
                                <TableCell className="text-sm font-medium">{field.label}</TableCell>
                                {formats.map(f => (
                                    <TableCell key={f.key} className="text-sm">
                                        {hasField(f.data, field[f.key]) ? (
                                            <CircleCheck className="size-4 text-green-600" />
                                        ) : (
                                            <CircleX className="size-4 text-red-300" />
                                        )}
                                    </TableCell>
                                ))}
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

// ---------------------------------------------------------------------------
// Report Card (rendered for completed jobs)
// ---------------------------------------------------------------------------

function ReportCard({ job }: { job: JobProps['job'] }) {
    const permissions = (job.tos_result?.permissions as Permission[] | undefined) ?? []
    const permitted = permissions.filter(p => p.permission === 'explicitly_permitted').length
    const prohibited = permissions.filter(p => p.permission === 'explicitly_prohibited').length

    const sitemapUrls = (job.sitemap_result?.sitemap_urls as string[] | undefined) ?? []
    const rssFeeds = (job.rss_result?.feeds as Array<{ url: string }> | undefined) ?? []
    const rssUrls = rssFeeds.map(f => f.url)

    const aiBots = (job.ai_bot_result?.bots as Record<string, { company: string; blocked: boolean }> | undefined) ?? null
    const blockedCount = aiBots ? Object.values(aiBots).filter(b => b.blocked).length : 0
    const totalBots = aiBots ? Object.keys(aiBots).length : 0

    const ar = job.article_result as Record<string, unknown> | null
    const formatsFound = (ar?.formats_found as string[] | undefined) ?? []
    const paywall = ar?.paywall as Record<string, unknown> | undefined
    const profile = ar?.profile as Record<string, unknown> | undefined

    const metadata = job.metadata_result as Record<string, unknown> | null
    const metadataOrg = metadata?.organization as Record<string, unknown> | undefined

    const crawlPermissionStatus: React.ReactNode = !job.robots_result
        ? <span className="text-sm text-muted-foreground italic">Not checked</span>
        : !!job.robots_result.url_allowed
            ? <span className="inline-flex items-center gap-1.5 text-sm text-emerald-700"><CircleCheck className="size-4" />Allowed by robots.txt</span>
            : <span className="inline-flex items-center gap-1.5 text-sm text-red-600"><CircleX className="size-4" />Disallowed by robots.txt</span>

    return (
        <div className="space-y-6">
            {/* Publisher metadata info row */}
            {!!metadata?.found && metadataOrg && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Globe className="size-3.5" />
                    <span className="font-medium">{metadataOrg.name as string}</span>
                    {!!metadataOrg.type && (
                        <>
                            <span className="text-border">|</span>
                            <span>{metadataOrg.type as string}</span>
                        </>
                    )}
                    {!!metadata.source && (
                        <>
                            <span className="text-border">|</span>
                            <span className="text-xs">via {metadata.source as string}</span>
                        </>
                    )}
                </div>
            )}

            {/* Status overview */}
            <Card>
                <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-gray-300">
                    <StatusIndicator
                        icon={Shield}
                        label="WAF"
                        value={
                            !job.waf_result
                                ? 'Not checked'
                                : job.waf_result.waf_detected
                                    ? ((job.waf_result.waf_type as string) || 'Detected')
                                    : 'None'
                        }
                        tooltip={
                            !job.waf_result
                                ? undefined
                                : job.waf_result.waf_detected
                                    ? 'Web Application Firewall detected'
                                    : 'No WAF detected'
                        }
                    />
                    <StatusIndicator
                        icon={Bot}
                        label="Robots.txt"
                        value={
                            !job.robots_result
                                ? 'Not checked'
                                : job.robots_result.robots_found
                                    ? 'Found'
                                    : 'Not found'
                        }
                    />
                    <StatusIndicator
                        icon={FileText}
                        label="ToS"
                        value={
                            !job.tos_result
                                ? 'Not checked'
                                : permissions.length === 0
                                    ? 'No data'
                                    : prohibited > 0
                                        ? `${prohibited} prohibited`
                                        : `${permitted} permitted`
                        }
                    />
                    <StatusIndicator
                        icon={Scale}
                        label="RSL"
                        value={
                            !job.rsl_result
                                ? 'Not checked'
                                : job.rsl_result.rsl_detected
                                    ? 'Detected'
                                    : 'None'
                        }
                        tooltip={
                            !job.rsl_result
                                ? undefined
                                : job.rsl_result.rsl_detected
                                    ? 'Rights & Syndication License detected'
                                    : 'No RSL licensing detected'
                        }
                    />
                    <StatusIndicator
                        icon={Rss}
                        label="Feeds"
                        value={`${job.sitemap_result?.count ?? 0} sitemaps, ${job.rss_result?.count ?? 0} RSS`}
                    />
                </div>
            </Card>

            {/* ToS Permissions */}
            {!job.tos_result ? (
                <Card>
                    <CardHeader><CardTitle>Terms of Service</CardTitle></CardHeader>
                    <CardContent>
                        <SectionPlaceholder label="ToS" reason="Not checked" />
                    </CardContent>
                </Card>
            ) : (
                <Collapsible>
                    <Card>
                        <CollapsibleTrigger className="w-full group">
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <ChevronRight className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                                        <CardTitle>Terms of Service</CardTitle>
                                    </div>
                                    {!!job.tos_result.tos_url && (
                                        <a
                                            href={job.tos_result.tos_url as string}
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
            )}

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
                                    <span className="text-xs text-muted-foreground">({sitemapUrls.length})</span>
                                </div>
                                {job.sitemap_result ? (
                                    <UrlList urls={sitemapUrls} />
                                ) : (
                                    <SectionPlaceholder label="Sitemaps" reason="Not checked" />
                                )}
                            </div>

                            <div>
                                <div className="flex items-center gap-2 mb-2">
                                    <Rss className="size-4 text-muted-foreground" />
                                    <h4 className="text-sm font-medium">RSS Feeds</h4>
                                    <span className="text-xs text-muted-foreground">({rssUrls.length})</span>
                                </div>
                                {job.rss_result ? (
                                    <UrlList urls={rssUrls} />
                                ) : (
                                    <SectionPlaceholder label="RSS" reason="Not checked" />
                                )}
                            </div>

                            {aiBots && totalBots > 0 && (
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <Bot className="size-4 text-muted-foreground" />
                                        <h4 className="text-sm font-medium">AI Bot Blocking</h4>
                                        <span className="text-xs text-muted-foreground">
                                            ({blockedCount}/{totalBots} blocked)
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 pl-7">
                                        {Object.entries(aiBots).map(([bot, info]) => (
                                            <div key={bot} className="flex items-center gap-1.5 text-sm">
                                                {info.blocked ? (
                                                    <CircleX className="size-3.5 text-red-500 shrink-0" />
                                                ) : (
                                                    <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
                                                )}
                                                <span className={info.blocked ? 'text-foreground' : 'text-muted-foreground'}>
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
                                    {!job.rsl_result
                                        ? 'Not checked'
                                        : job.rsl_result.rsl_detected
                                            ? `Detected${job.rsl_result.count ? ` (${job.rsl_result.count} indicator${(job.rsl_result.count as number) !== 1 ? 's' : ''})` : ''}`
                                            : 'Not detected'
                                    }
                                </span>
                            </div>

                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>

            {/* Competitive Intelligence */}
            <Card>
                <CardHeader>
                    <CardTitle>Competitive Intelligence</CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                    {/* CC Presence */}
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <Globe className="size-4 text-muted-foreground" />
                            <h4 className="text-sm font-medium">Common Crawl Presence</h4>
                        </div>
                        {!job.cc_result ? (
                            <SectionPlaceholder label="Common Crawl" reason="Not checked" />
                        ) : job.cc_result.available === false ? (
                            <p className="text-sm text-muted-foreground pl-6">
                                Unavailable{job.cc_result.error ? `: ${job.cc_result.error}` : ''}
                            </p>
                        ) : job.cc_result.in_index === true ? (
                            <p className="text-sm text-muted-foreground pl-6">
                                ~{(job.cc_result.page_count as number).toLocaleString()} pages | Last crawled {job.cc_result.latest_crawl as string}
                            </p>
                        ) : (
                            <p className="text-sm text-muted-foreground pl-6">
                                Not found in Common Crawl index
                            </p>
                        )}
                    </div>

                    {/* Google News Readiness */}
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <Newspaper className="size-4 text-muted-foreground" />
                            <h4 className="text-sm font-medium">Google News Readiness</h4>
                            {job.news_signals_result && !job.news_signals_result.error && !!job.news_signals_result.readiness && (
                                <ReadinessBadge level={job.news_signals_result.readiness as string} />
                            )}
                        </div>
                        {!job.news_signals_result ? (
                            <SectionPlaceholder label="Google News" reason="Not checked" />
                        ) : !!job.news_signals_result.error ? (
                            <p className="text-sm text-muted-foreground pl-6">
                                Unavailable: {job.news_signals_result.error as string}
                            </p>
                        ) : ((): React.ReactNode => {
                            const signals = job.news_signals_result.signals as Record<string, unknown>
                            return (
                                <div className="space-y-1 pl-6">
                                    <div className="flex items-center gap-1.5 text-sm">
                                        {!!signals.has_news_sitemap ? (
                                            <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
                                        ) : (
                                            <CircleX className="size-3.5 text-gray-300 shrink-0" />
                                        )}
                                        <span className={!!signals.has_news_sitemap ? 'text-foreground' : 'text-muted-foreground'}>
                                            News Sitemap
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-1.5 text-sm">
                                        {!!signals.has_news_article_schema ? (
                                            <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
                                        ) : (
                                            <CircleX className="size-3.5 text-gray-300 shrink-0" />
                                        )}
                                        <span className={!!signals.has_news_article_schema ? 'text-foreground' : 'text-muted-foreground'}>
                                            NewsArticle Schema{!!signals.has_news_article_schema && signals.article_schema_type ? ` (${String(signals.article_schema_type)})` : ''}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-1.5 text-sm">
                                        {!!signals.has_news_media_org ? (
                                            <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
                                        ) : (
                                            <CircleX className="size-3.5 text-gray-300 shrink-0" />
                                        )}
                                        <span className={!!signals.has_news_media_org ? 'text-foreground' : 'text-muted-foreground'}>
                                            NewsMediaOrganization{!!signals.has_news_media_org && signals.org_schema_type ? ` (${String(signals.org_schema_type)})` : ''}
                                        </span>
                                    </div>
                                </div>
                            )
                        })()}
                    </div>

                    {/* Update Frequency */}
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <Clock className="size-4 text-muted-foreground" />
                            <h4 className="text-sm font-medium">Update Frequency</h4>
                        </div>
                        {!job.frequency_result ? (
                            <SectionPlaceholder label="Update frequency" reason="Not checked" />
                        ) : !(job.frequency_result.frequency_label as string) ? (
                            <p className="text-sm text-muted-foreground pl-6">
                                Could not estimate publishing frequency
                            </p>
                        ) : (
                            <p className="text-sm text-muted-foreground pl-6">
                                {job.frequency_result.frequency_label as string}{' '}
                                <ConfidenceBadge level={job.frequency_result.confidence as string} />
                                {!!job.frequency_result.source && (job.frequency_result.source as string) !== 'none' && (
                                    <span className="text-xs"> from {job.frequency_result.source as string}</span>
                                )}
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Article Analysis */}
            <Card>
                <CardHeader>
                    <CardTitle>Article Analysis</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">


                    {/* Crawl Permission */}
                    <div className="flex items-center gap-3">
                        <Bot className="size-4 text-muted-foreground shrink-0" />
                        <span className="text-sm font-medium">Crawl Permission:</span>
                        {crawlPermissionStatus}
                    </div>

                    {/* Paywall Status */}
                    <div className="flex items-center gap-3">
                        <FileText className="size-4 text-muted-foreground shrink-0" />
                        <span className="text-sm font-medium">Paywall:</span>
                        <PaywallBadge status={(paywall?.paywall_status as string) ?? 'unknown'} />
                    </div>
                    {/* Format Badges */}
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <FileCode className="size-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Structured Data</span>
                        </div>
                        {ar ? (
                            <div className="flex items-center gap-1.5 pl-6">
                                <FormatBadge label="JSON-LD" present={formatsFound.includes('json-ld')} />
                                <FormatBadge label="OpenGraph" present={formatsFound.includes('opengraph')} />
                                <FormatBadge label="Microdata" present={formatsFound.includes('microdata')} />
                                <FormatBadge label="Twitter" present={formatsFound.includes('twitter-cards')} />
                            </div>
                        ) : (
                            <SectionPlaceholder label="Article metadata" reason="Not checked" />
                        )}
                    </div>

                    {/* Metadata Profile */}
                    {!!profile?.summary && (
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <FileText className="size-4 text-muted-foreground" />
                                <span className="text-sm font-medium">Metadata Profile</span>
                            </div>
                            <p className="text-sm text-muted-foreground leading-relaxed pl-6">
                                {profile.summary as string}
                            </p>
                        </div>
                    )}

                    {/* Field Presence Table */}
                    {ar && (
                        <FieldPresenceTable
                            jsonldFields={ar.jsonld_fields as Record<string, unknown> | null}
                            opengraphFields={ar.opengraph_fields as Record<string, unknown> | null}
                            microdataFields={ar.microdata_fields as Record<string, unknown> | null}
                            twitterCards={ar.twitter_cards as Record<string, unknown> | null}
                        />
                    )}
                </CardContent>
            </Card>
        </div>
    )
}

// ---------------------------------------------------------------------------
// Step Cards (rendered for running/pending/failed jobs)
// ---------------------------------------------------------------------------

const MAX_RETRIES = 5

function Show({ job }: JobProps) {
    const [stepStatuses, setStepStatuses] = useState<Record<string, PipelineEvent>>({})
    const [connected, setConnected] = useState(false)
    const [connectionFailed, setConnectionFailed] = useState(false)

    // Build initial step statuses from completed job props (no SSE needed)
    const initialStatuses = useMemo(() => {
        if (job.status !== 'completed' && job.status !== 'failed') return {}

        const statuses: Record<string, PipelineEvent> = {}

        // Publisher details: use metadata_result if available, otherwise just name/domain
        if (job.metadata_result) {
            statuses['publisher_details'] = {
                step: 'publisher_details',
                status: 'completed',
                data: job.metadata_result,
            }
        } else {
            statuses['publisher_details'] = {
                step: 'publisher_details',
                status: 'completed',
                data: { publisher_name: job.publisher_name, domain: job.publisher_domain },
            }
        }

        if (job.waf_result) {
            statuses['waf'] = {
                step: 'waf',
                status: 'completed',
                data: job.waf_result,
            }
        }

        if (job.tos_result) {
            // ToS discovery is complete if we have tos_result
            statuses['tos_discovery'] = {
                step: 'tos_discovery',
                status: 'completed',
                data: job.tos_result,
            }

            // ToS evaluation is complete if we have evaluation data in tos_result
            if (job.tos_result.scraping_permitted !== undefined || job.tos_result.permissions) {
                statuses['tos_evaluation'] = {
                    step: 'tos_evaluation',
                    status: 'completed',
                    data: job.tos_result,
                }
            }
        }

        if (job.robots_result) {
            statuses['robots'] = { step: 'robots', status: 'completed', data: job.robots_result }
        }
        if (job.sitemap_result) {
            statuses['sitemap'] = { step: 'sitemap', status: 'completed', data: job.sitemap_result }
        }
        if (job.rss_result) {
            statuses['rss'] = { step: 'rss', status: 'completed', data: job.rss_result }
        }
        if (job.rsl_result) {
            statuses['rsl'] = { step: 'rsl', status: 'completed', data: job.rsl_result }
        }
        if (job.cc_result) {
            statuses['cc'] = { step: 'cc', status: 'completed', data: job.cc_result }
        }
        if (job.sitemap_analysis_result) {
            statuses['sitemap_analysis'] = { step: 'sitemap_analysis', status: 'completed', data: job.sitemap_analysis_result }
        }
        if (job.frequency_result) {
            statuses['frequency'] = { step: 'frequency', status: 'completed', data: job.frequency_result }
        }
        if (job.news_signals_result) {
            statuses['google_news'] = { step: 'google_news', status: 'completed', data: job.news_signals_result }
        }
        if (job.ai_bot_result) {
            statuses['ai_bot_blocking'] = { step: 'ai_bot_blocking', status: 'completed', data: job.ai_bot_result }
        }
        if (job.article_result) {
            const ar = job.article_result as Record<string, unknown>
            statuses['article_extraction'] = {
                step: 'article_extraction',
                status: 'completed',
                data: {
                    formats_found: ar.formats_found,
                    jsonld_fields: ar.jsonld_fields,
                    opengraph_fields: ar.opengraph_fields,
                    microdata_fields: ar.microdata_fields,
                    twitter_cards: ar.twitter_cards,
                },
            }
            const paywall = ar.paywall as Record<string, unknown> | undefined
            if (paywall) {
                statuses['paywall_detection'] = {
                    step: 'paywall_detection',
                    status: 'completed',
                    data: paywall,
                }
            }
            const profile = ar.profile as Record<string, unknown> | undefined
            if (profile) {
                statuses['metadata_profile'] = {
                    step: 'metadata_profile',
                    status: 'completed',
                    data: profile,
                }
            }
        }
        // For completed jobs, any step without result data was skipped (freshness TTL)
        if (job.status === 'completed') {
            for (const step of PIPELINE_STEPS) {
                if (!statuses[step.key]) {
                    statuses[step.key] = {
                        step: step.key,
                        status: 'skipped',
                        data: { reason: 'fresh' },
                    }
                }
            }
        }

        return statuses
    }, [job])

    // Merge initial statuses (from props) with live SSE statuses
    const mergedStatuses = useMemo(() => {
        return { ...initialStatuses, ...stepStatuses }
    }, [initialStatuses, stepStatuses])

    useEffect(() => {
        if (job.status === 'completed' || job.status === 'failed') return

        let retryCount = 0
        const es = new EventSource(`/api/jobs/${job.id}/stream`)

        es.onopen = () => {
            setConnected(true)
            setConnectionFailed(false)
            retryCount = 0
        }

        es.onmessage = (event) => {
            const data: PipelineEvent = JSON.parse(event.data)
            setStepStatuses(prev => ({
                ...prev,
                [data.step]: data,
            }))
        }

        es.addEventListener('done', () => {
            es.close()
            setConnected(false)
            // Reload via Inertia to get final props from the server
            setTimeout(() => {
                router.reload()
            }, 500)
        })

        es.onerror = () => {
            setConnected(false)
            retryCount++
            if (retryCount >= MAX_RETRIES) {
                es.close()
                setConnectionFailed(true)
            }
        }

        return () => {
            es.close()
        }
    }, [job.id, job.status])

    const isActive = job.status === 'pending' || job.status === 'running'
    const isCompleted = job.status === 'completed'

    return (
        <div className={`container mx-auto py-10 ${isCompleted ? 'max-w-4xl' : 'max-w-2xl'}`}>
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <h1 className="text-xl font-semibold text-gray-900">
                        {truncateUrl(job.canonical_url)}
                    </h1>
                    {statusBadge(job.status)}
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-500">
                    {job.publisher_name && (
                        isCompleted ? (
                            <Link
                                href={`/publishers/${job.publisher_id}`}
                                className="hover:text-foreground transition-colors inline-flex items-center gap-1"
                            >
                                {job.publisher_name}
                                <ChevronRight className="size-3" />
                            </Link>
                        ) : (
                            <span>{job.publisher_name}</span>
                        )
                    )}
                    {job.publisher_domain && (
                        <span className="text-gray-400">{job.publisher_domain}</span>
                    )}
                    {isActive && !connectionFailed && (
                        <span className="flex items-center gap-1">
                            <span className={`inline-block w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
                            <span className="text-xs">{connected ? 'Connected' : 'Connecting...'}</span>
                        </span>
                    )}
                    {connectionFailed && (
                        <span className="flex items-center gap-1">
                            <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
                            <span className="text-xs text-red-600">Disconnected</span>
                            <button
                                onClick={() => router.reload()}
                                className="text-xs text-blue-600 hover:underline ml-1"
                            >
                                Refresh
                            </button>
                        </span>
                    )}
                </div>
            </div>

            {/* Completed: Report Card | Running/Pending/Failed: Step Cards */}
            {isCompleted ? (
                <ReportCard job={job} />
            ) : (
                <div className="space-y-3">
                    {PIPELINE_STEPS.slice(0, 12).map((step) => (
                        <StepCard
                            key={step.key}
                            step={step}
                            event={mergedStatuses[step.key]}
                        />
                    ))}

                    <div className="pt-2 pb-1">
                        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">Article Analysis</h3>
                    </div>

                    {PIPELINE_STEPS.slice(12).map((step) => (
                        <StepCard
                            key={step.key}
                            step={step}
                            event={mergedStatuses[step.key]}
                        />
                    ))}
                </div>
            )}

            {/* Submitted URL (if different from canonical) */}
            {job.submitted_url !== job.canonical_url && (
                <p className="mt-4 text-xs text-gray-400">
                    Submitted: {job.submitted_url}
                </p>
            )}

            {/* Timestamp */}
            <p className="mt-4 text-xs text-gray-400">
                Created: {new Date(job.created_at).toLocaleString()}
            </p>
        </div>
    )
}

Show.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Show
