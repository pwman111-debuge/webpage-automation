import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  const host = request.headers.get('host') ?? '';

  if (host.includes('stockanalysis2.pages.dev')) {
    const url = request.nextUrl.clone();
    url.protocol = 'https:';
    url.host = 'genesis-report.com';
    url.port = '';
    return NextResponse.redirect(url, { status: 301 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
