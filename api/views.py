import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import (
    AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember,
)
from .serializers import (
    AddMemberSerializer, AuditLogSerializer, CommentSerializer, DocumentSerializer,
    DocumentUpdateSerializer, DocumentVersionSerializer, TagSerializer, UserSerializer,
    WorkspaceMemberSerializer, WorkspaceSerializer,
)


def error(message, code):
    return Response({'error': message}, status=code)


def uuid_param(request, name):
    """Read a UUID query param; return None if absent, raise 400 if malformed."""
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ValidationError({name: f'"{value}" is not a valid UUID.'})


def date_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError({name: f'"{value}" is not a valid date (use YYYY-MM-DD).'})
    return parsed


# ---------------------------------------------------------------- Users
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'head', 'options']


# ----------------------------------------------------------- Workspaces
class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = Workspace.objects.select_related('owner').annotate(
            member_total=Count('memberships', distinct=True)
        )
        owner = uuid_param(self.request, 'owner')
        if owner:
            qs = qs.filter(owner_id=owner)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Workspace + owner membership + audit log: all or nothing.
        with transaction.atomic():
            workspace = serializer.save()
            WorkspaceMember.objects.create(
                workspace=workspace, user=workspace.owner, role=WorkspaceMember.Role.ADMIN
            )
            AuditLog.objects.create(
                actor=workspace.owner, action=AuditLog.Action.CREATED,
                model_name='Workspace', object_id=str(workspace.pk),
            )
        workspace = self.get_queryset().get(pk=workspace.pk)
        return Response(self.get_serializer(workspace).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='members')
    def members(self, request, pk=None):
        workspace = self.get_object()

        if request.method == 'GET':
            qs = workspace.memberships.select_related('user', 'workspace')
            role = request.query_params.get('role')
            if role:
                qs = qs.filter(role__in=role.split(','))
            return Response(WorkspaceMemberSerializer(qs, many=True).data)

        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.get(pk=serializer.validated_data['user'])
        except User.DoesNotExist:
            return error('User not found.', status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                member = WorkspaceMember.objects.create(
                    workspace=workspace, user=user, role=serializer.validated_data['role']
                )
        except IntegrityError:
            return error('This user is already a member of the workspace.', status.HTTP_409_CONFLICT)
        member = WorkspaceMember.objects.select_related('user').get(pk=member.pk)
        return Response(WorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        self.get_object()  # 404 if missing
        data = Workspace.objects.filter(pk=pk).aggregate(
            total_documents=Count('documents', distinct=True),
            total_members=Count('memberships', distinct=True),
            total_comments=Count('documents__comments', distinct=True),
        )
        return Response({'workspace': str(pk), **data})


# ------------------------------------------------------------ Documents
class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    http_method_names = ['get', 'post', 'put', 'head', 'options']

    def get_queryset(self):
        qs = Document.objects.select_related('workspace', 'created_by').prefetch_related('tags')
        p = self.request.query_params

        workspace = uuid_param(self.request, 'workspace')
        if workspace:
            qs = qs.filter(workspace_id=workspace)

        statuses = p.get('status')
        if statuses:
            qs = qs.filter(status__in=[s.strip() for s in statuses.split(',')])

        tag = p.get('tag')
        if tag:
            doc_ids = Document.tags.through.objects.filter(
                tag__name=tag.strip().lower()
            ).values_list('document_id', flat=True)
            qs = qs.filter(id__in=doc_ids)

        search = p.get('search')
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search))

        updated_from = date_param(self.request, 'updated_from')
        if updated_from:
            qs = qs.filter(updated_at__date__gte=updated_from)
        updated_to = date_param(self.request, 'updated_to')
        if updated_to:
            qs = qs.filter(updated_at__date__lte=updated_to)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        tag_ids = data.pop('tag_ids', [])
        try:
            # Document + version 1 + tags (+ AuditLog from the signal): one transaction.
            with transaction.atomic():
                document = Document.objects.create(**data)
                DocumentVersion.objects.create(
                    document=document,
                    content=document.content,
                    version_number=document.versions.count() + 1,
                    saved_by=document.created_by,
                )
                for tag_id in tag_ids:
                    document.tags.add(Tag.objects.get(pk=tag_id))
        except Tag.DoesNotExist:
            return error(
                'One of the tag_ids does not exist. Nothing was saved (transaction rolled back).',
                status.HTTP_404_NOT_FOUND,
            )
        document = self.get_queryset().get(pk=document.pk)
        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        document = self.get_object()
        serializer = DocumentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                saved_by = (
                    User.objects.get(pk=data['saved_by']) if 'saved_by' in data
                    else document.created_by
                )
                for field in ('title', 'content', 'status'):
                    if field in data:
                        setattr(document, field, data[field])
                document.save()  # post_save signal writes the AuditLog (same transaction)
                DocumentVersion.objects.create(
                    document=document,
                    content=document.content,
                    version_number=document.versions.count() + 1,
                    saved_by=saved_by,
                )
        except User.DoesNotExist:
            return error('saved_by user not found. Nothing was saved.', status.HTTP_404_NOT_FOUND)
        document = self.get_queryset().get(pk=document.pk)
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        document = self.get_object()
        qs = document.versions.select_related('saved_by', 'document')
        return Response(DocumentVersionSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        self.get_object()
        data = Document.objects.filter(pk=pk).aggregate(
            version_count=Count('versions', distinct=True),
            comment_count=Count('comments', distinct=True),
            contributor_count=Count('versions__saved_by', distinct=True),
        )
        return Response({'document': str(pk), **data})

    @action(detail=True, methods=['get', 'post'], url_path='tags')
    def tags(self, request, pk=None):
        document = self.get_object()
        if request.method == 'GET':
            return Response(TagSerializer(document.tags.all(), many=True).data)

        tag_ids = request.data.get('tag_ids')
        if not isinstance(tag_ids, list) or not tag_ids:
            return error('tag_ids must be a non-empty list of tag UUIDs.', status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                for tag_id in tag_ids:
                    document.tags.add(Tag.objects.get(pk=tag_id))
        except Tag.DoesNotExist:
            return error('One of the tags does not exist. Nothing was added.', status.HTTP_404_NOT_FOUND)
        except DjangoValidationError:
            return error('tag_ids contains an invalid UUID.', status.HTTP_400_BAD_REQUEST)
        return Response(TagSerializer(document.tags.all(), many=True).data, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------- Comments
class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = Comment.objects.select_related('author', 'document', 'parent')
        document = uuid_param(self.request, 'document')
        if document:
            qs = qs.filter(document_id=document)
        author = uuid_param(self.request, 'author')
        if author:
            qs = qs.filter(author_id=author)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        nested = bool(request.query_params.get('document'))
        if nested:
            qs = qs.filter(parent__isnull=True)  # threads: top-level + nested replies
        serializer = self.get_serializer(qs, many=True, context={**self.get_serializer_context(), 'nested': nested})
        return Response(serializer.data)


# ----------------------------------------------------------------- Tags
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = Tag.objects.annotate(document_total=Count('documents'))
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                tag = serializer.save()
        except IntegrityError:
            return error(
                f'Tag "{serializer.validated_data["name"]}" already exists.', status.HTTP_409_CONFLICT
            )
        return Response(self.get_serializer(tag).data, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------ Audit logs
class AuditLogViewSet(viewsets.ModelViewSet):
    serializer_class = AuditLogSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = AuditLog.objects.select_related('actor')
        p = self.request.query_params
        actor = uuid_param(self.request, 'actor')
        if actor:
            qs = qs.filter(actor_id=actor)
        date_from = date_param(self.request, 'date_from')
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        date_to = date_param(self.request, 'date_to')
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        if p.get('model_name'):
            qs = qs.filter(model_name__icontains=p['model_name'])
        if p.get('action'):
            qs = qs.filter(action__in=p['action'].split(','))
        if p.get('object_id'):
            qs = qs.filter(object_id=p['object_id'])
        return qs
