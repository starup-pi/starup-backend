"""Stable, non-identifying error responses."""

from uuid import uuid4

from django.http import JsonResponse
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "A operação conflita com o estado atual."
    default_code = "conflict"


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    codes = {
        400: "invalid_input",
        401: "authentication_required",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "rate_limited",
    }
    fields = response.data if response.status_code == 400 else {}
    response.data = {
        "code": codes.get(response.status_code, "request_failed"),
        "message": {
            400: "Verifique os campos informados.",
            403: "Operação não permitida.",
            404: "Recurso não encontrado.",
            409: "A operação conflita com o estado atual.",
            429: "Aguarde antes de tentar novamente.",
        }.get(response.status_code, "Não foi possível concluir a solicitação."),
        "fields": fields,
        "request_id": str(uuid4()),
    }
    return response


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "code": "csrf_failed",
            "message": "Atualize a sessão e tente novamente.",
            "fields": {},
            "request_id": str(uuid4()),
        },
        status=403,
    )


def not_found(request, exception):
    return JsonResponse(
        {
            "code": "not_found",
            "message": "Recurso não encontrado.",
            "fields": {},
            "request_id": str(uuid4()),
        },
        status=404,
    )


def server_error(request):
    return JsonResponse(
        {
            "code": "server_error",
            "message": "Não foi possível concluir a solicitação.",
            "fields": {},
            "request_id": str(uuid4()),
        },
        status=500,
    )
