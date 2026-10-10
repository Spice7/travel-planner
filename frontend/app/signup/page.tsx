import AuthForm from '@/components/AuthForm';
import { safeNext } from '@/lib/session';

export default async function SignupPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  return <AuthForm mode="signup" next={safeNext((await searchParams).next)} />;
}
