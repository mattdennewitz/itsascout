export function ConfidenceBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    high: 'bg-emerald-50 text-emerald-700',
    medium: 'bg-amber-50 text-amber-700',
    low: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[level] ?? styles.low}`}>
      {level} confidence
    </span>
  )
}
