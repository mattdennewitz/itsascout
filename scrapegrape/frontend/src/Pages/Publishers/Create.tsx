import { useForm, Link } from '@inertiajs/react'
import type { ReactNode, FormEventHandler } from 'react'
import AppLayout from '@/Layouts/AppLayout'
import { FormField } from '@/components/FormField'

function Create() {
    const { data, setData, post, processing, errors, reset } = useForm({
        name: '',
        url: ''
    })

    const handleSubmit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers/create', {
            onSuccess: () => reset()
        })
    }

    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl font-bold mb-6">Create Publisher</h1>

            <form onSubmit={handleSubmit} className="max-w-md">
                <FormField label="Name" error={errors.name}>
                    <input
                        type="text"
                        value={data.name}
                        onChange={e => setData('name', e.target.value)}
                        className={`w-full px-4 py-2 border rounded ${errors.name ? 'border-red-500' : ''}`}
                        disabled={processing}
                    />
                </FormField>

                <FormField label="URL" error={errors.url}>
                    <input
                        type="text"
                        value={data.url}
                        onChange={e => setData('url', e.target.value)}
                        placeholder="https://example.com"
                        className={`w-full px-4 py-2 border rounded ${errors.url ? 'border-red-500' : ''}`}
                        disabled={processing}
                    />
                </FormField>

                <div className="flex gap-2">
                    <button
                        type="submit"
                        disabled={processing}
                        className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                        {processing ? 'Creating...' : 'Create Publisher'}
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
Create.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Create
