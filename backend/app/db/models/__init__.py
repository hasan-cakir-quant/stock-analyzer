"""ORM models — importing this package registers every table on Base.metadata."""

from app.db.models.financial_import import FinancialImport
from app.db.models.job_run import JobRun
from app.db.models.quarterly_financial import QuarterlyFinancial
from app.db.models.setting import Setting
from app.db.models.snapshot import Snapshot
from app.db.models.stock import Stock
from app.db.models.stock_fair_value import StockFairValue
from app.db.models.stock_grade import StockGrade
from app.db.models.stock_parameter import StockParameter

__all__ = [
    "FinancialImport",
    "JobRun",
    "QuarterlyFinancial",
    "Setting",
    "Snapshot",
    "Stock",
    "StockFairValue",
    "StockGrade",
    "StockParameter",
]
