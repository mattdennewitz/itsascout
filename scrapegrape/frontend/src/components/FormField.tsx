import type { ReactNode } from 'react'

interface FormFieldProps {
    label: string
    error?: string
    children: ReactNode
}

export function FormField({ label, error, children }: FormFieldProps) {
    return (
        <div className="mb-4">
            <label className="block text-sm font-medium mb-2">
                {label}
            </label>
            {children}
            {error && (
                <p className="text-sm text-red-600 mt-1">
                    {error}
                </p>
            )}
        </div>
    )
}
