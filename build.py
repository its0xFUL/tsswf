#!/usr/bin/env python3
"""
TSSWF - Static site generator with component support.

Processes HTML pages with custom <c-*> components, conditional blocks,
CSS scoping, and signal expression transforms.

Usage: python build.py [project_path]
  project_path: Root directory containing src/ folder (default: current directory)
"""

import sys
import shutil
import re
import operator
import random
from pathlib import Path
from dataclasses import dataclass

# =============================================================================
# Data Types
# =============================================================================

@dataclass
class Component:
    html: str
    css: str | None = None


@dataclass
class PageMetadata:
    head_title: str
    title: str
    content: str


@dataclass
class ProjectPaths:
    base: Path
    src: Path
    pages: Path
    components: Path
    static: Path
    output: Path

    @classmethod
    def from_base(cls, base_path: Path) -> "ProjectPaths":
        src = base_path / "src"
        return cls(
            base=base_path,
            src=src,
            pages=src / "pages",
            components=src / "components",
            static=src / "static",
            output=base_path / "dist",
        )

# =============================================================================
# Component Processing
# =============================================================================

COMPONENT_PATTERN = re.compile(
    r'<c-(\w+)'                                      # Tag name: <c-button
    r'((?:\s+[\w-]+(?:=(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?)*)'  # Attributes
    r'\s*(?:/>'                                      # Self-closing />
    r'|>(.*?)</c-\1>)',                              # Or >content</c-name>
    re.DOTALL
)

ATTRIBUTE_PATTERN = re.compile(r'([\w-]+)=(["\'])(.*?)\2')


def parse_attributes(attr_string: str) -> dict[str, str]:
    """Extract key="value" pairs from an attribute string."""
    return {
        match.group(1): match.group(3)
        for match in ATTRIBUTE_PATTERN.finditer(attr_string)
    }


def scope_css_selectors(html: str, css: str, scope_id: int) -> tuple[str, str]:
    """Add unique suffix to CSS class for scoping."""
    selectors = re.findall(r'(?<![0-9])\.[a-zA-Z_][a-zA-Z0-9_-]*', css)
    
    for selector in selectors:
        name = selector[1:]  # Remove .
        scoped_name = f"{name}_{scope_id}"
        html = html.replace(name, scoped_name)
        css = css.replace(name, scoped_name)
    
    return html, css


def load_component(name: str, inputs: dict[str, str], paths: ProjectPaths) -> Component:
    """Load and process a component definition."""
    base_path = paths.components / name
    html_path = base_path / f"{name}.html"
    css_path = base_path / f"{name}.css"
    js_path = base_path / f"{name}.js"
    
    if not html_path.exists():
        print(f"  Warning: component '{name}' not found at {html_path}")
        return Component(html=f"<!-- Component '{name}' not found -->")
    
    html = html_path.read_text()
    
    # Parse input declarations and remove them from output
    declared_inputs = set(re.findall(r'#INPUT\s+(\w+)', html))
    declared_inputs.add("children")  # Always available
    html = re.sub(r'#INPUT\s+\w+\s*\n?', '', html)
    
    # Substitute input values
    for input_name in declared_inputs:
        html = html.replace(f"{{{input_name}}}", inputs.get(input_name, ""))
    
    # Warn about undeclared inputs
    for input_name in inputs:
        if input_name not in declared_inputs:
            print(f"  Warning: input '{input_name}' not declared in component '{name}'")
    
    # Append inline JS if present
    if js_path.exists():
        html += f"\n<script>\n{js_path.read_text()}\n</script>"
    
    # Process and scope CSS if present
    css = None
    if css_path.exists():
        scope_id = random.randint(0, 99999)
        css_content = css_path.read_text()
        html, css_content = scope_css_selectors(html, css_content, scope_id)
        css = f"<style>\n{css_content}\n</style>"
    
    return Component(html=html, css=css)


def process_components(content: str, known_components: set[str], paths: ProjectPaths) -> tuple[str, list[str]]:
    """Replace all <c-*> tags with their component HTML. Returns processed content and collected styles."""
    collected_styles: list[str] = []
    
    def replace_match(match: re.Match) -> str:
        component_name = match.group(1)
        attr_string = match.group(2) or ""
        children = match.group(3) or ""
        
        if component_name not in known_components:
            print(f"  Warning: unknown component '{component_name}'")
            return f"<!-- Unknown component: {component_name} -->"
        
        inputs = parse_attributes(attr_string)
        if children:
            inputs["children"] = children
        
        component = load_component(component_name, inputs, paths)
        
        if component.css:
            collected_styles.append(component.css)
        
        return component.html
    
    processed = COMPONENT_PATTERN.sub(replace_match, content)
    return processed, collected_styles

# =============================================================================
# Conditional Processing
# =============================================================================

COMPARISON_OPS = {
    '<=': operator.le,
    '>=': operator.ge,
    '!=': operator.ne,
    '==': operator.eq,
    '<': operator.lt,
    '>': operator.gt,
}


def parse_literal(value: str):
    """Parse a literal value (number, string, or boolean)."""
    value = value.strip()
    
    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    
    # Number
    try:
        return float(value) if '.' in value else int(value)
    except ValueError:
        pass
    
    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    
    # Unquoted string
    return value


def evaluate_condition(condition: str) -> bool:
    """Evaluate a conditional expression."""
    condition = condition.strip()
    
    # OR (lowest precedence)
    or_parts = re.split(r'\s+OR\s+', condition)
    if len(or_parts) > 1:
        return any(evaluate_condition(part) for part in or_parts)
    
    # AND
    and_parts = re.split(r'\s+AND\s+', condition)
    if len(and_parts) > 1:
        return all(evaluate_condition(part) for part in and_parts)
    
    # NOT
    if condition.startswith('NOT '):
        return not evaluate_condition(condition[4:])
    
    # Parentheses
    if condition.startswith('(') and condition.endswith(')'):
        return evaluate_condition(condition[1:-1])
    
    # Comparison operators
    for op_str, op_func in COMPARISON_OPS.items():
        if op_str in condition:
            left, right = condition.split(op_str, 1)
            right_val = bool(parse_literal(left)) if right == "" else parse_literal(right)
            return op_func(parse_literal(left), right_val)
    
    # Bare value - check truthiness
    return bool(parse_literal(condition))


def find_matching_brace(text: str, start: int) -> int:
    """Find the closing brace matching the opening brace at position start."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def process_conditionals(html: str) -> str:
    """Process @IF/@ELSE blocks in the HTML."""
    result = []
    i = 0
    
    while i < len(html):
        match = re.search(r'@IF\s*\(', html[i:])
        if not match:
            result.append(html[i:])
            break
        
        # Add text before @IF
        result.append(html[i:i + match.start()])
        i += match.end()
        
        # Extract condition (find matching closing paren)
        paren_depth = 1
        cond_start = i
        while i < len(html) and paren_depth > 0:
            if html[i] == '(':
                paren_depth += 1
            elif html[i] == ')':
                paren_depth -= 1
            i += 1
        
        condition = html[cond_start:i - 1]
        
        # Skip whitespace to opening brace
        while i < len(html) and html[i] in ' \t\n':
            i += 1
        
        if i >= len(html) or html[i] != '{':
            continue
        
        # Extract if-block content
        brace_end = find_matching_brace(html, i)
        if brace_end == -1:
            continue
        
        if_content = html[i + 1:brace_end]
        i = brace_end + 1
        
        # Check for @ELSE block
        else_content = ''
        else_match = re.match(r'\s*@ELSE\s*\{', html[i:])
        if else_match:
            i += else_match.end()
            else_end = find_matching_brace(html, i - 1)
            if else_end != -1:
                else_content = html[i:else_end]
                i = else_end + 1
        
        # Evaluate and recurse into chosen branch
        chosen = if_content if evaluate_condition(condition) else else_content
        result.append(process_conditionals(chosen))
    
    return ''.join(result)

# =============================================================================
# Signal Expression Processing
# =============================================================================

SIGNAL_IF_PATTERN = re.compile(
    r'(<\w+[^>]*)\s+data-signal-if="([^"]+)"([^>]*>)',
    re.DOTALL
)

SIGNAL_VAR_PATTERN = re.compile(r'\$\{(\w+)\}')

SIGNAL_CLASS_PATTERN = re.compile(
    r'data-signal-class\.([a-zA-Z_][a-zA-Z0-9_-]*)="([^"]+)"',
    re.DOTALL
)

ELEMENT_WITH_SIGNAL_CLASS = re.compile(
    r'<(\w+)((?:\s+[a-zA-Z_][\w.-]*(?:="[^"]*"|=\'[^\']*\'|=[^\s>]*)?)*)\s*/?>',
    re.DOTALL
)

_signal_counter = 0


def reset_signal_counter():
    """Reset the signal counter. Call at the start of each page build."""
    global _signal_counter
    _signal_counter = 0


def process_signal_if(html: str) -> tuple[str, str]:
    """
    Transform data-signal-if="expr" into data-signal-checker with generated computed signals.
    Returns (processed_html, generated_js).
    """
    global _signal_counter
    generated_signals: list[str] = []
    
    def replace_signal_if(match: re.Match) -> str:
        global _signal_counter
        before_attr = match.group(1)
        expression = match.group(2)
        after_attr = match.group(3)
        
        # Generate unique name for this computed signal
        signal_name = f"__computed_{_signal_counter}"
        _signal_counter += 1
        
        # Find all signal references like ${count}
        referenced_signals = SIGNAL_VAR_PATTERN.findall(expression)
        
        # Transform expression: ${count} -> count.get()
        js_expression = SIGNAL_VAR_PATTERN.sub(r'\1.get()', expression)
        
        # Build dependency array
        deps_array = ', '.join(referenced_signals) if referenced_signals else ''
        
        # Generate the computed signal creation
        generated_signals.append(
            f"window.{signal_name} = createComputed('{signal_name}', () => {js_expression}, [{deps_array}]);"
        )
        
        return f'{before_attr} data-signal-checker="{signal_name}"{after_attr}'
    
    processed_html = SIGNAL_IF_PATTERN.sub(replace_signal_if, html)
    
    generated_js = ""
    if generated_signals:
        generated_js = "\n".join(generated_signals)
    
    return processed_html, generated_js


def process_signal_classes(html: str) -> tuple[str, str]:
    """
    Transform data-signal-class.classname="expr" into JS that toggles classes.
    Groups all class bindings per element into a single IIFE.
    Returns (processed_html, generated_js).
    """
    global _signal_counter
    generated_blocks: list[str] = []
    element_counter = 0
    
    def process_element(match: re.Match) -> str:
        global _signal_counter
        nonlocal element_counter
        
        tag_name = match.group(1)
        attrs = match.group(2)
        full_match = match.group(0)
        is_self_closing = full_match.rstrip().endswith('/>')
        
        # Only process if this element has signal-class attributes
        if 'data-signal-class.' not in attrs:
            return full_match
        
        # Find all signal-class bindings on this element
        bindings = SIGNAL_CLASS_PATTERN.findall(attrs)
        if not bindings:
            return full_match
        
        # Generate element ID
        element_id = f"__sc_{element_counter}"
        element_counter += 1
        
        # Remove all data-signal-class.* attributes and add the ID
        cleaned_attrs = SIGNAL_CLASS_PATTERN.sub('', attrs)
        cleaned_attrs = re.sub(r'\s+', ' ', cleaned_attrs).strip()
        cleaned_attrs = f' data-signal-class-id="{element_id}" {cleaned_attrs}'.rstrip()
        
        # Collect all dependencies and build update statements
        all_deps: set[str] = set()
        update_lines: list[str] = []
        
        for class_name, expression in bindings:
            referenced_signals = SIGNAL_VAR_PATTERN.findall(expression)
            all_deps.update(referenced_signals)
            
            js_expression = SIGNAL_VAR_PATTERN.sub(r'\1.get()', expression)
            update_lines.append(
                f"    el.classList.toggle('{class_name}', !!({js_expression}));"
            )
        
        deps_array = ', '.join(sorted(all_deps))
        updates = '\n'.join(update_lines)
        
        generated_blocks.append(f"""\
(function() {{
  const el = document.querySelector('[data-signal-class-id="{element_id}"]');
  const update = () => {{
{updates}
  }};
  [{deps_array}].forEach(s => s.subscribe(update));
  update();
}})();""")
        
        closing = ' />' if is_self_closing else '>'
        return f'<{tag_name}{cleaned_attrs}{closing}'
    
    # Match all opening/self-closing tags and process those with signal-class
    ALL_TAGS = re.compile(
        r'<(\w+)((?:\s+[a-zA-Z_][\w.-]*(?:="[^"]*"|=\'[^\']*\'|=[^\s>]*)?)*)\s*/?>',
        re.DOTALL
    )
    
    html = ALL_TAGS.sub(process_element, html)
    
    generated_js = ""
    if generated_blocks:
        generated_js = "\n".join(generated_blocks)
    
    return html, generated_js


def process_signal_expressions(html: str) -> tuple[str, str]:
    """
    Process all signal expression transforms (data-signal-if, data-signal-class.*).
    Returns (processed_html, generated_js).
    """
    reset_signal_counter()
    
    html, signal_if_js = process_signal_if(html)
    html, signal_class_js = process_signal_classes(html)
    
    # Combine all generated JS
    js_parts = [js for js in [signal_if_js, signal_class_js] if js]
    combined_js = ""
    if js_parts:
        combined_js = "<script>\n" + "\n".join(js_parts) + "\n</script>"
    
    return html, combined_js

# =============================================================================
# Page Generation
# =============================================================================

def extract_page_metadata(content: str) -> PageMetadata:
    """Extract #PAGE_* directives from content."""
    head_title = None
    title = None
    
    # Extract head title
    match = re.search(r'^#PAGE_HEAD_TITLE:(.*)', content, re.MULTILINE)
    if match:
        head_title = match.group(1).strip()
        content = re.sub(r'^#PAGE_HEAD_TITLE:.*\n?', '', content, flags=re.MULTILINE)
    
    # Extract title
    match = re.search(r'^#PAGE_TITLE:(.*)', content, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        content = re.sub(r'^#PAGE_TITLE:.*\n?', '', content, flags=re.MULTILINE)
    
    # Default head_title to title if not specified
    if not head_title:
        head_title = title or ""
    
    return PageMetadata(
        head_title=head_title,
        title=title or "",
        content=content
    )


def generate_page(skeleton: str, metadata: PageMetadata, page_id: str, styles: list[str]) -> str:
    """Generate a complete page from skeleton and content."""
    html = skeleton
    
    # Replace placeholders
    replacements = {
        '#PAGE_HEAD_TITLE': metadata.head_title,
        '#PAGE_TITLE': metadata.title,
        '#PAGE_CONTENT': metadata.content,
        '#PAGE_ID': page_id,
        '#CSS_HASH': str(random.getrandbits(128)),
    }
    
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    
    # Inject component styles before </head>
    for style in styles:
        html = re.sub(r'</head>', f"{style}\n</head>", html, flags=re.IGNORECASE)
    
    # Process conditionals (build-time @IF/@ELSE)
    html = process_conditionals(html)
    
    # Process signal expressions (runtime data-signal-if, data-signal-class.*)
    html, signal_js = process_signal_expressions(html)
    if signal_js:
        # Inject before </body> so signals library is already loaded
        html = re.sub(r'</body>', f"{signal_js}\n</body>", html, flags=re.IGNORECASE)
    
    return html

# =============================================================================
# Build Process
# =============================================================================

def copy_static_files(paths: ProjectPaths):
    """Copy CSS, JS, and static assets to output directory."""
    # Root-level CSS and JS
    for pattern in ("*.css", "*.js"):
        for file in paths.src.glob(pattern):
            shutil.copyfile(file, paths.output / file.name)
    
    # Static directory
    if paths.static.exists():
        static_output = paths.output / "static"
        static_output.mkdir(parents=True, exist_ok=True)
        
        for file in paths.static.glob("**/*"):
            if file.is_file():
                shutil.copyfile(file, static_output / file.name)


def build(base_path: Path):
    """Main build process."""
    paths = ProjectPaths.from_base(base_path)
    
    print(f"Building project: {paths.base.resolve()}")
    
    paths.output.mkdir(exist_ok=True)
    
    # Load skeleton
    skeleton_path = paths.src / "skeleton.html"
    if not skeleton_path.exists():
        print(f"Error: skeleton.html missing in {paths.src}/")
        return
    
    skeleton = skeleton_path.read_text()
    
    # Discover available components
    known_components = set()
    if paths.components.exists():
        known_components = {path.name for path in paths.components.iterdir() if path.is_dir()}
    
    # Process pages
    if not paths.pages.exists():
        print(f"Error: pages directory missing at {paths.pages}/")
        return
    
    html_files = list(paths.pages.glob("*.html"))
    if not html_files:
        print(f"No HTML files found in {paths.pages}/")
        return
    
    for src_file in html_files:
        print(f"Processing: {src_file.name}")
        
        content = src_file.read_text()
        content, styles = process_components(content, known_components, paths)
        metadata = extract_page_metadata(content)
        
        print(f"  Title: {metadata.head_title}")
        
        output_html = generate_page(skeleton, metadata, src_file.stem, styles)
        
        out_file = paths.output / src_file.name
        out_file.write_text(output_html)
        print(f"  -> {out_file}")
    
    copy_static_files(paths)
    print("Build complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base = Path(sys.argv[1])
    else:
        base = Path.cwd()
    
    if not base.exists():
        print(f"Error: Path does not exist: {base}")
        sys.exit(1)
    
    build(base)