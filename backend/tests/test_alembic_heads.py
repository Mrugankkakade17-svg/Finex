"""Test Alembic migration graph integrity and single-head invariant."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_exactly_one_head() -> None:
    """Ensure the Alembic migration tree contains no unmerged split heads."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(backend_dir / "alembic"))

    script_dir = ScriptDirectory.from_config(config)
    heads = script_dir.get_heads()

    assert len(heads) == 1, (
        f"Alembic must have exactly one head revision, found {len(heads)}: {heads}. "
        "Create an Alembic merge migration to resolve parallel branch heads."
    )
    assert heads[0] == "s3_fx006_checkpoint"

    # Verify the merge revision parents
    merge_revision = script_dir.get_revision("s3_merge_fx006_heads")
    assert merge_revision is not None
    assert set(merge_revision.down_revision or ()) == {
        "s1li02_auth_persistence",
        "s3mr01_fx006",
        "s2pa04_fx006",
    }

    # Verify checkpoint revision points to merge revision
    checkpoint_revision = script_dir.get_revision("s3_fx006_checkpoint")
    assert checkpoint_revision is not None
    assert checkpoint_revision.down_revision == "s3_merge_fx006_heads"
