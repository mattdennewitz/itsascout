import { useForm, Link } from '@inertiajs/react'
import type { ReactNode, FormEventHandler, ChangeEvent } from 'react'
import AppLayout from '@/Layouts/AppLayout'
import { FormField } from '@/components/FormField'
import { ProgressBar } from '@/components/ProgressBar'

function BulkUpload() {
    const { data, setData, post, processing, progress, errors } = useForm<{
        csv_file: File | null
    }>({
        csv_file: null
    })

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0] || null
        setData('csv_file', file)
    }

    const handleSubmit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers/bulk-upload', {
            onSuccess: () => setData('csv_file', null)
        })
    }

    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Bulk Upload Publishers</h1>

            <form onSubmit={handleSubmit} className="max-w-md">
                <FormField label="CSV File" error={errors.csv_file}>
                    <input
                        type="file"
                        accept=".csv"
                        onChange={handleFileChange}
                        className="w-full px-4 py-2 border border-gray-300 rounded"
                        disabled={processing}
                    />
                </FormField>

                <p className="text-sm text-gray-600 mb-4">
                    CSV file must include a "URL" column header with one URL per row.
                </p>

                {processing && progress && progress.percentage !== undefined && (
                    <div className="mb-4">
                        <ProgressBar percentage={progress.percentage} />
                    </div>
                )}

                {processing && !progress && (
                    <p className="text-sm text-gray-600 mb-4">
                        Preparing upload...
                    </p>
                )}

                <div className="flex gap-2">
                    <button
                        type="submit"
                        disabled={processing || !data.csv_file}
                        className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                        {processing ? 'Uploading...' : 'Upload CSV'}
                    </button>

                    <Link
                        href="/"
                        className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-50"
                    >
                        Cancel
                    </Link>
                </div>
            </form>
        </div>
    )
}

BulkUpload.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default BulkUpload
