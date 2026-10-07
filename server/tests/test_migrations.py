from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect

from app import create_app, db
from tests.conftest import TestConfig


def make_app(tmp_path):
    class MigrationConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'migrations.db'}"

    return create_app(MigrationConfig)


def test_migrations_build_the_schema_the_models_describe(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upgrade()

        with db.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            # A non-empty diff means a model changed without a new migration.
            assert compare_metadata(context, db.metadata) == []

        tables = set(inspect(db.engine).get_table_names())
        assert tables == {
            "alembic_version",
            "users",
            "rooms",
            "students",
            "contracts",
            "payments",
        }


def test_migrated_database_works_and_downgrades_cleanly(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upgrade()

    assert app.test_cli_runner().invoke(args=["seed"]).exit_code == 0
    client = app.test_client()
    client.post("/auth/login", data={"login": "admin", "password": "Admin123!"})
    assert client.get("/rooms/").status_code == 200

    with app.app_context():
        downgrade(revision="base")
        db.engine.dispose()
        assert inspect(db.engine).get_table_names() == ["alembic_version"]
