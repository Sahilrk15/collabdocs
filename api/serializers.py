from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers

from .models import (
    AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_email(self, value):
        value = value.strip().lower()
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError('Enter a valid email address.')
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError('Phone must contain digits only.')
        if not 7 <= len(value) <= 15:
            raise serializers.ValidationError('Phone must be between 7 and 15 digits.')
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('A user with this phone already exists.')
        return value


class WorkspaceSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'description', 'owner', 'is_active', 'created_at', 'member_count']
        read_only_fields = ['id', 'created_at']

    def get_member_count(self, obj):
        if hasattr(obj, 'member_total'):
            return obj.member_total
        return obj.memberships.count()

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError('Workspace name must be at least 2 characters.')
        return value


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user', 'role', 'joined_at']


class AddMemberSerializer(serializers.Serializer):
    user = serializers.UUIDField()
    role = serializers.ChoiceField(choices=WorkspaceMember.Role.choices, default=WorkspaceMember.Role.VIEWER)


class DocumentSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    tag_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)

    class Meta:
        model = Document
        fields = [
            'id', 'workspace', 'title', 'content', 'status', 'created_by',
            'created_at', 'updated_at', 'tags', 'tag_ids',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'created_by': {'required': True, 'allow_null': False}}

    def get_tags(self, obj):
        return [t.name for t in obj.tags.all()]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title cannot be blank.')
        return value


class DocumentUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Document.Status.choices, required=False)
    saved_by = serializers.UUIDField(required=False)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('Title cannot be blank.')
        return value.strip()


class DocumentVersionSerializer(serializers.ModelSerializer):
    saved_by = UserSerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = ['id', 'document', 'version_number', 'content', 'saved_by', 'saved_at']


class CommentSerializer(serializers.ModelSerializer):
    reply_count = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'document', 'author', 'parent', 'body', 'created_at', 'reply_count', 'replies']
        read_only_fields = ['id', 'created_at']

    def get_reply_count(self, obj):
        return obj.replies.count()

    def get_replies(self, obj):
        if self.context.get('nested'):
            return CommentSerializer(
                obj.replies.select_related('author', 'document'), many=True,
                context=self.context,
            ).data
        return []

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError('Comment body cannot be blank.')
        return value

    def validate(self, data):
        parent = data.get('parent')
        document = data.get('document')
        if parent and document and parent.document_id != document.id:
            raise serializers.ValidationError('Parent comment belongs to a different document.')
        return data


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']
        read_only_fields = ['id']
        extra_kwargs = {'name': {'validators': []}}  # duplicates are handled in the view (409)

    def validate_name(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError('Tag name cannot be blank.')
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'action', 'model_name', 'object_id', 'timestamp']
