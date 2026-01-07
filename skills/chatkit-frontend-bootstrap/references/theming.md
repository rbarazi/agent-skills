# ChatKit Theme Synchronization

Patterns for syncing ChatKit theme with your application's dark/light mode.

## Theme Detection Strategy

### Priority Order

1. **HTML `data-theme` attribute** - Explicit theme set by app
2. **localStorage** - User's saved preference
3. **System preference** - `prefers-color-scheme` media query

```javascript
const resolveTheme = () => {
  // 1. Check explicit HTML attribute
  const explicit = document.documentElement.dataset.theme;
  if (explicit === "dark" || explicit === "light") return explicit;

  // 2. Check localStorage
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;

  // 3. Fall back to system preference
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};
```

### Simple Detection (When App Controls Theme)

```javascript
const currentTheme = () => {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
};
```

## Theme Sync Methods

### MutationObserver (Recommended)

Watch for changes to the HTML element's `data-theme` attribute:

```javascript
let currentTheme = "light";
let chatkitEl = null;

const syncTheme = () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  if (theme === currentTheme) return;

  currentTheme = theme;
  if (chatkitEl) {
    // Update element attributes
    chatkitEl.style.colorScheme = theme;
    chatkitEl.dataset.theme = theme;
    chatkitEl.dataset.colorScheme = theme;

    // Update ChatKit options
    chatkitEl.setOptions({ theme: { colorScheme: theme } });
  }
};

const observer = new MutationObserver((mutations) => {
  if (mutations.some((m) => m.attributeName === "data-theme")) {
    syncTheme();
  }
});

observer.observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"]
});
```

### System Preference Change

Listen for OS-level theme changes:

```javascript
const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)");

prefersDark?.addEventListener?.("change", (e) => {
  const nextTheme = e.matches ? "dark" : "light";

  // Update app theme
  document.documentElement.dataset.theme = nextTheme;

  // ChatKit will sync via MutationObserver
});
```

### Combined Approach

```javascript
let currentTheme = "light";

const applyTheme = () => {
  const theme = resolveTheme();
  document.documentElement.dataset.theme = theme;
  return theme;
};

// Initialize
currentTheme = applyTheme();

// Watch system preference
const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)");
prefersDark?.addEventListener?.("change", () => {
  const nextTheme = applyTheme();
  if (nextTheme !== currentTheme) {
    currentTheme = nextTheme;
    document.querySelector("openai-chatkit")?.setOptions({
      theme: { colorScheme: nextTheme }
    });
  }
});

// Watch data-theme attribute
const observer = new MutationObserver((mutations) => {
  if (mutations.some((m) => m.attributeName === "data-theme")) {
    const nextTheme = applyTheme();
    if (nextTheme !== currentTheme) {
      currentTheme = nextTheme;
      document.querySelector("openai-chatkit")?.setOptions({
        theme: { colorScheme: nextTheme }
      });
    }
  }
});
observer.observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"]
});
```

## ChatKit Theme Options

### Setting Theme on Init

```javascript
const options = {
  // ... other options
  theme: "dark"  // or "light"
};
el.setOptions(options);
```

### Updating Theme Later

```javascript
// Partial update - only theme
el.setOptions({ theme: { colorScheme: "dark" } });

// Or update full options with new theme
lastOptions.theme = "dark";
el.setOptions(lastOptions);
```

## Element Attributes

Apply multiple theme-related attributes for CSS targeting:

```javascript
const applyThemeToElement = (el, theme) => {
  el.style.colorScheme = theme;
  el.dataset.theme = theme;
  el.dataset.colorScheme = theme;
};
```

This enables CSS selectors like:

```css
openai-chatkit[data-theme="dark"] {
  /* Dark mode overrides */
}

openai-chatkit[data-theme="light"] {
  /* Light mode overrides */
}
```

## Standalone View Theme Styles

For standalone pages, include theme-aware base styles:

```html
<style>
  /* Dark mode default */
  html, body {
    color: #f8f8f8;
    background: #0e0e0e;
  }

  /* Light mode override */
  html[data-theme="light"],
  html[data-theme="light"] body {
    color: #1c1c1c;
    background: #f7f7f7;
  }
</style>
```

## Rails Theme Toggle Integration

If your app has a theme toggle (Stimulus controller):

```javascript
// app/javascript/controllers/theme_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  toggle() {
    const html = document.documentElement;
    const current = html.dataset.theme || "light";
    const next = current === "dark" ? "light" : "dark";

    html.dataset.theme = next;
    localStorage.setItem("theme", next);

    // ChatKit syncs automatically via MutationObserver
  }
}
```

## Debugging Theme Issues

```javascript
// Enable verbose logging
const log = (...args) => console.log("[ChatKit Theme]", ...args);

const syncTheme = () => {
  const htmlTheme = document.documentElement.dataset.theme;
  const resolvedTheme = htmlTheme === "dark" ? "dark" : "light";

  log("HTML data-theme:", htmlTheme);
  log("Resolved theme:", resolvedTheme);

  if (chatkitEl) {
    log("Applying to ChatKit:", resolvedTheme);
    chatkitEl.setOptions({ theme: { colorScheme: resolvedTheme } });
  }
};
```

## Common Issues

### Theme Not Updating

1. Ensure MutationObserver is properly attached
2. Check that `data-theme` is on `document.documentElement` (not body)
3. Verify ChatKit element reference is still valid

### Flash of Wrong Theme

Initialize theme before mounting ChatKit:

```javascript
// Apply theme immediately
const theme = resolveTheme();
document.documentElement.dataset.theme = theme;

// Then mount ChatKit with correct theme
const options = { theme: { colorScheme: theme }, /* ... */ };
el.setOptions(options);
```

### Observer Not Firing

```javascript
// Ensure correct observation target
observer.observe(document.documentElement, {  // NOT document.body
  attributes: true,
  attributeFilter: ["data-theme"]
});
```
