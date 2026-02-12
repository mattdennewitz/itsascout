import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'
import './index.css'

// Configure CSRF for Django compatibility (INRT-04)
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"

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
