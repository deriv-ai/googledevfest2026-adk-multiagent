import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@xyflow/react/dist/style.css";
import "./index.css";

async function boot() {
  // Dev-only mock backend. `import.meta.env.DEV` is the literal `false` in a
  // production build, so this branch and the mock chunk are dropped entirely.
  if (import.meta.env.DEV && import.meta.env.VITE_MOCK === "1") {
    await import("./mock");
  }
  const { mount } = await import("./App");
  mount(document.getElementById("root")!);
}

void boot();
