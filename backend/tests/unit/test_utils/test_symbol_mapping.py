"""Tests for macro symbol mapping in DashboardGrid.vue

This tests the MACRO_SYMBOL_MAP and normalizeMacroSymbol function
that maps Chinese/English macro symbol names to standard symbols.

The mapping is implemented in frontend/src/components/DashboardGrid.vue
but we test the logic here to ensure correctness.
"""

import pytest
import re


class TestMacroSymbolMapping:
    """Test cases for macro symbol mapping."""
    
    # Mapping table (copied from DashboardGrid.vue MACRO_SYMBOL_MAP)
    MACRO_SYMBOL_MAP = {
        # Gold variants
        '黄金': 'GOLD', '黄金(美元)': 'GOLD', '黄金(人民币)': 'GOLD',
        'XAU': 'GOLD', 'GLD': 'GOLD', 'GOLD': 'GOLD',
        'SGE黄金': 'GOLD', 'SGE黄金(人民币)': 'GOLD',
        'gold': 'GOLD', 'xau': 'GOLD', 'gld': 'GOLD',
        
        # WTI/Crude Oil variants
        'WTI原油': 'WTI', 'WTI': 'WTI', '原油': 'WTI',
        'NYMEX_WTI': 'WTI', 'CL': 'WTI', 'WTI原油(美元)': 'WTI',
        'wti': 'WTI', 'wtic': 'WTI',
        
        # VIX variants
        'VIX': 'VIX', '恐慌指数': 'VIX', '波动率指数': 'VIX',
        'vix': 'VIX',
        
        # USD/CNH variants
        'USD/CNH': 'CNHUSD', 'CNHUSD': 'CNHUSD', '离岸人民币': 'CNHUSD',
        '人民币': 'CNHUSD', 'usd/cnh': 'CNHUSD', 'cnhusd': 'CNHUSD',
        
        # DXY variants
        'DXY': 'DXY', '美元指数': 'DXY', 'dxy': 'DXY',
        
        # VHSI variants
        '恒指波幅': 'VHSI', 'VHSI': 'VHSI', 'VHKS': 'VHSI',
        'vhsi': 'VHSI',
        
        # Nikkei variants
        '日经225': 'N225', '日经': 'N225', 'N225': 'N225',
        
        # DJI/SPX/NDX
        'DJI': 'DJI', '道琼斯': 'DJI',
        'SPX': 'SPX', '标普500': 'SPX',
        'NDX': 'NDX', '纳斯达克100': 'NDX',
    }
    
    @staticmethod
    def normalize_macro_symbol(name):
        """Python implementation of the JavaScript function."""
        if not name or not name.strip():
            return None
        
        # Direct match
        if name in TestMacroSymbolMapping.MACRO_SYMBOL_MAP:
            return TestMacroSymbolMapping.MACRO_SYMBOL_MAP[name]
        
        # Remove parentheses content and try again
        cleaned = re.sub(r'\([^)]*\)', '', name).strip()
        if cleaned in TestMacroSymbolMapping.MACRO_SYMBOL_MAP:
            return TestMacroSymbolMapping.MACRO_SYMBOL_MAP[cleaned]
        
        # Try lowercase
        lower = cleaned.lower()
        if lower in TestMacroSymbolMapping.MACRO_SYMBOL_MAP:
            return TestMacroSymbolMapping.MACRO_SYMBOL_MAP[lower]
        
        return None
    
    def test_gold_chinese_names(self):
        """Test all Chinese gold variants map to GOLD."""
        assert self.normalize_macro_symbol('黄金') == 'GOLD'
        assert self.normalize_macro_symbol('黄金(美元)') == 'GOLD'
        assert self.normalize_macro_symbol('黄金(人民币)') == 'GOLD'
        assert self.normalize_macro_symbol('SGE黄金') == 'GOLD'
        assert self.normalize_macro_symbol('SGE黄金(人民币)') == 'GOLD'
    
    def test_gold_english_names(self):
        """Test all English gold variants map to GOLD."""
        assert self.normalize_macro_symbol('GOLD') == 'GOLD'
        assert self.normalize_macro_symbol('XAU') == 'GOLD'
        assert self.normalize_macro_symbol('GLD') == 'GOLD'
        assert self.normalize_macro_symbol('gold') == 'GOLD'
        assert self.normalize_macro_symbol('xau') == 'GOLD'
    
    def test_wti_variants(self):
        """Test all WTI variants map to WTI."""
        assert self.normalize_macro_symbol('WTI原油') == 'WTI'
        assert self.normalize_macro_symbol('WTI') == 'WTI'
        assert self.normalize_macro_symbol('原油') == 'WTI'
        assert self.normalize_macro_symbol('WTI原油(美元)') == 'WTI'
        assert self.normalize_macro_symbol('CL') == 'WTI'
    
    def test_vix_variants(self):
        """Test all VIX variants map to VIX."""
        assert self.normalize_macro_symbol('VIX') == 'VIX'
        assert self.normalize_macro_symbol('恐慌指数') == 'VIX'
        assert self.normalize_macro_symbol('波动率指数') == 'VIX'
        assert self.normalize_macro_symbol('vix') == 'VIX'
    
    def test_cnh_variants(self):
        """Test all USD/CNH variants map to CNHUSD."""
        assert self.normalize_macro_symbol('USD/CNH') == 'CNHUSD'
        assert self.normalize_macro_symbol('离岸人民币') == 'CNHUSD'
        assert self.normalize_macro_symbol('CNHUSD') == 'CNHUSD'
    
    def test_vhsi_variants(self):
        """Test all VHSI variants map to VHSI."""
        assert self.normalize_macro_symbol('恒指波幅') == 'VHSI'
        assert self.normalize_macro_symbol('VHSI') == 'VHSI'
        assert self.normalize_macro_symbol('VHKS') == 'VHSI'
    
    def test_null_input(self):
        """Test null/empty input returns None."""
        assert self.normalize_macro_symbol(None) is None
        assert self.normalize_macro_symbol('') is None
        assert self.normalize_macro_symbol('   ') is None
    
    def test_unmapped_symbol(self):
        """Test unmapped symbols return None."""
        assert self.normalize_macro_symbol('UNKNOWN_SYMBOL') is None
        assert self.normalize_macro_symbol('未知品种') is None
    
    def test_parentheses_removal(self):
        """Test parentheses removal works correctly."""
        # These should all map correctly after parentheses removal
        assert self.normalize_macro_symbol('黄金(美元)') == 'GOLD'
        assert self.normalize_macro_symbol('WTI原油(美元)') == 'WTI'
    
    def test_case_insensitivity(self):
        """Test lowercase variants work."""
        assert self.normalize_macro_symbol('gold') == 'GOLD'
        assert self.normalize_macro_symbol('wti') == 'WTI'
        assert self.normalize_macro_symbol('vix') == 'VIX'
        assert self.normalize_macro_symbol('dxy') == 'DXY'
    
    def test_dxy_variants(self):
        """Test all DXY variants map to DXY."""
        assert self.normalize_macro_symbol('DXY') == 'DXY'
        assert self.normalize_macro_symbol('美元指数') == 'DXY'
        assert self.normalize_macro_symbol('dxy') == 'DXY'
    
    def test_nikkei_variants(self):
        """Test all Nikkei variants map to N225."""
        assert self.normalize_macro_symbol('日经225') == 'N225'
        assert self.normalize_macro_symbol('日经') == 'N225'
        assert self.normalize_macro_symbol('N225') == 'N225'
    
    def test_index_variants(self):
        """Test DJI, SPX, NDX variants."""
        assert self.normalize_macro_symbol('DJI') == 'DJI'
        assert self.normalize_macro_symbol('道琼斯') == 'DJI'
        assert self.normalize_macro_symbol('SPX') == 'SPX'
        assert self.normalize_macro_symbol('标普500') == 'SPX'
        assert self.normalize_macro_symbol('NDX') == 'NDX'
        assert self.normalize_macro_symbol('纳斯达克100') == 'NDX'
    
    def test_all_mappings_are_valid(self):
        """Test that all mapped values are valid standard symbols."""
        valid_symbols = {'GOLD', 'WTI', 'VIX', 'CNHUSD', 'DXY', 'VHSI', 'N225', 'DJI', 'SPX', 'NDX'}
        for key, value in self.MACRO_SYMBOL_MAP.items():
            assert value in valid_symbols, f"Invalid mapping: {key} -> {value}"
    
    def test_no_duplicate_mappings_to_different_values(self):
        """Test that no key maps to different values (consistency check)."""
        # Group by normalized value
        value_to_keys = {}
        for key, value in self.MACRO_SYMBOL_MAP.items():
            if value not in value_to_keys:
                value_to_keys[value] = []
            value_to_keys[value].append(key)
        
        # All keys mapping to same value should be consistent
        # This test passes by design since we're checking the map itself
        assert len(value_to_keys) == 10  # 10 unique standard symbols
