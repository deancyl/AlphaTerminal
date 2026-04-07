"""
市场状态工具 — Phase 6
判断 A 股、港股、美股当前是否处于交易时段
"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


# ── A 股（上交所/深交所）────────────────────────
#   周一至周五：09:30-11:30，13:00-15:00
A_SHARE_OPEN  = (time(9, 30), time(11, 30))
A_SHARE_OPEN2 = (time(13, 0), time(15, 0))

# ── 港股（恒生）────────────────────────────────
#   周一至周五：09:30-12:00，13:00-16:00
HK_OPEN  = (time(9, 30), time(12, 0))
HK_OPEN2 = (time(13, 0), time(16, 0))

# ── 美股（纽交所/纳斯达克）─────────────────────
#   夏令时（3月中-11月初）：21:30-04:00（次日）
#   冬令时：22:30-05:00（次日）
#   为简化判断，统一用 22:00-04:00 做覆盖
US_OPEN  = (time(22, 0), time(4, 0))


def is_market_open(market_type: str = "A_SHARE") -> tuple[bool, str]:
    """
    返回 (is_open: bool, status: str)
    status: "交易中" | "已休市" | "盘前" | "盘后"
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=周一, 6=周日

    if market_type == "A_SHARE":
        if weekday >= 5:
            return False, "已休市"
        t = now.time()
        open1  = A_SHARE_OPEN[0]
        close1 = A_SHARE_OPEN[0].__class__(A_SHARE_OPEN[1].hour, A_SHARE_OPEN[1].minute)
        open2  = A_SHARE_OPEN2[0]
        close2 = A_SHARE_OPEN2[1]
        # 早盘
        if open1 <= t <= close1:
            return True, "交易中"
        # 午盘
        if open2 <= t <= close2:
            return True, "交易中"
        # 盘前 (08:30-09:30)
        if time(8, 30) <= t < open1:
            return False, "盘前"
        # 午休 (11:30-13:00)
        if t > close1 and t < open2:
            return False, "已休市"
        # 盘后
        if t > close2:
            return False, "已休市"
        return False, "已休市"

    elif market_type == "HK":
        if weekday >= 5:
            return False, "已休市"
        t = now.time()
        if HK_OPEN[0] <= t <= HK_OPEN[1]:
            return True, "交易中"
        if HK_OPEN2[0] <= t <= HK_OPEN2[1]:
            return True, "交易中"
        if time(9, 0) <= t < HK_OPEN[0]:
            return False, "盘前"
        if t > HK_OPEN2[1]:
            return False, "已休市"
        return False, "已休市"

    elif market_type == "US":
        # 使用美东时区判断（NYSE: UTC-5 冬令时 / UTC-4 夏令时）
        try:
            eastern = now.astimezone(ZoneInfo("America/New_York"))
            et_hour, et_min = eastern.hour, eastern.minute
            et_time = time(et_hour, et_min)
            et_weekday = eastern.weekday()

            # 周六/周日休市
            if et_weekday >= 5:
                return False, "已休市"

            # 盘前 09:30-16:00 ET（主要交易时段）
            if time(9, 30) <= et_time <= time(16, 0):
                return True, "交易中"
            # 盘后 16:00-20:00 ET
            if et_time > time(16, 0) and et_time <= time(20, 0):
                return False, "盘后"
            # 隔夜盘前 04:00-09:30 ET
            if et_time >= time(4, 0) and et_time < time(9, 30):
                return False, "盘前"
            # 隔夜交易时段（前日 20:00 - 当日 04:00 ET，实为盘后电子盘）
            if et_time < time(4, 0):
                return False, "盘后"
            return False, "已休市"
        except Exception:
            # 时区转换失败时用简化逻辑（本地时间，仅作保底）
            if weekday >= 5:
                return False, "已休市"
            t = now.time()
            if time(9, 30) <= t <= time(16, 0):
                return True, "交易中"
            return False, "已休市"

    elif market_type == "JP":
        # 日经225：周一至周五 09:00-15:00 JST（= 北京时间 08:00-14:00）
        try:
            eastern = now.astimezone(ZoneInfo("Asia/Tokyo"))
            et_weekday = eastern.weekday()
            et_time = time(eastern.hour, eastern.minute)
            if et_weekday >= 5:
                return False, "已休市"
            if time(9, 0) <= et_time <= time(15, 0):
                return True, "交易中"
            if time(8, 0) <= et_time < time(9, 0):
                return False, "盘前"
            if et_time > time(15, 0):
                return False, "已休市"
            return False, "已休市"
        except Exception:
            return False, "已休市"

    return False, "已休市"
