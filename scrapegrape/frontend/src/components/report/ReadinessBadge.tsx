export function ReadinessBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    strong: 'bg-emerald-50 text-emerald-700',
    moderate: 'bg-blue-50 text-blue-700',
    minimal: 'bg-amber-50 text-amber-700',
    none: 'bg-gray-100 text-gray-500',
  }
  const labels: Record<string, string> = {
    strong: 'Strong',
    moderate: 'Moderate',
    minimal: 'Minimal',
    none: 'None',
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[level] ?? styles.none}`}>
      {labels[level] ?? level}
    </span>
  )
}
