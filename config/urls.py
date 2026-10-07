"""Only the scoped v1 API and the authenticated admin are exposed."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from starup_backend.accounts.views import (
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegistrationView,
)
from starup_backend.common.pwa import pwa_file
from starup_backend.demands.views import CategoryViewSet, DemandViewSet
from starup_backend.feed.views import FeedView
from starup_backend.notifications.views import (
    PushConfigView,
    PushSubscriptionDetailView,
    PushSubscriptionView,
)
from starup_backend.profiles.views import OwnStartupViewSet, StartupViewSet
from starup_backend.reviews.views import ReviewCreateView
from starup_backend.solutions.views import SolutionViewSet

router = SimpleRouter(use_regex_path=False)
handler404 = "starup_backend.common.errors.not_found"
handler500 = "starup_backend.common.errors.server_error"
router.register("categories", CategoryViewSet, basename="category")
router.register("demands", DemandViewSet, basename="demand")
router.register("solutions", SolutionViewSet, basename="solution")
router.register("startups", StartupViewSet, basename="startup")
router.register("my-startups", OwnStartupViewSet, basename="own-startup")

urlpatterns = [
    path("", pwa_file, name="pwa"),
    *[
        path(filename, pwa_file, {"filename": filename})
        for filename in (
            "app.js",
            "app.css",
            "service-worker.js",
            "manifest.json",
            "icon.svg",
            "icon-192.png",
            "icon-512.png",
            "apple-touch-icon.png",
            "privacy.html",
        )
    ],
    path("admin/", admin.site.urls),
    path("api/v1/auth/csrf/", CsrfView.as_view(), name="csrf"),
    path("api/v1/auth/register/", RegistrationView.as_view(), name="register"),
    path("api/v1/auth/login/", LoginView.as_view(), name="login"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/v1/me/", MeView.as_view(), name="me"),
    path("api/v1/feed/", FeedView.as_view(), name="feed"),
    path("api/v1/reviews/", ReviewCreateView.as_view(), name="review-create"),
    path("api/v1/push/config/", PushConfigView.as_view(), name="push-config"),
    path(
        "api/v1/push/subscriptions/",
        PushSubscriptionView.as_view(),
        name="push-subscribe",
    ),
    path(
        "api/v1/push/subscriptions/<uuid:subscription_id>/",
        PushSubscriptionDetailView.as_view(),
        name="push-unsubscribe",
    ),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include(router.urls)),
]
