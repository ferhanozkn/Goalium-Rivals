from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema

from apps.imports.models import ImportJob
from apps.imports.serializers import ImportJobSerializer, ImportRequestSerializer
from apps.imports.services import CatalogImporter


EDITOR_AUTHENTICATION = [JWTAuthentication, SessionAuthentication]


@extend_schema(request=ImportRequestSerializer, responses={201: ImportJobSerializer}, tags=["content-imports"])
@api_view(["POST"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def imports_create(request):
    serializer = ImportRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    job = ImportJob.objects.create(
        provider=values["provider"],
        source_url=values["source_url"],
        license_name=values["license_name"],
        license_status=values["license_status"],
        requested_by=request.user,
    )
    CatalogImporter().run(job, values["records"])
    return Response(ImportJobSerializer(job).data, status=status.HTTP_201_CREATED)


@extend_schema(responses={200: ImportJobSerializer}, tags=["content-imports"])
@api_view(["GET"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def imports_detail(request, job_id):
    job = ImportJob.objects.filter(id=job_id).first()
    if job is None:
        return Response({"detail": "İçe aktarma işi bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    return Response(ImportJobSerializer(job).data)
