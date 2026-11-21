from rest_framework import serializers


class OwnedRelatedField(serializers.PrimaryKeyRelatedField):
    """A foreign-key field that only accepts rows the current user owns (admins: any row).

    Stops a sales rep from, say, attaching a lead to another rep's contact by guessing its id.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        if request is None or request.user.is_admin:
            return queryset
        return queryset.filter(owner=request.user)


class OwnedModelSerializer(serializers.ModelSerializer):
    """Adds a read-only owner id + name to any OwnedModel serializer."""

    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    owner_name = serializers.SerializerMethodField()

    def get_owner_name(self, obj) -> str | None:
        owner = getattr(obj, "owner", None)
        return (owner.get_full_name() or owner.username) if owner else None
