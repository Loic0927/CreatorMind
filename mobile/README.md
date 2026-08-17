# CreatorMind Mobile (phase one)

Independent React Native + Expo + TypeScript client for CreatorMind. It does not wrap the website in a WebView and does not publish to social platforms.

This app currently targets Expo SDK 54 so it can be tested with the current Expo Go app on a physical iPhone. Keep the SDK and Expo-managed dependencies aligned with `npx expo install --fix`.

## Requirements

- Windows 10/11
- Node.js 20.19.4 or newer
- npm
- Expo Go on an iPhone or Android phone
- Phone and Windows PC on the same Wi-Fi network

## Install and start

```powershell
cd C:\Users\0927b\OneDrive\Desktop\CreatorMind\mobile
npm install
Copy-Item .env.example .env.local
npx expo start
```

Edit `.env.local` before starting. For a physical phone, replace `192.168.1.100` with the Windows PC's LAN IPv4 address from `ipconfig`. Start the CreatorMind backend so it listens on the LAN:

```powershell
cd C:\Users\0927b\OneDrive\Desktop\CreatorMind
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Allow Python/port 8000 through Windows Firewall only for Private networks if prompted. Keep `EXPO_PUBLIC_CAPTION_MODE=mock` for phase one.

## Expo Go on a physical phone

1. Connect the phone and PC to the same Wi-Fi. Disable phone VPN/mobile-data switching if it blocks LAN traffic.
2. Run `npx expo start` in `mobile`.
3. Android: open Expo Go and scan the QR code. iPhone: scan with Camera, then open in Expo Go.
4. If LAN discovery is blocked, try `npx expo start --tunnel` (slower and requires internet).
5. Reload Expo Go after changing `.env.local`.

`localhost` on a physical phone means the phone itself. Use the PC LAN IP. Android Emulator uses `http://10.0.2.2:8000`; iOS Simulator on macOS can use `http://127.0.0.1:8000`. Windows cannot run Apple's iOS Simulator, but Expo Go on a real iPhone works.

## Environment and security

Expo embeds every `EXPO_PUBLIC_*` value in the app bundle. Put only non-secret values such as the CreatorMind API URL and a display environment name there. Never add OpenAI, Gemini, Meta, OAuth client secrets, passwords, or permanent access tokens. Third-party calls must be performed by the CreatorMind backend.

Demo login state is stored using `expo-secure-store`, not AsyncStorage. It is not real authentication and contains no server token.

## Real versus mock

- Real: native image selection and preview, editable form state, SecureStore-backed demo session, environment display.
- Mock: caption and hashtag generation (`src/services/caption.ts`). It is visibly labelled `MOCK AI`.
- Skeleton only: Likes, Comments, Saves, Shares, Reach, Engagement rate.
- Not implemented: real authentication, media upload, `/mobile/caption`, Instagram OAuth, publishing, live insights.

When the backend adds an authenticated `POST /mobile/caption` endpoint, set `EXPO_PUBLIC_CAPTION_MODE=api`. The endpoint must call the AI provider server-side and return `{ "caption": "...", "hashtags": "..." }`.

## Checks

```powershell
npm run typecheck
npm run lint
npm test
npx expo-doctor@latest
npx expo config --type public
```
