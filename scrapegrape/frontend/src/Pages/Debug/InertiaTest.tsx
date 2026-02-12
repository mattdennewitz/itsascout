interface Props {
    message: string
    timestamp: string
}

export default function InertiaTest({ message, timestamp }: Props) {
    return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
            <h1>Inertia Smoke Test</h1>
            <p><strong>Message from Django:</strong> {message}</p>
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p style={{ color: 'green', marginTop: '1rem' }}>
                ✓ Inertia.js is correctly configured
            </p>
        </div>
    )
}
