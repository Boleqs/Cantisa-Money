<template>
    <div class="modal-overlay-settings" @click="closeModal">
        <div class="modal-settings" @click.stop>
            <h1>settings</h1>
            <button @click="closeModal">Close</button>
        </div>
    </div>
</template>

<script>
    export default {
        name: 'SettingsModal',
        methods: {
        closeModal() {
            this.$emit('close');
        }
    }
}
</script>

<style>
    .modal-overlay-settings {
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
    .modal-settings {
    background: grey;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}
</style>