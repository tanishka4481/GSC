export const AUTH_STORAGE_KEY = 'provchain_demo_user';

export function getCurrentUser() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getOwnerId() {
  const user = getCurrentUser();
  return user?.ownerId || user?.email?.toLowerCase() || user?.name?.toLowerCase() || 'demo-user';
}
