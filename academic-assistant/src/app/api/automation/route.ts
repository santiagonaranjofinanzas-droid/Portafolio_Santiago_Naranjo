import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

export async function GET() {
  try {
    const { data, error } = await supabase
      .from('sistema_config')
      .select('*')
      .eq('id', 1)
      .single();

    if (error  !data) {
      // Fallback for UI if table doesn't exist yet
      return NextResponse.json({
        automatizacion_activa: true,
        ultima_ejecucion_scraper: null,
        intervalo_horas: 3
      });
    }
    
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to read config' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    
    // Update or insert config row
    const { data, error } = await supabase
      .from('sistema_config')
      .upsert({ id: 1, ...body }, { onConflict: 'id' })
      .select()
      .single();

    if (error) throw error;
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json({ error: 'Failed to update config' }, { status: 500 });
  }
}
