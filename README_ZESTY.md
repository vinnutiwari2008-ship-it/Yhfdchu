# Zesty Level Up — Users JSON Secure Dashboard

## User features
- Black responsive dashboard
- Logout control
- Fast ZIP export of the current user's Level-Up IDs
- Access expiry with automatic browser logout when time reaches zero
- Expired accounts cannot authenticate again
- Admin broadcast/notice shown on the dashboard
- UID + password and access-token Level-Up ID support
- Slot enforcement: one saved ID consumes one slot; deleting an ID immediately frees the slot
- Multi-ID runtime handling
- Pause/resume/restart/refresh controls
- Persistent user-owned Level-Up IDs in `users.json`

## Security
- Server-side authentication and authorization
- PBKDF2 password hashing
- Signed HTTP-only session cookies
- Session expiry and auth-version invalidation
- User-agent binding
- Login rate limiting
- CSRF protection for admin mutations
- Security headers and CSP
- Private dashboard/API responses are `no-store`
- Private routes marked `noindex`
- No `accounts.json` dependency

## Important limitation
No web application can guarantee that its public HTML/CSS/JavaScript can never be inspected by a visitor. This build therefore keeps secrets and authorization decisions server-side and does not place passwords, tokens, or admin credentials in frontend source.

## Railway
- `Procfile` included
- `railway.toml` included
- `PORT` environment variable supported
- Install dependencies from `requirements.txt`

## Dashboard UI upgrade
- True black, high-contrast dashboard theme with subtle borders and reduced background glow.
- Responsive desktop/mobile layout retained.
- Added a live Access Overview showing username, plan, saved-ID slots, remaining access time, role, and service state.
- Added an in-dashboard Guide explaining Add ID, Export IDs, Pause/Resume, Refresh/Restart, and access expiry.
- Added an explicit security note explaining the server-side security boundary and the fact that public frontend code can be inspected.
- Access profile data is populated from `/api/account/profile`; timed access continues to redirect to login when expired.
- Removed the misleading static “100% Operational” wording in favor of live telemetry wording.


## Dashboard Upgrade — Black Professional Control Center
- True-black dashboard surfaces throughout.
- Per-ID Match Mode selector: Lone Wolf, Battle Royale, or Mix (Lone Wolf → Battle Royale alternating).
- Admin global pause/resume for runtime IDs.
- Admin one-click delete/cancel for all normal-user Level-Up IDs.
- Custom slot limits per access user.
- Admin-managed public pricing and custom purchase/support links.
- Admin broadcast/notice system remains available and is shown live in the dashboard.
- Pricing is persisted in `pricing.json` and included in secure ZIP backups.

### Important
The existing codebase exposes the Lone Wolf and Battle Royale starter functions separately. The dashboard now routes mode selection through those functions; the supplied engine currently aliases `start_game_lone_wolf` to the existing starter implementation, so replacing that protocol-specific function is required if a distinct Lone Wolf packet is needed.
