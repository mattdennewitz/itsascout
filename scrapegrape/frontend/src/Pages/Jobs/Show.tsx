import { useEffect, useState, useMemo } from 'react'
import { router } from '@inertiajs/react'
import AppLayout from '@/Layouts/AppLayout'
import type { ReactNode } from 'react'

interface PipelineEvent {
    step: string
    status: 'started' | 'completed' | 'failed' | 'skipped'
    data: Record<string, unknown>
}

interface JobProps {
    job: {
        id: string
        status: string
        canonical_url: string
        submitted_url: string
        publisher_name: string
        publisher_domain: string
        waf_result: Record<string, unknown> | null
        tos_result: Record<string, unknown> | null
        robots_result: Record<string, unknown> | null
        sitemap_result: Record<string, unknown> | null
        rss_result: Record<string, unknown> | null
        rsl_result: Record<string, unknown> | null
        created_at: string
    }
}

const PIPELINE_STEPS = [
    { key: 'publisher_resolution', label: 'Publisher Resolution', icon: '1' },
    { key: 'waf', label: 'WAF Detection', icon: '2' },
    { key: 'tos_discovery', label: 'ToS Discovery', icon: '3' },
    { key: 'tos_evaluation', label: 'ToS Evaluation', icon: '4' },
    { key: 'robots', label: 'robots.txt Analysis', icon: '5' },
    { key: 'sitemap', label: 'Sitemap Discovery', icon: '6' },
    { key: 'rss', label: 'RSS Feed Discovery', icon: '7' },
    { key: 'rsl', label: 'RSL Detection', icon: '8' },
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

function stepDataSummary(step: string, data: Record<string, unknown>): string | null {
    if (!data || Object.keys(data).length === 0) return null

    if (step === 'publisher_resolution') {
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
        if (data.scraping_permitted !== undefined) {
            return data.scraping_permitted ? 'Scraping: Permitted' : 'Scraping: Restricted'
        }
        if (data.permissions) return `Permissions: ${JSON.stringify(data.permissions)}`
        return null
    }
    if (step === 'robots') {
        if (data.robots_found === false) return 'No robots.txt found'
        if (data.url_allowed === true) return 'URL allowed by robots.txt'
        if (data.url_allowed === false) return 'URL disallowed by robots.txt'
        return null
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
    if (data.reason) return String(data.reason)
    if (data.error) return `Error: ${String(data.error)}`
    return null
}

function StepCard({ step, event }: { step: typeof PIPELINE_STEPS[number]; event: PipelineEvent | undefined }) {
    let borderClass = 'border-gray-200'
    let bgClass = 'bg-white'
    let textClass = 'text-gray-400'
    let statusLabel = 'Pending'
    let animate = ''

    if (event) {
        switch (event.status) {
            case 'completed':
                borderClass = 'border-green-300'
                bgClass = 'bg-green-50'
                textClass = 'text-green-800'
                statusLabel = 'Completed'
                break
            case 'started':
                borderClass = 'border-blue-300'
                bgClass = 'bg-blue-50'
                textClass = 'text-blue-800'
                statusLabel = 'Running'
                animate = 'animate-pulse'
                break
            case 'failed':
                borderClass = 'border-red-300'
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
            {event?.status === 'skipped' && !summary && (
                <p className="text-xs mt-1 text-gray-500">Skipped (publisher recently checked)</p>
            )}
            {event?.status === 'failed' && event.data?.error && (
                <p className="text-xs mt-1 text-red-700">{String(event.data.error)}</p>
            )}
        </div>
    )
}

const MAX_RETRIES = 5

function Show({ job }: JobProps) {
    const [stepStatuses, setStepStatuses] = useState<Record<string, PipelineEvent>>({})
    const [connected, setConnected] = useState(false)
    const [connectionFailed, setConnectionFailed] = useState(false)

    // Build initial step statuses from completed job props (no SSE needed)
    const initialStatuses = useMemo(() => {
        if (job.status !== 'completed' && job.status !== 'failed') return {}

        const statuses: Record<string, PipelineEvent> = {}

        // Publisher resolution is always completed for finished jobs
        statuses['publisher_resolution'] = {
            step: 'publisher_resolution',
            status: 'completed',
            data: { publisher_name: job.publisher_name, domain: job.publisher_domain },
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

    return (
        <div className="container mx-auto py-10 max-w-2xl">
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
                        <span>{job.publisher_name}</span>
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

            {/* Step Cards */}
            <div className="space-y-3">
                {PIPELINE_STEPS.map((step) => (
                    <StepCard
                        key={step.key}
                        step={step}
                        event={mergedStatuses[step.key]}
                    />
                ))}
            </div>

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
