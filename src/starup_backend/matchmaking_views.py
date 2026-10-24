"""Serializers and views for matchmaking endpoints."""

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, views
from rest_framework.response import Response

from starup_backend.matchmaking import (
    get_investor_traction_vitrine,
    get_matchmaking_for_demand,
    get_recommended_demands_for_startup,
)


class MatchmakingDetailsSerializer(serializers.Serializer):
    score = serializers.FloatField()
    has_seal = serializers.BooleanField()
    c_setor = serializers.FloatField()
    m_auditoria = serializers.FloatField()
    e_economia = serializers.FloatField()
    t_maturidade = serializers.FloatField()


class DemandMatchResultSerializer(serializers.Serializer):
    startup_id = serializers.UUIDField()
    startup_name = serializers.CharField()
    startup_description = serializers.CharField(allow_blank=True)
    startup_website = serializers.CharField(allow_blank=True)
    startup_category = serializers.CharField(allow_blank=True)
    average_rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()
    completed_tests = serializers.IntegerField()
    has_seal = serializers.BooleanField()
    score = serializers.FloatField()
    details = MatchmakingDetailsSerializer()


class RecommendedDemandResultSerializer(serializers.Serializer):
    demand_id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    category_id = serializers.UUIDField()
    category_name = serializers.CharField()
    category_slug = serializers.CharField()
    created_at = serializers.DateTimeField()
    score = serializers.FloatField()
    has_seal = serializers.BooleanField()
    details = MatchmakingDetailsSerializer()


class DemandMatchmakingView(views.APIView):
    """Returns ranked startup matches for a specific demand."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: DemandMatchResultSerializer(many=True)})
    def get(self, request, demand_id):
        results = get_matchmaking_for_demand(demand_id)
        return Response(results)


class StartupRecommendationsView(views.APIView):
    """Returns open demands ranked by sector match for the authenticated startup."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: RecommendedDemandResultSerializer(many=True)})
    def get(self, request):
        results = get_recommended_demands_for_startup(request.user)
        return Response(results)


class InvestorTractionVitrineView(views.APIView):
    """Returns top startups ranked by traction and practical audit scores."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: DemandMatchResultSerializer(many=True)})
    def get(self, request):
        min_score = float(request.query_params.get("min_score", 0.0))
        results = get_investor_traction_vitrine(min_score=min_score)
        return Response(results)
