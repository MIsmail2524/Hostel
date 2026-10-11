import { router } from 'expo-router';

import { useAuth } from './auth';

/** Returns a guard: runs the action if signed in & verified, otherwise routes to login/verify. */
export function useRequireAuth() {
  const { user } = useAuth();
  return (action: () => void, needVerified = true) => {
    if (!user) return router.push('/auth/login');
    if (needVerified && !user.contact_verified) return router.push('/auth/verify');
    action();
  };
}
