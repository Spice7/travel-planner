import { NextResponse } from 'next/server';
import { TOKEN_COOKIE } from '@/lib/session';

export async function POST() {
  const response = new NextResponse(null, { status: 204 });
  response.cookies.delete(TOKEN_COOKIE);
  return response;
}
