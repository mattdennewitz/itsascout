import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'

interface Props {
    publishers: Publisher[]
}

export default function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}
