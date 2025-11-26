<template>
  <div v-show=showEventBool :class="props.pType">
    <slot>
      Default message content.
      A message should be displaying here
    </slot>
  </div>
</template>

<script setup>
  import {onMounted, ref} from "vue";

  defineExpose({showDiv})

  const showEventBool = ref(false)
  const props = defineProps({
    pType: {
      validator(value, props) {return ['info', 'warning', 'error'].includes(value)},
      type: String,
      required: true},

    }
  )

  function showDiv () {
    showEventBool.value = true
    setTimeout(() => {
    showEventBool.value = false
  }, 5000)
  }

</script>

<style scoped>
  .error{
    position: fixed;
    right: 0%;
    background: red;
    border: 2px solid red;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
    transition: opacity 0.8s linear;
  }
  .warning{
    position: fixed;
    right: 0%;
    background: orangered;
    border: 2px solid orangered;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
  }
  .info{
    position: fixed;
    right: 0%;
    background: gray;
    border: 2px solid gray;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
  }
</style>