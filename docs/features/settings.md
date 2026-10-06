# Settings

The Settings page (`/settings`) allows users to customize their display name, bio, application appearance, and email preferences. 

## Database Schema
Preferences are stored in `public.profiles` on a 1:1 basis with `auth.users`. 
All settings are stored alongside core user information like name and avatar. This eliminates the need for a JOIN when looking up user preferences.

Newly added columns:

| Column | Type | Default | Description |
|---|---|---|---|
| `display_name` | `text` | null | User's preferred display name for UI. |
| `bio` | `text` | null | A short user biography (max 160). |
| `theme` | `text` | `'system'` | The UI theme: `'light'`, `'dark'`, or `'system'`. |
| `default_view` | `text` | `'tree'` | The default file manager view: `'grid'`, `'list'`, or `'tree'`. |
| `email_on_upload` | `boolean` | `false` | Whether to trigger an email notification on successful file upload. |
| `warn_near_quota` | `boolean` | `true` | Whether to show a warning banner when nearing storage limits. |
| `quota_threshold` | `int` | `80` | The percentage threshold for the quota warning banner. |

## Backend Endpoints

The settings feature provides minimal REST API endpoints within ` services/api/app/runtime/account.py`.

- **`GET /account/settings`**: Returns a JSON representation of all settings for the currently authenticated user.
- **`PATCH /account/settings`**: Partially updates user settings. Only fields explicitly provided in the request body are modified utilizing the PostgREST partial representation feature (`Prefer: return=representation`). 
