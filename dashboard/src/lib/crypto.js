// Key obfuscation for browser-stored API keys.
//
// This is NOT real encryption: anything the browser can decrypt, an attacker
// with devtools access can too. What it does is keep keys from sitting in
// localStorage as copy-paste plaintext (shoulder-surfing, accidental pastes
// into screenshots/logs). Real protection is the cloud managed-keys path,
// where secrets never touch the browser at all.
//
// Small Module, small Interface: encrypt/decrypt + nothing else. Callers and
// tests cross this one seam; the XOR detail stays inside.
const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'OpenShorts-Static-Salt-Change-Me';
const ENCRYPTION_PREFIX = 'ENC:';

export function encrypt(text) {
  if (!text) return '';
  try {
    const xor = text
      .split('')
      .map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ SECRET_KEY.charCodeAt(i % SECRET_KEY.length)))
      .join('');
    return ENCRYPTION_PREFIX + btoa(xor);
  } catch (e) {
    console.error('Encryption failed', e);
    return text;
  }
}

export function decrypt(text) {
  if (!text) return '';
  if (text.startsWith(ENCRYPTION_PREFIX)) {
    try {
      const xor = atob(text.slice(ENCRYPTION_PREFIX.length));
      return xor
        .split('')
        .map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ SECRET_KEY.charCodeAt(i % SECRET_KEY.length)))
        .join('');
    } catch {
      // Corrupt payload: fail closed rather than surfacing garbage as a key.
      return '';
    }
  }
  // Backward compatibility: pre-prefix values were stored as plaintext.
  // Returned as-is so the field populates; the next save re-encrypts it.
  return text;
}
