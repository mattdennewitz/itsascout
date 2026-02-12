from inertia import share


def inertia_share(get_response):
    def middleware(request):
        share(request,
            # User authentication state -- available as props.auth.user on all pages
            auth=lambda: {
                'user': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'is_authenticated': request.user.is_authenticated,
                } if request.user.is_authenticated else None,
            },

            # Flash messages -- auto-clear from session on read
            flash=lambda: {
                'success': request.session.pop('success', None),
                'error': request.session.pop('error', None),
                'info': request.session.pop('info', None),
            },

            # Validation errors -- auto-clear from session on read, consumed by useForm
            errors=lambda: request.session.pop('errors', {}),
        )
        return get_response(request)
    return middleware
