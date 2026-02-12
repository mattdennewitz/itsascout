import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import AppLayout from '@/Layouts/AppLayout'
import type { ReactNode } from 'react'

interface Props {
    publishers: Publisher[]
}

function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}

// Persistent layout: AppLayout instance preserved across page navigations
Index.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Index
