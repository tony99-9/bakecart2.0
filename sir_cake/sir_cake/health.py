"""
Health check and system status API view.
"""
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_view(request):
    """
    Lightweight health-check endpoint.
    Verifies service liveness and database connectivity.
    """
    db_ok = True
    db_error = None
    try:
        connection.ensure_connection()
    except Exception as e:
        db_ok = False
        db_error = str(e)

    payload = {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "bakecart-api",
        "database": {
            "connected": db_ok,
            "engine": connection.settings_dict.get('ENGINE', '').split('.')[-1],
        }
    }

    if not db_ok:
        payload["database"]["error"] = db_error
        return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(payload, status=status.HTTP_200_OK)
