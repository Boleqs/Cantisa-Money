<template>
  <div class="modal-overlay" @click.self="close">
    <div class="modal">
      <h2>{{ title }}</h2>
      <slot></slot>
      <div class="modal-actions">
        <button class="modify" @click="handleAction">{{ actionLabel }}</button>
        <button class="close" @click="close">Annuler</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, computed } from 'vue'

const props = defineProps({
  title: String,
  modifyVirement: Function,
  addVirement: Function,
  action: {
    type: String,
    default: 'modify'
  }
})

const emit = defineEmits(['close'])

const close = () => {
  emit('close')
}

const handleAction = () => {
  if (props.action === 'modify') {
    props.modifyVirement()
  } else if (props.action === 'add') {
    props.addVirement()
  }
}

const actionLabel = computed(() => {
  return props.action === 'modify' ? 'Enregistrer' : 'Ajouter'
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 40px;
  max-width: 600px;
  width: 100%;
  color: black;
  display: flex;
  flex-direction: column;
  gap: 10px; 
}

.modal-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 20px;
  
}

.modal-actions button {
  width: 40%;
  height: 40px;
  justify-self: center;
  border-radius: 10px; 

}
.modal-actions button.modify {
  background: green;
  color: white;
}
.modal-actions button.close {
  background: red;
  color: white;
}
</style>