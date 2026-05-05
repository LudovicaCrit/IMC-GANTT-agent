// ─────────────────────────────────────────────────────────────────────────
//  FullScreenLoader.jsx — Spinner full-screen durante operazioni di auth
//
//  Mostrato mentre AuthContext sta verificando la sessione (chiamata /me).
//  Tipicamente <100ms, ma evita il flash "vedo la pagina poi redirect".
// ─────────────────────────────────────────────────────────────────────────

export default function FullScreenLoader() {
  return (
    <div
      className="flex h-screen items-center justify-center"
      style={{ backgroundColor: 'var(--color-surface-950)' }}
    >
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{
            borderColor: '#60a5fa',
            borderTopColor: 'transparent',
          }}
        />
        <p className="text-xs text-gray-500">Caricamento…</p>
      </div>
    </div>
  );
}