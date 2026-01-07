# ChatKit JavaScript Initialization

Complete patterns for initializing the `<openai-chatkit>` custom element.

## Bootstrap Script Structure

```javascript
(function() {
  // Debug logging (development only)
  const log = (...args) => console.log("[ChatKit]", ...args);

  const hostSelector = ".chatkit-shell__frame";
  let lastOptions = null;
  let chatkitEl = null;

  // Parse accept MIME types into ChatKit format
  const parseAccept = (raw) => {
    if (!raw) return undefined;
    const list = raw.split(",").map((v) => v.trim()).filter(Boolean);
    if (list.length === 0) return undefined;
    return list.reduce((acc, type) => {
      acc[type] = [];
      return acc;
    }, {});
  };

  // Get current theme from HTML element
  const currentTheme = () => {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  };

  // Build options from container data attributes
  const buildOptions = (container) => {
    const ds = container.dataset;
    const theme = currentTheme();

    // Header configuration
    const header = ds.chatkitHeaderTitleValue
      ? { title: { text: ds.chatkitHeaderTitleValue } }
      : undefined;

    // Initial thread (for resuming conversations)
    const initialThread = ds.chatkitInitialThreadValue || null;

    // Composer/attachment configuration
    const composer = ds.chatkitUploadUrlValue ? {
      attachments: {
        enabled: true,
        maxSize: Number(ds.chatkitUploadMaxSizeValue || 0) || undefined,
        accept: parseAccept(ds.chatkitUploadAcceptValue)
      }
    } : undefined;

    // Hosted mode: use client secret endpoint
    if (ds.chatkitClientSecretPathValue) {
      return {
        api: {
          getClientSecret: async (currentSecret) => {
            const response = await fetch(ds.chatkitClientSecretPathValue, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": document.querySelector("meta[name='csrf-token']")?.content
              },
              body: JSON.stringify({ current_client_secret: currentSecret })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.client_secret) {
              throw new Error(payload.error || "Unable to fetch ChatKit client secret");
            }
            return payload.client_secret;
          }
        },
        initialThread,
        composer,
        theme
      };
    }

    // Self-hosted mode: direct API URL
    const options = {
      api: {
        url: ds.chatkitApiUrlValue,
        domainKey: ds.chatkitDomainKeyValue || "local-dev"
      },
      initialThread,
      composer,
      theme
    };

    // Upload strategy for self-hosted
    if (ds.chatkitUploadUrlValue) {
      options.api.uploadStrategy = {
        type: "direct",
        uploadUrl: ds.chatkitUploadUrlValue
      };
    }

    if (header) options.header = header;
    return options;
  };

  // Create or find the ChatKit element
  const ensureChatkitEl = () => {
    if (chatkitEl && chatkitEl.isConnected) return chatkitEl;

    chatkitEl = document.querySelector("openai-chatkit");
    if (!chatkitEl) {
      chatkitEl = document.createElement("openai-chatkit");
      chatkitEl.classList.add("chatkit-embed");
      chatkitEl.style.width = "100%";
      chatkitEl.style.height = "100%";
      chatkitEl.style.display = "block";
      chatkitEl.style.flex = "1 1 auto";

      const host = document.querySelector(hostSelector);
      if (host) host.appendChild(chatkitEl);
    }
    return chatkitEl;
  };

  // Apply options to ChatKit element
  const applyOptions = async () => {
    const container = document.querySelector(hostSelector);
    if (!container) {
      log("Container not found, skipping");
      return;
    }

    const options = buildOptions(container);
    lastOptions = options;
    log("Applying options", options);

    // Wait for custom element definition
    try {
      await customElements.whenDefined("openai-chatkit");
    } catch (e) {
      log("Custom element not ready", e);
      return;
    }

    const el = ensureChatkitEl();

    // Apply theme attributes
    el.style.colorScheme = options.theme;
    el.dataset.theme = options.theme;
    el.dataset.colorScheme = options.theme;

    try {
      el.setOptions(options);
    } catch (error) {
      log("setOptions failed", error);
    }
  };

  // Sync theme when document theme changes
  const syncTheme = () => {
    if (!lastOptions) return;
    lastOptions.theme = currentTheme();
    if (chatkitEl) {
      chatkitEl.style.colorScheme = lastOptions.theme;
      chatkitEl.dataset.theme = lastOptions.theme;
      chatkitEl.dataset.colorScheme = lastOptions.theme;
      log("Theme changed to", lastOptions.theme);
      chatkitEl.setOptions(lastOptions);
    }
  };

  // Watch for theme changes
  const observer = new MutationObserver((mutations) => {
    if (mutations.some((m) => m.attributeName === "data-theme")) {
      syncTheme();
    }
  });

  // Initialize on page load (both Turbo and regular)
  document.addEventListener("turbo:load", applyOptions);
  document.addEventListener("DOMContentLoaded", applyOptions);

  // Start observing theme changes
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"]
  });

  log("ChatKit bootstrap ready");
})();
```

## Options Object Structure

### Self-Hosted Mode

```javascript
{
  api: {
    url: "/chatkit?agent_id=123",
    domainKey: "local-dev",
    uploadStrategy: {
      type: "direct",
      uploadUrl: "/chatkit/upload?agent_id=123"
    }
  },
  header: {
    title: { text: "Agent Name" }
  },
  composer: {
    attachments: {
      enabled: true,
      maxSize: 26214400,
      accept: {
        "image/png": [],
        "image/jpeg": [],
        "application/pdf": []
      }
    }
  },
  initialThread: null,
  theme: "dark"
}
```

### Hosted Mode

```javascript
{
  api: {
    getClientSecret: async (currentSecret) => {
      // Fetch from backend
      return "new-secret";
    }
  },
  composer: {
    attachments: {
      enabled: true,
      maxSize: 26214400
    }
  },
  initialThread: "thread_abc123",
  theme: "light"
}
```

## Standalone Initialization

For pages without the bootstrap partial:

```javascript
(function() {
  // Theme resolution with fallbacks
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

  const applyTheme = () => {
    const theme = resolveTheme();
    document.documentElement.dataset.theme = theme;
    return theme;
  };

  let currentTheme = applyTheme();

  // Build attachment config from server data
  const acceptTypes = ["image/png", "image/jpeg", "application/pdf"];
  const attachmentsConfig = {
    enabled: true,
    maxSize: 26214400
  };
  if (acceptTypes.length > 0) {
    attachmentsConfig.accept = Object.fromEntries(
      acceptTypes.map(type => [type, []])
    );
  }

  const options = {
    api: {
      url: "/chatkit?agent_id=123",
      domainKey: "local-dev",
      uploadStrategy: {
        type: "direct",
        uploadUrl: "/chatkit/upload?agent_id=123"
      }
    },
    header: {
      title: { text: "Agent Name" }
    },
    history: { enabled: true },
    composer: { attachments: attachmentsConfig },
    theme: { colorScheme: currentTheme },
    initialThread: null
  };

  function ensureChatkitEl() {
    const host = document.getElementById("chatkit-host");
    let el = host.querySelector("openai-chatkit");
    if (!el) {
      el = document.createElement("openai-chatkit");
      el.style.width = "100%";
      el.style.height = "100%";
      host.appendChild(el);
    }
    return el;
  }

  function mountChatkit() {
    customElements.whenDefined("openai-chatkit").then(() => {
      const chatkitEl = ensureChatkitEl();
      if (typeof chatkitEl.setOptions === "function") {
        chatkitEl.setOptions(options);
      } else {
        // Retry if not upgraded yet
        requestAnimationFrame(mountChatkit);
      }
    });
  }

  // System preference change listener
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

  // Theme attribute change observer
  const themeObserver = new MutationObserver((mutations) => {
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
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"]
  });

  // Mount when ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountChatkit);
  } else {
    mountChatkit();
  }
})();
```

## Custom Element Lifecycle

### Wait for Definition

```javascript
await customElements.whenDefined("openai-chatkit");
```

### Create Dynamically

```javascript
const el = document.createElement("openai-chatkit");
el.style.width = "100%";
el.style.height = "100%";
el.style.display = "block";
el.style.flex = "1 1 auto";
container.appendChild(el);
```

### Apply Options

```javascript
// Full options
el.setOptions(fullOptions);

// Partial update (e.g., theme only)
el.setOptions({ theme: { colorScheme: "dark" } });
```

## Error Handling

```javascript
try {
  el.setOptions(options);
} catch (error) {
  console.error("ChatKit initialization failed:", error);

  // Show user-friendly error
  const errorEl = document.querySelector(".chatkit-shell__error");
  if (errorEl) {
    errorEl.textContent = "Failed to initialize chat. Please refresh.";
    errorEl.hidden = false;
  }
}
```

## Client Secret Refresh (Hosted Mode)

```javascript
api: {
  getClientSecret: async (currentSecret) => {
    const response = await fetch("/chatkit/client_secret", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": document.querySelector("meta[name='csrf-token']")?.content
      },
      body: JSON.stringify({ current_client_secret: currentSecret })
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok || !payload.client_secret) {
      throw new Error(payload.error || "Unable to fetch client secret");
    }

    return payload.client_secret;
  }
}
```
