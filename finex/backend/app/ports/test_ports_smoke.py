from app.ports.operational_store import OperationalStore


def test_operational_store_shape():
    methods = [
        "fetch_one",
        "fetch_many",
        "insert",
        "update",
        "soft_delete",
        "run_in_transaction",
    ]
    for method in methods:
        assert hasattr(OperationalStore, method)
