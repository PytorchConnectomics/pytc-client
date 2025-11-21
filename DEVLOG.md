# DEVLOG.md — pytc-client Development Log

This file records the major development steps, design decisions, and UI/UX changes made to the pytc-client project. It is formatted for easy reading by humans and AI agents.

---

## Project Context
- **Repo:** PytorchConnectomics/pytc-client
- **Frontend:** React + Electron (Ant Design)
- **Backend:** FastAPI (Python), local user management for prototype

---

## Major Features & Changes

### 1. Welcome Page
- Added a full-screen Welcome page as the app's entry point.
- Includes project name, intro, and warm message.
- Two buttons: "Sign in" and "Sign up".
- Styled to resemble cursor.com (modern, clean, gradient background).
- Welcome page is always shown on app start (automatic sign out).

### 2. Local User Management
- Implemented `UserContext` using React Context and localforage.
- User model: `{ id, name, passwordHash, files: [file1, file2, file3], createdAt }`
- Passwords hashed with SHA-256 (Web Crypto API, prototype only).
- Sign-in and sign-up modals (Ant Design) wired to local user manager.
- Automatic sign out on app start (always shows Welcome).

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

---

## Next Steps / TODOs
- [ ] Add multi-file support or previews in Files tab.
- [ ] Add manual sign-out button in main app view.
- [ ] Integrate backend user management (FastAPI, JWT, etc.) for production.
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

_Last updated: 2025-11-20_
