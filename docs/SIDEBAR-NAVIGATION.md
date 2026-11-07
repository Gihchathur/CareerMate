# Sidebar navigation and Overview

## How the desktop sidebar works

The desktop rail expands on pointer hover (and on keyboard focus). No collapse/reopen button is required. The expanded rail has three vertical regions:

1. **Brand header** — fixed at the top.
2. **Navigation list** — the only independently scrollable region. All navigation groups remain in the DOM and can be reached by scrolling or by tabbing through their links.
3. **Profile readiness and provider status** — fixed below the navigation list; it does not cover or replace navigation items.

On shorter desktop windows, link rows compact slightly and the navigation list scrolls. Section labels can be hidden at short heights to preserve room, but links are not removed. On touch devices the existing bottom navigation and More sheet remain in use.

## Overview route

The first navigation item is **Today**. It is the Overview page and maps to the `overview` workspace view, rendered by `TodayDashboard`. The CareerMate brand/home action also opens this view. The navigation hint describes it as the overview of priorities, next actions and recent activity.

## Portal registry document

The editable local employer portal registry lives at `data/sources.json`. Start from `data/portals.example.json` only on a new setup. For an existing installation, back up the active file and merge optional `career_url`, `jobs_url`, and `notes` fields rather than replacing the user's portal list. See [Portal configuration](PORTAL-CONFIGURATION.md).
