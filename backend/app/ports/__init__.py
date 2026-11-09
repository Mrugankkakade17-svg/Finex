"""
backend/app/ports

Abstract interfaces the whole FinEx team codes against instead of vendor
SDKs. See each file's module docstring for what it's for. Concrete
implementations (e.g. `LakebaseOperationalStore`) live elsewhere (typically
under `backend/app/adapters/`) and get built as later sprints need them.
"""
