import { NextResponse } from 'next/server';
import { getRedisClient } from '@/lib/redis';
import { totalReturn, sharpeRatio, maxDrawdown, portfolioVolatility, winRate, dailyReturns } from '@/lib/calculations';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const redis = await getRedisClient();
    let navHistoryStr: string[] = [];
    let tradesStr: string[] = [];
    
    try {
      if (redis.isOpen) {
          navHistoryStr = await redis.lRange("portfolio:nav_history", 0, -1);
          tradesStr = await redis.lRange("trades:all", 0, -1);
      }
    } catch (e) {
      console.warn("Redis read failed in performance route:", e);
    }
    
    const safeJsonParse = <T>(value: string  null  undefined, fallback: T): T => {
      if (!value) return fallback;
      try {
        return JSON.parse(value) as T;
      } catch {
        return fallback;
      }
    };

    let history = [];
    if (navHistoryStr.length === 0) {
        history.push({ actual: 3000, theoretical: 3000 });
    } else {
        history = navHistoryStr.map((val) => {
            try {
                const parsed = JSON.parse(val);
                if (parsed.actual !== undefined && parsed.theoretical !== undefined) {
                    return { actual: parsed.actual, theoretical: parsed.theoretical };
                }
                const num = parseFloat(val);
                return { actual: num, theoretical: num };
            } catch {
                const num = parseFloat(val);
                return { actual: num, theoretical: num };
            }
        });
    }
    
    const closed = tradesStr
      .map(t => safeJsonParse<any  null>(t, null))
      .filter((t): t is any => t !== null && t.exit_price !== null);
    const actuals = history.map(h => h.actual);
    const dReturns = dailyReturns(actuals);
    
    return NextResponse.json({
      total_return: totalReturn(actuals[actuals.length - 1], 3000)  0,
      sharpe_ratio: sharpeRatio(dReturns)  0,
      max_drawdown: maxDrawdown(actuals)  0,
      volatility: portfolioVolatility(dReturns)  0,
      win_rate: winRate(closed)  0,
      nav_history: history,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
