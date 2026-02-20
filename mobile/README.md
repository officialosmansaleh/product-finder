# Product Finder Mobile (Android/iOS)

Questa cartella crea una app mobile senza toccare il backend Python.

## 1) Prerequisiti

- Node.js 20+
- Android Studio (per Android)
- Xcode + macOS (per iOS)

## 2) Configura URL backend

Apri `capacitor.config.json` e sostituisci:

- `https://YOUR-BACKEND-URL`

con l'URL pubblico raggiungibile dal telefono.

Esempio:

- `https://abc123.ngrok-free.app`

## 3) Installa dipendenze

Da `mobile/`:

```bash
npm install
```

## 4) Genera progetti nativi

```bash
npx cap add android
npx cap add ios
npx cap sync
```

## 5) Avvia

Android:

```bash
npx cap open android
```

iOS:

```bash
npx cap open ios
```

## Note importanti

- Non usare `localhost` nel `server.url`: su telefono punta a se stesso, non al tuo PC.
- Per test locale usa tunnel (ngrok/cloudflared) o un backend deployato.
- iOS richiede Mac/Xcode per build e firma.
