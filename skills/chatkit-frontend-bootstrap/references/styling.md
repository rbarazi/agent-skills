# ChatKit CSS Styling

CSS patterns for embedding and styling ChatKit.

## Container Structure

```
.chatkit-page
└── .chatkit-shell
    └── .chatkit-shell__frame
        └── openai-chatkit.chatkit-embed
```

## Core Styles

```css
/* app/assets/stylesheets/components/chatkit.css */

/* Full-height page container */
.chatkit-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1 1 auto;
}

/* Shell wrapper */
.chatkit-shell {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  width: 100%;
  flex: 1 1 auto;
  min-height: calc(100vh - 140px);
}

/* Frame containing ChatKit element */
.chatkit-shell__frame {
  position: relative;
  min-height: 520px;
  background: transparent;
  border-radius: 0;
  border: none;
  padding: 0;
  overflow: hidden;
  height: 100%;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}

/* ChatKit custom element */
.chatkit-shell__frame > openai-chatkit,
.chatkit-shell__frame > .chatkit-embed {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  height: 100%;
  display: block;
}

/* Dynamically created element class */
.chatkit-embed {
  display: block;
  width: 100%;
  min-height: 520px;
  height: 100%;
  border: none;
  flex: 1 1 auto;
  container-type: inline-size;
  container-name: chat;
}
```

## App Layout Integration

```css
/* Ensure container fills available space */
.app-layout__container.chatkit-container {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.chatkit-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}
```

## Status Indicators

```css
/* Loading/status display */
.chatkit-shell__status {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  color: var(--color-text-muted);
  padding: var(--spacing-sm);
}

/* Hide status inside frame */
.chatkit-shell__status--inline,
.chatkit-shell__frame > .chatkit-shell__status {
  display: none !important;
  visibility: hidden !important;
}

/* Loading spinner */
.chatkit-shell__spinner {
  width: 18px;
  height: 18px;
  border-radius: 9999px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  animation: chatkit-spin 0.9s linear infinite;
}

@keyframes chatkit-spin {
  to {
    transform: rotate(360deg);
  }
}
```

## Error & Empty States

```css
/* Error message */
.chatkit-shell__error {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-md);
  background: var(--color-error-surface);
  color: var(--color-error-700);
  border: 1px solid var(--color-error-200);
}

/* Configuration missing state */
.chatkit-shell__empty {
  padding: var(--spacing-md);
  background: var(--color-surface-elevated);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  border: 1px dashed var(--color-border);
}

.chatkit-shell__hint {
  margin-top: var(--spacing-xs);
  font-size: 14px;
  color: var(--color-text-muted);
}
```

## Iframe Wrapper (If Needed)

```css
.ck-wrapper {
  height: 100%;
}

.ck-wrapper iframe {
  width: 100%;
  height: 100%;
}
```

## Standalone Page Styles

For full-page ChatKit without app layout:

```css
html, body {
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Dark mode default */
html, body {
  color: #f8f8f8;
  background: #0e0e0e;
}

/* Light mode override */
html[data-theme="light"],
body[data-theme="light"] {
  color: #1c1c1c;
  background: #f7f7f7;
}

.ck-standalone {
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  box-sizing: border-box;
}

.ck-standalone__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

#chatkit-host {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}

#chatkit-host openai-chatkit {
  display: block;
  width: 100%;
  height: 100%;
  flex: 1 1 auto;
  min-height: 0;
}
```

## JavaScript-Applied Styles

When creating the element dynamically:

```javascript
const el = document.createElement("openai-chatkit");
el.classList.add("chatkit-embed");
el.style.width = "100%";
el.style.height = "100%";
el.style.display = "block";
el.style.flex = "1 1 auto";
```

## Theme-Aware Styling

```css
/* Target ChatKit based on theme attribute */
openai-chatkit[data-theme="dark"] {
  /* Dark mode customizations */
}

openai-chatkit[data-theme="light"] {
  /* Light mode customizations */
}
```

## Container Queries

For responsive widget sizing:

```css
.chatkit-embed {
  container-type: inline-size;
  container-name: chat;
}

@container chat (max-width: 400px) {
  /* Narrow container styles */
}
```

## CSS Custom Properties

Use app-wide CSS variables for consistency:

```css
:root {
  --chatkit-min-height: 520px;
  --chatkit-border-radius: 0;
  --chatkit-background: transparent;
}

.chatkit-shell__frame {
  min-height: var(--chatkit-min-height);
  border-radius: var(--chatkit-border-radius);
  background: var(--chatkit-background);
}
```

## Full-Height Layout Pattern

Ensure ChatKit fills available vertical space:

```css
/* Parent containers must use flexbox */
.parent-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ChatKit section expands to fill */
.chatkit-section {
  flex: 1 1 auto;
  min-height: 0;  /* Important: allow shrinking */
  display: flex;
  flex-direction: column;
}

/* ChatKit itself fills the section */
.chatkit-shell {
  flex: 1 1 auto;
  display: flex;
}

.chatkit-shell__frame {
  flex: 1 1 auto;
  display: flex;
}
```

## Hiding During Load

```css
/* Hide ChatKit until initialized */
.chatkit-shell__frame[data-loading="true"] openai-chatkit {
  opacity: 0;
}

/* Or use visibility */
.chatkit-shell__frame:not([data-ready]) openai-chatkit {
  visibility: hidden;
}
```

## Print Styles

```css
@media print {
  .chatkit-shell {
    display: none;
  }

  .chatkit-print-fallback {
    display: block;
  }
}
```

## Accessibility

```css
/* Ensure focus visibility */
.chatkit-shell__frame:focus-within {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .chatkit-shell__spinner {
    animation: none;
  }
}
```
