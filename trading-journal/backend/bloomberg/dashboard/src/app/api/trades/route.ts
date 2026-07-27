import { NextResponse } from 'next/server';
import { getRedisClient } from '@/lib/redis';
import { Trade } from '@/lib/calculations';
import crypto from 'crypto';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const redis = await getRedisClient();
    let tradesStr: string[] = [];
    try {
      if (redis.isOpen) {
          tradesStr = await redis.lRange("trades:all", 0, -1);
      }
    } catch (e) {
      console.warn("Redis read failed in trades route:", e);
    }
    const safeJsonParse = <T>(value: string  null  undefined, fallback: T): T => {
      if (!value) return fallback;
      try {
        return JSON.parse(value) as T;
      } catch {
        return fallback;
      }
    };

    const trades = tradesStr
      .map(t => safeJsonParse<any  null>(t, null))
      .filter((t): t is any => t !== null);
    return NextResponse.json(trades);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const redis = await getRedisClient();
    
    const trade: Trade = {
      id: crypto.randomUUID(),
      ...body,
      entry_date: new Date().toISOString(),
      exit_price: null,
      exit_date: null,
    };
    
    try {
      if (redis.isOpen) {
        await redis.lPush("trades:all", JSON.stringify(trade));
      }
    } catch (e) {
      console.warn("Redis write failed in trades route:", e);
    }
    return NextResponse.json({ success: true, trade });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
