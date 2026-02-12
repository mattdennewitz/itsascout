import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import AppLayout from '@/Layouts/AppLayout'
import { Link } from '@inertiajs/react'
import type { ReactNode } from 'react'

interface Props {
    publishers: Publisher[]
}

function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Publishers</h1>
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
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}

// Persistent layout: AppLayout instance preserved across page navigations
Index.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Index
