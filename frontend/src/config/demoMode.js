/**
 * Demo / viva helpers (login shortcuts, demo monitoring link).
 *
 * Enabled when Vite DEV (`npm run dev`) OR VITE_ENABLE_DEMO_HELPERS is an
 * explicit truthy build/runtime flag. Production nginx images set the flag to 0
 * so equality checks fold to false and demo UI is omitted from the bundle.
 */
export const DEMO_HELPERS_ENABLED =
  import.meta.env.DEV ||
  import.meta.env.VITE_ENABLE_DEMO_HELPERS === "1" ||
  import.meta.env.VITE_ENABLE_DEMO_HELPERS === "true" ||
  import.meta.env.VITE_ENABLE_DEMO_HELPERS === "yes" ||
  import.meta.env.VITE_ENABLE_DEMO_HELPERS === "on";

/** Prefill only for local/demo user-creation forms — never a production default. */
export const DEMO_FORM_PASSWORD = DEMO_HELPERS_ENABLED ? "Demo@123" : "";
