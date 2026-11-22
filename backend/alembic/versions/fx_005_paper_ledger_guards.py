"""S2-MR01 fx_005: enforce append-only ledger and nonnegative cash.

Revision ID: s2mr01_fx005
Revises: s2mr01_fx004
"""

from typing import Sequence, Union

from alembic import op

revision: str = "s2mr01_fx005"
down_revision: Union[str, Sequence[str], None] = "s2mr01_fx004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION finex.enforce_paper_ledger_balance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            current_balance BIGINT;
        BEGIN
            -- Serialize writes per account so concurrent debits cannot overspend.
            PERFORM 1
              FROM finex.paper_accounts
             WHERE account_id = NEW.account_id
               AND user_id = NEW.user_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'paper account does not exist for ledger owner'
                    USING ERRCODE = '23503';
            END IF;

            SELECT COALESCE(SUM(cash_delta_cents), 0)
              INTO current_balance
              FROM finex.paper_ledger
             WHERE account_id = NEW.account_id;

            IF current_balance + NEW.cash_delta_cents < 0 THEN
                RAISE EXCEPTION 'paper ledger entry would create a negative cash balance'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_paper_ledger_nonnegative_balance
        BEFORE INSERT ON finex.paper_ledger
        FOR EACH ROW EXECUTE FUNCTION finex.enforce_paper_ledger_balance()
        """
    )
    op.execute(
        """
        CREATE FUNCTION finex.reject_paper_ledger_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'paper ledger is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_paper_ledger_append_only
        BEFORE UPDATE OR DELETE ON finex.paper_ledger
        FOR EACH ROW EXECUTE FUNCTION finex.reject_paper_ledger_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_paper_ledger_append_only ON finex.paper_ledger")
    op.execute("DROP FUNCTION finex.reject_paper_ledger_mutation()")
    op.execute("DROP TRIGGER trg_paper_ledger_nonnegative_balance ON finex.paper_ledger")
    op.execute("DROP FUNCTION finex.enforce_paper_ledger_balance()")

