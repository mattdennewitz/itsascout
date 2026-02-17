export function PaywallBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    free: 'bg-emerald-50 text-emerald-700',
    paywalled: 'bg-red-50 text-red-700',
    metered: 'bg-amber-50 text-amber-700',
    unknown: 'bg-gray-100 text-gray-500',
  }
  const labels: Record<string, string> = {
    free: 'Free',
    paywalled: 'Paywalled',
    metered: 'Metered',
    unknown: 'Unknown',
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {labels[status] ?? status}
    </span>
  )
}
