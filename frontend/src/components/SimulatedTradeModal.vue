<template>
  <div
    v-if="visible"
    ref="modalContainerRef"
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    role="dialog"
    aria-modal="true"
    aria-labelledby="trade-modal-title"
    @click.self="close"
  >
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-sm p-6 w-96 shadow-sm">
      <!-- Header -->
      <div class="flex items-center justify-between mb-5">
        <h3 id="trade-modal-title" class="text-theme-primary font-bold text-base">📋 模拟调仓</h3>
        <button
          @click="close"
          class="text-[var(--text-secondary)] hover:text-theme-primary text-lg"
          aria-label="关闭对话框"
          type="button"
        >×</button>
      </div>

      <!-- 账户标识 -->
      <div class="text-xs text-[var(--text-secondary)] mb-4 bg-[var(--bg-secondary)] rounded-sm px-3 py-2">
        账户: <span class="text-theme-primary">{{ portfolioName }}</span>
        (ID: {{ portfolioId }})
        <span v-if="isAggregated" class="ml-2 text-[var(--color-warning)]">📂 含子账户聚合</span>
      </div>

      <!-- 方向切换 -->
      <div class="flex gap-2 mb-4" role="group" aria-label="交易方向">
        <button
          @click="form.direction = 'buy'"
          :class="[
            'flex-1 py-2 rounded-sm text-sm font-bold transition-colors',
            form.direction === 'buy'
              ? 'bg-green-600 text-theme-primary'
              : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
          ]"
          :aria-pressed="form.direction === 'buy'"
          aria-label="买入"
          type="button"
        >📈 买入</button>
        <button
          @click="form.direction = 'sell'"
          :class="[
            'flex-1 py-2 rounded-sm text-sm font-bold transition-colors',
            form.direction === 'sell'
              ? 'bg-red-600 text-theme-primary'
              : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
          ]"
          :aria-pressed="form.direction === 'sell'"
          aria-label="卖出"
          type="button"
        >📉 卖出</button>
      </div>

      <!-- 表单 -->
      <div class="space-y-3">
        <!-- 标的代码 -->
        <div>
          <label for="trade-symbol" class="text-[var(--text-secondary)] text-xs mb-1 block">标的代码</label>
          <input
            id="trade-symbol"
            v-model="form.symbol"
            @input="form.symbol = form.symbol.toLowerCase()"
            class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary text-sm tracking-wider"
            placeholder="sh000001 / sz000001"
            aria-describedby="trade-symbol-hint"
          />
          <span id="trade-symbol-hint" class="sr-only">输入股票代码，如 sh000001 或 sz000001</span>
        </div>

        <!-- 价格 -->
        <div>
          <label for="trade-price" class="text-[var(--text-secondary)] text-xs mb-1 block">交易价格 (元)</label>
          <input
            id="trade-price"
            v-model.number="form.price"
            type="number"
            step="0.001"
            min="0"
            class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary text-sm"
            placeholder="10.00"
            aria-describedby="price-hint"
          />
        </div>

        <!-- 数量 -->
        <div>
          <label for="trade-shares" class="text-[var(--text-secondary)] text-xs mb-1 block">交易数量 (股)</label>
          <input
            id="trade-shares"
            v-model.number="form.shares"
            type="number"
            step="1"
            min="1"
            class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary text-sm"
            placeholder="1000"
          />
        </div>

        <!-- 日期 -->
        <div>
          <label for="trade-date" class="text-[var(--text-secondary)] text-xs mb-1 block">交易日期</label>
          <input
            id="trade-date"
            v-model="form.date"
            type="date"
            class="w-full bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-sm px-3 py-2 text-theme-primary text-sm"
          />
        </div>

        <!-- 错误提示 -->
        <div
          v-if="error"
          class="text-[var(--color-danger)] text-xs bg-[var(--color-danger-light)]/10 border border-[var(--color-danger-border)]/20 rounded-sm px-3 py-2"
          role="alert"
          aria-live="polite"
        >
          {{ error }}
        </div>

        <!-- 成功提示 -->
        <div
          v-if="success"
          class="text-[var(--color-success)] text-xs bg-[var(--color-success-light)]/10 border border-[var(--color-success-border)]/20 rounded-sm px-3 py-2"
          role="status"
          aria-live="polite"
        >
          ✅ {{ success }}
        </div>
      </div>

      <!-- 确认面板（第二步确认） -->
      <div v-if="showConfirmation" class="mt-4 border-t border-[var(--border-primary)] pt-4">
        <div class="bg-[var(--bg-secondary)] rounded-sm p-4 mb-4">
          <h4 class="text-theme-primary font-bold text-sm mb-3">📋 交易确认</h4>
          
          <!-- 交易摘要 -->
          <div class="space-y-2 text-xs">
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">账户：</span>
              <span class="text-theme-primary">{{ portfolioName }} (ID: {{ portfolioId }})</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">操作：</span>
              <span :class="form.direction === 'buy' ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
                {{ form.direction === 'buy' ? '📈 买入' : '📉 卖出' }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">标的：</span>
              <span class="text-theme-primary font-medium">{{ form.symbol?.toUpperCase() }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">价格：</span>
              <span class="text-theme-primary">¥{{ form.price?.toFixed(3) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">数量：</span>
              <span class="text-theme-primary">{{ form.shares }} 股</span>
            </div>
            <div class="flex justify-between border-t border-[var(--border-light)] pt-2 mt-2">
              <span class="text-[var(--text-secondary)] font-medium">交易总额：</span>
              <span class="text-theme-primary font-bold">¥{{ ((form.price || 0) * (form.shares || 0)).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">交易日期：</span>
              <span class="text-theme-primary">{{ form.date }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">操作时间：</span>
              <span class="text-theme-primary">{{ new Date().toLocaleString() }}</span>
            </div>
          </div>
          
          <!-- 警告提示 -->
          <div class="mt-3 text-xs text-[var(--color-warning)] bg-[var(--color-warning-bg)]/10 border border-[var(--color-warning-border)]/20 rounded-sm px-3 py-2">
            ⚠️ 此操作不可撤销，请确认交易信息无误
          </div>
        </div>
        
        <!-- 确认复选框 -->
        <label class="flex items-center gap-2 cursor-pointer mb-4">
          <input
            type="checkbox"
            v-model="confirmedCheckbox"
            class="w-4 h-4 rounded border-[var(--border-primary)] bg-[var(--bg-secondary)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
            aria-label="确认交易信息"
          />
          <span class="text-xs text-theme-primary">我已确认以上交易信息</span>
        </label>
        
        <!-- 确认按钮 -->
        <div class="flex gap-3">
          <button
            @click="cancelConfirmation"
            class="flex-1 py-2 text-[var(--text-secondary)] hover:text-theme-primary rounded-sm border border-[var(--border-primary)] text-sm"
            type="button"
          >返回修改</button>
          <button
            @click="executeTrade"
            :disabled="!confirmedCheckbox || loading"
            :class="[
              'flex-1 py-2 rounded-sm text-sm font-bold transition-colors',
              !confirmedCheckbox || loading
                ? 'bg-gray-600 text-[var(--text-secondary)] cursor-not-allowed'
                : form.direction === 'buy'
                  ? 'bg-[var(--color-success)] hover:bg-[var(--color-success-hover)] text-theme-primary'
                  : 'bg-[var(--color-danger)] hover:bg-[var(--color-danger-hover)] text-theme-primary'
            ]"
            :aria-busy="loading"
            type="button"
          >
            <span v-if="loading">提交中...</span>
            <span v-else>✓ 确认提交</span>
          </button>
        </div>
      </div>

      <!-- 底部按钮（第一步：表单填写） -->
      <div v-if="!showConfirmation" class="flex gap-3 mt-5">
        <button
          @click="close"
          class="flex-1 py-2 text-[var(--text-secondary)] hover:text-theme-primary rounded-sm border border-[var(--border-primary)] text-sm"
          type="button"
        >取消</button>
        <button
          @click="proceedToConfirmation"
          :disabled="loading"
          :class="[
            'flex-1 py-2 rounded-sm text-sm font-bold transition-colors',
            loading
              ? 'bg-gray-600 text-[var(--text-secondary)] cursor-not-allowed'
              : form.direction === 'buy'
                ? 'bg-[var(--color-success)] hover:bg-[var(--color-success-hover)] text-theme-primary'
                : 'bg-[var(--color-danger)] hover:bg-[var(--color-danger-hover)] text-theme-primary'
          ]"
          :aria-busy="loading"
          type="button"
        >
          <span v-if="loading">提交中...</span>
          <span v-else>{{ form.direction === 'buy' ? '📈 确认买入' : '📉 确认卖出' }}</span>
        </button>
      </div>

      <!-- 市价参考（买入时显示今日收盘价参考） -->
      <div v-if="priceHint" class="mt-3 text-xs text-[var(--text-muted)] text-center" id="price-hint">
        💡 {{ priceHint }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue';
import { apiFetch } from '../utils/api.js';
import { useFocusTrap } from '../composables/useFocusTrap.js';

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
const modalContainerRef = ref(null);
const triggerRef = ref(null);
const showConfirmation = ref(false);
const confirmedCheckbox = ref(false);

const isModalActive = computed(() => props.visible);

useFocusTrap({
  isActive: isModalActive,
  containerRef: modalContainerRef,
  onClose: close,
  triggerRef: triggerRef
});

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
  showConfirmation.value = false;
  confirmedCheckbox.value = false;
  form.direction = 'buy';
  form.symbol = '';
  form.price = null;
  form.shares = null;
  form.date = today;
}

function close() {
  emit('close');
}

function proceedToConfirmation() {
  error.value = '';
  success.value = '';

  // 验证
  if (!form.symbol.trim()) { error.value = '请输入标的代码'; return; }
  if (!form.price || form.price <= 0) { error.value = '请输入有效的交易价格'; return; }
  if (!form.shares || form.shares <= 0) { error.value = '请输入有效的交易数量'; return; }
  if (!form.date) { error.value = '请选择交易日期'; return; }

  // 显示确认面板
  showConfirmation.value = true;
  confirmedCheckbox.value = false;
}

function cancelConfirmation() {
  showConfirmation.value = false;
  confirmedCheckbox.value = false;
}

async function executeTrade() {
  if (!confirmedCheckbox.value) return;
  
  error.value = '';
  success.value = '';
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
