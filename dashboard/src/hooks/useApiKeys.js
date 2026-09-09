import { useEffect, useState } from 'react';
import { decrypt, encrypt } from '../lib/crypto';

// Browser API-key store behind one seam. Load decodes (with plaintext
// back-compat inside crypto.js); persist encodes — except gemini_key, which
// stays plaintext on purpose (compat with older builds and server fallback).
// Writes only fire when the value is truthy so clearing a field in one tab
// never wipes the stored key with an empty string.
//
// Interface: the same [value, setter] pairs App.jsx used as raw useState,
// so callers keep working unchanged.
const readPlain = (key) => {
  try {
    return localStorage.getItem(key) || '';
  } catch (_) {
    return '';
  }
};

const readSecret = (key) => {
  try {
    const stored = localStorage.getItem(key);
    return stored ? decrypt(stored) : '';
  } catch (_) {
    return '';
  }
};

const write = (key, value, secret) => {
  if (!value) return;
  try {
    localStorage.setItem(key, secret ? encrypt(value) : value);
  } catch (_) {
    // Quota/full/disabled storage — keys just don't persist. Ignore.
  }
};

export function useApiKeys() {
  const [apiKey, setApiKey] = useState(() => readPlain('gemini_key'));
  const [uploadPostKey, setUploadPostKey] = useState(() => readSecret('uploadPostKey_v3'));
  const [elevenLabsKey, setElevenLabsKey] = useState(() => readSecret('elevenLabsKey_v1'));
  const [falKey, setFalKey] = useState(() => readSecret('falKey_v1'));
  const [uploadUserId, setUploadUserId] = useState(() => readPlain('uploadUserId'));

  useEffect(() => {
    // Encrypt Gemini Key too for consistency if desired, but user asked specifically about Social integration not saving well.
    // For now keeping gemini plain for compatibility unless requested.
    write('gemini_key', apiKey, false);
  }, [apiKey]);

  useEffect(() => {
    write('uploadPostKey_v3', uploadPostKey, true);
    write('uploadUserId', uploadUserId, false);
  }, [uploadPostKey, uploadUserId]);

  useEffect(() => {
    write('elevenLabsKey_v1', elevenLabsKey, true);
  }, [elevenLabsKey]);

  useEffect(() => {
    write('falKey_v1', falKey, true);
  }, [falKey]);

  return {
    apiKey, setApiKey,
    uploadPostKey, setUploadPostKey,
    elevenLabsKey, setElevenLabsKey,
    falKey, setFalKey,
    uploadUserId, setUploadUserId,
  };
}
