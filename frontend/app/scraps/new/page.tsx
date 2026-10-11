import { redirect } from 'next/navigation';
import PostScrapForm from '@/components/PostScrapForm';
import { getMe } from '@/lib/server-api';

export const dynamic = 'force-dynamic';

export default async function NewPostScrapPage() {
  if (!(await getMe().catch(() => null))) redirect('/login?next=/scraps/new');
  return <PostScrapForm />;
}
