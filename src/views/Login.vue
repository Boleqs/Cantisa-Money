  <template>
    <Title title="Login" />
    <div class="div_form">
      <form id="form_login">
        <br>
        <label for="login">Login : </label>
        <input type="text" id="login" name="login"/>
        <br>
        <label for="password">Password : </label>
        <input type="password" id="password" name="password" minlength="4"/>
        <br><br>
        <button class="submit_button" id="submit_button">Submit</button>
      </form>
    </div>
  </template>

  <script>
  import Title from './Title.vue';

  export default {
    components: {
      Title
    }
  }

  </script>

  <style>
  .div_form {
    align-items: center;
  }

  .submit_button {
    color: white;
  }

  </style>