"""Serializers and views for matchmaking endpoints."""

import math

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, views
from rest_framework.response import Response

from starup_backend.common.roles import Role
from starup_backend.common.serializers import StrictSerializer
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


class TractionQuerySerializer(StrictSerializer):
    min_score = serializers.FloatField(default=0.0, min_value=0.0, max_value=100.0)

    def validate_min_score(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Informe uma pontuação finita.")
        return value


class StartupRecommendationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.ativo
            and request.user.perfil_ativo == Role.STARTUP
        )


class DemandMatchmakingView(views.APIView):
    """Returns ranked startup matches for a specific demand."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: DemandMatchResultSerializer(many=True)})
    def get(self, request, demand_id):
        results = get_matchmaking_for_demand(demand_id, user=request.user)
        return Response(DemandMatchResultSerializer(results, many=True).data)


class StartupRecommendationsView(views.APIView):
    """Returns open demands ranked by sector match for the authenticated startup."""

    permission_classes = [permissions.IsAuthenticated, StartupRecommendationPermission]

    @extend_schema(responses={200: RecommendedDemandResultSerializer(many=True)})
    def get(self, request):
        results = get_recommended_demands_for_startup(request.user)
        return Response(RecommendedDemandResultSerializer(results, many=True).data)


class InvestorTractionVitrineView(views.APIView):
    """Returns active startups ranked by client-reviewed delivery history."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        parameters=[TractionQuerySerializer],
        responses={200: DemandMatchResultSerializer(many=True)},
    )
    def get(self, request):
        query = TractionQuerySerializer(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        results = get_investor_traction_vitrine(**query.validated_data)
        return Response(DemandMatchResultSerializer(results, many=True).data)
