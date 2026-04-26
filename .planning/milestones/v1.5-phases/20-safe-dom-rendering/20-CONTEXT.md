# Context — Phase 20: Safe DOM Rendering

**Milestone:** v1.5 XSS Security Fix
**Phase:** 20 - Safe DOM Rendering
**Date:** 2026-04-26

---

## Objective

Replace all unsafe `innerHTML` usage for user-controlled content in frontend templates with safe DOM APIs (`textContent`, `createElement`, `setAttribute`) to prevent script injection.

---

## Dependencies

**Phase 19 Complete:** Server-side validation ensures all metadata originates from trusted Jellyfin source. Phase 20 adds defense-in-depth by ensuring frontend rendering is also secure.

---

## Scope

**Templates to Modify:**
1. `jellyswipe/templates/index.html` - Primary application UI
2. `data/index.html` - PWA-oriented copy (mirrors above with hardcoded mediaProvider)

**Unsafe Patterns to Eliminate:**
- Template literal interpolation with user data inside `innerHTML`
- Direct assignment of user-controlled data to DOM properties
- Any pattern that could result in script execution

**User-Controlled Data Fields:**
- `m.title` - Movie title
- `m.summary` - Movie description
- `m.thumb` - Thumbnail URL
- `m.movie_id` - Movie identifier
- `actor.name` - Actor name
- `actor.character` - Character name (if present)
- `actor.profile_path` - Actor photo URL

---

## Technical Context

### Current Implementation (Vulnerable)

Both templates use template literals with `innerHTML`:

```javascript
// VULNERABLE: User data in innerHTML
card.innerHTML = `
    <div class="card-front"><img src="${m.thumb}"></div>
    <div class="card-back">
        <div class="movie-title">${m.title}</div>
        <div class="back-content"><p>${m.summary || 'No description available.'}</p></div>
    </div>
`;
```

### Target Implementation (Safe)

```javascript
// SAFE: DOM construction with textContent
const cardInner = document.createElement('div');
cardInner.className = 'card-inner';

const cardFront = document.createElement('div');
cardFront.className = 'card-front';
const img = document.createElement('img');
img.src = m.thumb; // Safe: src property assignment
img.alt = 'Movie poster';
cardFront.appendChild(img);
cardInner.appendChild(cardFront);

const cardBack = document.createElement('div');
cardBack.className = 'card-back';
const titleEl = document.createElement('div');
titleEl.className = 'movie-title';
titleEl.textContent = m.title; // Safe: textContent escapes HTML
cardBack.appendChild(titleEl);

const backContent = document.createElement('div');
backContent.className = 'back-content';
const p = document.createElement('p');
p.textContent = m.summary || 'No description available.';
backContent.appendChild(p);
cardBack.appendChild(backContent);

cardInner.appendChild(cardBack);
card.appendChild(cardInner);
```

---

## Decisions

### D-01: DOM Construction Pattern
Use `document.createElement()` for element creation, `textContent` for text content, and `setAttribute()` or direct property assignment for attributes. This provides explicit control and prevents script injection.

**Rationale:** `textContent` automatically escapes HTML special characters, while `innerHTML` parses and executes any embedded scripts. Direct property assignment (e.g., `img.src = url`) is safe for URLs as the browser validates and encodes appropriately.

### D-02: Match Card Rendering
Refactor `openMatches()` function to construct match cards using safe DOM methods instead of template literals.

**Rationale:** Match cards display user-controlled titles, summaries, and other metadata. Safe DOM construction ensures these values render as text, not executable HTML.

### D-03: Movie Card Rendering
Refactor `createCard()` function to construct movie cards using safe DOM methods.

**Rationale:** Movie cards display all user-controlled fields (title, summary, cast). Safe construction is critical as this is the primary UI component.

### D-04: Cast Member Rendering
Refactor cast loading logic to construct cast member elements using safe DOM methods.

**Rationale:** Cast names and character names are user-controlled. Safe construction prevents script injection through these fields.

### D-05: Trailer Iframe
Use `iframe.src` property assignment instead of `innerHTML` for YouTube embeds.

**Rationale:** While YouTube keys are not user-controlled, using safe patterns consistently reduces risk and improves code maintainability.

### D-06: Empty State Handling
Maintain existing empty state rendering: `list.innerHTML = data.length ? '' : '<p>No matches yet</p>'` is acceptable because the text is literal (not user-controlled).

**Rationale:** Empty state text is hard-coded, not derived from user data. This exception is safe and maintains readability.

---

## the agent's Discretion

The agent may:
- Refactor helper functions if they improve code clarity (e.g., extract repeated DOM construction patterns)
- Add comments explaining safe DOM usage where beneficial for maintainers
- Choose between property assignment (`img.src = url`) and `setAttribute()` based on consistency with existing code patterns
- Optimize DOM construction for performance if needed, without compromising security

---

## Success Criteria

From ROADMAP.md:

1. Movie titles, summaries, actor names, and character names are rendered using `textContent` (not `innerHTML`)
2. Image sources and movie IDs are set using `setAttribute()` or DOM property assignment (not `innerHTML`)
3. All `innerHTML` usages for user-controlled content have been removed or refactored to safe DOM construction
4. Malicious script tags in movie data render as literal text in the browser (not executed)

---

## Implementation Notes

### Pattern: Safe Text Content
```javascript
// Instead of: element.innerHTML = userValue;
// Use:
element.textContent = userValue;
```

### Pattern: Safe Attribute Assignment
```javascript
// Instead of: element.innerHTML = `<img src="${userUrl}">`;
// Use:
const img = document.createElement('img');
img.src = userUrl; // or img.setAttribute('src', userUrl);
```

### Pattern: Safe HTML Structure
```javascript
// Instead of: container.innerHTML = userHtmlTemplate;
// Use:
const parent = document.createElement('div');
parent.className = 'parent-class';
const child = document.createElement('div');
child.textContent = userText;
parent.appendChild(child);
container.appendChild(parent);
```

---

## Verification

After implementation, verify:
1. No `innerHTML` assignments contain template literal interpolations with user data
2. All text content uses `textContent` property
3. All attributes use `setAttribute()` or direct property assignment
4. Both templates (`jellyswipe/templates/index.html` and `data/index.html`) have identical safe DOM implementations
5. Manual test: Add `<script>alert('XSS')</script>` to a movie title in the database and verify it renders as literal text

---

*Context created: 2026-04-26*
