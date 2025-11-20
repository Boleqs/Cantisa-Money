<template>
    <div class="modal-overlay-myaccount" @click="closeModal">
        <div class="modal-myaccount" @click.stop>
            <h1>My Account</h1>
            <button @click="closeModal">Close</button>
            <button @click="logOff">Log off</button>
        </div>
    </div>
</template>

<script>
    import axios from "axios";
    function getCookie(name) {
            return document.cookie
              .split('; ')
              .find(row => row.startsWith(name + '='))
              ?.split('=')[1]
              }
    export default {
        name: 'MyAccountModal',
        methods: {


        closeModal() {
            this.$emit('close');
        },
        logOff() {
            const csrfToken = getCookie('csrf_access_token')
            axios.post('http://localhost:5000/api/auth/logout', {headers: {'X-CSRF-TOKEN': csrfToken}})
            this.$emit('close')
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