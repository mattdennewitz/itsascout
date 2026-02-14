import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import AppLayout from '@/Layouts/AppLayout'
import { Link, router, usePage, Deferred } from '@inertiajs/react'
import { useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

interface Props {
    publishers: Publisher[]
}

function LoadingSpinner() {
    return (
        <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        </div>
    )
}

function getCsrfToken(): string {
    const match = document.cookie.match(/csrftoken=([^;]+)/)
    return match ? match[1] : ''
}

function Index({ publishers }: Props) {
    const { url } = usePage()
    const csrfToken = getCsrfToken()
    const [search, setSearch] = useState(() => {
        const params = new URLSearchParams(url.split('?')[1])
        return params.get('search') || ''
    })

    const isInitialMount = useRef(true)

    useEffect(() => {
        if (isInitialMount.current) {
            isInitialMount.current = false
            return
        }
        const timeout = setTimeout(() => {
            router.get('/',
                { search: search || undefined },
                {
                    only: ['publishers'],
                    preserveScroll: true,
                    preserveState: true,
                    replace: true,
                }
            )
        }, 300)
        return () => clearTimeout(timeout)
    }, [search])

    return (
        <div className="container mx-auto py-10">
            <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-2">Analyze a URL</h2>
                <p className="text-sm text-gray-500 mb-4">
                    Paste a URL to get a comprehensive scraping report card
                </p>
                <form action="/submit" method="POST" className="flex gap-3">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    <input
                        type="url"
                        name="url"
                        placeholder="https://example.com/article"
                        required
                        className="flex-1 rounded-md border border-gray-300 px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <button
                        type="submit"
                        className="bg-blue-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
                    >
                        Analyze
                    </button>
                </form>
            </div>
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl">Publishers</h1>
                <div className="flex gap-2">
                    <Link
                        href="/publishers/create"
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                        Add Publisher
                    </Link>
                    <Link
                        href="/publishers/bulk-upload"
                        className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                    >
                        Bulk Upload
                    </Link>
                </div>
            </div>
            <div className="mb-4">
                <input
                    type="text"
                    placeholder="Filter by name..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="px-4 py-2 border rounded w-full max-w-md"
                />
            </div>
            <Deferred data="publishers" fallback={<LoadingSpinner />}>
                <DataTable columns={columns} data={publishers} />
            </Deferred>
        </div>
    )
}

// Persistent layout: AppLayout instance preserved across page navigations
Index.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Index
