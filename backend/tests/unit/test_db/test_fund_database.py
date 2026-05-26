"""
Tests for fund_database.py schema.

This test file verifies the fund database schema including:
1. Database initialization and table creation
2. Table existence for all 12 tables
3. Schema validation for key tables
4. CRUD operations

Tables covered (12 total):
- fund_indicators
- fund_issue_pipeline
- fund_company_metadata
- fund_company_distribution_history
- market_fear_greed_sentiment_history
- market_style_strength_history
- bond_equity_yield_spread_history
- index_valuation_history
- market_crowding_valuation_history
- bond_yield_curve_structure
- bond_credit_spread_history
- backtest_stats_macro_strategies
"""

import pytest
import sqlite3
import os

# Expected tables in fund_database
EXPECTED_TABLES = [
    'fund_indicators',
    'fund_issue_pipeline',
    'fund_company_metadata',
    'fund_company_distribution_history',
    'market_fear_greed_sentiment_history',
    'market_style_strength_history',
    'bond_equity_yield_spread_history',
    'index_valuation_history',
    'market_crowding_valuation_history',
    'bond_yield_curve_structure',
    'bond_credit_spread_history',
    'backtest_stats_macro_strategies',
]


@pytest.fixture(scope="module")
def fund_db():
    """Get the fund database connection for testing."""
    from app.db.fund_database import init_fund_database, get_fund_db_path
    
    # Initialize database
    init_fund_database()
    
    # Get path and connect
    db_path = get_fund_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    yield conn
    
    conn.close()


class TestFundDatabaseInitialization:
    """Test cases for fund database initialization."""

    def test_get_fund_db_path_returns_valid_path(self):
        """Test that get_fund_db_path returns a valid path."""
        from app.db.fund_database import get_fund_db_path
        
        path = get_fund_db_path()
        assert path is not None
        assert path.endswith('fund_database.db')
        assert '.config' in path or 'APP_DATA' in os.environ

    def test_init_fund_database_creates_tables(self, fund_db):
        """Test that init_fund_database creates all required tables."""
        cursor = fund_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        for table in EXPECTED_TABLES:
            assert table in tables, f"Table {table} should exist"

    def test_wal_mode_enabled(self, fund_db):
        """Test that WAL mode is enabled for the fund database."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        
        assert journal_mode.upper() == 'WAL', f"WAL mode should be enabled, got {journal_mode}"

    def test_performance_pragma_enabled(self, fund_db):
        """Test that performance PRAGMA settings are applied."""
        cursor = fund_db.cursor()
        
        # Check cache_size (negative = KB)
        cursor.execute("PRAGMA cache_size")
        cache_size = cursor.fetchone()[0]
        assert cache_size < 0, f"cache_size should be negative (KB mode), got {cache_size}"


class TestFundIndicatorsTable:
    """Test cases for fund_indicators table schema."""

    def test_fund_indicators_columns(self, fund_db):
        """Test that fund_indicators has all required columns."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(fund_indicators)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {
            'fund_code', 'fund_name', 'fund_type', 'manager', 'scale',
            'return_1y', 'return_3y', 'return_5y', 'sharpe_1y', 'max_drawdown_1y'
        }
        
        for col in required_columns:
            assert col in columns, f"Column {col} should exist in fund_indicators"

    def test_fund_indicators_primary_key(self, fund_db):
        """Test that fund_indicators has correct primary key."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(fund_indicators)")
        rows = cursor.fetchall()
        
        pk_columns = [row['name'] for row in rows if row['pk'] > 0]
        
        assert 'fund_code' in pk_columns, "fund_code should be primary key"

    def test_fund_indicators_indexes(self, fund_db):
        """Test that fund_indicators has performance indexes."""
        cursor = fund_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='fund_indicators'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        # Check for at least one composite index
        has_type_index = any('type' in idx.lower() and 'scale' in idx.lower() for idx in indexes)
        assert has_type_index or len(indexes) >= 3, "Should have performance indexes"


class TestMarketHistoryTables:
    """Test cases for market history tables."""

    def test_market_fear_greed_sentiment_history_schema(self, fund_db):
        """Test market_fear_greed_sentiment_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(market_fear_greed_sentiment_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'trade_date', 'composite_score', 'sentiment_status'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"

    def test_market_style_strength_history_schema(self, fund_db):
        """Test market_style_strength_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(market_style_strength_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'trade_date', 'index_code_num', 'index_code_den', 'ratio_value'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"

    def test_bond_equity_yield_spread_history_schema(self, fund_db):
        """Test bond_equity_yield_spread_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(bond_equity_yield_spread_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'index_code', 'trade_date', 'erp_spread', 'pe_ttm'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"

    def test_index_valuation_history_schema(self, fund_db):
        """Test index_valuation_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(index_valuation_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'index_code', 'trade_date', 'pe_ttm', 'pb'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestBondYieldTables:
    """Test cases for bond yield tables."""

    def test_bond_yield_curve_structure_schema(self, fund_db):
        """Test bond_yield_curve_structure table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(bond_yield_curve_structure)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'bond_type', 'trade_date', 'tenor', 'yield_ytm'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"

    def test_bond_credit_spread_history_schema(self, fund_db):
        """Test bond_credit_spread_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(bond_credit_spread_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # Actual columns in schema
        required_columns = {'bond_category', 'rating', 'tenor', 'trade_date', 'credit_spread'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestBacktestStatsTable:
    """Test cases for backtest_stats_macro_strategies table."""

    def test_backtest_stats_macro_strategies_schema(self, fund_db):
        """Test backtest_stats_macro_strategies table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(backtest_stats_macro_strategies)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {'index_code', 'metric_type', 'range_min', 'range_max', 'holding_period'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestFundCompanyTables:
    """Test cases for fund company tables."""

    def test_fund_company_metadata_schema(self, fund_db):
        """Test fund_company_metadata table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(fund_company_metadata)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {'company_id', 'company_name', 'total_scale', 'fund_count'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"

    def test_fund_company_distribution_history_schema(self, fund_db):
        """Test fund_company_distribution_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(fund_company_distribution_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {'company_id', 'dist_type', 'stat_quarter'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestFundIssuePipelineTable:
    """Test cases for fund_issue_pipeline table."""

    def test_fund_issue_pipeline_schema(self, fund_db):
        """Test fund_issue_pipeline table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(fund_issue_pipeline)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {'fund_code', 'fund_name', 'subscribe_start_date', 'status'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestMarketCrowdingValuationTable:
    """Test cases for market_crowding_valuation_history table."""

    def test_market_crowding_valuation_history_schema(self, fund_db):
        """Test market_crowding_valuation_history table schema."""
        cursor = fund_db.cursor()
        cursor.execute("PRAGMA table_info(market_crowding_valuation_history)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        required_columns = {'asset_code', 'trade_date', 'category', 'crowding_score'}
        for col in required_columns:
            assert col in columns, f"Column {col} should exist"


class TestCRUDOperations:
    """Test cases for CRUD operations on fund database."""

    def test_insert_and_query_fund_indicators(self, fund_db):
        """Test inserting and querying fund_indicators."""
        cursor = fund_db.cursor()
        
        # Clean up any existing test data
        cursor.execute("DELETE FROM fund_indicators WHERE fund_code = 'CRUD_TEST_001'")
        fund_db.commit()
        
        # Insert test data
        cursor.execute("""
            INSERT INTO fund_indicators (
                fund_code, fund_name, fund_type, manager, scale, return_1y, return_3y, return_5y
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('CRUD_TEST_001', 'Test Fund', '股票型', 'Test Manager', 10.5, 15.2, 45.6, 78.9))
        
        fund_db.commit()
        
        # Query test data
        cursor.execute("SELECT * FROM fund_indicators WHERE fund_code = ?", ('CRUD_TEST_001',))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['fund_name'] == 'Test Fund'
        assert row['fund_type'] == '股票型'
        assert row['scale'] == 10.5
        
        # Clean up
        cursor.execute("DELETE FROM fund_indicators WHERE fund_code = 'CRUD_TEST_001'")
        fund_db.commit()

    def test_insert_and_query_market_history(self, fund_db):
        """Test inserting and querying market history data."""
        cursor = fund_db.cursor()
        
        # Clean up any existing test data
        cursor.execute("DELETE FROM market_fear_greed_sentiment_history WHERE trade_date = '2099-01-01'")
        fund_db.commit()
        
        # Insert test data (using actual schema columns)
        cursor.execute("""
            INSERT INTO market_fear_greed_sentiment_history (
                trade_date, composite_score, sentiment_status
            ) VALUES (?, ?, ?)
        """, ('2099-01-01', 45.5, '中性'))
        
        fund_db.commit()
        
        # Query test data
        cursor.execute("SELECT * FROM market_fear_greed_sentiment_history WHERE trade_date = ?", ('2099-01-01',))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['composite_score'] == 45.5
        assert row['sentiment_status'] == '中性'
        
        # Clean up
        cursor.execute("DELETE FROM market_fear_greed_sentiment_history WHERE trade_date = '2099-01-01'")
        fund_db.commit()

    def test_unique_constraint_fund_indicators(self, fund_db):
        """Test that fund_indicators has unique constraint on fund_code (primary key)."""
        cursor = fund_db.cursor()
        
        # Clean up any existing test data
        cursor.execute("DELETE FROM fund_indicators WHERE fund_code = 'UNIQUE_TEST_001'")
        fund_db.commit()
        
        # Insert first record
        cursor.execute("""
            INSERT INTO fund_indicators (fund_code, fund_name) VALUES (?, ?)
        """, ('UNIQUE_TEST_001', 'Fund 1'))
        fund_db.commit()
        
        # Try to insert duplicate - should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO fund_indicators (fund_code, fund_name) VALUES (?, ?)
            """, ('UNIQUE_TEST_001', 'Fund 2'))
            fund_db.commit()
        
        # Clean up
        cursor.execute("DELETE FROM fund_indicators WHERE fund_code = 'UNIQUE_TEST_001'")
        fund_db.commit()

    def test_bond_yield_curve_insert(self, fund_db):
        """Test inserting bond yield curve data."""
        cursor = fund_db.cursor()
        
        # Clean up any existing test data
        cursor.execute("DELETE FROM bond_yield_curve_structure WHERE trade_date = '2099-01-01'")
        fund_db.commit()
        
        # Insert test data (using actual schema columns)
        cursor.execute("""
            INSERT INTO bond_yield_curve_structure (
                bond_type, trade_date, tenor, yield_ytm
            ) VALUES (?, ?, ?, ?)
        """, ('国债', '2099-01-01', '10Y', 2.65))
        
        fund_db.commit()
        
        # Query test data
        cursor.execute("""
            SELECT * FROM bond_yield_curve_structure 
            WHERE bond_type = ? AND trade_date = ? AND tenor = ?
        """, ('国债', '2099-01-01', '10Y'))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['yield_ytm'] == 2.65
        
        # Clean up
        cursor.execute("DELETE FROM bond_yield_curve_structure WHERE trade_date = '2099-01-01'")
        fund_db.commit()


class TestSchemaVerification:
    """Test cases for schema verification function."""

    def test_verify_schema_function(self):
        """Test that verify_schema returns correct information."""
        from app.db.fund_database import verify_schema
        
        result = verify_schema()
        
        assert result['success'] is True
        assert len(result['tables']) == 12
        assert len(result['missing']) == 0
        assert len(result['indexes']) > 0
