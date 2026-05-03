#!/usr/bin/env python3
"""
内存分析工具 - 详细分析Python进程内存占用
"""
import sys
import gc
import os

# 必须在其他导入之前设置
os.environ['PYTHONUNBUFFERED'] = '1'

def get_size(obj, seen=None):
    """递归计算对象内存大小"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    
    if isinstance(obj, dict):
        size += sum(get_size(v, seen) for v in obj.values())
        size += sum(get_size(k, seen) for k in obj.keys())
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        try:
            size += sum(get_size(i, seen) for i in obj)
        except:
            pass
    return size

def analyze_memory():
    """分析内存占用"""
    import psutil
    import pandas as pd
    import numpy as np
    
    process = psutil.Process()
    mem_info = process.memory_info()
    
    print("=" * 60)
    print("AlphaTerminal 内存分析报告")
    print("=" * 60)
    print(f"\n进程基础信息:")
    print(f"  PID: {process.pid}")
    print(f"  RSS: {mem_info.rss / 1024 / 1024:.1f} MB")
    print(f"  VMS: {mem_info.vms / 1024 / 1024:.1f} MB")
    print(f"  Data: {mem_info.data / 1024 / 1024:.1f} MB")
    
    # 强制垃圾回收
    gc.collect()
    
    # 分析全局变量
    print(f"\n全局对象分析:")
    
    # 查找所有DataFrame
    dfs = []
    for obj in gc.get_objects():
        try:
            if isinstance(obj, pd.DataFrame):
                dfs.append(obj)
        except:
            pass
    
    print(f"  DataFrame对象数: {len(dfs)}")
    total_df_memory = 0
    for i, df in enumerate(dfs[:20]):  # 只显示前20个
        mem = df.memory_usage(deep=True).sum()
        total_df_memory += mem
        shape = df.shape
        print(f"    DataFrame {i+1}: {shape[0]}x{shape[1]}, {mem/1024:.1f} KB")
    if len(dfs) > 20:
        print(f"    ... 还有 {len(dfs)-20} 个DataFrame")
    print(f"  DataFrame总内存: {total_df_memory/1024/1024:.1f} MB")
    
    # 查找numpy数组
    arrays = []
    for obj in gc.get_objects():
        try:
            if isinstance(obj, np.ndarray):
                arrays.append(obj)
        except:
            pass
    
    total_array_memory = sum(a.nbytes for a in arrays)
    print(f"\n  NumPy数组数: {len(arrays)}")
    print(f"  NumPy数组总内存: {total_array_memory/1024/1024:.1f} MB")
    
    # 查找列表和字典
    lists = [obj for obj in gc.get_objects() if isinstance(obj, list)]
    dicts = [obj for obj in gc.get_objects() if isinstance(obj, dict)]
    print(f"\n  列表对象数: {len(lists)}")
    print(f"  字典对象数: {len(dicts)}")
    
    # 查找缓存对象
    cache_objects = []
    for obj in gc.get_objects():
        try:
            if isinstance(obj, dict) and len(obj) > 0:
                # 检查是否是缓存
                keys = list(obj.keys())[:5]
                if any('cache' in str(k).lower() or 'data' in str(k).lower() for k in keys):
                    cache_objects.append(obj)
        except:
            pass
    
    print(f"\n  疑似缓存字典数: {len(cache_objects)}")
    for i, cache in enumerate(cache_objects[:10]):
        try:
            size = get_size(cache)
            print(f"    Cache {i+1}: {len(cache)} 条目, {size/1024:.1f} KB")
        except:
            pass

if __name__ == "__main__":
    analyze_memory()
