<script>
  import { Router, Route } from "svelte-routing";
  import Login from "./pages/login.svelte";
  import Main from "./pages/main.svelte";
  export let url = "";

  const routes = [
    { path: "/login", component: Login },
    { path: "/", component: Main }
  ];
</script>

<Router {url}>
  {#each routes as route}
    <Route path={route.path} let:params>
      <svelte:component this={route.component} {params} />
    </Route>
  {/each}
</Router>
