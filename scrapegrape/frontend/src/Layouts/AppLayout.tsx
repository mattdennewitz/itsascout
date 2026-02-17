import { Link, usePage } from '@inertiajs/react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

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
        <div className="min-h-screen">
            <nav className="border-b border-gray-300 bg-background">
                <div className="container mx-auto px-4 py-3 flex items-center justify-between">
                    <Link href="/" className="text-lg font-bold text-foreground hover:text-foreground/80">
                        Scrapegrape
                    </Link>
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" asChild>
                            <Link href="/">Publishers</Link>
                        </Button>
                        {auth?.user && (
                            <span className="text-sm text-muted-foreground">
                                {auth.user.username}
                            </span>
                        )}
                    </div>
                </div>
            </nav>

            {showFlash && (
                <div className="container mx-auto px-4 pt-4">
                    {flash?.success && (
                        <div className={cn(
                            "rounded-md border border-gray-300 px-4 py-3 mb-2 text-sm",
                            "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                        )}>
                            {flash.success}
                        </div>
                    )}
                    {flash?.error && (
                        <div className={cn(
                            "rounded-md border border-gray-300 px-4 py-3 mb-2 text-sm",
                            "bg-destructive/10 text-destructive"
                        )}>
                            {flash.error}
                        </div>
                    )}
                    {flash?.info && (
                        <div className={cn(
                            "rounded-md border border-gray-300 px-4 py-3 mb-2 text-sm",
                            "bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
                        )}>
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
