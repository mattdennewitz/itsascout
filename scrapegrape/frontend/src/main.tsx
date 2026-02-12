import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'
import { StrictMode } from 'react'
import axios from 'axios'
import './index.css'

// Configure CSRF for Django compatibility (INRT-04)
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"

// Detect Inertia context: InertiaMiddleware injects <div id="app" data-page="...">
const inertiaRoot = document.getElementById('app')

if (inertiaRoot?.dataset.page) {
    // Inertia path — render page component from Django's render_inertia() response
    createInertiaApp({
        resolve: name => {
            const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
            const page = pages[`./Pages/${name}.tsx`]
            if (!page) {
                throw new Error(
                    `Page not found: ${name}. Available: ${Object.keys(pages).join(', ')}`
                )
            }
            return page
        },
        setup({ el, App, props }) {
            createRoot(el).render(<App {...props} />)
        },
    })
} else {
    // Legacy path — existing template-based React app (Phase 1 coexistence)
    // This branch handles "/" which still uses index.html + json_script embedding
    // Will be removed when "/" is migrated to Inertia in Phase 3
    const legacyRoot = document.getElementById('root')
    if (legacyRoot) {
        import('./App').then(({ default: App }) => {
            createRoot(legacyRoot).render(
                <StrictMode>
                    <App />
                </StrictMode>
            )
        })
    }
}
