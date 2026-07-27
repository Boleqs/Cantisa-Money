<template>
  <Teleport to="body">
    <div class="toast-stack" role="status" aria-live="polite">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" :class="['toast', t.type]">
          <span class="toast-icon">{{ ICONS[t.type] }}</span>
          <span class="toast-message">{{ t.message }}</span>
          <button class="toast-close" type="button" aria-label="Fermer" @click="dismiss(t.id)">✕</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '@/utils/toast'

const { toasts, dismiss } = useToast()

const ICONS = { success: '✓', error: '✕', info: 'ℹ' }
</script>

<style scoped>
.toast-stack {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  max-width: min(380px, calc(100vw - 40px));
}


.toast {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--color-border-hover);
  background: #111827;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  color: var(--color-text);
  font-size: 13.5px;
  line-height: 1.5;
}

.toast.success { border-color: var(--color-success-border); }
.toast.error { border-color: var(--color-danger-border); }
.toast.info { border-color: var(--color-border-hover); }

.toast-icon {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  margin-top: 1px;
}

.toast.success .toast-icon { background: var(--color-success-soft); color: var(--color-success-text); }
.toast.error .toast-icon { background: var(--color-danger-soft); color: var(--color-danger-text); }
.toast.info .toast-icon { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }

.toast-message { flex: 1; word-break: break-word; }

.toast-close {
  flex: none;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 12px;
  padding: 2px;
  line-height: 1;
}
.toast-close:hover { color: var(--color-text); }

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-leave-to { opacity: 0; transform: translateX(8px); }
.toast-leave-active { position: absolute; }

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active, .toast-leave-active { transition: none; }
}
</style>
