import AuthForm from '@/components/AuthForm';
import { safeNext } from '@/lib/session';

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  return <AuthForm mode="login" next={safeNext((await searchParams).next)} />;
}
