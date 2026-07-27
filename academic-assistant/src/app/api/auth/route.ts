import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function POST(request: Request) {
  try {
    const { password } = await request.json();
    const adminPassword = process.env.WEB_ADMIN_PASSWORD;

    if (!adminPassword) {
      return NextResponse.json(
        { error: 'Error de configuración: WEB_ADMIN_PASSWORD no está configurada.' },
        { status: 500 }
      );
    }

    if (password === adminPassword) {
      const cookieStore = await cookies();
      cookieStore.set('auth_session', 'authenticated', {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 60 * 60 * 24 * 7, // 1 semana
        path: '/',
      });

      return NextResponse.json({ success: true });
    }

    return NextResponse.json(
      { error: 'Contraseña incorrecta' },
      { status: 401 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: 'Error interno del servidor' },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete('auth_session');
  return NextResponse.json({ success: true });
}
