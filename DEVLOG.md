# DEVLOG.md — pytc-client Development Log

This file records the major development steps, design decisions, and UI/UX changes made to the pytc-client project. It is formatted for easy reading by humans and AI agents.

---

## Project Context
- **Repo:** PytorchConnectomics/pytc-client
- **Frontend:** React + Electron (Ant Design)
- **Backend:** FastAPI (Python), local user management for prototype

---

## Major Features & Changes

### [2025-11-21] Backend User Management
*   **Backend Auth**: Integrated FastAPI with `python-jose` (JWT) and `passlib` (bcrypt) for secure authentication.
*   **Database**: Added SQLite database (`sql_app.db`) with SQLAlchemy models for Users.
*   **Frontend Integration**: Updated `UserContext` to communicate with backend endpoints (`/register`, `/token`, `/users/me`) instead of local storage.
*   **Dependencies**: Added `python-jose`, `passlib`, `sqlalchemy` to requirements.

### [2025-11-21] Advanced File Management & UI Polish
*   **Manual Sign Out**: Added a sign-out button to the header, allowing users to return to the Welcome screen.
*   **File Previews**: Implemented a preview modal for files (images and text) triggered by double-click or context menu.
*   **Multi-Select & Drag Selection**: Added drag selection box and keyboard shortcuts (Ctrl/Shift) for selecting multiple files.
*   **Enhanced Drag & Drop**: Enabled moving multiple selected files/folders at once, including within the same parent directory.
*   **Context Menu Enhancements**: Updated context menu to handle multiple selections (bulk Copy/Delete) and hide "Preview" for multi-select.
*   **Bug Fixes**: Resolved issues with drag selection (single item) and Electron path handling on Windows.

### 1. Welcome Page
- Added a full-screen Welcome page as the app's entry point.
- Includes project name, intro, and warm message.
- Two buttons: "Sign in" and "Sign up".
- Styled to resemble cursor.com (modern, clean, gradient background).
- Welcome page is always shown on app start (automatic sign out).

### 2. Backend User Management (New)
- Replaced local storage with production-ready backend auth.
- Users are stored in `server_api/sql_app.db` (SQLite).
- Passwords are hashed with bcrypt.
- JWT tokens used for session management (stored in localStorage).

### 3. Main App Navigation
- After login, user sees main app view (tabs: Visualization, Model Training, Model Inference, Tensorboard, Files).
- "Welcome" tab removed from main menu after login.
- Navigation to Welcome page is blocked after login.

### 4. Files Tab (Google Drive-like)
- Files tab shows three file slots per user.
- Each slot displays file info (name, size, type) or "Empty".
- Upload, rename, and delete actions for each slot (Ant Design components).
- Upload is local only; rename uses modal; delete clears slot.

### 5. Debugging & Build Process
- Debug banners/messages added and removed for troubleshooting.
- Reminder: Electron app uses static build (`client/build/`), so `npm run build` is required after code changes.
- Hot reload only works in browser dev mode (`npm start`).

---

## Known Issues & Fixes
- [x] Welcome page not showing: fixed by auto sign out on app start.
- [x] "Welcome" tab visible after login: removed from menu.
- [x] Debug messages visible: removed.
- [x] Modals not working in Electron: fixed after proper build/restart.
- [x] Drag selection not selecting single items: fixed.
- [x] Electron "ERR_FILE_NOT_FOUND": fixed path separator in main.js.

---

## Next Steps / TODOs
- [x] Add multi-file support or previews in Files tab.
- [x] Add manual sign-out button in main app view.
- [x] Integrate backend user management (FastAPI, JWT, etc.) for production.
- [ ] Add user profile editing and avatar upload.
- [ ] Improve file upload to support actual file storage (not just metadata).

---

## How to Develop & Test
- Make code changes in `client/src/`.
- Run `npm --prefix client run build` to update the Electron app.
- Start the app with `./start.bat`.
- For live development, use `npm start` (browser only).

---

## AI Agent Notes
- All major UI/UX changes, context, and user flows are documented here.
- Use this file to bootstrap further development, onboarding, or automation.
- For backend integration, see FastAPI endpoints and user model notes above.

---

_Last updated: 2025-11-21_
