export function FormatBadge({ label, present }: { label: string; present: boolean }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${present ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-400'}`}>
      {label}
    </span>
  )
}
