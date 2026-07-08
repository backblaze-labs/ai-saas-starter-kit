<!-- last_verified: 2026-03-10 -->
# App Workflows

User journeys inside the application.

## Sign Up & Sign In

- New user navigates to `/signup`, enters name/email/password
- Supabase sends a confirmation email (locally, caught by Mailpit at `:54324`)
- User clicks the link → `/auth/confirm` verifies it and establishes the session → lands in the app
- Returning user signs in at `/signin` with password **or** an emailed 6-digit code
- Unauthenticated visits to any protected route redirect to `/signin?next=<path>`
- `/account` shows the profile (editable name), role badge, an "API session" check, and Sign out
- The first user to sign up is an admin
- See: [Authentication](features/authentication.md)

## Subscribe & Manage Billing

- User navigates to `/billing`, sees Free / Pro / Team plan cards and their current plan
- Clicking **Upgrade** starts a Stripe Checkout Session and redirects to Stripe
- Paying with the test card `4242 4242 4242 4242` returns to `/billing?checkout=success`
- Stripe's webhook syncs the subscription into Supabase; the plan badge updates to the new tier
- Pro-only surfaces (e.g. AI media generation) unlock once the tier is Pro or higher
- **Manage billing** opens the Stripe Billing Portal to change or cancel the plan
- A Free user sees the Pro feature preview card in a locked state
- See: [Billing](features/billing.md)

## Upload Files

- User navigates to `/upload`
- Drops or selects files in the dropzone
- Client validates file size (max 100MB) and type
- Progress bar shows per-file upload status
- On success: toast notification, green checkmark
- On failure: red status icon with error message
- User can clear completed uploads
- See: [File Upload](features/file-upload.md)

## Browse and Manage Files

- User navigates to `/files`
- Page loads file list from API (sorted most recent first)
- Files displayed in tree view with folders and type-specific icons
- Top-level folders auto-expand on load
- Hover a file row to see action buttons (preview / download / delete)
- **Preview**: opens dialog with image/PDF preview + metadata panel
- **Download**: fetches presigned URL, browser downloads file
- **Delete**: removes file from B2, row removed from tree, toast confirms
- Empty bucket shows "No files found" with upload prompt
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Three parallel API calls load: stats, recent files, upload activity
- Stats cards show: total files, storage used, uploads today, total downloads
- Upload chart shows last 7 days of upload activity as bar chart
- Recent uploads table shows last 10 files with filename, size, type, date
- Empty state: "No files uploaded yet" messages
- See: [Dashboard](features/dashboard.md)
