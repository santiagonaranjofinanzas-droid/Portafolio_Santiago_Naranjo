// src/middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export default async function proxy(request: NextRequest) {
  // If the user has the auth cookie, allow them through
  const session = request.cookies.get('auth_session');
  
  // Public paths that don't require authentication
  const isPublicPath = request.nextUrl.pathname === '/login'  request.nextUrl.pathname.startsWith('/api/auth');

  if (!session && !isPublicPath) {
    // Redirect to login if accessing a protected route without session
    return NextResponse.redirect(new URL('/login', request.url));
  }

  if (session && request.nextUrl.pathname === '/login') {
    // If already authenticated and trying to access login, redirect to home
    return NextResponse.redirect(new URL('/', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files
     */
    '/((?!_next/static_next/imagefavicon.ico.*\\.(?:svgpngjpgjpeggifwebp)$).*)',
  ],
};
