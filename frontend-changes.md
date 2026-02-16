# Frontend Changes: Dark/Light Theme Toggle

## Files Modified

### `frontend/index.html`
- Added `data-theme="dark"` attribute to `<body>` for CSS theme switching
- Added a fixed-position theme toggle button before the main container with:
  - Sun icon (shown in dark mode, click to switch to light)
  - Moon icon (shown in light mode, click to switch to dark)
  - `aria-label` for screen reader accessibility
- Bumped CSS cache version to `v=11`

### `frontend/style.css`
- **Light theme CSS variables**: Added `[data-theme="light"]` block with light background/surface colors, dark text, adjusted borders and shadows for good contrast
- **Added `--code-bg` variable** to both themes so inline code and pre blocks adapt to the theme (replaces hardcoded `rgba(0,0,0,0.2)`)
- **Theme toggle button styles**: Fixed position top-right, circular 44px button, hover scale animation, focus ring for keyboard navigation
- **Icon transition styles**: Sun/moon icons crossfade with rotation using CSS opacity and transform transitions
- **Global theme transition**: Added `transition` on `background-color`, `color`, `border-color`, and `box-shadow` for smooth theme switching
- **Source link colors**: Changed from hardcoded blue (`#5ebbf7`) to `var(--primary-color)` so links work in both themes

### `frontend/script.js`
- **`initTheme()`**: Reads saved theme from `localStorage` on page load and applies it to `data-theme`
- **`toggleTheme()`**: Switches between dark/light, saves preference to `localStorage`
- **`updateThemeAriaLabel()`**: Updates the toggle button's `aria-label` to reflect the available action
- Registered click listener for the theme toggle button in `setupEventListeners()`

## Design Decisions
- Default theme is dark (matching the existing design)
- Theme preference persists across page reloads via `localStorage`
- The toggle button uses a 44px touch target for mobile accessibility
- Sun icon = "click to get light", Moon icon = "click to get dark"
- All transitions are 300ms ease for a smooth, non-jarring switch
