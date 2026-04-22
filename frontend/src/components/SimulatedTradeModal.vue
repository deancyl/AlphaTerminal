<template>
  <div v-if="visible" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="close">
    <div class="bg-gray-900 border border-gray-700 rounded-lg p-6 w-96 shadow-2xl">
      <!-- Header -->
      <div class="flex items-center justify-between mb-5">
        <h3 class="text-white font-bold text-base">📋 模拟调仓</h3>
        <button @click="close" class="text-gray-400 hover:text-white text-lg">×</button>
      </div>

      <!-- 账户标识 -->
      <div class="text-xs text-gray-400 mb-4 bg-gray-800 rounded px-3 py-2">
        账户: <span class="text-white">{{ portfolioName }}</span>
        (ID: {{ portfolioId }})
        <span v-if="isAggregated" class="ml-2 text-yellow-400">📂 含子账户聚合</span>
      </div>

      <!-- 方向切换 -->
      <div class="flex gap-2 mb-4">
        <button
          @click="form.direction = 'buy'"
          :class="[
            'flex-1 py-2 rounded text-sm font-bold transition-colors',
            form.direction === 'buy'
              ? 'bg-green-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
          ]"
        >📈 买入</button>
        <button
          @click="form.direction = 'sell'"
          :class="[
            'flex-1 py-2 rounded text-sm font-bold transition-colors',
            form.direction === 'sell'
              ? 'bg-red-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
          ]"
        >📉 卖出</button>
      </div>

      <!-- 表单 -->
      <div class="space-y-3">
        <!-- 标的代码 -->
        <div>
          <label class="text-gray-400 text-xs mb-1 block">标的代码</label>
          <input
            v-model="form.symbol"
            @input="form.symbol = form.symbol.toLowerCase()"
            class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm tracking-wider"
            placeholder="sh000001 / sz000001"
          />
        </div>

        <!-- 价格 -->
        <div>
          <label class="text-gray-400 text-xs mb-1 block">交易价格 (元)</label>
          <input
            v-model.number="form.price"
            type="number"
            step="0.001"
            min="0"
            class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            placeholder="10.00"
          />
        </div>

        <!-- 数量 -->
        <div>
          <label class="text-gray-400 text-xs mb-1 block">交易数量 (股)</label>
          <input
            v-model.number="form.shares"
            type="number"
            step="1"
            min="1"
            class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            placeholder="1000"
          />
        </div>

        <!-- 日期 -->
        <div>
          <label class="text-gray-400 text-xs mb-1 block">交易日期</label>
          <input
            v-model="form.date"
            type="date"
            class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <!-- 错误提示 -->
        <div v-if="error" class="text-red-400 text-xs bg-red-400/10 border border-red-400/20 rounded px-3 py-2">
          {{ error }}
        </div>

        <!-- 成功提示 -->
        <div v-if="success" class="text-green-400 text-xs bg-green-400/10 border border-green-400/20 rounded px-3 py-2">
          ✅ {{ success }}
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="flex gap-3 mt-5">
        <button
          @click="close"
          class="flex-1 py-2 text-gray-400 hover:text-white rounded border border-gray-600 text-sm"
        >取消</button>
        <button
          @click="submitTrade"
          :disabled="loading"
          :class="[
            'flex-1 py-2 rounded text-sm font-bold transition-colors',
            loading
              ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
              : form.direction === 'buy'
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
          ]"
        >
          <span v-if="loading">提交中...</span>
          <span v-else>{{ form.direction === 'buy' ? '📈 确认买入' : '📉 确认卖出' }}</span>
        </button>
      </div>

      <!-- 市价参考（买入时显示今日收盘价参考） -->
      <div v-if="priceHint" class="mt-3 text-xs text-gray-500 text-center">
        💡 {{ priceHint }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { apiFetch } from '../utils/api.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  portfolioId: { type: Number, required: true },
  portfolioName: { type: String, default: '' },
  isAggregated: { type: Boolean, default: false },
});

const emit = defineEmits(['trade-done', 'close']);

const loading = ref(false);
const error = ref('');
const success = ref('');
const priceHint = ref('');

const today = new Date().toISOString().slice(0, 10);

const form = reactive({
  direction: 'buy',
  symbol: '',
  price: null,
  shares: null,
  date: today,
});

// 账户切换时重置表单
watch(() => props.portfolioId, () => reset());
watch(() => props.visible, (v) => { if (v) reset(); });

function reset() {
  error.value = '';
  success.value = '';
  priceHint.value = '';
  form.direction = 'buy';
  form.symbol = '';
  form.price = null;
  form.shares = null;
  form.date = today;
}

function close() {
  emit('close');
}

async function submitTrade() {
  error.value = '';
  success.value = '';

  // 验证
  if (!form.symbol.trim()) { error.value = '请输入标的代码'; return; }
  if (!form.price || form.price <= 0) { error.value = '请输入有效的交易价格'; return; }
  if (!form.shares || form.shares <= 0) { error.value = '请输入有效的交易数量'; return; }
  if (!form.date) { error.value = '请选择交易日期'; return; }

  loading.value = true;
  const endpoint = form.direction === 'buy' ? 'buy' : 'sell';
  const body = form.direction === 'buy'
    ? {
        symbol:     form.symbol.trim(),
        shares:     form.shares,
        buy_price:  form.price,
        buy_date:   form.date,
      }
    : {
        symbol:     form.symbol.trim(),
        shares:     form.shares,
        sell_price: form.price,
      };

  try {
    const res = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/lots/${endpoint}`, {
      method: 'POST',
      body: JSON.stringify(body),
    });

    if (res.code === 0 || res.code === undefined) {
      const action = form.direction === 'buy' ? '买入' : '卖出';
      const d = res.data || res;
      success.value = `${action}成功！${d.symbol} × ${form.shares}股 @ ¥${form.price}`;
      // 通知父组件刷新
      setTimeout(() => {
        emit('trade-done');
        close();
      }, 800);
    } else {
      error.value = res.message || `${form.direction === 'buy' ? '买入' : '卖出'}失败`;
    }
  } catch (e) {
    error.value = `网络错误: ${e.message}`;
  } finally {
    loading.value = false;
  }
}
</script>
