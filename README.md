# TSSWF

Tom's Stupid-Simple Web Framework - A minimal static site generator with component support, CSS scoping, and conditional rendering.

## Project Structure

```
src/
├── skeleton.html        # Base template for all pages
├── *.css                # Global stylesheets (copied to dist/)
├── *.js                 # Global scripts (copied to dist/)
├── pages/
│   └── *.html           # Page content files
├── components/
│   └── button/          # Component directory (name = folder name)
│       ├── button.html  # Component template (required)
│       ├── button.css   # Component styles (optional, auto-scoped)
│       └── button.js    # Component script (optional, inlined)
└── static/
    └── *                # Static assets (images, fonts, etc.)

dist/                    # Build output
├── *.html
├── *.css
├── *.js
└── static/
```

## Usage

```bash
python build.py
```

## Pages

Pages live in `src/pages/` and are injected into `skeleton.html`. Each page can define metadata using directives at the top of the file:

```html
#PAGE_TITLE:About Us
#PAGE_HEAD_TITLE:About

<p>This is the about page content.</p>
```

| Directive | Description |
|-----------|-------------|
| `#PAGE_TITLE:` | Page title (available as `#PAGE_TITLE` in skeleton) |
| `#PAGE_HEAD_TITLE:` | Browser tab title (falls back to `#PAGE_TITLE` if omitted) |

## Skeleton

The skeleton (`src/skeleton.html`) is the base template. Use these placeholders:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=2.0, user-scalable=yes", target-densitydpi=device-dpi />

    <title>#PAGE_HEAD_TITLE | My Website</title>

    <link rel="stylesheet" href="styles.css?v=#CSS_HASH">
  </head>
  <body data-page="#PAGE_ID">
    <h1>#PAGE_TITLE</h1>
    <main>
      #PAGE_CONTENT
    </main>
  </body>
</html>
```

| Placeholder | Replaced With |
|-------------|---------------|
| `#PAGE_HEAD_TITLE` | Value from page directive |
| `#PAGE_TITLE` | Value from page directive |
| `#PAGE_CONTENT` | The page's HTML content |
| `#PAGE_ID` | Filename without extension (e.g., `about` for `about.html`) |
| `#CSS_HASH` | Random cache-busting hash |

## Components

Components are reusable HTML fragments. Create a folder in `src/components/` with matching HTML file:

```
src/components/card/
├── card.html    # Required
├── card.css     # Optional
└── card.js      # Optional
```

### Using Components

```html
<!-- Self-closing (no children) -->
<c-card title="Hello" />

<!-- With children -->
<c-card title="Hello">
    <p>Card content goes here.</p>
</c-card>
```

### Defining Components

**card.html:**
```html
#INPUT title
#INPUT subtitle

<div class="card">
    <h2>{title}</h2>
    <h3>{subtitle}</h3>
    <div class="card-body">
        {children}
    </div>
</div>
```

- `#INPUT name` declares an input variable
- `{name}` substitutes the value (empty string if not provided)
- `{children}` is always available and contains nested content

### Component CSS

Component CSS is automatically scoped. Class selectors get a unique suffix to prevent collisions:

**card.css:**
```css
.card { border: 1px solid #ccc; }
.card-body { padding: 1rem; }
```

Becomes something like:
```css
.card_84721 { border: 1px solid #ccc; }
.card-body_84721 { padding: 1rem; }
```

The HTML class references are updated to match.

### Component JS

If a component has a `.js` file, it's inlined as a `<script>` tag after the component HTML.

## Conditionals

Use `@IF` / `@ELSE` blocks for conditional rendering. These work in both pages and the skeleton.

```html
@IF(showBanner) {
    <div class="banner">Welcome!</div>
}

@IF(count > 0) {
    <p>You have items.</p>
} @ELSE {
    <p>No items yet.</p>
}
```

### Supported Operators

| Operator | Example |
|----------|---------|
| `==` | `@IF(status == "active")` |
| `!=` | `@IF(type != "hidden")` |
| `<` `>` `<=` `>=` | `@IF(count >= 10)` |
| `AND` | `@IF(loggedIn AND isAdmin)` |
| `OR` | `@IF(showA OR showB)` |
| `NOT` | `@IF(NOT disabled)` |

### Values

- Strings: `"hello"` or `'hello'` (or unquoted)
- Numbers: `42`, `3.14`
- Booleans: `true`, `false`

Bare values are evaluated for truthiness: empty string and `false` are falsy, everything else is truthy.

## Example

**src/skeleton.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>#PAGE_HEAD_TITLE</title>
</head>
<body>
    <nav><a href="/">Home</a></nav>
    #PAGE_CONTENT
</body>
</html>
```

**src/components/button/button.html:**
```html
#INPUT label
#INPUT href

<a class="btn" href="{href}">{label}</a>
```

**src/pages/index.html:**
```html
#PAGE_TITLE:Home

<h1>Welcome</h1>
<c-button label="Learn More" href="/about" />
```

**Output (dist/index.html):**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Home</title>
</head>
<body>
    <nav><a href="/">Home</a></nav>
    <h1>Welcome</h1>
    <a class="btn" href="/about">Learn More</a>
</body>
</html>
```