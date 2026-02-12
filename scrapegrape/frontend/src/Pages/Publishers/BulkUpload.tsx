import { useForm, Link } from '@inertiajs/react'
import { usePapaParse } from 'react-papaparse'
import { useState } from 'react'
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

    const { readString } = usePapaParse()
    const [csvError, setCsvError] = useState<string | null>(null)
    const [fileName, setFileName] = useState<string | null>(null)

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) {
            setData('csv_file', null)
            setFileName(null)
            setCsvError(null)
            return
        }

        // Client-side validation: check if CSV has 'URL' column
        const reader = new FileReader()
        reader.onload = (event) => {
            const csvText = event.target?.result as string
            readString(csvText, {
                header: true,
                complete: (results) => {
                    const headers = results.meta.fields || []
                    if (!headers.includes('URL')) {
                        setCsvError('CSV file must have a "URL" column header')
                        setData('csv_file', null)
                        setFileName(null)
                    } else {
                        setCsvError(null)
                        setData('csv_file', file)
                        setFileName(file.name)
                    }
                },
                error: () => {
                    setCsvError('Failed to parse CSV file')
                    setData('csv_file', null)
                    setFileName(null)
                }
            })
        }
        reader.readAsText(file)
    }

    const handleSubmit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers/bulk-upload', {
            onSuccess: () => {
                setData('csv_file', null)
                setFileName(null)
                setCsvError(null)
            }
        })
    }

    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl font-bold mb-6">Bulk Upload Publishers</h1>

            <form onSubmit={handleSubmit} className="max-w-md">
                <FormField label="CSV File" error={csvError || errors.csv_file}>
                    <input
                        type="file"
                        accept=".csv"
                        onChange={handleFileChange}
                        className="w-full px-4 py-2 border rounded"
                        disabled={processing}
                    />
                    {fileName && (
                        <p className="text-sm text-gray-600 mt-1">
                            Selected: {fileName}
                        </p>
                    )}
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
                        disabled={processing || !data.csv_file || csvError !== null}
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

// Persistent layout: AppLayout instance preserved across page navigations
BulkUpload.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default BulkUpload
