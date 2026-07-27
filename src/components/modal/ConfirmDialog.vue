<template>
  <div v-if="state.open" class="modal-backdrop" @click.self="cancel" @keydown.esc="cancel">
    <div class="modal" role="alertdialog" aria-modal="true" :aria-label="state.title">
      <h2>{{ state.title }}</h2>
      <p class="message">{{ state.message }}</p>
      <footer class="modal-footer">
        <button ref="cancelBtn" type="button" class="btn" @click="cancel">{{ state.cancelLabel }}</button>
        <button
          type="button"
          class="btn btn-confirm"
          :class="{ danger: state.danger }"
          @click="confirm"
        >{{ state.confirmLabel }}</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { useConfirmDialogState, resolveConfirmDialog } from '@/utils/confirmDialog'

const state = useConfirmDialogState()
const cancelBtn = ref(null)

// Focus sur "Annuler" par défaut (pas sur l'action destructrice) dès l'ouverture — au clavier,
// Entrée ne valide donc jamais accidentellement une suppression.
watch(() => state.open, (open) => {
  if (open) nextTick(() => cancelBtn.value?.focus())
})

function cancel() {
  resolveConfirmDialog(false)
}

function confirm() {
  resolveConfirmDialog(true)
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  width: 400px;
  max-width: 92vw;
  background: #020617;
  border-radius: 16px;
  border: 1px solid #1f2937;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  padding: 20px 22px;
}

.modal h2 {
  margin: 0 0 10px;
  font-size: 17px;
  color: var(--color-heading, #f8fafc);
}

.message {
  margin: 0;
  font-size: 14px;
  color: #cbd5e1;
  line-height: 1.55;
}

.modal-footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  border-radius: 999px;
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  padding: 7px 16px;
  font-size: 13px;
  cursor: pointer;
}
.btn:hover { opacity: 0.92; }
.btn:focus-visible { outline: 2px solid var(--color-accent, #2563eb); outline-offset: 2px; }

.btn-confirm {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
}
.btn-confirm.danger {
  background: linear-gradient(90deg, #dc2626, #ef4444);
}
</style>
