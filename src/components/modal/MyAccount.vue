<template>
    <div class="modal-overlay-myaccount" @click="closeModal">
        <div class="modal-myaccount" @click.stop>
            <h1>My Account</h1>
            <button @click="closeModal">Close</button>
            <button>Log off</button>
        </div>
    </div>
</template>

<script>
    export default {
        name: 'MyAccountModal',
        methods: {
        closeModal() {
            this.$emit('close');
        }

    }
}
</script>

<style>
    .modal-overlay-myaccount {
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
    .modal-myaccount {
    background: grey;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}
</style>