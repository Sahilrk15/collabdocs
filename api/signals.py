from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AuditLog, Document


@receiver(pre_save, sender=Document)
def remember_if_document_is_new(sender, instance, **kwargs):
    # By the time post_save runs, instance._state.adding is already False,
    # so we capture it here, before the row is written.
    instance._is_new = instance._state.adding


@receiver(post_save, sender=Document)
def write_document_audit_log(sender, instance, **kwargs):
    action = AuditLog.Action.CREATED if getattr(instance, '_is_new', False) else AuditLog.Action.UPDATED
    AuditLog.objects.create(
        actor=instance.created_by,
        action=action,
        model_name='Document',
        object_id=str(instance.pk),
    )
