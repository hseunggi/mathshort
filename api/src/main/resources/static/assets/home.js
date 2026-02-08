import { initHeader } from "./auth.js";

async function boot(){
  await initHeader("home", { requireAuth: false });
}

boot();
