def append_debug_patterns(urlpatterns):
    from django.conf import settings
    if settings.DEBUG:
        from django.contrib.staticfiles.urls import staticfiles_urlpatterns
        from django.conf.urls.static import static

        urlpatterns += staticfiles_urlpatterns()
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    return urlpatterns
