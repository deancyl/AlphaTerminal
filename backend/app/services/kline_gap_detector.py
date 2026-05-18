"""
K线缺口检测器

功能:
- 检测K线数据中的时间缺口（停牌、数据源故障）
- 估算缺失的K线数量
- 返回缺口信息供前端展示

设计原则:
- 各周期有不同的最大允许间隔
- 跳过周末和节假日（日K）
- 提供缺口补齐建议
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class KlineGapDetector:
    """K线缺口检测器"""
    
    # 各周期允许的最大间隔（秒）
    # 日K：3天（跳过周末）
    # 分钟K：考虑交易时间段
    PERIOD_MAX_GAP = {
        'daily': 3 * 24 * 3600,      # 3天（跳过周末）
        'weekly': 10 * 24 * 3600,     # 10天
        'monthly': 40 * 24 * 3600,    # 40天
        '1min': 120,                  # 2分钟
        '5min': 600,                  # 10分钟
        '15min': 1800,                # 30分钟
        '30min': 3600,                # 1小时
        '60min': 7200,                # 2小时
        'minutely': 120,              # 2分钟（别名）
    }
    
    def detect_gaps(self, history: List[Dict], period: str) -> List[Dict]:
        """
        检测K线缺口
        
        Args:
            history: K线历史数据，按时间升序排列
            period: 周期 (daily, weekly, monthly, 1min, 5min, etc.)
            
        Returns:
            缺口列表: [{'start_date', 'end_date', 'missing_count', 'gap_seconds'}, ...]
        """
        if len(history) < 2:
            return []
        
        max_gap = self.PERIOD_MAX_GAP.get(period, 3 * 24 * 3600)
        gaps = []
        
        for i in range(1, len(history)):
            prev_date = self._parse_date(history[i-1].get('date', ''))
            curr_date = self._parse_date(history[i].get('date', ''))
            
            if not prev_date or not curr_date:
                continue
            
            gap_seconds = (curr_date - prev_date).total_seconds()
            
            if gap_seconds > max_gap:
                gap_info = {
                    'start_date': history[i-1]['date'],
                    'end_date': history[i]['date'],
                    'missing_count': self._estimate_missing(gap_seconds, period),
                    'gap_seconds': int(gap_seconds),
                    'gap_type': self._classify_gap(gap_seconds, period)
                }
                gaps.append(gap_info)
                
                logger.warning(
                    f"[K-line Gap] Detected: {gap_info['start_date']} -> {gap_info['end_date']}, "
                    f"missing ~{gap_info['missing_count']} bars, type={gap_info['gap_type']}"
                )
        
        return gaps
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
            
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y%m%d',
            '%Y%m%d%H%M',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    def _estimate_missing(self, gap_seconds: float, period: str) -> int:
        """
        估算缺失的K线数量
        
        注意：这是粗略估算，不考虑交易时间段
        """
        if period == 'daily':
            # 日K：跳过周末，每个交易日约86400秒
            # 粗略估算：gap_days - 2（周末）
            gap_days = gap_seconds / (24 * 3600)
            return max(1, int(gap_days) - 2)
        
        elif period in ('1min', '5min', '15min', '30min', '60min', 'minutely'):
            minutes = {
                '1min': 1, '5min': 5, '15min': 15, 
                '30min': 30, '60min': 60, 'minutely': 1
            }
            # 考虑交易时间（每天约4小时 = 240分钟）
            trading_minutes_per_day = 240
            gap_minutes = gap_seconds / 60
            expected_bars_per_day = trading_minutes_per_day / minutes[period]
            
            gap_days = gap_seconds / (24 * 3600)
            return max(1, int(gap_days * expected_bars_per_day))
        
        elif period == 'weekly':
            gap_weeks = gap_seconds / (7 * 24 * 3600)
            return max(1, int(gap_weeks))
        
        elif period == 'monthly':
            gap_months = gap_seconds / (30 * 24 * 3600)
            return max(1, int(gap_months))
        
        return 1
    
    def _classify_gap(self, gap_seconds: float, period: str) -> str:
        """
        分类缺口类型
        
        Returns:
            'suspension': 停牌（几天到几周）
            'data_error': 数据源故障（超过一个月）
            'normal': 正常间隔（周末、节假日）
        """
        days = gap_seconds / (24 * 3600)
        
        if period == 'daily':
            if days <= 3:
                return 'normal'  # 周末
            elif days <= 30:
                return 'suspension'  # 停牌
            else:
                return 'data_error'  # 数据源故障
        
        return 'suspension' if days <= 30 else 'data_error'
    
    def get_gap_summary(self, gaps: List[Dict]) -> Dict:
        """
        生成缺口摘要
        
        Returns:
            {'total_gaps', 'total_missing', 'suspension_count', 'data_error_count'}
        """
        if not gaps:
            return {
                'total_gaps': 0,
                'total_missing': 0,
                'suspension_count': 0,
                'data_error_count': 0
            }
        
        return {
            'total_gaps': len(gaps),
            'total_missing': sum(g['missing_count'] for g in gaps),
            'suspension_count': sum(1 for g in gaps if g['gap_type'] == 'suspension'),
            'data_error_count': sum(1 for g in gaps if g['gap_type'] == 'data_error')
        }


# 全局实例
gap_detector = KlineGapDetector()
