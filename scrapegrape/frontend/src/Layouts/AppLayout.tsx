import { Link, usePage } from '@inertiajs/react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

interface SharedProps {
    auth: {
        user: {
            id: number
            username: string
            is_authenticated: boolean
        } | null
    }
    flash: {
        success: string | null
        error: string | null
        info: string | null
    }
}

export default function AppLayout({ children }: { children: ReactNode }) {
    const { auth, flash } = usePage<{ props: SharedProps }>().props as unknown as SharedProps
    const [showFlash, setShowFlash] = useState(false)

    useEffect(() => {
        if (flash?.success || flash?.error || flash?.info) {
            setShowFlash(true)
            const timer = setTimeout(() => setShowFlash(false), 5000)
            return () => clearTimeout(timer)
        }
    }, [flash])

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow-sm border-b">
                <div className="container mx-auto px-4 py-3 flex items-center justify-between">
                    <Link href="/" className="text-lg font-bold text-gray-900 hover:text-gray-700">
                        Scrapegrape
                    </Link>
                    <div className="flex items-center gap-4">
                        <Link
                            href="/"
                            className="text-sm text-gray-600 hover:text-gray-900"
                        >
                            Publishers
                        </Link>
                        {auth?.user && (
                            <span className="text-sm text-gray-500">
                                {auth.user.username}
                            </span>
                        )}
                    </div>
                </div>
            </nav>

            {showFlash && (
                <div className="container mx-auto px-4 pt-4">
                    {flash?.success && (
                        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-2">
                            {flash.success}
                        </div>
                    )}
                    {flash?.error && (
                        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-2">
                            {flash.error}
                        </div>
                    )}
                    {flash?.info && (
                        <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded mb-2">
                            {flash.info}
                        </div>
                    )}
                </div>
            )}

            <main>
                {children}
            </main>
        </div>
    )
}
