"""Migration operations that only run on PostgreSQL (no-ops on SQLite for local dev)."""

from django.db import migrations


class PostgresOnlySQL(migrations.RunSQL):
    """RunSQL that is skipped on non-Postgres databases."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)
