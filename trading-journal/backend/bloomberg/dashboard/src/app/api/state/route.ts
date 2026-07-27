import { NextResponse } from 'next/server';
import { getRedisClient } from '@/lib/redis';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const redis = await getRedisClient();
    let quantStr, mirofishStr, nav, hwm, tickerStr, historyStr, newsStr, weightsStr;
    try {
      if (redis.isOpen) {
        [quantStr, mirofishStr, nav, hwm, tickerStr, historyStr, newsStr, weightsStr] = await Promise.all([
          redis.get("quant:latest"),
          redis.get("mirofish:latest"),
          redis.get("portfolio:nav"),
          redis.get("portfolio:hwm"),
          redis.get("ticker:latest"),
          redis.lRange("quant:history", 0, -1),
          redis.get("processed_feed:latest"),
          redis.get("portfolio:weights")
        ]);
      }
    } catch (e) {
      console.warn("Redis read failed in state route:", e);
    }

    const safeJsonParse = <T>(value: string  null  undefined, fallback: T): T => {
      if (!value) return fallback;
      try {
        return JSON.parse(value) as T;
      } catch {
        return fallback;
      }
    };

    const quant = safeJsonParse(quantStr, {
      regime_probabilities: { low: 0, high: 0, transition: 0 },
      stress_probability_t5: 0,
      status: "WAITING_DATA"
    });
    
    const mirofish = safeJsonParse(mirofishStr, {
      R_narr: 0,
      omega_narr: 0,
      dominant_theme: "Esperando Ingesta",
      confidence: 0,
      reasoning: "El sistema está inicializado en modo real. A la espera de que los cronjobs de Python envíen la primera inferencia a Redis."
    });

    const portfolio = {
      nav: nav ? parseFloat(nav) : 3000,
      hwm: hwm ? parseFloat(hwm) : 3000
    };

    const weights = safeJsonParse<Record<string, number>>(weightsStr, {
      QQQ: 0.6,
      GLD: 0.4,
      CASH: 0.0
    });

    const ticker = safeJsonParse<any[]>(tickerStr, []);
    const history = (historyStr  [])
      .map((s: string) => safeJsonParse<any  null>(s, null))
      .filter((item): item is any => item !== null)
      .reverse();
    const newsPayload = safeJsonParse<any>(newsStr, []);
    const news = Array.isArray(newsPayload)
      ? newsPayload
      : Array.isArray(newsPayload?.data)
      ? newsPayload.data
      : [];

    return NextResponse.json({ quant, mirofish, portfolio, ticker, history, news, weights });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
