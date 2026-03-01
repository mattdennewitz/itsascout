import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import AppLayout from '@/Layouts/AppLayout'
import { router, usePage, Deferred } from '@inertiajs/react'
import { useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Props {
    publishers: Publisher[]
}

function LoadingSpinner() {
    return (
        <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-300" />
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
        <div className="container mx-auto py-10 max-w-3xl">
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle>Analyze a URL</CardTitle>
                    <CardDescription>
                        Paste a URL to get a comprehensive scraping report card
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form action="/submit" method="POST" className="flex gap-3">
                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                        <input
                            type="url"
                            name="url"
                            placeholder="https://example.com/article"
                            required
                            className="flex-1 rounded-md border border-gray-300 bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                        <Button type="submit">Analyze</Button>
                    </form>
                </CardContent>
            </Card>

            <div className="mb-6">
                <h1 className="text-2xl font-semibold">Publishers</h1>
            </div>

            <div className="mb-4">
                <input
                    type="text"
                    placeholder="Filter by name..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="rounded-md border border-gray-300 bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring w-full max-w-md"
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
