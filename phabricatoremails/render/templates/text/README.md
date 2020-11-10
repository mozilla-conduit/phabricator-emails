Unlike with the HTML part of emails, the spacing
of text emails matters. The general convention that's being followed here is that there's a line of whitespace between
each section.

An example well-formatted email looks like:
```
http://phabricator.test/D1

(Associated with secure bug 1)
(http://bmo.test/show_bug.cgi?id=1)

conduit created this revision.
[!] Your review is needed

Reviewers:
- ConduitReviewer (r+)

Affected files:
- /c added
- /b added
- /README modified

-------------------------------

Email preferences:
https://phabricator.services.mozilla.com/preferences/this-link-is-fake
Feedback/issues/comments for this email are very welcome, please report
them on Bugzilla: https://bugzilla.mozilla.org/fake-link-again
```

Note that there's whitespace between each section:
* Revision link
* Bug information
* Event that occurred + "actionable" text
* Reviewers
* Affected files
* Footer line
* Footer text
* (There's other section types, but these^ are all that are used in this example)

### Techniques

#### Whitespace before section, trim after

Jinja allows you to remove whitespace before or after expressions using a dash:
* `{{- ... }}` will remove all whitespace between the previous element and this expression
* `{{ ... -}}` will remove all whitespace after this expression and the next element

See [the jinja docs](https://jinja.palletsprojects.com/en/2.11.x/templates/#whitespace-control) for more details.

A general styling convention that's used here when writing a block is that mandatory whitespace should be
 added before the content, and whitespace after the content should be trimmed.
 
For example, if writing a macro to handle outputting an optional comment, that block would look like:
```jinja2
{% macro output_optional_comment(comment) %}

{{ event.main_comment_message | comment }}
{%- endmacro %}
```

Note the `-` in the `endmacro` block.

Additionally, for consistency, when a `-` is needed, add it to the beginning of a line, rather than the end.
E.g.:
```jinja2
{# Doesn't follow convention #}
{% macros.thing1() -%}

{% macros.thing2() %}
-----
{# Follows convention #}
{% macros.thing1() %}

{%- macros.thing2() %}
```

#### Put whitespace in macros, if possible

For some things, like the email summary, it's most convenient to place whitespace directly in the template.
However, if whitespace is needed before a macro's contents, place the whitespace in the macro itself.

### Note by mhentges:

These techniques were discovered by trial-and-error, and may not be optimal - they're experimental!
The constraints that I was handling was:
* I wanted to logically separate sections (e.g.: email summary separated from details) in the templates with whitespace
  without adding unwanted whitespace to the templates themselves.
* Some sections were optional, so they needed to not take up any space if they weren't rendered
* I didn't want `-` to be over-used in a redundant way, so by only placing them on the front of expressions, 
  theoretically there was less risk of missing an unnecessary `-`.   
